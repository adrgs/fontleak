from pydantic import BaseModel, Field, field_validator, ValidationError
import string
import os
from urllib.parse import urlparse
from .logger import logger
from typing import Optional


class Settings(BaseModel):
    host: str = Field(
        ...,
        description="Base URL where the application is accessible (e.g., http://localhost:4242)",
    )
    host_leak: str = Field(
        ...,
        description="Base URL where the leak is accessible (e.g., http://127.0.0.1:4242). This is for images to not throttle the connection limit.",
    )
    fastapi_logging: bool = Field(
        default=os.getenv("FASTAPI_LOGGING", "true").lower() == "true",
        description="Enable or disable FastAPI logging",
    )

    @field_validator("host", "host_leak")
    def validate_host(cls, v):
        # Remove trailing slash if present
        v = v.rstrip("/")

        # Parse the URL
        parsed = urlparse(v)

        # Validate the URL
        if not parsed.scheme and not v.startswith("//"):
            raise ValueError(f"Relative URL {repr(v)} is not allowed")

        if not parsed.netloc:
            raise ValueError(f"URL {repr(v)} must contain a network location")

        return v


try:
    host = os.getenv("BASE_URL", "http://localhost:4242")
    host_leak = os.getenv("BASE_LEAK_URL", host)
    settings = Settings(host=host, host_leak=host_leak)
    logger.info("Application settings loaded successfully. Host: %s", settings.host)
except ValidationError as e:
    logger.critical("Failed to load application settings:\n%s", str(e))
    raise SystemExit(1) from e


class BaseLeakSetupParams(BaseModel):
    selector: str = Field(
        default=os.getenv("SELECTOR", "script:first-of-type"),
        description="CSS selector for target element",
    )
    parent: str = Field(
        default=os.getenv("PARENT", "body"), description="Parent element (body or head)"
    )
    alphabet: str = Field(
        default=os.getenv(
            "ALPHABET",
            "".join(c for c in string.printable if c == " " or not c.isspace()),
        ),
        description="Characters to include in the font",
    )
    timeout: int = Field(
        default=int(os.getenv("TIMEOUT", 10)), description="Timeout for @import url()"
    )
    prefix: Optional[str] = Field(default="", description="Prefix for the dynamic leak")
    strip: bool = Field(
        default=True, description="Strip unknown characters from the leak"
    )
    length: int = Field(default=100, description="Length of the leak")

    @field_validator("parent")
    def validate_parent(cls, v):
        if v not in ["body", "head"]:
            raise ValueError("Parent must be either 'body' or 'head'")
        return v

    @field_validator("alphabet")
    def validate_alphabet(cls, v):
        # Define the main alphabet
        main_alphabet = "".join(
            c for c in string.printable if c == " " or not c.isspace()
        )

        # Check if all characters are in the main alphabet
        if not all(c in main_alphabet for c in v):
            raise ValueError(
                "All characters must be in the main alphabet (string.printable minus whitespace except space)"
            )

        if not all(ord(c) < 256 for c in v):
            raise ValueError("fontleak only supports ASCII characters for now")

        # Create ordered set of characters while preserving order
        seen = set()
        unique_chars = []
        for c in v:
            if c not in seen:
                seen.add(c)
                unique_chars.append(c)
        v = "".join(unique_chars)

        return v


class DynamicLeakSetupParams(BaseLeakSetupParams):
    id: Optional[str] = Field(
        default=None, description="Unique identifier for the payload"
    )
    step: Optional[int] = Field(default=None, description="Step number")
    staging: bool = Field(default=True, description="Staging mode")


class StaticLeakSetupParams(BaseLeakSetupParams):
    length: int = Field(
        default=int(os.getenv("LENGTH", 100)), description="Length of the payload"
    )
    browser: str = Field(
        default=os.getenv("BROWSER", "all"),
        description="Browser compatibility (all, chrome, firefox, safari)",
    )

    @field_validator("browser")
    def validate_browser(cls, v):
        if v not in ["all", "chrome", "firefox", "safari"]:
            raise ValueError("Invalid browser option")
        return v


class LeakParams(BaseModel):
    idx: int = Field(
        default=0, description="Index of the character to leak in the alphabet"
    )
    step: Optional[int] = Field(default=None, description="Step number")
    id: Optional[str] = Field(
        default=None, description="Unique identifier for the dynamic leak state"
    )
    sid: Optional[str] = Field(
        default=None, description="Unique identifier for static leaks"
    )


class LeakState(BaseModel):
    id: str = Field(description="Unique identifier for the dynamic leak state")
    reconstruction: str = Field(default="", description="Reconstructed leaked text")
    step: int = Field(default=0, description="Step number")
    step_map: list[int] = Field(default=[0x100], description="Step map for the font")
    font_path: str = Field(default="TODO", description="Font path")
    length: int = Field(default=100, description="Length of the leak")
    prefix: str = Field(default="", description="Prefix for the dynamic leak")
    strip: bool = Field(
        default=True, description="Strip unknown characters from the leak"
    )
    setup: BaseLeakSetupParams = Field(
        description="Setup parameters for the dynamic leak"
    )
    parent: str = Field(
        default="body",
        description="Parent element (body or head)",
    )
    browser: str = Field(
        default="all",
        description="Browser compatibility (all, chrome, firefox, safari)",
    )

"""
AI-Driven QA Platform – Application Entrypoint.

Starts the FastAPI server using uvicorn with uvloop as the default event loop.
"""

from __future__ import annotations

import uvicorn
import uvloop

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvloop.install()
    uvicorn.run(
        "app.api.app:create_app",
        factory=True,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=settings.DEBUG,
        loop="uvloop",
    )


if __name__ == "__main__":
    main()

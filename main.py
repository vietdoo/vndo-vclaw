"""
Vclaw Platform entry point.

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
    python main.py  (starts with uvicorn programmatically)
"""
from __future__ import annotations

import asyncio
import signal
import sys

import uvicorn

from vclaw.api import create_app
from vclaw.config import get_settings

app = create_app()


def _handle_signals(server: uvicorn.Server) -> None:
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, server.handle_exit, sig, None)


if __name__ == "__main__":
    settings = get_settings()
    config = uvicorn.Config(
        app=app,
        host=settings.api_host,
        port=settings.api_port,
        workers=1,  # Use single worker; scale horizontally via K8s/replicas
        loop="asyncio",
        log_config=None,  # Handled by structlog
        access_log=settings.debug,
    )
    server = uvicorn.Server(config)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.serve())
    finally:
        loop.close()

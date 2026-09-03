"""Small ASGI middleware used by the public API boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.exceptions import HTTPException

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestBodyLimitMiddleware:
    """Reject request bodies incrementally, including chunked transfers."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="Request body exceeds the configured limit",
                    )
            return message

        await self.app(scope, limited_receive, send)

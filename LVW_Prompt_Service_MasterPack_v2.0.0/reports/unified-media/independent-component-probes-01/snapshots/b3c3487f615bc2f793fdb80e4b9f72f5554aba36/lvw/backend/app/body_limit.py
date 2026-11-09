"""Bound receive bytes before multipart parsing can spool an unbounded body."""
import uuid
from fastapi.responses import JSONResponse
from .errors import AppError
from fastapi import HTTPException

MAX_UPLOAD_REQUEST_BYTES = 256 * 1024 * 1024 + 1024 * 1024


class BodyLimitExceeded(HTTPException):
    def __init__(self):
        super().__init__(status_code=422, detail="流式请求超过本机处理上限")


class RequestBodyLimit:
    def __init__(self, app, upload_limit=MAX_UPLOAD_REQUEST_BYTES):
        self.app, self.upload_limit = app, upload_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        limit = self.upload_limit if scope["path"] == "/api/v1/media" else 1024 * 1024
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = limit + 1
        if length > limit or length < 0:
            response = JSONResponse(status_code=422, content={"error": {
                "code": "MEDIA_LIMIT_EXCEEDED", "message": "请求超过本机处理上限",
                "retryable": False, "details": {"request_limit_bytes": limit}}, "request_id": uuid.uuid4().hex})
            return await response(scope, receive, send)
        count = 0

        async def bounded_receive():
            nonlocal count
            message = await receive()
            count += len(message.get("body", b""))
            if count > limit:
                raise BodyLimitExceeded()
            return message

        await self.app(scope, bounded_receive, send)

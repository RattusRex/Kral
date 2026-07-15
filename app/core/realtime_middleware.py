from starlette.background import BackgroundTask
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.realtime import infer_realtime_events, publish_realtime_event


class RealtimeMutationMiddleware(BaseHTTPMiddleware):
    """Broadcast successful project mutations after their transaction commits."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        project_header = request.headers.get("X-Project-ID")
        events = infer_realtime_events(request.method, request.url.path)
        if response.status_code < 400 and project_header and events:
            try:
                project_id = int(project_header)
            except ValueError:
                return response

            async def broadcast() -> None:
                for event_type in sorted(events):
                    await publish_realtime_event(project_id, event_type)

            response.background = BackgroundTask(broadcast)
        return response

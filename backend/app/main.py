import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from app.api.v1 import (
    admin,
    auth,
    dashboard,
    demo,
    findings,
    meta,
    programmes,
    reports,
    students,
    uploads,
    verification,
)
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
        "form-action 'self'"
    ),
}


@asynccontextmanager
async def lifespan(_app: FastAPI):  # noqa: ANN201
    settings = get_settings()
    if settings.using_dev_keys:
        logger.warning(
            "Using built-in DEVELOPMENT identifier keys. Fine for local demos with synthetic "
            "data; set IDENTIFIER_HMAC_KEY and IDENTIFIER_ENCRYPTION_KEY for anything else."
        )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="APAAR Student Data Platform API (SIH26263 prototype)",
        version="0.1.0",
        description="Prototype API using synthetic data. Identity verification is SIMULATED.",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    register_error_handlers(app)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "X-CSRF-Token"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # noqa: ANN001, ANN202
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    api = APIRouter(prefix="/api/v1")
    for module in (
        auth,
        meta,
        demo,
        programmes,
        students,
        uploads,
        findings,
        dashboard,
        reports,
        verification,
        admin,
    ):
        api.include_router(module.router)
    app.include_router(api)

    @app.get("/api/health", tags=["meta"])
    def health() -> JSONResponse:
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            return JSONResponse({"status": "ok", "database": "ok"})
        except Exception:
            logger.exception("Health check failed")
            return JSONResponse({"status": "degraded", "database": "unavailable"}, 503)

    _mount_frontend(app, Path(settings.frontend_dist_dir))
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built single-page app (production/demo container) when it exists."""
    if not dist.is_absolute():
        dist = (Path(__file__).resolve().parent.parent / dist).resolve()
    index = dist / "index.html"
    if not index.exists():
        return

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            return JSONResponse(  # type: ignore[return-value]
                {"error": {"code": "not_found", "message": "Not found"}}, status_code=404
            )
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()

import logging
import os
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from limiter import limiter
from routers import onboarding, chat, query

# ---------------------------------------------------------------------------
# Logging configuration — runs once at startup
# LOG_LEVEL env var controls verbosity (default: INFO for production safety).
# Set LOG_LEVEL=DEBUG locally to restore verbose output.
# ---------------------------------------------------------------------------
_log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)

logging.basicConfig(
    level=_log_level,
    format="%(asctime)s  %(levelname)-8s  %(name)s  |  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Quiet down noisy third-party loggers so our logs stay readable
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("supabase").setLevel(logging.WARNING)
logging.getLogger("postgrest").setLevel(logging.WARNING)

logger = logging.getLogger("main")
logger.info("Log level set to %s", _log_level_name)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Database Sidekick API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ALLOWED_ORIGINS: comma-separated list of allowed origins.
# Example: ALLOWED_ORIGINS=https://your-app.vercel.app,http://localhost:3000
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
logger.info("CORS allowed origins: %s", _allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboarding.router)
app.include_router(chat.router)
app.include_router(query.router)


# ---------------------------------------------------------------------------
# Request / response logging middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    logger.info("→ %s %s  (client: %s)", request.method, request.url.path, request.client)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled exception during %s %s", request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "← %s %s  status=%d  %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    logger.debug("Health check called")
    return {"status": "ok"}


@app.get("/runtime")
async def runtime_info():
    from services.gemma_llm import settings
    config = settings()
    return {"model": config["model"], "provider": config["provider"],
            "write_approval": True, "max_queries": chat.MAX_ITERATIONS}

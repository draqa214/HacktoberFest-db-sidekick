import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from models import ConnectRequest, ConnectResponse
from auth import verify_jwt
from supabase_client import supabase
from services import schema as schema_service
from services import history
from limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/connect", response_model=ConnectResponse)
@limiter.limit("5/minute")
async def connect_database(
    request: Request,
    body: ConnectRequest,
    user_id: str = Depends(verify_jwt),
):
    """
    Connect a user's database:
    1. Introspect schema
    2. Cache schema in memory and clear prior chat history
    3. Store connection string in Supabase
    """
    cs = body.connection_string
    cs_safe = cs.split("@")[-1] if "@" in cs else cs
    if cs.startswith(("postgresql", "postgres")):
        db_type = "postgresql"
    elif cs.startswith("mysql"):
        db_type = "mysql"
    elif cs.startswith("sqlite"):
        db_type = "sqlite"
    else:
        db_type = "unknown"
    logger.info("user=%s  db_type=%s  host/path=%s", user_id, db_type, cs_safe)

    # ── Schema introspection ──────────────────────────────────────────────
    logger.debug("user=%s  Starting schema introspection", user_id)
    try:
        schema_text = schema_service.introspect_schema(cs)
        table_count = schema_text.count("\nTable:")
        logger.info(
            "user=%s  Schema introspection complete — ~%d table(s) found, schema length=%d chars",
            user_id, table_count, len(schema_text),
        )
        logger.debug("user=%s  Schema preview (first 500 chars):\n%s", user_id, schema_text[:500])
    except ValueError as e:
        logger.error("user=%s  Schema introspection failed: %s", user_id, e)
        raise HTTPException(status_code=400, detail=str(e))

    # ── Seed in-memory state ──────────────────────────────────────────────
    history.clear(user_id)
    history.set_schema(user_id, schema_text)
    logger.info("user=%s  History cleared and schema cached", user_id)

    # ── Persist to Supabase ───────────────────────────────────────────────
    logger.debug("user=%s  Upserting connection record to Supabase", user_id)
    try:
        supabase.table("connections").upsert(
            {
                "user_id": user_id,
                "connection_string": cs,
                "db_type": db_type,
            },
            on_conflict="user_id",
        ).execute()
        logger.info("user=%s  Connection record saved to Supabase", user_id)
    except Exception as e:
        logger.exception("user=%s  Failed to upsert connection record", user_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save connection record: {str(e)}",
        )

    logger.info("user=%s  Onboarding complete", user_id)
    return ConnectResponse(success=True)

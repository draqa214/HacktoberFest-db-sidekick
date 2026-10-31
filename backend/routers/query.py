import logging
from fastapi import APIRouter, Depends, HTTPException
from models import QueryRunRequest, QueryRunResponse
from auth import verify_jwt
from supabase_client import supabase
from services import db as db_service
from services.sql_policy import classify

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["query"])

@router.post("/run", response_model=QueryRunResponse)
async def run_query(
    body: QueryRunRequest,
    user_id: str = Depends(verify_jwt),
):
    """Execute a SQL statement against the user's connected database.
    Only reads are permitted here; writes must use chat approval.
    """
    sql_preview = body.sql.strip()[:200]
    logger.info("user=%s  Query run requested — SQL preview: %r", user_id, sql_preview)

    try:
        if classify(body.sql) != "read":
            raise ValueError("Writes must go through chat approval.")
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    # ── Fetch connection string from Supabase ─────────────────────────────
    logger.debug("user=%s  Fetching connection record from Supabase", user_id)
    result = (
        supabase.table("connections")
        .select("connection_string")
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        logger.warning("user=%s  No connection record found in Supabase", user_id)
        raise HTTPException(
            status_code=404,
            detail="No database connection found. Please complete onboarding first.",
        )
    # Never log the connection string itself — it contains credentials
    logger.debug("user=%s  Connection record fetched from Supabase ✓", user_id)
    connection_string = result.data["connection_string"]

    # ── Execute query ─────────────────────────────────────────────────────
    logger.debug("user=%s  Executing SQL against user DB", user_id)
    try:
        columns, rows = db_service.execute_query(connection_string, body.sql)
        logger.info(
            "user=%s  Query executed — %d column(s), %d row(s) returned",
            user_id, len(columns), len(rows),
        )
        logger.debug("user=%s  Columns: %s", user_id, columns)
    except ValueError as e:
        logger.error("user=%s  Query execution failed: %s", user_id, e)
        raise HTTPException(status_code=400, detail=str(e))

    return QueryRunResponse(columns=columns, rows=rows)

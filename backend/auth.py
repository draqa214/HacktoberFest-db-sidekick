import logging
import os
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dotenv import load_dotenv
from supabase_client import supabase

load_dotenv()

logger = logging.getLogger(__name__)
security = HTTPBearer()


def verify_jwt(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """Verify Supabase JWT via the Supabase admin API and return the user_id."""
    token = credentials.credentials
    # Log only a safe prefix — never the full token
    token_preview = f"{token[:12]}…" if len(token) > 12 else "***"
    logger.debug("Verifying JWT (token prefix: %s)", token_preview)

    try:
        response = supabase.auth.get_user(token)
        user = response.user
        if user is None:
            logger.warning("JWT verification returned no user (token prefix: %s)", token_preview)
            raise HTTPException(status_code=401, detail="Invalid token")
        logger.info("JWT verified — user_id=%s", user.id)
        return user.id
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("JWT verification failed (token prefix: %s)", token_preview)
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")

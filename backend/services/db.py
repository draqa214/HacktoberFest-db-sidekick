import logging
import time
from typing import List, Any, Tuple
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def _make_engine(connection_string: str):
    """
    Create a SQLAlchemy engine. For PostgreSQL, enforce SSL for cloud-hosted DBs.
    """
    is_postgres = connection_string.startswith(("postgresql", "postgres"))
    if is_postgres and "sslmode" not in connection_string:
        sep = "&" if "?" in connection_string else "?"
        connection_string = f"{connection_string}{sep}sslmode=require"
        logger.debug("SSL mode appended to PostgreSQL connection string")
    return create_engine(connection_string)


def execute_query(connection_string: str, sql: str) -> Tuple[List[str], List[List[Any]]]:
    """
    Execute a SQL statement against the user's database.

    For SELECT (and INSERT/UPDATE ... RETURNING): returns (columns, rows).
    For INSERT/UPDATE without RETURNING: commits the write and returns
      (["rows_affected"], [[n]]) so callers have a consistent return shape.

    Raises ValueError on connection or execution failure.
    """
    sql_preview = sql.strip()[:200]
    logger.debug("Creating DB engine for query execution")
    try:
        engine = _make_engine(connection_string)
    except Exception as e:
        logger.error("Failed to create DB engine: %s", e)
        raise ValueError(f"Invalid connection string: {str(e)}")

    logger.debug("Executing SQL: %r", sql_preview)
    start = time.perf_counter()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))

            if result.returns_rows:
                # SELECT, or INSERT/UPDATE ... RETURNING
                columns = list(result.keys())
                rows = [list(row) for row in result.fetchall()]
                conn.commit()  # harmless for SELECT; required for RETURNING writes
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "Query executed in %.1fms — %d column(s), %d row(s)  SQL: %r",
                    elapsed_ms, len(columns), len(rows), sql_preview,
                )
                logger.debug("Column names: %s", columns)
            else:
                # INSERT / UPDATE without RETURNING — commit and surface rowcount
                rows_affected = result.rowcount
                conn.commit()
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "Write executed in %.1fms — %d row(s) affected  SQL: %r",
                    elapsed_ms, rows_affected, sql_preview,
                )
                columns = ["rows_affected"]
                rows = [[rows_affected]]

            return columns, rows

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "Query failed after %.1fms — SQL: %r  error: %s",
            elapsed_ms, sql_preview, e,
        )
        raise ValueError(f"Query execution failed: {str(e)}")
    finally:
        engine.dispose()
        logger.debug("DB engine disposed after query execution")

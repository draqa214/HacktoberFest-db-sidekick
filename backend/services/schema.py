import logging
import time
from sqlalchemy import create_engine, inspect, text

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


def introspect_schema(connection_string: str) -> str:
    """
    Connect to the user's database, introspect its schema, and return
    a formatted text summary of all tables, columns, keys, and indexes.
    Raises an exception with a clear message if connection or introspection fails.
    """
    # Mask password for logging
    host_part = connection_string.split("@")[-1] if "@" in connection_string else connection_string
    logger.info("Connecting to database — host/path: %s", host_part)
    start = time.perf_counter()

    try:
        engine = _make_engine(connection_string)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("Database connection established (%.1fms)", elapsed_ms)
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "Database connection failed after %.1fms — host: %s  error: %s",
            elapsed_ms, host_part, e,
        )
        raise ValueError(
            f"Could not connect to the database. Please check your connection string. "
            f"Details: {str(e)}"
        )

    try:
        logger.debug("Starting schema reflection")
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        logger.info("Found %d table(s): %s", len(table_names), table_names)

        schema_lines = [f"SQL dialect: {engine.dialect.name}", ""]

        for table_name in table_names:
            logger.debug("Introspecting table: %s", table_name)
            schema_lines.append(f"Table: {table_name}")

            # Primary keys
            pk_info = inspector.get_pk_constraint(table_name)
            pk_cols = set(pk_info.get("constrained_columns", []))
            logger.debug("  table=%s  PKs: %s", table_name, pk_cols)

            # Foreign keys
            fk_map = {}
            for fk in inspector.get_foreign_keys(table_name):
                for local_col, remote_col in zip(
                    fk["constrained_columns"], fk["referred_columns"]
                ):
                    fk_map[local_col] = f"{fk['referred_table']}.{remote_col}"
            if fk_map:
                logger.debug("  table=%s  FKs: %s", table_name, fk_map)

            # Columns
            columns = inspector.get_columns(table_name)
            logger.debug("  table=%s  %d column(s)", table_name, len(columns))
            for col in columns:
                col_name = col["name"]
                col_type = str(col["type"])
                parts = [f"    - {col_name} ({col_type}"]

                flags = []
                if col_name in pk_cols:
                    flags.append("PRIMARY KEY")
                if col_name in fk_map:
                    flags.append(f"FK -> {fk_map[col_name]}")
                if not col.get("nullable", True):
                    flags.append("NOT NULL")

                if flags:
                    parts.append(", ".join(flags))
                    schema_lines.append("".join(parts) + ")")
                else:
                    schema_lines.append("".join(parts) + ")")

            # Indexes
            indexes = inspector.get_indexes(table_name)
            if indexes:
                logger.debug("  table=%s  %d index(es)", table_name, len(indexes))
                for idx in indexes:
                    idx_cols = ", ".join(idx["column_names"])
                    unique = " UNIQUE" if idx.get("unique") else ""
                    schema_lines.append(f"    [INDEX{unique}: {idx['name']} on ({idx_cols})]")

            schema_lines.append("")

        total_ms = (time.perf_counter() - start) * 1000
        schema_text = "\n".join(schema_lines)
        logger.info(
            "Schema introspection complete — %d tables, %d chars total (%.1fms)",
            len(table_names), len(schema_text), total_ms,
        )
        return schema_text

    except Exception as e:
        logger.exception("Schema introspection failed for host: %s", host_part)
        raise ValueError(f"Failed to introspect schema: {str(e)}")
    finally:
        engine.dispose()
        logger.debug("Database engine disposed")

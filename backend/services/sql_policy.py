"""Shared statement policy, used by both agent and direct-query routes."""
import sqlglot
from sqlglot import exp


def is_table_creation(sql: str) -> bool:
    return isinstance(sqlglot.parse_one(sql), exp.Create)


def classify(sql: str) -> str:
    try:
        statements = sqlglot.parse(sql)
    except sqlglot.errors.ParseError as exc:
        raise ValueError("SQL could not be parsed safely") from exc
    if len(statements) != 1 or statements[0] is None:
        raise ValueError("Exactly one SQL statement is allowed. Split this batch into separate execute_sql calls; propose only the first statement now and wait for its approval before the next. Nothing in this batch was executed.")
    statement = statements[0]
    if isinstance(statement, exp.Create):
        # Only additive, explicit table definitions. No CTAS, replacement,
        # views, functions, triggers, or writes to managed schemas.
        definition = statement.this
        if (statement.kind != "TABLE" or statement.args.get("replace")
                or statement.args.get("expression") is not None
                or statement.args.get("properties") is not None
                or not isinstance(definition, exp.Schema)
                or not any(isinstance(node, exp.ColumnDef) for node in definition.expressions)):
            raise ValueError("Only explicit CREATE TABLE definitions are allowed")
        table = definition.this
        if not isinstance(table, exp.Table) or table.catalog or table.db not in {"", "public"}:
            raise ValueError("New tables must be in the default/public schema")
        if any(isinstance(node, (exp.Query, exp.Command, exp.Insert, exp.Update, exp.Delete)) for node in statement.walk()):
            raise ValueError("Queries and nested writes in table definitions are blocked")
        return "write"
    # Reject nested writes, SELECT INTO and execution/administration commands.
    forbidden = (exp.DDL, exp.Delete, exp.Merge, exp.Command, exp.Into,
                 exp.Transaction, exp.Commit, exp.Rollback, exp.Grant, exp.Revoke)
    if any(isinstance(node, forbidden) and not isinstance(node, exp.Insert) for node in statement.walk()):
        raise ValueError("Destructive, administrative, and SELECT INTO statements are blocked")
    writes = [node for node in statement.walk() if isinstance(node, (exp.Insert, exp.Update))]
    if isinstance(statement, (exp.Insert, exp.Update)):
        if len(writes) != 1:
            raise ValueError("Nested writes are blocked")
        return "write"
    if writes:
        raise ValueError("Writes inside a read query are blocked")
    if isinstance(statement, exp.Query):
        # A SELECT may invoke database functions. Use a read-only DB role too.
        return "read"
    raise ValueError("Only SELECT, INSERT, and UPDATE are allowed")

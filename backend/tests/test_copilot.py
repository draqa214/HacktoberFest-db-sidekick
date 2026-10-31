import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key-not-a-real-secret")

from services import gemma_llm, history, db
from services.sql_policy import classify
from routers import chat
from models import ChatExecuteRequest


def tool(sql, call_id="test-call"):
    return {"role": "assistant", "content": "", "tool_calls": [{
        "id": call_id, "type": "function",
        "function": {"name": "execute_sql", "arguments": json.dumps({"sql": sql})},
    }]}


class PolicyTests(unittest.TestCase):
    def test_reads_and_approved_write_types(self):
        for sql in ("SELECT 1", "WITH x AS (SELECT 1) SELECT * FROM x", "SELECT 'DELETE' AS word"):
            self.assertEqual(classify(sql), "read")
        for sql in ("INSERT INTO items(name) VALUES ('x')", "UPDATE items SET name='x'", "WITH x AS (SELECT 1) UPDATE items SET name='x'"):
            self.assertEqual(classify(sql), "write")

    def test_bypasses_blocked(self):
        for sql in ("SELECT 1; UPDATE items SET name='x'", "WITH x AS (UPDATE items SET name='x' RETURNING *) SELECT * FROM x", "DROP TABLE items", "DELETE FROM items", "SELECT * INTO copied FROM items", "PRAGMA writable_schema=1", "BEGIN", "", "COPY items TO '/tmp/x'"):
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                classify(sql)

    def test_adapter_protocol(self):
        message = gemma_llm._normalize({"content": "", "thinking": "private", "tool_calls": [{"function": {"name": "execute_sql", "arguments": {"sql": "SELECT 1"}}}]})
        self.assertNotIn("thinking", message)
        self.assertTrue(message["tool_calls"][0]["id"])
        wire = gemma_llm._ollama_messages([message, {"role": "tool", "tool_call_id": "x", "content": "1"}])
        self.assertEqual(wire[0]["tool_calls"][0]["function"]["arguments"], {"sql": "SELECT 1"})
        self.assertEqual(wire[1]["tool_name"], "execute_sql")


class AgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cs = "sqlite:///" + str(Path(self.temp.name) / "test.db").replace("\\", "/")
        engine = db._make_engine(self.cs)
        with engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("CREATE TABLE items (name TEXT)"))
            conn.execute(text("INSERT INTO items VALUES ('before')"))
        engine.dispose()
        history.clear("test-user")
        history.set_schema("test-user", "Dialect: sqlite\nTable: items\n - name TEXT")

    def tearDown(self):
        history.clear("test-user")
        self.temp.cleanup()

    async def test_select_then_grounded_answer(self):
        with patch.object(gemma_llm, "chat", AsyncMock(side_effect=[tool("SELECT * FROM items"), {"role": "assistant", "content": "One item: before"}])):
            result = await chat._run_agentic_loop(self.cs, "test-user")
        self.assertEqual(result.status, "done")
        self.assertEqual(result.completed_steps[0].rows, [["before"]])

    async def test_write_pauses_then_approval_executes_server_sql(self):
        with patch.object(gemma_llm, "chat", AsyncMock(return_value=tool("UPDATE items SET name='after'"))):
            result = await chat._run_agentic_loop(self.cs, "test-user")
        self.assertEqual(result.status, "needs_approval")
        self.assertEqual(db.execute_query(self.cs, "SELECT name FROM items")[1], [["before"]])
        with patch.object(chat, "_fetch_connection", return_value={"connection_string": self.cs}), patch.object(gemma_llm, "chat", AsyncMock(return_value={"role": "assistant", "content": "Updated"})):
            result = await chat.execute_pending_query.__wrapped__(request=None, body=ChatExecuteRequest(approved=True, sql="DROP TABLE items"), user_id="test-user")
        self.assertEqual(db.execute_query(self.cs, "SELECT name FROM items")[1], [["after"]])
        self.assertEqual(result.completed_steps[0].kind, "approved")
        self.assertIsNone(history.get_pending_sql("test-user"))

    async def test_rejected_write_does_not_execute(self):
        with patch.object(gemma_llm, "chat", AsyncMock(return_value=tool("UPDATE items SET name='after'"))):
            await chat._run_agentic_loop(self.cs, "test-user")
        with patch.object(chat, "_fetch_connection", return_value={"connection_string": self.cs}), patch.object(gemma_llm, "chat", AsyncMock(return_value={"role": "assistant", "content": "Cancelled"})):
            result = await chat.execute_pending_query.__wrapped__(request=None, body=ChatExecuteRequest(approved=False), user_id="test-user")
        self.assertEqual(db.execute_query(self.cs, "SELECT name FROM items")[1], [["before"]])
        self.assertEqual(result.completed_steps[0].kind, "rejected")

    async def test_multiple_calls_execute_nothing(self):
        batch = tool("SELECT * FROM items")
        batch["tool_calls"].extend(tool("UPDATE items SET name='oops'", "second")["tool_calls"])
        with patch.object(gemma_llm, "chat", AsyncMock(side_effect=[batch, {"role": "assistant", "content": "No queries run"}])):
            result = await chat._run_agentic_loop(self.cs, "test-user")
        self.assertEqual(result.completed_steps, [])
        self.assertEqual(len([m for m in history.get_history("test-user") if m["role"] == "tool"]), 2)

    async def test_table_creation_requires_approval_and_refreshes_schema(self):
        sql = "CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        with patch.object(gemma_llm, "chat", AsyncMock(return_value=tool(sql))):
            result = await chat._run_agentic_loop(self.cs, "test-user")
        self.assertEqual(result.status, "needs_approval")
        from sqlalchemy import inspect
        engine = db._make_engine(self.cs)
        self.assertNotIn("projects", inspect(engine).get_table_names())
        engine.dispose()
        with patch.object(chat, "_fetch_connection", return_value={"connection_string": self.cs}), patch.object(gemma_llm, "chat", AsyncMock(return_value={"role": "assistant", "content": "Created projects"})):
            await chat.execute_pending_query.__wrapped__(request=None, body=ChatExecuteRequest(approved=True), user_id="test-user")
        self.assertIn("Table: projects", history.get_schema("test-user"))
        self.assertEqual(db.execute_query(self.cs, "SELECT * FROM projects")[1], [])

    async def test_batch_is_blocked_then_single_table_is_recoverable(self):
        first = "CREATE TABLE projects (id INTEGER PRIMARY KEY)"
        batch = first + "; CREATE TABLE shipments (id INTEGER PRIMARY KEY)"
        with patch.object(gemma_llm, "chat", AsyncMock(side_effect=[tool(batch), tool(first, "single")])):
            result = await chat._run_agentic_loop(self.cs, "test-user")
        self.assertEqual(result.status, "needs_approval")
        self.assertEqual(result.pending_sql, first)
        self.assertEqual(result.completed_steps[0].kind, "blocked")
        recovered = await chat.pending_query(user_id="test-user")
        self.assertEqual(recovered.pending_sql, first)
        self.assertEqual(recovered.status, "needs_approval")
        other_user = await chat.pending_query(user_id="other-user")
        self.assertEqual(other_user.pending_sql, "")
        self.assertEqual(other_user.status, "done")
        from models import ChatMessageRequest
        with patch.object(gemma_llm, "chat", AsyncMock()) as model:
            retried = await chat.send_chat_message.__wrapped__(request=None, body=ChatMessageRequest(message="Try again"), user_id="test-user")
        self.assertEqual(retried.pending_sql, first)
        model.assert_not_awaited()
        from sqlalchemy import inspect
        engine = db._make_engine(self.cs)
        self.assertEqual(inspect(engine).get_table_names(), ["items"])
        engine.dispose()


if __name__ == "__main__":
    unittest.main()

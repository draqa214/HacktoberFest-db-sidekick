import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from google.genai import types
from services import gemma_llm


class GeminiTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_tool_round_trip_preserves_signature(self):
        response = types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
            role="model", parts=[
                types.Part(text="internal reasoning", thought=True),
                types.Part(function_call=types.FunctionCall(id="fc1", name="execute_sql", args={"sql": "SELECT 1"}), thought_signature=b"opaque-signature"),
            ]))])
        api = MagicMock()
        api.models.generate_content = AsyncMock(return_value=response)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=api)
        context.__aexit__ = AsyncMock(return_value=False)
        client = MagicMock()
        client.aio = context
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "LLM_PROVIDER": "gemini", "GEMMA_MODEL": "gemma-4-26b-a4b-it"}), patch("google.genai.Client", return_value=client):
            answer = await gemma_llm.chat([{"role": "system", "content": "Be accurate"}, {"role": "user", "content": "Count"}])
        sent = api.models.generate_content.call_args.kwargs
        self.assertEqual(sent["model"], "gemma-4-26b-a4b-it")
        self.assertTrue(sent["config"].automatic_function_calling.disable)
        self.assertEqual(sent["config"].tools[0].function_declarations[0].name, "execute_sql")
        self.assertEqual(json.loads(answer["tool_calls"][0]["function"]["arguments"]), {"sql": "SELECT 1"})
        self.assertNotIn("internal reasoning", str(answer))
        system, wire = gemma_llm._gemini_contents([
            {"role": "system", "content": "Be accurate"}, {"role": "user", "content": "Count"}, answer,
            {"role": "tool", "tool_call_id": "fc1", "content": "1"},
        ])
        self.assertEqual(system, "Be accurate")
        self.assertEqual(wire[1].parts[0].thought_signature, b"opaque-signature")
        self.assertEqual(wire[2].parts[0].function_response.id, "fc1")
        self.assertEqual(wire[2].parts[0].function_response.response, {"result": "1"})

    async def test_summary_has_no_tools(self):
        response = types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text="There is one row.")]))])
        api = MagicMock()
        api.models.generate_content = AsyncMock(return_value=response)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=api)
        context.__aexit__ = AsyncMock(return_value=False)
        client = MagicMock()
        client.aio = context
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "LLM_PROVIDER": "gemini", "GEMMA_MODEL": "gemma-4-26b-a4b-it"}), patch("google.genai.Client", return_value=client):
            answer = await gemma_llm.chat([{"role": "user", "content": "Summarize"}], allow_tools=False)
        self.assertEqual(answer["content"], "There is one row.")
        self.assertIsNone(api.models.generate_content.call_args.kwargs["config"].tools)

    async def test_missing_key_fails_before_network(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}), self.assertRaisesRegex(ValueError, "Set GEMINI_API_KEY"):
            await gemma_llm._gemini_chat([{"role": "user", "content": "Hi"}], "gemma-4-26b-a4b-it", True)

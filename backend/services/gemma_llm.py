"""Gemma 4 tool calling through the native Gemini SDK or optional local servers.

Only the final response and tool calls enter conversation history. No reasoning
traces are retained. The SQL agent remains responsible for approval and execution.
"""
import json
import base64
import os
import uuid

import httpx
from dotenv import load_dotenv

load_dotenv()

EXECUTE_SQL_TOOL = {
    "type": "function",
    "function": {
        "name": "execute_sql",
        "description": "Run one SELECT, INSERT, UPDATE, or CREATE TABLE. Writes and table creation require human approval. Destructive SQL is blocked.",
        "parameters": {
            "type": "object",
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
        },
    },
}


def settings() -> dict:
    provider = os.getenv("LLM_PROVIDER", "gemini")
    if provider not in {"gemini", "ollama", "openai-compatible"}:
        raise ValueError("LLM_PROVIDER must be gemini, ollama or openai-compatible")
    model = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it" if provider == "gemini" else "gemma4:e4b")
    if "gemma" not in model.lower() or "4" not in model:
        raise ValueError("GEMMA_MODEL must identify a Gemma 4 model")
    return {
        "provider": provider,
        "model": model,
        "base_url": os.getenv("LLM_BASE_URL", "http://localhost:11434").rstrip("/"),
    }


def _ollama_messages(messages: list[dict]) -> list[dict]:
    converted = []
    for message in messages:
        item = dict(message)
        item.pop("_gemini_parts", None)
        item["content"] = item.get("content") or ""
        if item.get("tool_calls"):
            item["tool_calls"] = [
                {"function": {"name": tc["function"]["name"],
                              "arguments": json.loads(tc["function"]["arguments"])}}
                for tc in item["tool_calls"]
            ]
        if item["role"] == "tool":
            item.pop("tool_call_id", None)
            item["tool_name"] = "execute_sql"
        converted.append(item)
    return converted


def _normalize(message: dict) -> dict:
    result = {"role": "assistant", "content": message.get("content") or ""}
    calls = message.get("tool_calls") or []
    if calls:
        result["tool_calls"] = []
        for call in calls:
            function = call["function"]
            if function["name"] != "execute_sql":
                raise ValueError("Model requested an unsupported tool")
            args = function["arguments"]
            if isinstance(args, str):
                args = json.loads(args)
            if not isinstance(args, dict) or not isinstance(args.get("sql"), str):
                raise ValueError("Model returned invalid SQL tool arguments")
            result["tool_calls"].append({
                "id": call.get("id") or f"call_{uuid.uuid4().hex}",
                "type": "function",
                "function": {"name": "execute_sql", "arguments": json.dumps(args)},
            })
    return result


def _gemini_contents(messages: list[dict]) -> tuple[str, list]:
    from google.genai import types

    system = []
    contents = []
    calls = {}
    for message in messages:
        role = message["role"]
        if role == "system":
            system.append(message["content"])
            continue
        if role == "assistant":
            for call in message.get("tool_calls", []):
                calls[call["id"]] = call["function"]["name"]
            if message.get("_gemini_parts"):
                parts = [types.Part.model_validate(part) for part in message["_gemini_parts"]]
            else:
                parts = [types.Part(text=message["content"])] if message.get("content") else []
                for call in message.get("tool_calls", []):
                    parts.append(types.Part(function_call=types.FunctionCall(
                        id=call["id"], name=call["function"]["name"],
                        args=json.loads(call["function"]["arguments"]))))
            target_role = "model"
        elif role == "tool":
            call_id = message["tool_call_id"]
            if call_id not in calls:
                raise ValueError("Tool result has no matching model call")
            parts = [types.Part(function_response=types.FunctionResponse(
                id=call_id, name=calls[call_id], response={"result": message["content"]}))]
            target_role = "user"
        else:
            parts = [types.Part.from_bytes(data=base64.b64decode(image["data"]), mime_type=image["mime_type"])
                     for image in message.get("images", [])]
            parts.append(types.Part(text=message["content"]))
            target_role = "user"
        if parts:
            if contents and contents[-1].role == target_role:
                contents[-1].parts.extend(parts)
            else:
                contents.append(types.Content(role=target_role, parts=parts))
    return "\n\n".join(system), contents


async def _gemini_chat(messages: list[dict], model: str, allow_tools: bool) -> dict:
    from google import genai
    from google.genai import types, errors

    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Set GEMINI_API_KEY in backend/.env to use hosted Gemma 4.")
    system, contents = _gemini_contents(messages)
    config = types.GenerateContentConfig(
        system_instruction=system or None,
        temperature=0,
        max_output_tokens=4096,
        thinking_config=types.ThinkingConfig(thinking_level="minimal"),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        tools=[types.Tool(function_declarations=[EXECUTE_SQL_TOOL["function"]])] if allow_tools else None,
    )
    try:
        async with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=90000)).aio as client:
            response = await client.models.generate_content(model=model, contents=contents, config=config)
    except errors.APIError as exc:
        # Do not surface request contents or API keys in errors.
        raise ValueError(f"Gemini API returned HTTP {exc.code}. Check your key, Gemma model access, and quota.") from None
    if not response.candidates or not response.candidates[0].content:
        raise ValueError("Gemma returned no answer. The response may have been blocked.")
    parts = response.candidates[0].content.parts or []
    text = []
    calls = []
    retained_parts = []
    for part in parts:
        if part.thought:
            continue
        if part.text:
            text.append(part.text)
        if part.function_call:
            call = part.function_call
            call.id = call.id or f"call_{uuid.uuid4().hex}"
            calls.append({"id": call.id, "function": {"name": call.name, "arguments": call.args}})
        # Preserve opaque signatures required for subsequent function-result turns.
        retained_parts.append(part.model_dump(exclude_none=True))
    result = _normalize({"content": "".join(text), "tool_calls": calls})
    if not result["content"] and not result.get("tool_calls"):
        raise ValueError("Gemma returned an empty answer; try a shorter request.")
    result["_gemini_parts"] = retained_parts
    return result


async def chat(messages: list[dict], *, allow_tools: bool = True) -> dict:
    config = settings()
    if config["provider"] == "gemini":
        return await _gemini_chat(messages, config["model"], allow_tools)
    if any(message.get("images") for message in messages):
        raise ValueError("Image conversations require LLM_PROVIDER=gemini.")
    ollama = config["provider"] == "ollama"
    payload = {
        "model": config["model"],
        "messages": _ollama_messages(messages) if ollama else [{k: v for k, v in m.items() if not k.startswith("_")} for m in messages],
        "stream": False,
    }
    if allow_tools:
        payload["tools"] = [EXECUTE_SQL_TOOL]
    if ollama:
        payload["options"] = {"temperature": 0, "num_ctx": 16384, "num_predict": 2048}
        payload["keep_alive"] = "10m"
    else:
        payload.update(temperature=0, max_tokens=2048)
        payload["tool_choice"] = "auto" if allow_tools else "none"
        if allow_tools:
            payload["parallel_tool_calls"] = False
    headers = {}
    if os.getenv("LLM_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['LLM_API_KEY']}"
    path = "/api/chat" if ollama else "/chat/completions"
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            response = await client.post(config["base_url"] + path, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ValueError(f"Gemma server returned HTTP {exc.response.status_code}. Check model name and server configuration.") from exc
        except httpx.RequestError as exc:
            raise ValueError("Cannot reach Gemma. Start Ollama and pull the configured model, or check LLM_BASE_URL.") from exc
    data = response.json()
    message = data["message"] if ollama else data["choices"][0]["message"]
    return _normalize(message)

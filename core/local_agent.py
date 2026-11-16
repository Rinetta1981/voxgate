"""Fully local Ollama adapter for VOXGATE's deliberately inert model benchmark.

Only TCP 127.0.0.1:11434 is contacted. No cloud endpoint, API key,
model download, tool execution, or arbitrary URL is exposed by this module.
"""
from __future__ import annotations

import json
import re
from http.client import HTTPConnection, HTTPException

from .live_agent import ModelResponseError, SYSTEM_INSTRUCTIONS, build_user_input

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 11434
DEFAULT_MODEL = "qwen2.5:0.5b"
_MODEL_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]*(?::[a-zA-Z0-9._-]+)?$")


def validate_local_model_name(model: str) -> str:
    """Reject cloud-tagged or malformed model identifiers before any request."""
    if not isinstance(model, str) or not _MODEL_NAME.fullmatch(model):
        raise ModelResponseError("Invalid Ollama model name")
    if model.endswith(":cloud") or model.endswith("-cloud"):
        raise ModelResponseError("Cloud models are disabled in VOXGATE's free local mode")
    return model


def _local_json_request(method: str, path: str, payload: dict | None = None) -> dict:
    """Fixed loopback HTTP, using Python's standard library (no proxies or redirects)."""
    if (method, path) not in {("GET", "/api/tags"), ("POST", "/api/chat")}:
        raise ValueError("Endpoint is not allowlisted")
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    connection = None
    try:
        connection = HTTPConnection(LOCAL_HOST, LOCAL_PORT, timeout=180)
        connection.request(method, path, body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read(2_000_001)  # prevent unexpectedly large local responses
        if len(raw) > 2_000_000:
            raise ModelResponseError("Local model response exceeds 2 MB")
        if response.status != 200:
            raise ModelResponseError(f"Local Ollama returned HTTP {response.status}; check that the model is installed")
        result = json.loads(raw.decode("utf-8"))
        if not isinstance(result, dict):
            raise ModelResponseError("Ollama returned a non-object JSON response")
        return result
    except (ConnectionError, TimeoutError, OSError, HTTPException) as exc:
        raise ModelResponseError(
            "Cannot reach local Ollama at 127.0.0.1:11434. Open Ollama on your Mac, then retry."
        ) from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise ModelResponseError("Ollama returned invalid JSON/encoding") from exc
    finally:
        if connection is not None:
            connection.close()


def installed_model_info(model: str) -> dict:
    """Require a locally installed model; never pull or fall back to cloud."""
    model = validate_local_model_name(model)
    result = _local_json_request("GET", "/api/tags")
    models = result.get("models")
    if not isinstance(models, list):
        raise ModelResponseError("Invalid local Ollama model listing")
    for item in models:
        if isinstance(item, dict) and model in {item.get("name"), item.get("model")}:
            return {
                "name": model,
                "digest": item.get("digest"),
                "size_bytes": item.get("size"),
                "details": item.get("details", {}),
            }
    raise ModelResponseError(
        f"'{model}' is not installed locally. Run: ollama pull {model} "
        "(downloads model weights once; no paid API)."
    )


def extract_local_chat_text(response: dict) -> str:
    """Transport failures abort; bad model text is handled by the existing safe parser."""
    if response.get("done") is not True:
        raise ModelResponseError("Ollama did not finish generating a response")
    message = response.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ModelResponseError("Ollama response did not contain message.content")
    return message["content"]


class LocalOllamaModel:
    """Local-only text model, compatible with evaluate_with_model()."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = validate_local_model_name(model)
        self.model_info: dict | None = None
        self.call_stats: list[dict] = []

    def check_ready(self) -> dict:
        if self.model_info is None:
            self.model_info = installed_model_info(self.model)
        return self.model_info

    def __call__(self, transcript: str, catalog: tuple[str, ...]) -> str:
        self.check_ready()
        request = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": build_user_input(transcript, catalog)},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 128, "num_ctx": 4096},
        }
        result = _local_json_request("POST", "/api/chat", request)
        self.call_stats.append({
            "prompt_eval_count": result.get("prompt_eval_count"),
            "eval_count": result.get("eval_count"),
            "total_duration_ns": result.get("total_duration"),
        })
        return extract_local_chat_text(result)

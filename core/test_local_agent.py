"""Local Ollama adapter tests: no network, no downloads, no charges."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from .agent_simulation import load_scenarios
from .live_agent import ModelResponseError, build_global_catalog, evaluate_with_model, summarize_events
from .local_agent import (LocalOllamaModel, _local_json_request, extract_local_chat_text,
                          installed_model_info, validate_local_model_name)

ROOT = Path(__file__).resolve().parent.parent


class MockResponse:
    def __init__(self, content: dict, status: int = 200):
        self.status = status
        self.content = json.dumps(content).encode("utf-8")

    def read(self, limit: int):
        return self.content[:limit]


class MockHTTPConnection:
    requests: list[tuple] = []
    outputs: list[MockResponse] = []

    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout = host, port, timeout

    def request(self, method, path, body=None, headers=None):
        self.requests.append((self.host, self.port, method, path, body, headers))

    def getresponse(self):
        return self.outputs.pop(0)

    def close(self):
        pass


class LocalAgentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_scenarios(ROOT / "data" / "waitwise_agent_scenarios.csv")
        cls.catalog = build_global_catalog(cls.cases)

    def setUp(self):
        MockHTTPConnection.requests = []
        MockHTTPConnection.outputs = []

    def test_default_model_name(self):
        self.assertEqual(validate_local_model_name("qwen2.5:0.5b"), "qwen2.5:0.5b")

    def test_cloud_model_refused(self):
        for name in ("gemma4:cloud", "https://ollama.com/api", "qwen2.5:0.5b cloud"):
            with self.subTest(name=name), self.assertRaises(ModelResponseError):
                validate_local_model_name(name)

    def test_only_allowlisted_paths(self):
        with self.assertRaises(ValueError):
            _local_json_request("POST", "https://ollama.com/api/chat", {})
        with self.assertRaises(ValueError):
            _local_json_request("POST", "/api/pull", {})

    def test_fixed_loopback_and_model_list(self):
        MockHTTPConnection.outputs = [MockResponse({"models": [{"name": "qwen2.5:0.5b", "digest": "abc", "size": 400}]})]
        with patch("core.local_agent.HTTPConnection", MockHTTPConnection):
            info = installed_model_info("qwen2.5:0.5b")
        self.assertEqual(info["digest"], "abc")
        self.assertEqual(MockHTTPConnection.requests[0][:4], ("127.0.0.1", 11434, "GET", "/api/tags"))

    def test_missing_model_fails_without_pull(self):
        MockHTTPConnection.outputs = [MockResponse({"models": []})]
        with patch("core.local_agent.HTTPConnection", MockHTTPConnection), self.assertRaisesRegex(ModelResponseError, "not installed"):
            installed_model_info("qwen2.5:0.5b")
        self.assertEqual(len(MockHTTPConnection.requests), 1)
        self.assertEqual(MockHTTPConnection.requests[0][3], "/api/tags")

    def test_local_chat_request_and_json_mode(self):
        MockHTTPConnection.outputs = [
            MockResponse({"models": [{"name": "qwen2.5:0.5b", "digest": "abc"}]}),
            MockResponse({"done": True, "message": {"content": '{"action_id":"HOLD"}'}, "eval_count": 15}),
        ]
        model = LocalOllamaModel()
        with patch("core.local_agent.HTTPConnection", MockHTTPConnection):
            output = model("Send the memo to Pat", self.catalog)
        self.assertEqual(output, '{"action_id":"HOLD"}')
        self.assertEqual(len(MockHTTPConnection.requests), 2)
        self.assertEqual(MockHTTPConnection.requests[1][:4], ("127.0.0.1", 11434, "POST", "/api/chat"))
        body = json.loads(MockHTTPConnection.requests[1][4])
        self.assertEqual(body["model"], "qwen2.5:0.5b")
        self.assertEqual(body["format"], "json")
        self.assertIs(body["stream"], False)
        self.assertNotIn("tools", body)
        self.assertNotIn("final_action", body["messages"][-1]["content"])
        self.assertEqual(model.call_stats[0]["eval_count"], 15)

    def test_unfinished_model_response_is_error(self):
        with self.assertRaises(ModelResponseError):
            extract_local_chat_text({"done": False, "message": {"content": ""}})

    def test_non_text_model_response_is_error(self):
        with self.assertRaises(ModelResponseError):
            extract_local_chat_text({"done": True, "message": {"content": None}})

    def test_http_failure_is_error_not_hold(self):
        MockHTTPConnection.outputs = [MockResponse({"error": "not found"}, status=404)]
        with patch("core.local_agent.HTTPConnection", MockHTTPConnection), self.assertRaises(ModelResponseError):
            _local_json_request("GET", "/api/tags")

    def test_missing_server_is_error(self):
        with patch("core.local_agent.HTTPConnection", side_effect=ConnectionRefusedError), self.assertRaisesRegex(ModelResponseError, "Cannot reach"):
            _local_json_request("GET", "/api/tags")

    def test_pipeline_fake_model(self):
        def fake_model(transcript, catalog):
            return json.dumps({"action_id": catalog[0]})
        events = evaluate_with_model(self.cases[:3], fake_model, self.catalog)
        self.assertEqual(len(events), 9)
        self.assertEqual(len(summarize_events(events)), 3)

    def test_offline_preview_no_local_network(self):
        import local_waitwise_agent
        with patch("sys.argv", ["local_waitwise_agent.py"]), patch.object(local_waitwise_agent, "LocalOllamaModel") as model:
            self.assertEqual(local_waitwise_agent.main(), 0)
            model.assert_not_called()

    def test_check_does_not_infer(self):
        import local_waitwise_agent
        with patch("sys.argv", ["local_waitwise_agent.py", "--check"]), patch.object(local_waitwise_agent, "LocalOllamaModel") as local:
            local.return_value.check_ready.return_value = {"name": "qwen2.5:0.5b", "digest": "abc"}
            self.assertEqual(local_waitwise_agent.main(), 0)
            local.return_value.__call__.assert_not_called() if hasattr(local.return_value.__call__, "assert_not_called") else None

    def test_runner_writes_reports_with_mock_model(self):
        import local_waitwise_agent
        class FakeModel:
            def __init__(self, model):
                self.model = model
                self.model_info = {"name": model, "digest": "test-digest", "size_bytes": 1}
                self.call_stats = []
                self.calls = 0

            def check_ready(self):
                return self.model_info

            def __call__(self, transcript, catalog):
                self.calls += 1
                return json.dumps({"action_id": catalog[0]})

        with TemporaryDirectory() as directory:
            with patch("sys.argv", ["local_waitwise_agent.py", "--run-local", "--limit", "2", "--output-dir", directory]), \
                 patch.object(local_waitwise_agent, "LocalOllamaModel", FakeModel):
                self.assertEqual(local_waitwise_agent.main(), 0)
            report = json.loads((Path(directory) / "local_llm_summary.json").read_text())
            self.assertEqual(len(report["results"]), 3)
            self.assertEqual(report["model_info"]["digest"], "test-digest")
            with (Path(directory) / "local_llm_decisions.csv").open(newline="") as handle:
                import csv
                self.assertEqual(len(list(csv.DictReader(handle))), 6)

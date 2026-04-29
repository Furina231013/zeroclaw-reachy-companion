from __future__ import annotations

import asyncio
import time

from fastapi.testclient import TestClient

from zeroclaw_reachy_companion.config import AppConfig
from zeroclaw_reachy_companion.service import create_service_app
from zeroclaw_reachy_companion.tools import ToolResult


def _client() -> TestClient:
    app = create_service_app(
        AppConfig(
            mode="service",
            reachy_mode="dry_run",
            llm_backend="mock",
            tts_backend="print",
        )
    )
    return TestClient(app)


def test_service_health_and_state() -> None:
    with _client() as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["reachy_mode"] == "dry_run"
        assert "speak" in data["tools"]
        assert data["queue"]["max_queue_size"] >= 1


def test_service_tools_formats() -> None:
    with _client() as client:
        zeroclaw = client.get("/tools").json()
        openai = client.get("/tools", params={"format": "openai"}).json()

        assert zeroclaw["format"] == "zeroclaw"
        assert any(tool["name"] == "soothe_baby" for tool in zeroclaw["tools"])
        assert openai["format"] == "openai"
        assert any(tool["function"]["name"] == "soothe_baby" for tool in openai["tools"])


def test_service_execute_tool() -> None:
    with _client() as client:
        response = client.post(
            "/tools/speak/execute",
            json={"arguments": {"text": "Hello from service."}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tool"] == "speak"
        assert data["status"] == "succeeded"
        assert data["job_id"]
        assert data["success"]
        assert data["spoken_text"] == "Hello from service."
        assert data["duration_ms"] >= 0


def test_service_event_injection() -> None:
    with _client() as client:
        response = client.post(
            "/events",
            json={"type": "baby_cry_detected", "confidence": 0.92, "source": "test"},
        )
        assert response.status_code == 200
        data = response.json()
        tools = [item["call"]["name"] for item in data["tools"]]
        assert data["event_type"] == "baby_cry_detected"
        assert "soothe_baby" in tools


def test_service_text_turn_debug_endpoint() -> None:
    with _client() as client:
        response = client.post("/turns/text", json={"text": "Can you nod gently?"})
        assert response.status_code == 200
        data = response.json()
        tools = [item["call"]["name"] for item in data["tools"]]
        assert tools == ["move_head", "move_head"]
        assert data["used_fallback"]


def test_service_async_tool_job_can_be_polled() -> None:
    with _client() as client:
        response = client.post(
            "/tools/speak/execute",
            json={"arguments": {"text": "Queued hello."}, "wait": False},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        job = _wait_for_terminal_job(client, job_id)
        assert job["status"] == "succeeded"
        assert job["result"]["success"]
        assert job["result"]["spoken_text"] == "Queued hello."


def test_service_tool_timeout_returns_failed_tool_payload() -> None:
    with _client() as client:
        async def slow_execute(name, args):  # noqa: ANN001
            await asyncio.sleep(1.0)
            return ToolResult.ok("late")

        client.app.state.reachy_service.runtime.registry.execute = slow_execute
        response = client.post(
            "/tools/speak/execute",
            json={"arguments": {"text": "Too slow."}, "timeout_s": 0.01},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "timed_out"
        assert not data["success"]
        assert "timed out" in data["error"]


def test_service_running_job_can_be_canceled() -> None:
    with _client() as client:
        async def slow_execute(name, args):  # noqa: ANN001
            await asyncio.sleep(2.0)
            return ToolResult.ok("late")

        client.app.state.reachy_service.runtime.registry.execute = slow_execute
        response = client.post(
            "/tools/speak/execute",
            json={"arguments": {"text": "Cancel me."}, "wait": False, "timeout_s": 5.0},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        cancel_response = client.post(f"/jobs/{job_id}/cancel")
        assert cancel_response.status_code == 200
        job = _wait_for_terminal_job(client, job_id)
        assert job["status"] == "canceled"


def _wait_for_terminal_job(client: TestClient, job_id: str) -> dict:
    for _ in range(50):
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"succeeded", "failed", "canceled", "timed_out"}:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish")

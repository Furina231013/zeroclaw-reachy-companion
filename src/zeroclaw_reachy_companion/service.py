from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from zeroclaw_reachy_companion.config import AppConfig
from zeroclaw_reachy_companion.runtime.events import CompanionEvent
from zeroclaw_reachy_companion.runtime.text_chat_loop import CompanionTurnResult, ReachyCompanionRuntime
from zeroclaw_reachy_companion.tools import ToolResult


TERMINAL_JOB_STATUSES = {"succeeded", "failed", "canceled", "timed_out"}


@dataclass
class ExecutionJob:
    """One queued service operation."""

    operation: str
    name: str
    payload: dict[str, Any]
    timeout_s: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    cancel_requested: bool = False
    future: asyncio.Future[dict[str, Any]] | None = field(default=None, repr=False, compare=False)

    def public(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "operation": self.operation,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "timeout_s": self.timeout_s,
            "cancel_requested": self.cancel_requested,
            "error": self.error,
            "result": self.result,
        }


class ReachyExecutionService:
    """Service façade around one Reachy companion runtime instance."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.runtime: ReachyCompanionRuntime | None = None
        self._job_queue: asyncio.Queue[ExecutionJob] = asyncio.Queue(maxsize=max(1, config.service_max_queue_size))
        self._jobs: OrderedDict[str, ExecutionJob] = OrderedDict()
        self._worker_task: asyncio.Task[None] | None = None
        self._current_job: ExecutionJob | None = None
        self._current_task: asyncio.Task[dict[str, Any]] | None = None

    async def start(self) -> None:
        self.runtime = await ReachyCompanionRuntime.create(self.config)
        self._worker_task = asyncio.create_task(self._run_worker())

    async def close(self) -> None:
        if self._current_task is not None:
            self._current_task.cancel()
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        if self.runtime is not None:
            await self.runtime.close()
            self.runtime = None

    def state(self) -> dict[str, Any]:
        runtime = self._require_runtime()
        return {
            "profile": runtime.profile.name,
            "reachy_mode": self.config.reachy_mode,
            "quiet_mode": runtime.state.quiet_mode,
            "tools": runtime.registry.names,
            "queue": self.queue_state(),
            "zeroclaw_text_url": self.config.zeroclaw_text_url,
        }

    def tools(self, *, spec_format: str = "zeroclaw") -> list[dict[str, Any]]:
        runtime = self._require_runtime()
        if spec_format == "openai":
            return runtime.registry.openai_specs()
        return runtime.registry.zeroclaw_specs()

    def queue_state(self) -> dict[str, Any]:
        return {
            "queued": self._job_queue.qsize(),
            "current_job_id": self._current_job.id if self._current_job else None,
            "current_status": self._current_job.status if self._current_job else None,
            "max_queue_size": self.config.service_max_queue_size,
            "job_history": len(self._jobs),
        }

    def list_jobs(self) -> list[dict[str, Any]]:
        return [job.public() for job in reversed(self._jobs.values())]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        job = self._jobs.get(job_id)
        return job.public() if job else None

    async def execute_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        wait: bool = True,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        job = self._enqueue_job(
            operation="tool",
            name=name,
            payload=arguments or {},
            timeout_s=timeout_s,
        )
        if not wait:
            return job.public()
        return await self._wait_for_job(job)

    async def handle_event(
        self,
        event: CompanionEvent | dict[str, Any],
        *,
        wait: bool = True,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        companion_event = CompanionEvent.from_value(event)
        job = self._enqueue_job(
            operation="event",
            name=companion_event.type,
            payload={
                "type": companion_event.type,
                "confidence": companion_event.confidence,
                "source": companion_event.source,
                "payload": companion_event.payload,
            },
            timeout_s=timeout_s,
        )
        if not wait:
            return job.public()
        return await self._wait_for_job(job)

    async def handle_text(self, text: str, *, wait: bool = True, timeout_s: float | None = None) -> dict[str, Any]:
        job = self._enqueue_job(
            operation="text",
            name="turn",
            payload={"text": text},
            timeout_s=timeout_s,
        )
        if not wait:
            return job.public()
        return await self._wait_for_job(job)

    async def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if job.status in TERMINAL_JOB_STATUSES:
            return job.public()

        job.cancel_requested = True
        if job.status == "queued":
            self._finish_job(job, status="canceled", error="canceled before execution")
            return job.public()

        if job is self._current_job and self._current_task is not None:
            self._current_task.cancel()
            await self._stop_motion_after_interrupt()
            if job.future is not None:
                try:
                    await asyncio.wait_for(asyncio.shield(job.future), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
        return job.public()

    def _enqueue_job(
        self,
        *,
        operation: str,
        name: str,
        payload: dict[str, Any],
        timeout_s: float | None,
    ) -> ExecutionJob:
        self._require_runtime()
        if self._job_queue.full():
            raise asyncio.QueueFull("execution queue is full")
        loop = asyncio.get_running_loop()
        job = ExecutionJob(
            operation=operation,
            name=name,
            payload=payload,
            timeout_s=self.config.service_default_timeout_s if timeout_s is None else max(0.0, float(timeout_s)),
            future=loop.create_future(),
        )
        self._jobs[job.id] = job
        self._trim_jobs()
        self._job_queue.put_nowait(job)
        return job

    async def _wait_for_job(self, job: ExecutionJob) -> dict[str, Any]:
        if job.future is None:
            raise RuntimeError("job future is missing")
        return await asyncio.shield(job.future)

    async def _run_worker(self) -> None:
        while True:
            job = await self._job_queue.get()
            try:
                if job.cancel_requested or job.status == "canceled":
                    self._finish_job(job, status="canceled", error=job.error or "canceled before execution")
                    continue

                self._current_job = job
                job.status = "running"
                job.started_at = time.time()
                self._current_task = asyncio.create_task(self._run_job(job))
                try:
                    if job.timeout_s > 0:
                        result = await asyncio.wait_for(self._current_task, timeout=job.timeout_s)
                    else:
                        result = await self._current_task
                    self._finish_job(job, status="succeeded", result=result)
                except asyncio.TimeoutError:
                    await self._stop_motion_after_interrupt()
                    self._finish_job(
                        job,
                        status="timed_out",
                        result=self._failure_payload(job, f"execution timed out after {job.timeout_s:g}s"),
                        error=f"execution timed out after {job.timeout_s:g}s",
                    )
                except asyncio.CancelledError:
                    await self._stop_motion_after_interrupt()
                    self._finish_job(
                        job,
                        status="canceled",
                        result=self._failure_payload(job, "execution canceled"),
                        error="execution canceled",
                    )
                    if asyncio.current_task() and asyncio.current_task().cancelling() and not job.cancel_requested:
                        raise
                except Exception as exc:
                    self._finish_job(
                        job,
                        status="failed",
                        result=self._failure_payload(job, f"{type(exc).__name__}: {exc}"),
                        error=f"{type(exc).__name__}: {exc}",
                    )
            finally:
                self._current_task = None
                self._current_job = None
                self._job_queue.task_done()

    async def _run_job(self, job: ExecutionJob) -> dict[str, Any]:
        runtime = self._require_runtime()
        start = time.perf_counter()
        if job.operation == "tool":
            result = await runtime.registry.execute(job.name, job.payload)
            return {
                "job_id": job.id,
                "status": "succeeded",
                "tool": job.name,
                **_tool_result_payload(result),
                "duration_ms": round((time.perf_counter() - start) * 1000),
            }
        if job.operation == "event":
            result = await runtime.handle_event(job.payload, announce=False)
            payload = _turn_result_payload(result)
            payload.update({"job_id": job.id, "status": "succeeded"})
            return payload
        if job.operation == "text":
            text = job.payload.get("text")
            if not isinstance(text, str):
                raise ValueError("text job requires text")
            result = await runtime.handle_text(text, announce=False)
            payload = _turn_result_payload(result)
            payload.update({"job_id": job.id, "status": "succeeded"})
            return payload
        raise ValueError(f"unknown job operation: {job.operation}")

    async def _stop_motion_after_interrupt(self) -> None:
        runtime = self.runtime
        if runtime is None:
            return
        try:
            await runtime.reachy.stop_motion()
        except Exception:
            pass

    def _finish_job(
        self,
        job: ExecutionJob,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        job.status = status
        job.finished_at = time.time()
        job.error = error
        if result is not None:
            result["job_id"] = job.id
            result["status"] = status
            job.result = result
        elif job.result is None:
            job.result = {"job_id": job.id, "status": status, "error": error}

        if job.future is not None and not job.future.done():
            job.future.set_result(job.result)

    def _failure_payload(self, job: ExecutionJob, error: str) -> dict[str, Any]:
        if job.operation == "tool":
            return {
                "job_id": job.id,
                "status": job.status,
                "tool": job.name,
                "success": False,
                "output": "",
                "spoken_text": None,
                "error": error,
                "duration_ms": _elapsed_ms(job),
            }
        return {
            "job_id": job.id,
            "status": job.status,
            "final_text": "",
            "response": "",
            "used_fallback": False,
            "event_type": job.name if job.operation == "event" else None,
            "tools": [],
            "error": error,
        }

    def _trim_jobs(self) -> None:
        limit = max(1, self.config.service_job_history_limit)
        while len(self._jobs) > limit:
            oldest_id, oldest_job = next(iter(self._jobs.items()))
            if oldest_job.status not in TERMINAL_JOB_STATUSES:
                break
            self._jobs.pop(oldest_id, None)

    def _require_runtime(self) -> ReachyCompanionRuntime:
        if self.runtime is None:
            raise RuntimeError("Reachy execution service is not started")
        return self.runtime


def create_service_app(config: AppConfig):
    try:
        from fastapi import FastAPI, HTTPException, Query
    except Exception as exc:  # pragma: no cover - optional runtime import
        raise RuntimeError("Service mode requires fastapi and uvicorn.") from exc

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service = ReachyExecutionService(config)
        await service.start()
        app.state.reachy_service = service
        try:
            yield
        finally:
            await service.close()

    app = FastAPI(title="ZeroClaw Reachy Execution Service", version="0.1.0", lifespan=lifespan)

    def service() -> ReachyExecutionService:
        return app.state.reachy_service

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", **service().state()}

    @app.get("/state")
    async def state() -> dict[str, Any]:
        return service().state()

    @app.get("/tools")
    async def tools(format: str = Query(default="zeroclaw", pattern="^(zeroclaw|openai)$")) -> dict[str, Any]:
        return {"format": format, "tools": service().tools(spec_format=format)}

    @app.get("/jobs")
    async def jobs() -> dict[str, Any]:
        return {"queue": service().queue_state(), "jobs": service().list_jobs()}

    @app.get("/jobs/{job_id}")
    async def job(job_id: str) -> dict[str, Any]:
        payload = service().get_job(job_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="job not found")
        return payload

    @app.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str) -> dict[str, Any]:
        payload = await service().cancel_job(job_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="job not found")
        return payload

    @app.post("/tools/{tool_name}/execute")
    async def execute_tool(tool_name: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = body or {}
        arguments = _tool_arguments_from_body(payload)
        if not isinstance(arguments, dict):
            raise HTTPException(status_code=400, detail="arguments must be a JSON object")
        try:
            return await service().execute_tool(
                tool_name,
                arguments,
                wait=_wait_from_body(payload),
                timeout_s=_timeout_from_body(payload),
            )
        except asyncio.QueueFull as exc:
            raise HTTPException(status_code=429, detail="execution queue is full") from exc

    @app.post("/events")
    async def events(body: dict[str, Any]) -> dict[str, Any]:
        try:
            return await service().handle_event(
                body,
                wait=_wait_from_body(body),
                timeout_s=_timeout_from_body(body),
            )
        except asyncio.QueueFull as exc:
            raise HTTPException(status_code=429, detail="execution queue is full") from exc

    @app.post("/turns/text")
    async def turns_text(body: dict[str, Any]) -> dict[str, Any]:
        text = body.get("text") or body.get("prompt") or body.get("user_text")
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(status_code=400, detail="text is required")
        try:
            return await service().handle_text(
                text,
                wait=_wait_from_body(body),
                timeout_s=_timeout_from_body(body),
            )
        except asyncio.QueueFull as exc:
            raise HTTPException(status_code=429, detail="execution queue is full") from exc

    return app


async def run_service(config: AppConfig) -> None:
    try:
        import uvicorn
    except Exception as exc:  # pragma: no cover - optional runtime import
        raise RuntimeError("Service mode requires uvicorn.") from exc

    app = create_service_app(config)
    uvicorn_config = uvicorn.Config(
        app,
        host=config.service_host,
        port=config.service_port,
        log_level=config.log_level.lower(),
    )
    server = uvicorn.Server(uvicorn_config)
    await server.serve()


def _tool_result_payload(result: ToolResult) -> dict[str, Any]:
    return {
        "success": result.success,
        "output": result.output,
        "spoken_text": result.spoken_text,
        "error": result.error,
    }


def _turn_result_payload(result: CompanionTurnResult) -> dict[str, Any]:
    return {
        "final_text": result.final_text,
        "response": result.response,
        "used_fallback": result.used_fallback,
        "event_type": result.event_type,
        "tools": [
            {
                "call": {
                    "name": item.call.name,
                    "arguments": item.call.arguments,
                },
                "result": _tool_result_payload(item.result),
            }
            for item in result.tools
        ],
    }


def _tool_arguments_from_body(payload: dict[str, Any]) -> dict[str, Any]:
    if "arguments" in payload:
        arguments = payload.get("arguments")
        return arguments if isinstance(arguments, dict) else {}
    return {
        key: value
        for key, value in payload.items()
        if key not in {"wait", "timeout_s", "request_id"}
    }


def _wait_from_body(payload: dict[str, Any]) -> bool:
    value = payload.get("wait", True)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _timeout_from_body(payload: dict[str, Any]) -> float | None:
    value = payload.get("timeout_s")
    if value in (None, ""):
        return None
    return float(value)


def _elapsed_ms(job: ExecutionJob) -> int:
    start = job.started_at or job.created_at
    end = job.finished_at or time.time()
    return round((end - start) * 1000)

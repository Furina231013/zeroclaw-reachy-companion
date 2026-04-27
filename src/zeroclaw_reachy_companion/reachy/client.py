from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Any


class ReachyConnectionError(RuntimeError):
    """Raised when the Reachy Mini daemon or SDK cannot be reached."""


@dataclass
class ReachyClient:
    """Thin adapter around Reachy Mini SDK with a first-class dry-run mode.

    The local baby companion app initializes the SDK with ``ReachyMini()`` and
    lets the daemon choose simulation or hardware. This adapter follows that
    pattern for ``sim`` and ``real`` while keeping dry-run fully runnable on a
    Mac without robot hardware.
    """

    mode: str = "dry_run"
    host: str = "localhost"
    port: int | None = None
    _robot: Any | None = field(default=None, init=False, repr=False)
    _recorded_emotions: Any | None = field(default=None, init=False, repr=False)
    actions: list[str] = field(default_factory=list, init=False)

    async def connect(self) -> None:
        mode = self.mode.lower()
        if mode == "dry_run":
            self.actions.append("[DRY-RUN] connect")
            return
        if mode not in {"sim", "real"}:
            raise ValueError("reachy mode must be one of: dry_run, sim, real")

        try:
            from reachy_mini import ReachyMini
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ReachyConnectionError(
                "reachy-mini is not installed. Install the optional 'reachy' extra "
                "and start reachy-mini-daemon before using sim/real mode."
            ) from exc

        try:
            kwargs: dict[str, Any] = {}
            if self.host:
                kwargs["host"] = self.host
            if self.port is not None:
                kwargs["port"] = self.port
            if self.host in {"localhost", "127.0.0.1", "::1"}:
                kwargs["connection_mode"] = "localhost_only"
                kwargs.setdefault("port", 8000)

            self._robot = await asyncio.to_thread(ReachyMini, **kwargs)
        except Exception as exc:  # pragma: no cover - requires daemon/hardware
            raise ReachyConnectionError(f"Failed to initialize ReachyMini SDK: {exc}") from exc

    async def close(self) -> None:
        if self.mode.lower() == "dry_run":
            self.actions.append("[DRY-RUN] close")
            return
        robot = self._robot
        if robot is None:
            return
        media = getattr(robot, "media", None)
        if media is not None and hasattr(media, "close"):
            await asyncio.to_thread(media.close)
        client = getattr(robot, "client", None)
        if client is not None and hasattr(client, "disconnect"):
            await asyncio.to_thread(client.disconnect)

    async def speak(self, text: str) -> str:
        if self.mode.lower() == "dry_run":
            return self._dry_run(f"speak: {text}", f"spoke: {text}")

        robot = self._require_robot()
        for method_name in ("speak", "say"):
            method = getattr(robot, method_name, None)
            if callable(method):  # pragma: no cover - SDK-version dependent
                await asyncio.to_thread(method, text)
                return f"spoke via ReachyMini.{method_name}"
        line = f"{self._prefix()} speak unavailable in SDK; external TTS should say: {text}"
        print(line)
        return "Reachy SDK speech output is not available; printed text for external TTS."

    async def move_head(self, yaw: float = 0, pitch: float = 0, roll: float = 0, duration: float = 1.0) -> str:
        if self.mode.lower() == "dry_run":
            return self._dry_run(
                f"move_head: yaw={yaw:g} pitch={pitch:g} roll={roll:g} duration={duration:g}",
                f"moved head yaw={yaw:g} pitch={pitch:g} roll={roll:g}",
            )

        await self._goto_head_pose(yaw=yaw, pitch=pitch, roll=roll, duration=duration)
        line = f"{self._prefix()} move_head: yaw={yaw:g} pitch={pitch:g} roll={roll:g} duration={duration:g}"
        print(line)
        return f"moved head yaw={yaw:g} pitch={pitch:g} roll={roll:g}"

    async def play_emotion(self, emotion: str) -> str:
        if self.mode.lower() == "dry_run":
            return self._dry_run(f"play_emotion: {emotion}", f"played emotion: {emotion}")

        requested = (emotion or "gentle").strip().lower().replace(" ", "_")
        try:
            move_name = self._resolve_emotion_name(requested)
            recorded_move = self._get_recorded_emotions().get(move_name)
            await self._play_evaluated_move(recorded_move, max_duration=8.0)
            line = f"{self._prefix()} play_emotion: {requested} -> recorded:{move_name}"
            print(line)
            return f"played recorded emotion: {move_name}"
        except Exception as exc:
            print(f"{self._prefix()} recorded emotion unavailable ({type(exc).__name__}: {exc}); using fallback")
            await self._play_fallback_emotion(requested)
            line = f"{self._prefix()} play_emotion: {requested}"
            print(line)
            return f"played fallback emotion: {requested}"

    async def dance(self, style: str = "gentle", duration: float = 5.0) -> str:
        if self.mode.lower() == "dry_run":
            return self._dry_run(
                f"dance: style={style} duration={duration:g}",
                f"danced style={style} duration={duration:g}",
            )

        requested = (style or "gentle").strip().lower().replace(" ", "_")
        try:
            from reachy_mini_dances_library.dance_move import DanceMove

            move_name = self._resolve_dance_name(requested)
            dance_move = DanceMove(move_name)
            repeats = max(1, math.ceil(duration / max(float(dance_move.duration), 0.1)))
            for _ in range(repeats):
                await self._play_evaluated_move(dance_move, max_duration=duration)
                duration -= float(dance_move.duration)
                if duration <= 0:
                    break
            await self._goto_head_pose(yaw=0, pitch=0, roll=0, duration=0.35)
            line = f"{self._prefix()} dance: {requested} -> recorded:{move_name}"
            print(line)
            return f"danced recorded move={move_name}"
        except Exception as exc:
            print(f"{self._prefix()} recorded dance unavailable ({type(exc).__name__}: {exc}); using fallback")
            await self._play_fallback_dance(requested, duration)
            line = f"{self._prefix()} dance: style={requested} duration={duration:g}"
            print(line)
            return f"danced fallback style={requested} duration={duration:g}"

    async def stop_motion(self) -> str:
        if self.mode.lower() == "dry_run":
            return self._dry_run("stop_motion", "stopped motion")

        robot = self._require_robot()
        current_head_pose = await asyncio.to_thread(robot.get_current_head_pose)
        _, current_antennas = await asyncio.to_thread(robot.get_current_joint_positions)
        await asyncio.to_thread(
            robot.goto_target,
            head=current_head_pose,
            antennas=list(current_antennas),
            body_yaw=0.0,
            duration=0.1,
        )
        line = f"{self._prefix()} stop_motion"
        print(line)
        return "stopped motion"

    def _dry_run(self, action: str, result: str) -> str:
        line = f"[DRY-RUN] {action}"
        self.actions.append(line)
        print(line)
        return result

    async def _goto_head_pose(self, yaw: float, pitch: float, roll: float, duration: float) -> None:
        robot = self._require_robot()
        try:
            from reachy_mini.utils import create_head_pose
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ReachyConnectionError("reachy_mini.utils.create_head_pose is unavailable.") from exc

        target = create_head_pose(0, 0, 0, roll, pitch, yaw, degrees=True)
        await asyncio.to_thread(
            robot.goto_target,
            head=target,
            antennas=[0.0, 0.0],
            body_yaw=0.0,
            duration=duration,
        )
        await asyncio.sleep(max(0.0, duration + 0.05))

    async def _play_evaluated_move(self, move: Any, *, max_duration: float | None = None, frequency_hz: float = 25.0) -> None:
        robot = self._require_robot()
        duration = float(getattr(move, "duration"))
        if max_duration is not None:
            duration = min(duration, max_duration)
        period = 1.0 / frequency_hz
        steps = max(1, int(duration * frequency_hz))

        for step in range(steps + 1):
            t = min(duration, step * period)
            head_pose, antennas, body_yaw = move.evaluate(t)
            await asyncio.to_thread(
                robot.set_target,
                head=head_pose,
                antennas=self._coerce_antennas(antennas),
                body_yaw=float(body_yaw) if body_yaw is not None else 0.0,
            )
            await asyncio.sleep(period)

    def _get_recorded_emotions(self) -> Any:
        if self._recorded_emotions is None:
            from reachy_mini.motion.recorded_move import RecordedMoves

            self._recorded_emotions = RecordedMoves("pollen-robotics/reachy-mini-emotions-library")
        return self._recorded_emotions

    def _resolve_emotion_name(self, requested: str) -> str:
        moves = self._get_recorded_emotions()
        available = set(moves.list_moves())
        aliases = {
            "gentle": "calming1",
            "calm": "calming1",
            "happy": "cheerful1",
            "excited": "enthusiastic1",
            "sleepy": "sleep1",
            "sad": "sad1",
            "surprised": "surprised1",
            "success": "success1",
            "loving": "loving1",
            "serene": "serenity1",
        }
        candidate = aliases.get(requested, requested)
        if candidate in available:
            return candidate
        raise ValueError(f"unknown emotion '{requested}'. Available examples: {sorted(available)[:12]}")

    @staticmethod
    def _resolve_dance_name(requested: str) -> str:
        from reachy_mini_dances_library.collection.dance import AVAILABLE_MOVES

        aliases = {
            "gentle": "side_to_side_sway",
            "calm": "pendulum_swing",
            "happy": "groovy_sway_and_roll",
            "playful": "side_peekaboo",
            "excited": "yeah_nod",
            "nod": "simple_nod",
            "dance": "groovy_sway_and_roll",
            "random": "groovy_sway_and_roll",
        }
        candidate = aliases.get(requested, requested)
        if candidate in AVAILABLE_MOVES:
            return candidate
        raise ValueError(f"unknown dance move '{requested}'. Available examples: {list(AVAILABLE_MOVES)[:12]}")

    @staticmethod
    def _coerce_antennas(antennas: Any) -> list[float] | None:
        if antennas is None:
            return None
        try:
            return [float(antennas[0]), float(antennas[1])]
        except Exception as exc:
            raise ValueError(f"Invalid antennas value: {antennas!r}") from exc

    async def _play_fallback_emotion(self, normalized: str) -> None:
        sequences = {
            "happy": [(0, -8, 0, 0.35), (0, 8, 0, 0.35), (0, 0, 0, 0.3)],
            "excited": [(-12, -8, 0, 0.3), (12, 8, 0, 0.3), (0, 0, 0, 0.3)],
            "calm": [(0, -5, 0, 0.8), (0, 0, 0, 0.5)],
            "gentle": [(0, -4, 5, 0.6), (0, 0, 0, 0.5)],
            "sleepy": [(0, 8, 0, 0.8), (0, 0, 0, 0.5)],
            "surprised": [(0, -12, 0, 0.3), (0, 0, 0, 0.4)],
            "sad": [(0, 10, 0, 0.8), (0, 0, 0, 0.5)],
        }
        for yaw, pitch, roll, duration in sequences.get(normalized, sequences["gentle"]):
            await self._goto_head_pose(yaw=yaw, pitch=pitch, roll=roll, duration=duration)

    async def _play_fallback_dance(self, normalized: str, duration: float) -> None:
        step_duration = 0.45 if normalized in {"happy", "playful", "excited"} else 0.7
        steps = max(2, min(8, int(duration / step_duration)))
        for index in range(steps):
            direction = -1 if index % 2 else 1
            yaw = 12 * direction
            roll = 8 * direction
            pitch = -5 if normalized in {"happy", "excited", "playful"} else 0
            await self._goto_head_pose(yaw=yaw, pitch=pitch, roll=roll, duration=step_duration)
        await self._goto_head_pose(yaw=0, pitch=0, roll=0, duration=0.5)

    def _prefix(self) -> str:
        return f"[REACHY-{self.mode.upper()}]"

    def _require_robot(self) -> Any:
        if self._robot is None:
            raise ReachyConnectionError("ReachyClient is not connected. Call connect() first.")
        return self._robot

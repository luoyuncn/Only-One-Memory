from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from oom.memory_core.pipeline.checkpoint import PipelineSessionState


L1Runner = Callable[[str], Awaitable[object] | object]
L2Runner = Callable[[str], Awaitable[object] | object]
L3Runner = Callable[[], Awaitable[object] | object]


class PipelineManager:
    def __init__(
        self,
        every_n_conversations: int = 5,
        enable_warmup: bool = True,
        idle_timeout_seconds: int | None = None,
        l1_runner: L1Runner | None = None,
        l2_runner: L2Runner | None = None,
        l3_runner: L3Runner | None = None,
    ) -> None:
        if every_n_conversations <= 0:
            raise ValueError("every_n_conversations must be positive")
        self.every_n_conversations = every_n_conversations
        self.enable_warmup = enable_warmup
        self.idle_timeout_seconds = idle_timeout_seconds
        self.l1_runner = l1_runner
        self.l2_runner = l2_runner
        self.l3_runner = l3_runner
        self._states: dict[str, PipelineSessionState] = {}
        self._l3_running = False
        self._l3_pending = False

    async def notify_conversation(self, session_key: str) -> None:
        state = self._states.get(session_key)
        if state is None:
            state = PipelineSessionState.new(session_key, enable_warmup=self.enable_warmup)
        state.conversation_count += 1
        state.last_activity_at = datetime.now(timezone.utc)
        self._states[session_key] = state

        if self._should_run_l1(state):
            await self._run_l1(session_key)

    async def flush_session(self, session_key: str) -> None:
        if session_key not in self._states:
            self._states[session_key] = PipelineSessionState.new(session_key, enable_warmup=self.enable_warmup)
        await self._run_l1(session_key)

    async def flush_idle_sessions(self, now: datetime | None = None) -> None:
        if self.idle_timeout_seconds is None:
            return
        current = now or datetime.now(timezone.utc)
        threshold = timedelta(seconds=self.idle_timeout_seconds)
        for state in list(self._states.values()):
            if current - state.last_activity_at >= threshold:
                await self._run_l1(state.session_key)

    def state_for(self, session_key: str) -> PipelineSessionState | None:
        return self._states.get(session_key)

    def load_states(self, states: dict[str, PipelineSessionState]) -> None:
        self._states = dict(states)

    def dump_states(self) -> dict[str, PipelineSessionState]:
        return dict(self._states)

    def status(self) -> dict[str, object]:
        return {
            "l1": {
                "sessions": len(self._states),
                "conversation_count": sum(state.conversation_count for state in self._states.values()),
            },
            "l2": {"pending": sum(state.l2_pending_l1_count for state in self._states.values())},
            "l3": {"running": self._l3_running, "pending": self._l3_pending},
        }

    def trigger_l2(self, session_key: str) -> None:
        state = self._states.get(session_key)
        if state is None:
            state = PipelineSessionState.new(session_key, enable_warmup=self.enable_warmup)
            self._states[session_key] = state
        state.l2_pending_l1_count += 1

    def trigger_l3(self) -> None:
        if self._l3_running:
            self._l3_pending = True
            return
        self._l3_pending = True

    async def drain_l3_for_test(self) -> None:
        await self._drain_l3()

    def mark_l3_running_for_test(self, running: bool) -> None:
        self._l3_running = running

    async def _drain_l3(self) -> None:
        if self._l3_running or not self._l3_pending:
            return
        self._l3_pending = False
        self._l3_running = True
        try:
            if self.l3_runner is not None:
                result = self.l3_runner()
                if inspect.isawaitable(result):
                    await result
        finally:
            self._l3_running = False

    def _should_run_l1(self, state: PipelineSessionState) -> bool:
        if state.warmup_threshold and state.conversation_count == state.warmup_threshold:
            return True
        return state.conversation_count % self.every_n_conversations == 0

    async def _run_l1(self, session_key: str) -> None:
        if self.l1_runner is None:
            return
        state = self._states.get(session_key)
        try:
            result = self.l1_runner(session_key)
            if inspect.isawaitable(result):
                await result
        except Exception:
            if state is not None:
                state.l1_retry_count += 1
            raise
        if state is not None:
            state.l1_retry_count = 0

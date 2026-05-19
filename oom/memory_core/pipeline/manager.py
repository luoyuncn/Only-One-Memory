from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from oom.memory_core.observability.metrics import increment
from oom.memory_core.pipeline.checkpoint import PipelineSessionState


L1Runner = Callable[..., Awaitable[object] | object]
L2Runner = Callable[..., Awaitable[object] | object]
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

    async def notify_conversation(self, session_key: str, tenant_id: str = "default") -> None:
        key = self._state_key(tenant_id, session_key)
        state = self._states.get(key)
        if state is None:
            state = PipelineSessionState.new(session_key, enable_warmup=self.enable_warmup, tenant_id=tenant_id)
        else:
            state.tenant_id = tenant_id
        state.conversation_count += 1
        state.last_activity_at = datetime.now(timezone.utc)
        self._states[key] = state

        if self._should_run_l1(state):
            await self._run_l1(session_key, tenant_id=tenant_id)

    async def flush_session(self, session_key: str, tenant_id: str = "default") -> None:
        key = self._state_key(tenant_id, session_key)
        if key not in self._states:
            self._states[key] = PipelineSessionState.new(
                session_key, enable_warmup=self.enable_warmup, tenant_id=tenant_id
            )
        await self._run_l1(session_key, tenant_id=tenant_id)

    async def flush_idle_sessions(self, now: datetime | None = None) -> None:
        if self.idle_timeout_seconds is None:
            return
        current = now or datetime.now(timezone.utc)
        threshold = timedelta(seconds=self.idle_timeout_seconds)
        for state in list(self._states.values()):
            if current - state.last_activity_at >= threshold:
                await self._run_l1(state.session_key, tenant_id=state.tenant_id)

    def state_for(self, session_key: str, tenant_id: str = "default") -> PipelineSessionState | None:
        return self._states.get(self._state_key(tenant_id, session_key))

    def load_states(self, states: dict[str, PipelineSessionState]) -> None:
        self._states = {self._state_key(state.tenant_id, state.session_key): state for state in states.values()}

    def dump_states(self) -> dict[str, PipelineSessionState]:
        return dict(self._states)

    def dump_states_for_tenant(self, tenant_id: str) -> dict[str, PipelineSessionState]:
        return {state.session_key: state for state in self._states.values() if state.tenant_id == tenant_id}

    def merge_states(self, states: dict[str, PipelineSessionState]) -> None:
        for state in states.values():
            self._states[self._state_key(state.tenant_id, state.session_key)] = state

    def status(self) -> dict[str, object]:
        return {
            "l1": {
                "sessions": len(self._states),
                "conversation_count": sum(state.conversation_count for state in self._states.values()),
            },
            "l2": {"pending": sum(state.l2_pending_l1_count for state in self._states.values())},
            "l3": {"running": self._l3_running, "pending": self._l3_pending},
        }

    def trigger_l2(self, session_key: str, tenant_id: str = "default") -> None:
        key = self._state_key(tenant_id, session_key)
        state = self._states.get(key)
        if state is None:
            state = PipelineSessionState.new(session_key, enable_warmup=self.enable_warmup, tenant_id=tenant_id)
            self._states[key] = state
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

    async def _run_l1(self, session_key: str, tenant_id: str = "default") -> None:
        if self.l1_runner is None:
            return
        state = self._states.get(self._state_key(tenant_id, session_key))
        try:
            result = self._call_l1_runner(session_key, tenant_id)
            if inspect.isawaitable(result):
                await result
        except Exception:
            if state is not None:
                state.l1_retry_count += 1
            raise
        if state is not None:
            state.l1_retry_count = 0
        increment("oom_l1_extraction_total")

    def _call_l1_runner(self, session_key: str, tenant_id: str) -> object:
        if self.l1_runner is None:
            return None
        try:
            signature = inspect.signature(self.l1_runner)
            positional = [
                param
                for param in signature.parameters.values()
                if param.kind
                in {
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.VAR_POSITIONAL,
                }
            ]
            if any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in positional) or len(positional) >= 2:
                return self.l1_runner(session_key, tenant_id)
        except (TypeError, ValueError):
            pass
        return self.l1_runner(session_key)

    @staticmethod
    def _state_key(tenant_id: str, session_key: str) -> str:
        return f"{tenant_id}:{session_key}"

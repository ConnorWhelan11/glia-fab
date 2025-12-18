"""
Event System - Structured event logging for observability.

Events are logged to .dev-kernel/logs/events.jsonl and can be
consumed by beads_viewer or other observability tools.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


def _utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class EventType(str, Enum):
    """Types of kernel events."""

    # Lifecycle events
    KERNEL_STARTED = "kernel.started"
    KERNEL_STOPPED = "kernel.stopped"
    CYCLE_STARTED = "cycle.started"
    CYCLE_COMPLETED = "cycle.completed"

    # Scheduling events
    SCHEDULE_COMPUTED = "schedule.computed"
    ISSUE_SCHEDULED = "issue.scheduled"
    ISSUE_SKIPPED = "issue.skipped"

    # Dispatch events
    WORKCELL_CREATED = "workcell.created"
    WORKCELL_STARTED = "workcell.started"
    WORKCELL_COMPLETED = "workcell.completed"
    WORKCELL_FAILED = "workcell.failed"
    WORKCELL_TIMEOUT = "workcell.timeout"

    # Verification events
    GATES_STARTED = "gates.started"
    GATES_PASSED = "gates.passed"
    GATES_FAILED = "gates.failed"

    # Speculate events
    SPECULATE_STARTED = "speculate.started"
    SPECULATE_VOTED = "speculate.voted"
    SPECULATE_WINNER = "speculate.winner"

    # Issue events
    ISSUE_STARTED = "issue.started"
    ISSUE_COMPLETED = "issue.completed"
    ISSUE_FAILED = "issue.failed"
    ISSUE_ESCALATED = "issue.escalated"
    ISSUE_CREATED = "issue.created"

    # System events
    ADAPTER_HEALTH = "adapter.health"
    ERROR = "error"


@dataclass
class Event:
    """Structured event for logging."""

    type: EventType | str
    timestamp: datetime = field(default_factory=_utc_now)
    issue_id: str | None = None
    workcell_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    # Metrics
    duration_ms: int | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "type": self.type.value if isinstance(self.type, EventType) else self.type,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
        }

        if self.issue_id:
            result["issue_id"] = self.issue_id
        if self.workcell_id:
            result["workcell_id"] = self.workcell_id
        if self.data:
            result["data"] = self.data
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.tokens_used is not None:
            result["tokens_used"] = self.tokens_used
        if self.cost_usd is not None:
            result["cost_usd"] = self.cost_usd

        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class EventEmitter:
    """
    Emits and logs structured events.

    Events are written to .dev-kernel/logs/events.jsonl
    """

    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.logs_dir / "events.jsonl"

    def emit(self, event: Event) -> None:
        """Emit an event to the log file."""
        try:
            with open(self.events_file, "a") as f:
                f.write(event.to_json() + "\n")

            logger.debug(
                "Event emitted",
                type=event.type,
                issue_id=event.issue_id,
            )
        except OSError as e:
            logger.error("Failed to write event", error=str(e))

    def kernel_started(self, config: dict[str, Any]) -> None:
        """Log kernel start event."""
        self.emit(Event(
            type=EventType.KERNEL_STARTED,
            data={
                "max_concurrent_workcells": config.get("max_concurrent_workcells"),
                "toolchain_priority": config.get("toolchain_priority"),
            },
        ))

    def kernel_stopped(self, stats: dict[str, Any]) -> None:
        """Log kernel stop event."""
        self.emit(Event(
            type=EventType.KERNEL_STOPPED,
            data=stats,
        ))

    def cycle_started(self, cycle_number: int) -> None:
        """Log cycle start."""
        self.emit(Event(
            type=EventType.CYCLE_STARTED,
            data={"cycle": cycle_number},
        ))

    def cycle_completed(
        self,
        cycle_number: int,
        scheduled: int,
        completed: int,
        failed: int,
    ) -> None:
        """Log cycle completion."""
        self.emit(Event(
            type=EventType.CYCLE_COMPLETED,
            data={
                "cycle": cycle_number,
                "scheduled": scheduled,
                "completed": completed,
                "failed": failed,
            },
        ))

    def issue_scheduled(
        self,
        issue_id: str,
        toolchain: str,
        speculate: bool = False,
    ) -> None:
        """Log issue scheduling."""
        self.emit(Event(
            type=EventType.ISSUE_SCHEDULED,
            issue_id=issue_id,
            data={
                "toolchain": toolchain,
                "speculate": speculate,
            },
        ))

    def workcell_started(
        self,
        workcell_id: str,
        issue_id: str,
        toolchain: str,
    ) -> None:
        """Log workcell start."""
        self.emit(Event(
            type=EventType.WORKCELL_STARTED,
            issue_id=issue_id,
            workcell_id=workcell_id,
            data={"toolchain": toolchain},
        ))

    def workcell_completed(
        self,
        workcell_id: str,
        issue_id: str,
        status: str,
        duration_ms: int,
        tokens_used: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        """Log workcell completion."""
        self.emit(Event(
            type=EventType.WORKCELL_COMPLETED,
            issue_id=issue_id,
            workcell_id=workcell_id,
            data={"status": status},
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        ))

    def issue_completed(
        self,
        issue_id: str,
        toolchain: str,
        duration_ms: int,
    ) -> None:
        """Log issue completion."""
        self.emit(Event(
            type=EventType.ISSUE_COMPLETED,
            issue_id=issue_id,
            data={"toolchain": toolchain},
            duration_ms=duration_ms,
        ))

    def issue_failed(
        self,
        issue_id: str,
        error: str,
        attempt: int,
    ) -> None:
        """Log issue failure."""
        self.emit(Event(
            type=EventType.ISSUE_FAILED,
            issue_id=issue_id,
            data={
                "error": error,
                "attempt": attempt,
            },
        ))

    def issue_escalated(self, issue_id: str, reason: str) -> None:
        """Log issue escalation."""
        self.emit(Event(
            type=EventType.ISSUE_ESCALATED,
            issue_id=issue_id,
            data={"reason": reason},
        ))

    def gates_result(
        self,
        workcell_id: str,
        passed: bool,
        results: dict[str, Any],
    ) -> None:
        """Log gates result."""
        event_type = EventType.GATES_PASSED if passed else EventType.GATES_FAILED
        self.emit(Event(
            type=event_type,
            workcell_id=workcell_id,
            data={"gates": results},
        ))

    def error(self, message: str, context: dict[str, Any] | None = None) -> None:
        """Log an error event."""
        self.emit(Event(
            type=EventType.ERROR,
            data={
                "message": message,
                "context": context or {},
            },
        ))


class EventReader:
    """
    Reads events from log file for analysis and dashboard.
    """

    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.events_file = self.logs_dir / "events.jsonl"

    def read_all(self) -> list[dict[str, Any]]:
        """Read all events from file."""
        if not self.events_file.exists():
            return []

        events = []
        with open(self.events_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events

    def read_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Read most recent events."""
        all_events = self.read_all()
        return all_events[-limit:]

    def read_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """Read events of a specific type."""
        return [e for e in self.read_all() if e.get("type") == event_type]

    def read_by_issue(self, issue_id: str) -> list[dict[str, Any]]:
        """Read all events for an issue."""
        return [e for e in self.read_all() if e.get("issue_id") == issue_id]

    def get_stats(self) -> dict[str, Any]:
        """
        Compute statistics from events.

        Returns metrics suitable for dashboard display.
        """
        events = self.read_all()

        if not events:
            return {
                "total_events": 0,
                "issues_completed": 0,
                "issues_failed": 0,
                "total_tokens": 0,
                "total_cost_usd": 0,
                "avg_duration_ms": 0,
            }

        completed = [e for e in events if e.get("type") == EventType.ISSUE_COMPLETED.value]
        failed = [e for e in events if e.get("type") == EventType.ISSUE_FAILED.value]

        total_tokens = sum(e.get("tokens_used", 0) or 0 for e in events)
        total_cost = sum(e.get("cost_usd", 0) or 0 for e in events)

        durations = [e.get("duration_ms", 0) for e in completed if e.get("duration_ms")]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_events": len(events),
            "issues_completed": len(completed),
            "issues_failed": len(failed),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "avg_duration_ms": int(avg_duration),
            "success_rate": len(completed) / (len(completed) + len(failed))
            if completed or failed
            else 0,
        }


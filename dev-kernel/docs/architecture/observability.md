# Observability

## Overview

The kernel provides comprehensive observability through event logging, audit trails, and integration with beads_viewer.

## Event Types

```python
EVENT_TYPES = [
    "kernel_start",
    "kernel_stop",
    "schedule_cycle",
    "workcell_spawn",
    "workcell_complete",
    "workcell_fail",
    "gate_pass",
    "gate_fail",
    "vote_start",
    "vote_complete",
    "merge",
    "issue_create",
    "issue_update",
    "escalation",
    "error"
]
```

## Event Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "KernelEvent",
  "type": "object",
  "required": ["event_id", "timestamp", "type", "data"],
  "properties": {
    "event_id": {
      "type": "string",
      "format": "uuid"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "type": {
      "type": "string",
      "enum": ["kernel_start", "kernel_stop", "..."]
    },
    "data": {
      "type": "object",
      "additionalProperties": true
    },
    "context": {
      "type": "object",
      "properties": {
        "run_id": { "type": "string" },
        "issue_id": { "type": "string" },
        "workcell_id": { "type": "string" },
        "toolchain": { "type": "string" }
      }
    }
  }
}
```

## Example Events

```jsonl
{"event_id":"550e8400-e29b-41d4-a716-446655440001","timestamp":"2025-01-15T14:30:00Z","type":"kernel_start","data":{"config_hash":"abc123","issues_total":47,"ready_count":5},"context":{"run_id":"run-20250115-143000"}}
{"event_id":"550e8400-e29b-41d4-a716-446655440002","timestamp":"2025-01-15T14:30:01Z","type":"workcell_spawn","data":{"workcell_id":"wc-42-20250115T143001Z","toolchain":"codex","speculate":false},"context":{"run_id":"run-20250115-143000","issue_id":"42"}}
{"event_id":"550e8400-e29b-41d4-a716-446655440003","timestamp":"2025-01-15T14:52:18Z","type":"gate_pass","data":{"gate":"test","duration_ms":4523},"context":{"run_id":"run-20250115-143000","issue_id":"42","workcell_id":"wc-42-20250115T143001Z"}}
{"event_id":"550e8400-e29b-41d4-a716-446655440004","timestamp":"2025-01-15T14:52:20Z","type":"workcell_complete","data":{"status":"success","proof_path":".workcells/wc-42-xxx/proof.json"},"context":{"run_id":"run-20250115-143000","issue_id":"42","workcell_id":"wc-42-20250115T143001Z","toolchain":"codex"}}
```

## Audit Log

```python
class AuditLog:
    """Immutable audit trail for all kernel actions"""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_event(self, event: KernelEvent):
        # Append to daily log file (append-only)
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"events-{date_str}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def get_run_history(self, run_id: str) -> List[KernelEvent]:
        """Reconstruct full history for a run"""
        events = []
        for log_file in sorted(self.log_dir.glob("events-*.jsonl")):
            with open(log_file) as f:
                for line in f:
                    event = json.loads(line)
                    if event.get("context", {}).get("run_id") == run_id:
                        events.append(event)
        return events

    def get_issue_history(self, issue_id: str) -> List[KernelEvent]:
        """Get all events for an issue across all runs"""
        events = []
        for log_file in sorted(self.log_dir.glob("events-*.jsonl")):
            with open(log_file) as f:
                for line in f:
                    event = json.loads(line)
                    if event.get("context", {}).get("issue_id") == issue_id:
                        events.append(event)
        return events
```

## beads_viewer Integration

### Node Decorations

```yaml
observability:
  beads_viewer:
    node_decorations:
      - field: dk_risk
        color_map:
          low: green
          medium: yellow
          high: orange
          critical: red

      - field: status
        icon_map:
          running: spinner
          blocked: stop
          review: eye
          escalated: warning
```

### Robot Endpoints

The kernel consumes these beads_viewer robot endpoints:

```yaml
robot_endpoints:
  - "--robot-plan" # Get prioritized work plan
  - "--robot-insights" # Get analysis/recommendations
  - "--robot-graph" # Get machine-readable graph
```

### Custom Panels

beads_viewer can display kernel-specific panels:

```yaml
panels:
  - name: "Kernel Status"
    data: /api/kernel/status
    refresh: 5s

  - name: "Active Workcells"
    data: /api/workcells
    refresh: 2s

  - name: "Run History"
    data: /api/runs
    paginated: true

  - name: "Failure Analysis"
    data: /api/failures
    grouped_by: failure_class
```

## CLI Commands

```bash
# Show run history
dev-kernel history
dev-kernel history --run run-20250115-143000
dev-kernel history --issue 42
dev-kernel history --limit 100
dev-kernel history --json

# Show statistics
dev-kernel stats
dev-kernel stats --cost
dev-kernel stats --success-rate
dev-kernel stats --time
```

## Statistics Tracked

### Cost Tracking

```python
@dataclass
class CostStats:
    total_tokens: int
    total_cost_usd: float
    by_toolchain: Dict[str, float]
    by_issue: Dict[str, float]
```

### Success Rates

```python
@dataclass
class SuccessStats:
    total_attempts: int
    successful: int
    failed: int
    by_toolchain: Dict[str, float]  # success rate per toolchain
    by_failure_class: Dict[str, int]  # count per failure type
```

### Timing Analysis

```python
@dataclass
class TimingStats:
    avg_workcell_duration_ms: int
    avg_gate_duration_ms: Dict[str, int]
    p50_duration_ms: int
    p95_duration_ms: int
    p99_duration_ms: int
```

## Configuration

```yaml
# .dev-kernel/config.yaml
observability:
  log_level: "info" # debug, info, warning, error
  event_log_dir: ".dev-kernel/logs"
  archive_dir: ".dev-kernel/archives"

  beads_viewer_integration: true

  retention:
    event_logs_days: 30
    archived_workcells_days: 7

  structured_logging:
    enabled: true
    format: "json" # json or console
```

## Log File Structure

```
.dev-kernel/
├── logs/
│   ├── events-2025-01-15.jsonl
│   ├── events-2025-01-16.jsonl
│   └── kernel.log
└── archives/
    ├── wc-42-20250115T143022Z/
    │   ├── proof.json
    │   ├── manifest.json
    │   └── logs/
    └── wc-43-20250115T144000Z/
```

# Failure Handling & Self-Healing

## Overview

The kernel treats failures as first-class citizens. Every failure creates a traceable record and potentially new issues to fix the problem.

## Failure Classification

```python
class FailureClass(Enum):
    TEST_FAILURE = "test_failure"
    TYPE_ERROR = "type_error"
    LINT_ERROR = "lint_error"
    BUILD_ERROR = "build_error"
    TIMEOUT = "timeout"
    SECURITY_VIOLATION = "security_violation"
    LOW_CONFIDENCE = "low_confidence"
    UNKNOWN = "unknown"
```

### Classification Logic

```python
class FailureClassifier:
    def classify(self, proof: PatchProof) -> FailureClass:
        if proof.status == "timeout":
            return FailureClass.TIMEOUT

        if proof.patch.forbidden_path_violations:
            return FailureClass.SECURITY_VIOLATION

        if not proof.verification.all_passed:
            failing_gates = proof.verification.blocking_failures

            if "test" in failing_gates:
                return FailureClass.TEST_FAILURE
            if "typecheck" in failing_gates:
                return FailureClass.TYPE_ERROR
            if "lint" in failing_gates:
                return FailureClass.LINT_ERROR
            if "build" in failing_gates:
                return FailureClass.BUILD_ERROR

        if proof.confidence < 0.3:
            return FailureClass.LOW_CONFIDENCE

        return FailureClass.UNKNOWN
```

## Automatic Fix Issue Creation

When a workcell fails, the kernel can automatically create a fix issue:

```python
class SelfHealer:
    def create_fix_issue(
        self,
        original_issue: Issue,
        proof: PatchProof,
        failure_class: FailureClass
    ) -> str:
        description = f"""
## Original Issue
{original_issue.title} (#{original_issue.id})

## Failure Type
{failure_class.value}

## Failure Details
```

{proof.verification.blocking_failures}

```

## Agent's Analysis
{proof.risk_factors}

## Files Modified
{proof.patch.files_modified}

## Suggested Fix Approach
{self._suggest_fix(failure_class, proof)}
"""

        # Create fix issue in Beads
        fix_id = bd_create(
            title=f"[FIX] {failure_class.value}: {original_issue.title}",
            description=description,
            priority=self._escalate_priority(original_issue.dk_priority),
            tags=[
                f"@gate:{failure_class.value}",
                f"@attempt:{original_issue.dk_attempts + 1}",
                "@auto-generated"
            ]
        )

        # Add dependency edge
        bd_dep_add(
            from_id=fix_id,
            to_id=original_issue.id,
            type="fix-for"
        )

        # Update original issue
        bd_update(
            issue_id=original_issue.id,
            status="blocked",
            dk_attempts=original_issue.dk_attempts + 1
        )

        return fix_id
```

### Suggested Fixes by Failure Type

```python
def _suggest_fix(self, failure_class: FailureClass, proof: PatchProof) -> str:
    suggestions = {
        FailureClass.TEST_FAILURE:
            "Review failing tests. Consider: missing assertions, async timing issues, mock setup.",
        FailureClass.TYPE_ERROR:
            "Check type definitions. Common issues: missing return types, incorrect generics, any escapes.",
        FailureClass.LINT_ERROR:
            "Run linter locally and auto-fix. May need manual formatting or rule exceptions.",
        FailureClass.BUILD_ERROR:
            "Check imports and exports. Verify all dependencies are installed.",
        FailureClass.TIMEOUT:
            "Task may be too large. Consider breaking into smaller subtasks.",
        FailureClass.LOW_CONFIDENCE:
            "Agent was uncertain. May need clearer requirements or context.",
    }
    return suggestions.get(failure_class, "Manual investigation required.")
```

## Retry Policies

```yaml
retry_policies:
  default:
    max_attempts: 3
    backoff_base_seconds: 60
    backoff_multiplier: 2
    max_backoff_seconds: 3600

  by_failure_class:
    test_failure:
      max_attempts: 3
      same_toolchain: true # Retry with same tool

    type_error:
      max_attempts: 2
      same_toolchain: true

    timeout:
      max_attempts: 2
      increase_timeout: 1.5 # 50% more time
      try_different_toolchain: true

    security_violation:
      max_attempts: 1 # Don't retry
      escalate_immediately: true

    low_confidence:
      max_attempts: 2
      try_different_toolchain: true
      add_context: true # Provide more context
```

### Backoff Calculation

```python
def calculate_backoff(attempt: int, config: RetryConfig) -> int:
    """Exponential backoff with cap"""
    backoff = config.backoff_base_seconds * (config.backoff_multiplier ** (attempt - 1))
    return min(backoff, config.max_backoff_seconds)
```

## Escalation Logic

### When to Escalate

```python
class EscalationManager:
    def should_escalate(self, issue: Issue, history: List[PatchProof]) -> bool:
        # Exceeded max attempts
        if issue.dk_attempts >= issue.dk_max_attempts:
            return True

        # Security violation
        if any(p.patch.forbidden_path_violations for p in history):
            return True

        # Repeated same failure
        recent_failures = [p for p in history[-3:] if p.status != "success"]
        if len(recent_failures) >= 3:
            failure_types = [self._classify(p) for p in recent_failures]
            if len(set(failure_types)) == 1:
                return True  # Same failure 3x in a row

        # Critical path blocked too long
        if issue.on_critical_path and issue.dk_attempts >= 2:
            return True

        return False
```

### Escalation Actions

```python
def escalate(self, issue: Issue, reason: str):
    # Update issue status
    bd_update(
        issue_id=issue.id,
        status="escalated",
        tags=issue.tags + ["@human-escalated"]
    )

    # Log escalation event
    self._log_event({
        "type": "escalation",
        "issue_id": issue.id,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
        "attempts": issue.dk_attempts
    })

    # Send notification (if configured)
    if self.config.notification_webhook:
        self._send_notification(issue, reason)
```

## Failure Flow Diagram

```
Workcell completes
        │
        ▼
    ┌───────────┐
    │  Success? │
    └───────────┘
        │
   Yes  │   No
   ─────┴───────
   │            │
   ▼            ▼
┌──────┐   ┌────────────┐
│ Done │   │  Classify  │
└──────┘   │  Failure   │
           └────────────┘
                 │
                 ▼
           ┌───────────┐
           │ Security  │───Yes──► Escalate immediately
           │ Violation?│
           └───────────┘
                 │ No
                 ▼
           ┌───────────┐
           │ Attempts  │───Yes──► Escalate (max attempts)
           │ Exceeded? │
           └───────────┘
                 │ No
                 ▼
           ┌───────────┐
           │  Create   │
           │ Fix Issue │
           └───────────┘
                 │
                 ▼
           ┌───────────┐
           │  Schedule │
           │   Retry   │
           └───────────┘
```

## Configuration

```yaml
# .dev-kernel/config.yaml
failure_handling:
  auto_create_fix_issues: true
  escalation:
    max_attempts: 3
    notify_webhook: "https://..."

  retry:
    default_max_attempts: 3
    backoff_base_seconds: 60
    backoff_multiplier: 2

  self_healing:
    try_different_toolchain_on_failure: true
    add_context_on_low_confidence: true
```

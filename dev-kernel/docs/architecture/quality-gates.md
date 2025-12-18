# Quality Gates & Verification

## Overview

Quality gates are mandatory verification steps that must pass before a workcell's patch can be merged. The kernel runs these automatically and records results in the Patch+Proof artifact.

## Gate Types

### Required Gates (Blocking)

These must pass for a patch to be considered valid:

| Gate | Purpose | Typical Command |
|------|---------|-----------------|
| test | Unit/integration tests | `npm test` |
| typecheck | Static type checking | `npm run typecheck` |
| lint | Code style/quality | `npm run lint` |
| build | Compilation/bundling | `npm run build` |

### Optional Gates (Informational)

These provide useful signals but don't block merging:

| Gate | Purpose | Typical Command |
|------|---------|-----------------|
| coverage | Test coverage threshold | `npm run test:coverage` |
| security | Dependency vulnerabilities | `npm audit` |
| bundle-size | Output size check | `npm run analyze:bundle` |

### Custom Gates

Special gates that inspect the diff itself:

| Gate | Purpose |
|------|---------|
| forbidden-paths | Ensure certain paths aren't modified |
| max-diff-size | Limit patch size |
| secret-detection | Check for leaked secrets |

## Configuration

```yaml
# .dev-kernel/config.yaml
quality_gates:
  required:
    - name: test
      command: "npm test"
      timeout: 300        # seconds
      retries: 2          # automatic retries on failure

    - name: typecheck
      command: "npm run typecheck"
      timeout: 120
      retries: 1

    - name: lint
      command: "npm run lint"
      timeout: 60
      retries: 1

    - name: build
      command: "npm run build"
      timeout: 180
      retries: 1

  optional:
    - name: coverage
      command: "npm run test:coverage"
      threshold: 80       # minimum coverage %

    - name: security
      command: "npm audit --audit-level=high"

    - name: bundle-size
      command: "npm run analyze:bundle"
      threshold_kb: 500

  custom:
    - name: forbidden-paths
      type: diff-check
      forbidden:
        - "*.env*"
        - "**/secrets/**"
        - "**/migrations/**"

    - name: max-diff-size
      type: diff-check
      max_lines: 500
      max_files: 20
```

## Gate Execution

### Execution Order

1. Custom diff-check gates (fast, no execution)
2. Build gate (ensures code compiles)
3. Lint gate (fast feedback)
4. Typecheck gate (catches type errors)
5. Test gate (slowest, most important)
6. Optional gates (parallel)

### Deterministic Re-run Rules

```python
def should_rerun_gate(gate: Gate, result: GateResult, history: List[GateResult]) -> bool:
    """Decide whether to re-run a gate based on history and flakiness"""
    
    # Never re-run on success
    if result.passed:
        return False

    # Check flakiness history
    recent_runs = [r for r in history if r.gate == gate.name][-10:]
    flaky_score = sum(1 for r in recent_runs if r.flaky_detected) / max(len(recent_runs), 1)

    # High flakiness + explicit retry config
    if flaky_score > 0.3 and gate.retries > 0:
        return result.attempt < gate.retries

    # Transient error patterns
    transient_patterns = [
        "ECONNRESET",
        "ETIMEDOUT",
        "rate limit",
        "503",
        "socket hang up"
    ]

    if any(p in result.stderr for p in transient_patterns):
        return result.attempt < gate.retries

    return False
```

## Flaky Test Handling

### Detection

Tests are marked flaky when they have both passed and failed on the same commit:

```python
class FlakyTestDetector:
    def get_flaky_tests(self, window_days: int = 7) -> List[str]:
        """Tests that have both passed and failed on same commit"""
        cursor = self.db.execute("""
            SELECT test_name
            FROM test_results
            WHERE timestamp > datetime('now', ?)
            GROUP BY test_name, commit
            HAVING COUNT(DISTINCT passed) > 1
        """, (f'-{window_days} days',))
        return [row[0] for row in cursor.fetchall()]
```

### Handling Strategies

1. **Retry**: Re-run the test up to N times
2. **Quarantine**: Allow known flaky tests to pass with warning
3. **Track**: Create Beads issue to fix the flaky test
4. **Alert**: Notify humans when flakiness exceeds threshold

### CLI Commands

```bash
# List known flaky tests
dev-kernel flaky-tests list

# Ignore a specific flaky test
dev-kernel flaky-tests ignore "test_name"

# Clear flaky test data
dev-kernel flaky-tests clear
```

## Diff-Check Gates

### Forbidden Paths

Prevents modification of sensitive paths:

```python
def check_forbidden_paths(diff: str, forbidden: List[str]) -> List[str]:
    violations = []
    modified_files = parse_diff_files(diff)
    
    for file in modified_files:
        for pattern in forbidden:
            if fnmatch(file, pattern):
                violations.append(f"Modified forbidden path: {file}")
    
    return violations
```

### Max Diff Size

Limits patch complexity:

```python
def check_diff_size(diff: str, max_lines: int, max_files: int) -> List[str]:
    violations = []
    stats = parse_diff_stats(diff)
    
    if stats['lines'] > max_lines:
        violations.append(f"Diff too large: {stats['lines']} > {max_lines} lines")
    
    if stats['files'] > max_files:
        violations.append(f"Too many files: {stats['files']} > {max_files}")
    
    return violations
```

## Gate Result Schema

```json
{
  "gate": "test",
  "passed": true,
  "exit_code": 0,
  "duration_ms": 4523,
  "attempt": 1,
  "output_path": ".workcells/wc-42-xxx/logs/test.log",
  "failure_summary": null,
  "flaky_detected": false
}
```

## Verification Workflow

```
1. Workcell completes execution
   │
   ├─► Run forbidden-paths check
   │   └─► If violations: FAIL immediately
   │
   ├─► Run max-diff-size check
   │   └─► If violations: FAIL immediately
   │
   ├─► Run secret-detection
   │   └─► If violations: FAIL + escalate
   │
   ├─► Run build gate
   │   └─► If fails: retry up to N times
   │
   ├─► Run lint gate
   │   └─► If fails: retry up to N times
   │
   ├─► Run typecheck gate
   │   └─► If fails: retry up to N times
   │
   ├─► Run test gate
   │   ├─► If fails: check flakiness
   │   │   ├─► Known flaky: warn + pass
   │   │   └─► Not flaky: retry up to N times
   │   └─► If still fails: record failure
   │
   ├─► Run optional gates (parallel)
   │
   └─► Aggregate results into proof.json
```


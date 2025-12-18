# Security & Safety

## Overview

The Dev Kernel assumes agents can be wrong, malicious, or buggy. Multiple layers of defense ensure safety.

## Principles

1. **Defense in depth**: Multiple verification layers
2. **Least privilege**: Workcells have minimal access
3. **Blast radius containment**: Git worktrees isolate damage
4. **Audit everything**: Full trail of all actions
5. **Fail closed**: Uncertain situations block, don't proceed

## Sandboxing Strategy

### File System Isolation

```yaml
security:
  sandboxing:
    workcell_allowed_paths:
      - "${WORKCELL_PATH}/**" # Own worktree
      - "${HOME}/.cache/**" # Shared cache (read-only)

    workcell_denied_paths:
      - "${REPO_ROOT}/.git/**" # No direct git manipulation
      - "${REPO_ROOT}/.beads/**" # Kernel owns beads
      - "${HOME}/.ssh/**"
      - "${HOME}/.aws/**"
      - "${HOME}/.gnupg/**"
      - "/etc/**"
      - "/var/**"
```

### Network Isolation

```yaml
network:
  allowed_hosts:
    - "api.openai.com"
    - "api.anthropic.com"
    - "registry.npmjs.org"
    - "pypi.org"
  denied_hosts:
    - "*" # Default deny
```

### Process Isolation

```yaml
process:
  max_cpu_percent: 80
  max_memory_mb: 4096
  max_processes: 50
  max_open_files: 1000
```

## Secret Handling

### Secret Detection Patterns

```python
class SecretSanitizer:
    PATTERNS = [
        r'(?i)(api[_-]?key|apikey)["\s:=]+["\']?([a-zA-Z0-9_-]{20,})',
        r'(?i)(secret|password|token)["\s:=]+["\']?([a-zA-Z0-9_-]{8,})',
        r'(?i)(aws[_-]?access|aws[_-]?secret)["\s:=]+["\']?([A-Z0-9]{16,})',
        r'-----BEGIN [A-Z]+ PRIVATE KEY-----',
    ]
```

### Sanitization Functions

```python
def sanitize_manifest(self, manifest: dict) -> dict:
    """Remove any secrets from task manifest"""
    return self._recursive_sanitize(manifest)

def sanitize_logs(self, log_content: str) -> str:
    """Redact secrets from log output"""
    for pattern in self.PATTERNS:
        log_content = re.sub(pattern, r'\1=[REDACTED]', log_content)
    return log_content

def check_diff(self, diff: str) -> List[str]:
    """Check if diff contains secrets"""
    violations = []
    for pattern in self.PATTERNS:
        matches = re.findall(pattern, diff)
        if matches:
            violations.append(f"Potential secret in diff: {pattern}")
    return violations
```

## Git Worktree Isolation

### Workcell Creation

```python
class WorkcellIsolation:
    def create_workcell(self, issue_id: str) -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        workcell_name = f"wc-{issue_id}-{timestamp}"
        branch_name = f"wc/{issue_id}/{timestamp}"
        workcell_path = self.workcells_dir / workcell_name

        # Create isolated worktree from main
        subprocess.run([
            "git", "worktree", "add",
            str(workcell_path),
            "-b", branch_name,
            "main"  # Always branch from main
        ], check=True)

        # Remove .beads from workcell (kernel owns it)
        shutil.rmtree(workcell_path / ".beads", ignore_errors=True)

        # Create isolation marker
        (workcell_path / ".workcell").write_text(json.dumps({
            "id": workcell_name,
            "issue_id": issue_id,
            "created": timestamp,
            "parent_commit": self._get_main_head()
        }))

        return workcell_path
```

### Workcell Cleanup

```python
def cleanup_workcell(self, workcell_path: Path, keep_logs: bool = True):
    """Safely remove workcell"""
    workcell_name = workcell_path.name

    # Archive logs if requested
    if keep_logs:
        archive_path = self.archives_dir / workcell_name
        archive_path.mkdir(parents=True, exist_ok=True)
        for log_file in (workcell_path / "logs").glob("*"):
            shutil.copy(log_file, archive_path)

    # Remove worktree
    subprocess.run([
        "git", "worktree", "remove", "--force",
        str(workcell_path)
    ], check=True)

    # Delete branch
    branch_name = self._get_branch_for_workcell(workcell_name)
    subprocess.run([
        "git", "branch", "-D", branch_name
    ], check=False)  # OK if already deleted
```

## Repository Corruption Prevention

### Forbidden Commands

```python
class RepoGuard:
    FORBIDDEN_COMMANDS = [
        r"git\s+push\s+.*--force",
        r"git\s+reset\s+--hard",
        r"git\s+clean\s+-fd",
        r"rm\s+-rf\s+\.git",
        r"git\s+rebase",  # In automated context
    ]

    def validate_command(self, cmd: str) -> bool:
        for pattern in self.FORBIDDEN_COMMANDS:
            if re.search(pattern, cmd):
                raise SecurityViolation(f"Forbidden command: {cmd}")
        return True
```

### Forbidden Files

```python
FORBIDDEN_FILES = [
    ".git/config",
    ".git/HEAD",
    ".git/index",
    ".beads/issues.jsonl",  # Kernel-only
]
```

### Pre-Merge Checks

```python
def pre_merge_checks(self, branch: str) -> bool:
    """Final checks before merging workcell branch"""

    # Verify branch is ahead of main (not diverged)
    result = subprocess.run([
        "git", "merge-base", "--is-ancestor", "main", branch
    ])
    if result.returncode != 0:
        raise MergeError(f"Branch {branch} has diverged from main")

    # Verify no merge conflicts
    result = subprocess.run([
        "git", "merge", "--no-commit", "--no-ff", branch
    ], capture_output=True)
    subprocess.run(["git", "merge", "--abort"], capture_output=True)

    if result.returncode != 0:
        raise MergeError(f"Branch {branch} has conflicts with main")

    return True
```

## Diff Validation

```python
def validate_diff(self, diff: str, manifest: TaskManifest) -> List[str]:
    violations = []

    # Check forbidden paths
    for forbidden in self.FORBIDDEN_FILES + manifest.forbidden_paths:
        if forbidden in diff:
            violations.append(f"Modified forbidden path: {forbidden}")

    # Check diff size
    stats = self._parse_diff_stats(diff)
    if stats['lines'] > manifest.max_diff_lines:
        violations.append(
            f"Diff too large: {stats['lines']} > {manifest.max_diff_lines}"
        )

    return violations
```

## Security Configuration

```yaml
# .dev-kernel/config.yaml
security:
  forbidden_paths:
    - ".env*"
    - "**/secrets/**"
    - ".git/**"
    - ".beads/**"
    - "**/migrations/**"

  max_diff_lines: 500
  max_diff_files: 20

  secret_detection:
    enabled: true
    escalate_on_detection: true

  command_validation:
    enabled: true
    log_all_commands: true
```

## Escalation on Security Violations

Security violations trigger immediate escalation:

1. Issue marked as `escalated`
2. Workcell preserved for forensics
3. Human notification sent
4. No retry attempts

```python
if proof.patch.forbidden_path_violations:
    return FailureClass.SECURITY_VIOLATION
    # -> escalate_immediately: true
    # -> max_attempts: 1
```

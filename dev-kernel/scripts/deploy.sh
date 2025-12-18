#!/usr/bin/env bash
#
# Deploy Dev Kernel to a target project
#
# Usage: ./scripts/deploy.sh /path/to/target/project
#

set -e

TARGET_DIR="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KERNEL_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Deploying Dev Kernel to: $TARGET_DIR"

# Check if target is a git repo
if [ ! -d "$TARGET_DIR/.git" ]; then
    echo "❌ Error: $TARGET_DIR is not a git repository"
    exit 1
fi

# Create .dev-kernel directory
mkdir -p "$TARGET_DIR/.dev-kernel"
mkdir -p "$TARGET_DIR/.dev-kernel/logs"

# Copy example config if none exists
if [ ! -f "$TARGET_DIR/.dev-kernel/config.yaml" ]; then
    echo "📝 Creating default config..."
    cat > "$TARGET_DIR/.dev-kernel/config.yaml" << 'EOF'
# Dev Kernel Configuration
# See docs for all options: https://github.com/your-org/dev-kernel

max_concurrent_workcells: 2
max_concurrent_tokens: 150000
starvation_threshold_hours: 4.0

# Toolchain priority (first available is used)
toolchain_priority:
  - codex
  - claude
  - crush

# Toolchain-specific config
toolchains:
  codex:
    enabled: true
    timeout_seconds: 1800
    model: o3
  claude:
    enabled: true
    timeout_seconds: 1800
    model: claude-sonnet-4-20250514
  crush:
    enabled: true
    timeout_seconds: 1800
    provider: anthropic

# Quality gates
gates:
  test_command: "pytest"
  typecheck_command: "mypy ."
  lint_command: "ruff check ."
  timeout_seconds: 300

# Speculate+vote mode
speculation:
  enabled: true
  default_parallelism: 2
  vote_threshold: 0.7
  auto_trigger_on_critical_path: true
  auto_trigger_risk_levels:
    - high
    - critical
EOF
    echo "✅ Config created at: $TARGET_DIR/.dev-kernel/config.yaml"
else
    echo "ℹ️  Config already exists, skipping"
fi

# Check for .beads directory
if [ ! -d "$TARGET_DIR/.beads" ]; then
    echo ""
    echo "⚠️  No .beads directory found!"
    echo "   Dev Kernel requires Beads for issue tracking."
    echo ""
    echo "   To initialize Beads:"
    echo "     cd $TARGET_DIR && bd init"
    echo ""
    echo "   Or create manually:"
    echo "     mkdir -p $TARGET_DIR/.beads"
    echo "     touch $TARGET_DIR/.beads/issues.jsonl"
    echo "     touch $TARGET_DIR/.beads/deps.jsonl"
fi

# Add to .gitignore if not already there
if [ -f "$TARGET_DIR/.gitignore" ]; then
    if ! grep -q ".dev-kernel/logs" "$TARGET_DIR/.gitignore" 2>/dev/null; then
        echo "" >> "$TARGET_DIR/.gitignore"
        echo "# Dev Kernel" >> "$TARGET_DIR/.gitignore"
        echo ".dev-kernel/logs/" >> "$TARGET_DIR/.gitignore"
        echo ".workcells/" >> "$TARGET_DIR/.gitignore"
        echo "✅ Added Dev Kernel ignores to .gitignore"
    fi
fi

echo ""
echo "✨ Dev Kernel deployed successfully!"
echo ""
echo "Next steps:"
echo "  1. Review config: $TARGET_DIR/.dev-kernel/config.yaml"
echo "  2. Ensure Beads is set up: $TARGET_DIR/.beads/"
echo "  3. Run kernel: cd $TARGET_DIR && dev-kernel run --dry-run"
echo ""


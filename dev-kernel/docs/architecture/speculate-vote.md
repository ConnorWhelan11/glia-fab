# Speculate + Vote

## Overview

For high-risk tasks, the kernel can spawn multiple workcells with different toolchains to produce competing implementations. A voting algorithm then selects the best candidate.

## When to Speculate

Speculate mode is triggered when:

1. Issue has `dk_speculate: true` explicitly set
2. Issue is on critical path AND has `dk_risk >= 'high'`
3. Config has `force_speculate` enabled
4. There is spare capacity (at least 2 extra workcell slots)

```python
def should_speculate(issue: Issue, config: KernelConfig) -> bool:
    return (
        issue.dk_speculate or
        (issue.dk_risk in ('high', 'critical') and
         issue in compute_critical_path(graph)) or
        config.force_speculate
    )
```

## Dispatching Multiple Workcells

```python
def dispatch_speculate(issue: Issue, config: KernelConfig) -> List[Workcell]:
    """Spawn multiple workcells for same task with different toolchains"""
    toolchains = ['codex', 'claude', 'opencode']
    workcells = []

    for i, tool in enumerate(toolchains[:config.speculate_parallelism]):
        wc = create_workcell(
            issue=issue,
            toolchain=tool,
            speculate_tag=f"speculate:{['primary', 'alt1', 'alt2'][i]}"
        )
        workcells.append(wc)

    return workcells
```

## Voting Algorithm

The selection algorithm scores candidates across 5 dimensions:

| Dimension    | Weight | Scoring                               |
| ------------ | ------ | ------------------------------------- |
| Verification | 40%    | Binary: all gates pass = 40, else 0   |
| Confidence   | 20%    | Linear: confidence × 20               |
| Diff Size    | 15%    | Smaller is better (normalized)        |
| Risk         | 15%    | low=15, medium=10, high=5, critical=0 |
| Review       | 10%    | approve=10, abstain=5, changes=0      |

### Selection Logic

```python
def select_winner(
    candidates: List[PatchProof],
    config: VoteConfig
) -> Optional[PatchProof]:
    """Select winning candidate from speculate mode"""

    def score(proof: PatchProof) -> float:
        s = 0.0

        # Verification: binary 0 or 40
        if proof.verification.all_passed:
            s += 40
        else:
            return 0  # Immediate disqualification

        # Confidence: 0-20
        s += proof.confidence * 20

        # Diff size: 15 for smallest, scaled down
        max_lines = max(
            p.patch.diff_stats['insertions'] + p.patch.diff_stats['deletions']
            for p in candidates
        )
        this_lines = (
            proof.patch.diff_stats['insertions'] +
            proof.patch.diff_stats['deletions']
        )
        s += (1 - this_lines / max(max_lines, 1)) * 15

        # Risk: 15 for low, 10 for medium, 5 for high, 0 for critical
        risk_scores = {'low': 15, 'medium': 10, 'high': 5, 'critical': 0}
        s += risk_scores.get(proof.risk_classification, 5)

        # Review verdict: 10 for approve, 5 for abstain, 0 for changes
        if proof.review:
            review_scores = {'approve': 10, 'abstain': 5, 'request_changes': 0}
            s += review_scores.get(proof.review.verdict, 5)

        return s

    # Score all candidates
    scored = [(score(p), p) for p in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)

    # Check if winner meets threshold
    if scored and scored[0][0] >= config.vote_threshold * 100:
        return scored[0][1]

    return None  # No clear winner, escalate
```

## Automatic Rejection Triggers

A candidate is automatically rejected if:

- Any required gate fails
- Forbidden paths are modified
- Diff exceeds size limits
- Confidence below minimum threshold
- Security violations detected

```python
def auto_reject(proof: PatchProof, config: VoteConfig) -> bool:
    if not proof.verification.all_passed:
        return True
    if proof.patch.forbidden_path_violations:
        return True
    if proof.patch.diff_stats['insertions'] + proof.patch.diff_stats['deletions'] > config.max_diff_lines:
        return True
    if proof.confidence < config.min_confidence:
        return True
    return False
```

## Adversarial Review

In speculate mode, each workcell can also review other candidates:

```python
def run_adversarial_review(
    candidates: List[PatchProof],
    config: VoteConfig
) -> List[PatchProof]:
    """Have each candidate review the others"""
    for candidate in candidates:
        other_candidates = [c for c in candidates if c != candidate]
        for other in other_candidates:
            review = spawn_review_workcell(
                reviewer_toolchain=candidate.metadata.toolchain,
                target_proof=other
            )
            other.reviews.append(review)
    return candidates
```

## Configuration

```yaml
speculation:
  enabled: true
  default_parallelism: 2 # How many parallel implementations
  max_parallelism: 3
  vote_threshold: 0.7 # Minimum score to auto-select (70/100)

  auto_trigger:
    on_critical_path: true
    risk_levels: ["high", "critical"]

  adversarial_review:
    enabled: false # Enable cross-review
    required_approvals: 1

  rejection:
    min_confidence: 0.3
    max_diff_lines: 500
```

## Flow Diagram

```
Issue marked for speculation
            │
            ▼
    ┌───────────────┐
    │ Dispatch N    │
    │ workcells     │
    └───────────────┘
            │
    ┌───────┼───────┐
    ▼       ▼       ▼
┌──────┐ ┌──────┐ ┌──────┐
│Codex │ │Claude│ │Open  │
│      │ │      │ │Code  │
└──────┘ └──────┘ └──────┘
    │       │       │
    └───────┼───────┘
            ▼
    ┌───────────────┐
    │ Collect       │
    │ Patch+Proofs  │
    └───────────────┘
            │
            ▼
    ┌───────────────┐
    │ Auto-reject   │
    │ invalid       │
    └───────────────┘
            │
            ▼
    ┌───────────────┐
    │ Score         │
    │ candidates    │
    └───────────────┘
            │
            ▼
    ┌───────────────┐
    │ Above         │
    │ threshold?    │
    └───────────────┘
       │         │
      Yes        No
       │         │
       ▼         ▼
  ┌────────┐  ┌──────────┐
  │ Select │  │ Escalate │
  │ winner │  │ to human │
  └────────┘  └──────────┘
```

## Tagging Speculate Candidates

Issues involved in speculation are tagged:

```
@speculate:primary   # First candidate
@speculate:alt1      # Second candidate
@speculate:alt2      # Third candidate
@speculate:winner    # Selected winner
@speculate:rejected  # Not selected
```

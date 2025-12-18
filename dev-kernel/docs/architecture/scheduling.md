# Scheduling Algorithm

## Overview

The scheduler is responsible for:
1. Computing which issues are ready to work on
2. Finding the critical path through the dependency graph
3. Packing ready issues into parallel execution lanes
4. Triggering speculate+vote mode for high-risk tasks
5. Preventing starvation of long-waiting tasks

## Ready Set Computation

An issue is ready if:
1. Status is `open` or `ready`
2. All blocking dependencies have status `done`
3. Not currently running in any workcell
4. Attempts < max_attempts

```python
def compute_ready_set(graph: BeadsGraph) -> List[Issue]:
    ready = []
    running_ids = get_running_workcell_tasks()

    for issue in graph.issues:
        if issue.status not in ('open', 'ready'):
            continue
        if issue.id in running_ids:
            continue
        if issue.dk_attempts >= issue.dk_max_attempts:
            continue

        blockers = graph.get_blocking_deps(issue.id)
        if all(b.status == 'done' for b in blockers):
            ready.append(issue)

    return ready
```

## Critical Path Computation

The critical path is the longest chain through the dependency graph, weighted by estimated effort.

```python
def compute_critical_path(graph: BeadsGraph) -> List[Issue]:
    """
    Critical path = longest chain through the dependency graph
    weighted by estimated effort (dk_size → hours mapping)

    Uses topological sort + dynamic programming
    """
    SIZE_TO_HOURS = {'XS': 1, 'S': 2, 'M': 4, 'L': 8, 'XL': 16}

    # Build adjacency list (A blocks B means edge A→B)
    adj = defaultdict(list)
    in_degree = defaultdict(int)

    for issue in graph.issues:
        for dep in graph.get_deps(issue.id, type='blocks'):
            adj[dep.id].append(issue.id)
            in_degree[issue.id] += 1

    # Topological sort
    queue = deque([i for i in graph.issues if in_degree[i.id] == 0])
    topo_order = []
    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for neighbor_id in adj[node.id]:
            in_degree[neighbor_id] -= 1
            if in_degree[neighbor_id] == 0:
                queue.append(graph.get_issue(neighbor_id))

    # DP: longest path ending at each node
    dist = {i.id: SIZE_TO_HOURS.get(i.dk_size, 4) for i in graph.issues}
    parent = {i.id: None for i in graph.issues}

    for node in topo_order:
        for neighbor_id in adj[node.id]:
            new_dist = dist[node.id] + SIZE_TO_HOURS.get(
                graph.get_issue(neighbor_id).dk_size, 4
            )
            if new_dist > dist[neighbor_id]:
                dist[neighbor_id] = new_dist
                parent[neighbor_id] = node.id

    # Backtrack from max
    end_id = max(dist, key=dist.get)
    path = []
    while end_id:
        path.append(graph.get_issue(end_id))
        end_id = parent[end_id]

    return list(reversed(path))
```

### Critical Path Example

Given this dependency graph:

```
#1 [M] ──blocks──► #2 [S] ──blocks──► #5 [S]
                       │
                       └──blocks──► #6 [XS]

#3 [L] ──blocks──► #4 [M]

#7 [S] (no deps)
```

Size mapping: XS=1h, S=2h, M=4h, L=8h, XL=16h

**Critical paths:**
- Path A: #1(4h) → #2(2h) → #5(2h) = 8h
- Path B: #1(4h) → #2(2h) → #6(1h) = 7h
- Path C: #3(8h) → #4(4h) = 12h ← **Critical path**
- Path D: #7(2h) = 2h

**Scheduling decision:**
1. #3 and #1 and #7 are all ready (no blockers)
2. #3 is on critical path → highest priority
3. #1 unblocks most downstream → second priority
4. #7 is independent → can run in parallel if capacity

## Lane Packing Algorithm

```python
def pack_lanes(
    ready_set: List[Issue],
    critical_path: List[Issue],
    config: KernelConfig
) -> List[List[Issue]]:
    """
    Pack ready issues into parallel lanes respecting:
    - max_concurrent_workcells
    - max_concurrent_llm_calls (token budget)
    - Critical path priority (always include CP items first)
    """
    lanes = []
    remaining_slots = config.max_concurrent_workcells
    remaining_tokens = config.max_concurrent_tokens

    # Priority 1: Critical path items that are ready
    cp_ready = [i for i in critical_path if i in ready_set]

    # Priority 2: High priority items
    high_pri = sorted(
        [i for i in ready_set if i not in cp_ready],
        key=lambda x: (x.dk_priority, -x.dk_risk_score)
    )

    # Pack into lanes
    for issue in cp_ready + high_pri:
        est_tokens = issue.dk_estimated_tokens or 50000

        if remaining_slots > 0 and remaining_tokens >= est_tokens:
            lanes.append(issue)
            remaining_slots -= 1
            remaining_tokens -= est_tokens

            # If speculate mode, reserve additional slots
            if issue.dk_speculate:
                speculate_count = min(2, remaining_slots)
                for _ in range(speculate_count):
                    if remaining_slots > 0 and remaining_tokens >= est_tokens:
                        remaining_slots -= 1
                        remaining_tokens -= est_tokens

    return lanes
```

## Speculate + Vote Triggering

```python
def should_speculate(issue: Issue, config: KernelConfig) -> bool:
    """
    Speculate mode is triggered when:
    1. Issue has dk_speculate: true
    2. Issue is on critical path AND has dk_risk >= 'high'
    3. Config has force_speculate enabled
    4. We have spare capacity (at least 2 extra slots)
    """
    return (
        issue.dk_speculate or
        (issue.dk_risk in ('high', 'critical') and
         issue in compute_critical_path(graph)) or
        config.force_speculate
    )

def dispatch_speculate(issue: Issue, config: KernelConfig) -> List[Workcell]:
    """
    Spawn multiple workcells for same task with different toolchains
    """
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

## Starvation Prevention

```python
def prevent_starvation(ready_set: List[Issue], history: RunHistory) -> List[Issue]:
    """
    Boost priority of issues that have been ready but unscheduled for too long
    """
    now = datetime.utcnow()

    for issue in ready_set:
        ready_since = history.get_ready_timestamp(issue.id)
        if ready_since:
            wait_hours = (now - ready_since).total_seconds() / 3600

            # After 4 hours waiting, boost priority
            if wait_hours > 4:
                issue.dk_priority = max('P0', chr(ord(issue.dk_priority[1]) - 1))

            # After 24 hours, force to front
            if wait_hours > 24:
                issue.dk_priority = 'P0'
                issue.dk_starved = True

    return sorted(ready_set, key=lambda x: (x.dk_priority, x.dk_starved))
```

## Configuration Options

```yaml
scheduling:
  max_concurrent_workcells: 4      # Max parallel workcells
  max_concurrent_tokens: 500000    # Token budget across all concurrent calls
  scheduling_interval_seconds: 30  # How often to re-evaluate ready set
  starvation_threshold_hours: 4    # When to start boosting priority
  
speculation:
  enabled: true
  default_parallelism: 2           # How many parallel implementations
  max_parallelism: 3
  auto_trigger_on_critical_path: true
  auto_trigger_risk_levels: ["high", "critical"]
```


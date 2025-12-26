import { useCallback } from "react";
import type { WorldBuildStatus } from "@/types";

type StatusTransitionMap = Record<WorldBuildStatus, Set<WorldBuildStatus>>;

const TERMINAL_STATUSES = new Set<WorldBuildStatus>(["complete", "failed"]);

const ALLOWED_TRANSITIONS: StatusTransitionMap = {
  queued: new Set([
    "queued",
    "scheduling",
    "generating",
    "rendering",
    "critiquing",
    "repairing",
    "exporting",
    "voting",
    "complete",
    "failed",
    "paused",
  ]),
  scheduling: new Set([
    "scheduling",
    "generating",
    "rendering",
    "critiquing",
    "repairing",
    "exporting",
    "voting",
    "complete",
    "failed",
    "paused",
  ]),
  generating: new Set([
    "generating",
    "rendering",
    "critiquing",
    "repairing",
    "exporting",
    "voting",
    "complete",
    "failed",
    "paused",
  ]),
  rendering: new Set([
    "rendering",
    "critiquing",
    "repairing",
    "exporting",
    "voting",
    "complete",
    "failed",
    "paused",
  ]),
  critiquing: new Set([
    "critiquing",
    "repairing",
    "exporting",
    "voting",
    "complete",
    "failed",
    "paused",
  ]),
  repairing: new Set([
    "repairing",
    "critiquing",
    "exporting",
    "voting",
    "complete",
    "failed",
    "paused",
  ]),
  exporting: new Set([
    "exporting",
    "voting",
    "complete",
    "failed",
    "paused",
  ]),
  voting: new Set([
    "voting",
    "complete",
    "failed",
    "paused",
  ]),
  complete: new Set(["complete", "queued"]),
  failed: new Set(["failed", "queued"]),
  paused: new Set(["paused", "queued", "complete", "failed"]),
};

function eventToBuildStatus(eventType: string): WorldBuildStatus | null {
  const mapping: Record<string, WorldBuildStatus> = {
    "schedule.computed": "scheduling",
    "workcell.created": "generating",
    "fab.stage.generate": "generating",
    "fab.stage.render": "rendering",
    "fab.stage.critics": "critiquing",
    "fab.stage.repair": "repairing",
    "fab.stage.godot": "exporting",
    "speculate.voting": "voting",
    "issue.completed": "complete",
    "issue.failed": "failed",
  };
  return mapping[eventType] ?? null;
}

export function useBuildStateMachine() {
  const transitionStatus = useCallback(
    (current: WorldBuildStatus, next: WorldBuildStatus): WorldBuildStatus => {
      if (current === next) return current;
      if (TERMINAL_STATUSES.has(current)) return current;
      if (current === "paused" && next !== "queued") {
        if (next === "failed" || next === "complete") {
          return next;
        }
        return current;
      }
      const allowed = ALLOWED_TRANSITIONS[current];
      if (!allowed || !allowed.has(next)) return current;
      return next;
    },
    []
  );

  const statusForEvent = useCallback((eventType: string): WorldBuildStatus | null => {
    return eventToBuildStatus(eventType);
  }, []);

  const applyKernelEvent = useCallback(
    (current: WorldBuildStatus, eventType: string): WorldBuildStatus => {
      const next = eventToBuildStatus(eventType);
      if (!next) return current;
      return transitionStatus(current, next);
    },
    [transitionStatus]
  );

  return {
    applyKernelEvent,
    statusForEvent,
    transitionStatus,
  };
}

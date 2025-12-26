/**
 * usePlaytestStateMachine - FSM for playtest status transitions
 *
 * Mirrors useBuildStateMachine pattern for playtest lifecycle.
 */

import { useCallback } from "react";

export type PlaytestStatus = "idle" | "running" | "passed" | "failed";

type StatusTransitionMap = Record<PlaytestStatus, Set<PlaytestStatus>>;

const TERMINAL_STATUSES = new Set<PlaytestStatus>(["passed", "failed"]);

const ALLOWED_TRANSITIONS: StatusTransitionMap = {
  idle: new Set(["idle", "running", "passed", "failed"]),
  running: new Set(["running", "passed", "failed"]),
  passed: new Set(["passed", "idle"]), // Can reset to idle for re-run
  failed: new Set(["failed", "idle"]), // Can reset to idle for retry
};

type PlaytestEventType =
  | "playtest.started"
  | "playtest.passed"
  | "playtest.failed"
  | "playtest.reset";

function eventToPlaytestStatus(eventType: string): PlaytestStatus | null {
  const mapping: Record<string, PlaytestStatus> = {
    "playtest.started": "running",
    "playtest.passed": "passed",
    "playtest.failed": "failed",
    "playtest.reset": "idle",
  };
  return mapping[eventType] ?? null;
}

export function usePlaytestStateMachine() {
  const transitionStatus = useCallback(
    (current: PlaytestStatus, next: PlaytestStatus): PlaytestStatus => {
      if (current === next) return current;

      // Terminal statuses can only transition to idle (for retry/re-run)
      if (TERMINAL_STATUSES.has(current) && next !== "idle") {
        return current;
      }

      const allowed = ALLOWED_TRANSITIONS[current];
      if (!allowed || !allowed.has(next)) return current;

      return next;
    },
    []
  );

  const statusForEvent = useCallback((eventType: string): PlaytestStatus | null => {
    return eventToPlaytestStatus(eventType);
  }, []);

  const applyPlaytestEvent = useCallback(
    (current: PlaytestStatus, eventType: PlaytestEventType): PlaytestStatus => {
      const next = eventToPlaytestStatus(eventType);
      if (!next) return current;
      return transitionStatus(current, next);
    },
    [transitionStatus]
  );

  const canTransition = useCallback(
    (current: PlaytestStatus, next: PlaytestStatus): boolean => {
      if (current === next) return true;
      const allowed = ALLOWED_TRANSITIONS[current];
      return allowed?.has(next) ?? false;
    },
    []
  );

  const isTerminal = useCallback((status: PlaytestStatus): boolean => {
    return TERMINAL_STATUSES.has(status);
  }, []);

  return {
    applyPlaytestEvent,
    canTransition,
    isTerminal,
    statusForEvent,
    transitionStatus,
  };
}

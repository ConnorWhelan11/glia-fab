/**
 * useWorldBuildEvents - Process kernel events for active build
 *
 * Uses decomposed state updaters for maintainability and testability.
 */

import { useCallback, useRef } from "react";
import type { KernelEvent } from "@/types";
import type { UseWorldBuildEventsOptions, WorldBuildEventsState } from "./types";
import { useBuildStateMachine } from "./useBuildStateMachine";
import { applyEventToState } from "./buildStateUpdaters";

export function useWorldBuildEvents(
  options: UseWorldBuildEventsOptions
): WorldBuildEventsState {
  const {
    activeIssueIdRef,
    activeJobIdRef,
    onKernelEvents,
    setActiveWorldBuild,
    updateRecentWorld,
  } = options;

  const { applyKernelEvent } = useBuildStateMachine();

  // Use refs for stable callback dependencies
  const onKernelEventsRef = useRef(onKernelEvents);
  onKernelEventsRef.current = onKernelEvents;

  const updateRecentWorldRef = useRef(updateRecentWorld);
  updateRecentWorldRef.current = updateRecentWorld;

  const processKernelEvents = useCallback(
    (events: KernelEvent[]) => {
      const activeIssueId = activeIssueIdRef.current;
      if (!activeIssueId) return;

      const relevantEvents = events.filter((e) => e.issueId === activeIssueId);
      if (relevantEvents.length === 0) return;

      // Notify external listeners
      onKernelEventsRef.current?.(relevantEvents);

      setActiveWorldBuild((prev) => {
        if (!prev || prev.issueId !== activeIssueId) return prev;

        let updated = prev;

        for (const event of relevantEvents) {
          // Compute next status via FSM
          const nextStatus = applyKernelEvent(updated.status, event.type);

          // Apply all updates for this event
          updated = applyEventToState(updated, event, nextStatus);

          // Handle terminal states - update recent worlds in same batch
          if (event.type === "issue.completed" && nextStatus === "complete") {
            activeJobIdRef.current = null;
            updateRecentWorldRef.current(prev.issueId, {
              status: "complete",
              fitness: updated.bestFitness,
              generation: updated.generation,
              lastRunOutcome: "pass",
            });
          }

          if (event.type === "issue.failed" && nextStatus === "failed") {
            activeJobIdRef.current = null;
            updateRecentWorldRef.current(prev.issueId, {
              status: "failed",
              lastRunOutcome: "fail",
            });
          }
        }

        return updated;
      });
    },
    [activeIssueIdRef, activeJobIdRef, setActiveWorldBuild, applyKernelEvent]
  );

  return { processKernelEvents };
}

/**
 * usePlaytest - Playtest state management for World Builder
 *
 * Manages NitroGen-based gameplay testing lifecycle with FSM and timeout handling.
 */

import { useCallback, useEffect, useRef } from "react";
import { startPlayabilityTest, killJob } from "@/services/runService";
import type { WorldBuildState } from "@/types";
import { usePlaytestStateMachine, type PlaytestStatus } from "./usePlaytestStateMachine";
import { PLAYTEST_TIMEOUT_MS } from "../constants";

export interface UsePlaytestConfig {
  projectRoot?: string | null;
  activeWorldBuild: WorldBuildState | null;
  setActiveWorldBuild: React.Dispatch<React.SetStateAction<WorldBuildState | null>>;
}

export interface UsePlaytestReturn {
  runPlaytest: () => Promise<void>;
  cancelPlaytest: () => Promise<void>;
  resetPlaytest: () => void;
}

export function usePlaytest({
  projectRoot,
  activeWorldBuild,
  setActiveWorldBuild,
}: UsePlaytestConfig): UsePlaytestReturn {
  const { transitionStatus } = usePlaytestStateMachine();

  // Refs for cleanup
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      abortControllerRef.current?.abort();
    };
  }, []);

  const updatePlaytestStatus = useCallback(
    (status: PlaytestStatus, extra?: Partial<WorldBuildState>) => {
      setActiveWorldBuild((prev) => {
        if (!prev) return null;

        const currentStatus = prev.playtestStatus ?? "idle";
        const nextStatus = transitionStatus(currentStatus, status);

        if (nextStatus === currentStatus && !extra) return prev;

        return {
          ...prev,
          playtestStatus: nextStatus,
          ...extra,
        };
      });
    },
    [setActiveWorldBuild, transitionStatus]
  );

  const runPlaytest = useCallback(async () => {
    if (!projectRoot || !activeWorldBuild) return;
    if (activeWorldBuild.status !== "complete") return;

    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    // Create new abort controller
    abortControllerRef.current = new AbortController();

    // Transition to running
    updatePlaytestStatus("running", {
      playtestError: undefined,
      playtestMetrics: undefined,
      playtestFailures: undefined,
      playtestWarnings: undefined,
    });

    try {
      // Default Godot project path - could be derived from world config
      const godotProjectPath = `fab/vault/godot/templates/fab_game_template/project`;

      const jobInfo = await startPlayabilityTest({
        projectRoot,
        worldId: activeWorldBuild.issueId,
        godotProjectPath,
      });

      // Store job ID for potential cancellation
      setActiveWorldBuild((prev) =>
        prev ? { ...prev, playtestJobId: jobInfo.jobId } : null
      );

      // Set timeout for playtest
      timeoutRef.current = setTimeout(() => {
        // Check if still running before timing out
        setActiveWorldBuild((prev) => {
          if (!prev || prev.playtestStatus !== "running") return prev;
          return {
            ...prev,
            playtestStatus: "failed",
            playtestError: `Playtest timed out after ${PLAYTEST_TIMEOUT_MS / 1000}s`,
          };
        });

        // Try to kill the job on timeout
        if (jobInfo.jobId) {
          killJob(jobInfo.jobId).catch(console.error);
        }
      }, PLAYTEST_TIMEOUT_MS);

      // Note: Actual results come through kernel events via useWorldBuildEvents
      // The playtest.passed or playtest.failed event will update the status

    } catch (error) {
      // Check if aborted
      if (abortControllerRef.current?.signal.aborted) return;

      updatePlaytestStatus("failed", {
        playtestError: error instanceof Error ? error.message : String(error),
      });
    }
  }, [projectRoot, activeWorldBuild, setActiveWorldBuild, updatePlaytestStatus]);

  const cancelPlaytest = useCallback(async () => {
    // Clear timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    // Abort any pending operations
    abortControllerRef.current?.abort();

    if (!activeWorldBuild?.playtestJobId) {
      updatePlaytestStatus("idle", { playtestJobId: undefined });
      return;
    }

    try {
      await killJob(activeWorldBuild.playtestJobId);
    } catch (error) {
      console.error("Failed to cancel playtest:", error);
    }

    updatePlaytestStatus("idle", { playtestJobId: undefined });
  }, [activeWorldBuild?.playtestJobId, updatePlaytestStatus]);

  const resetPlaytest = useCallback(() => {
    // Clear timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    updatePlaytestStatus("idle", {
      playtestJobId: undefined,
      playtestError: undefined,
      playtestMetrics: undefined,
      playtestFailures: undefined,
      playtestWarnings: undefined,
    });
  }, [updatePlaytestStatus]);

  return {
    runPlaytest,
    cancelPlaytest,
    resetPlaytest,
  };
}

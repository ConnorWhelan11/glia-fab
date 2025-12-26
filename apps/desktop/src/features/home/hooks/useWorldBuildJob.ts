import { useCallback, useRef } from "react";
import { startJob, killJob } from "@/services/runService";
import type { BlueprintDraft } from "@/types";
import type { WorldBuildJobState, UseWorldBuildJobOptions } from "./types";

export function useWorldBuildJob(
  options: UseWorldBuildJobOptions
): WorldBuildJobState {
  const {
    projectRoot,
    promptText,
    blueprintDraft,
    setActiveWorldBuild,
    upsertRecentWorld,
    createInitialBuildState,
  } = options;

  const activeJobIdRef = useRef<string | null>(null);

  const stopActiveJob = useCallback(async () => {
    const jobId = activeJobIdRef.current;
    activeJobIdRef.current = null;
    if (!jobId) return;
    try {
      await killJob(jobId);
    } catch (error) {
      console.error("Failed to kill job:", error);
    }
  }, []);

  const startWorldBuild = useCallback(
    async (
      issueId: string,
      init?: { prompt?: string; blueprint?: BlueprintDraft; recentName?: string }
    ) => {
      if (!projectRoot) {
        console.warn("Cannot start world build without projectRoot");
        return;
      }

      try {
        setActiveWorldBuild((prev) => {
          if (prev && prev.issueId === issueId) return prev;
          const nextPrompt = init?.prompt ?? promptText;
          const nextBlueprint = init?.blueprint ?? blueprintDraft;
          return createInitialBuildState(issueId, nextPrompt, nextBlueprint);
        });

        if (init?.recentName) {
          upsertRecentWorld({
            id: issueId,
            name: init.recentName,
            status: "building",
            lastPrompt: init?.prompt ?? promptText,
            updatedAt: Date.now(),
          });
        }

        const jobInfo = await startJob({
          projectRoot,
          command: `cyntra run --once --issue ${issueId}`,
          label: `Build World ${issueId}`,
        });

        activeJobIdRef.current = jobInfo.jobId;

        setActiveWorldBuild((prev) =>
          prev && prev.issueId === issueId
            ? { ...prev, runId: jobInfo.runId, status: "scheduling", error: undefined }
            : prev
        );
      } catch (error) {
        console.error("Failed to start world build:", error);
        setActiveWorldBuild((prev) =>
          prev && prev.issueId === issueId
            ? {
                ...prev,
                status: "failed",
                error: error instanceof Error ? error.message : "Failed to start build",
              }
            : prev
        );
      }
    },
    [
      blueprintDraft,
      createInitialBuildState,
      projectRoot,
      promptText,
      setActiveWorldBuild,
      upsertRecentWorld,
    ]
  );

  return {
    activeJobIdRef,
    startWorldBuild,
    stopActiveJob,
  };
}

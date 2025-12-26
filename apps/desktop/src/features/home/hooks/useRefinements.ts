import { useCallback } from "react";
import { createIssue } from "@/services/kernelService";
import type { RefinementMessage } from "@/types";
import type { RefinementsState, UseRefinementsOptions } from "./types";

export function useRefinements(options: UseRefinementsOptions): RefinementsState {
  const {
    activeWorldBuild,
    projectRoot,
    createInitialBuildState,
    blueprintToTags,
    setActiveWorldBuild,
    startWorldBuild,
    stopActiveJob,
    updateRecentWorld,
    upsertRecentWorld,
  } = options;

  const queueRefinement = useCallback(async (text: string) => {
    if (!activeWorldBuild || !projectRoot) return;

    const refinement: RefinementMessage = {
      id: `ref-${Date.now()}`,
      text,
      timestamp: Date.now(),
      status: "pending",
    };

    try {
      const description = `${activeWorldBuild.prompt}\n\nRefinement: ${text}`;
      const issue = await createIssue({
        projectRoot,
        title: `Refine: ${text.slice(0, 50)}${text.length > 50 ? "..." : ""}`,
        description,
        tags: [...blueprintToTags(activeWorldBuild.blueprint), "refinement"],
        dkPriority: "P1",
        dkRisk: "medium",
        dkSize: "S",
        dkToolHint: null,
      });

      setActiveWorldBuild((prev) =>
        prev
          ? {
              ...prev,
              refinements: [
                ...prev.refinements,
                { ...refinement, issueId: issue.id, status: "queued", issueTitle: issue.title },
              ],
            }
          : null
      );
    } catch (error) {
      console.error("Failed to create refinement issue:", error);
    }
  }, [activeWorldBuild, blueprintToTags, projectRoot, setActiveWorldBuild]);

  const applyRefinementNow = useCallback(async (refinementId: string) => {
    if (!activeWorldBuild) return;

    const refinement = activeWorldBuild.refinements.find((r) => r.id === refinementId);
    if (!refinement) return;
    if (!refinement.issueId) return;

    await stopActiveJob();
    updateRecentWorld(activeWorldBuild.issueId, { status: "canceled", lastRunOutcome: null });

    setActiveWorldBuild((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        refinements: prev.refinements.map((r) =>
          r.id === refinementId ? { ...r, status: "applying" } : r
        ),
      };
    });

    if (projectRoot) {
      const combinedPrompt = `${activeWorldBuild.prompt}\n\nRefinement: ${refinement.text}`;
      const recentName = refinement.issueTitle ?? `Refine: ${refinement.text.slice(0, 50)}`;

      setActiveWorldBuild(
        createInitialBuildState(refinement.issueId, combinedPrompt, activeWorldBuild.blueprint)
      );

      upsertRecentWorld({
        id: refinement.issueId,
        name: recentName,
        status: "building",
        lastPrompt: combinedPrompt,
        updatedAt: Date.now(),
      });

      await startWorldBuild(refinement.issueId, {
        prompt: combinedPrompt,
        blueprint: activeWorldBuild.blueprint,
        recentName,
      });
    }
  }, [
    activeWorldBuild,
    createInitialBuildState,
    projectRoot,
    setActiveWorldBuild,
    startWorldBuild,
    stopActiveJob,
    updateRecentWorld,
    upsertRecentWorld,
  ]);

  return { queueRefinement, applyRefinementNow };
}

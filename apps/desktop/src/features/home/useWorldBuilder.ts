/**
 * useWorldBuilder - State management hook for World Builder Console
 *
 * Manages prompt text, blueprint configuration, template selection,
 * submission lifecycle, and active world builds with kernel integration.
 */

import { useCallback, useMemo, useState, useEffect, useRef } from "react";
import type {
  BlueprintDraft,
  WorldBuilderMode,
  WorldSubmitState,
  WorldTemplate,
  RecentWorld,
  WorldBuildState,
  WorldBuildStatus,
  KernelEvent,
} from "@/types";
import { WORLD_TEMPLATES } from "./templates";
import { createIssue } from "@/services/kernelService";
import { listActiveJobs } from "@/services/runService";
import {
  useBlueprintDraft,
  usePlaytest,
  usePromptState,
  useRecentWorlds,
  useRefinements,
  useTemplateSelection,
  useWorldBuildEvents,
  useWorldBuildJob,
} from "./hooks";
import { SUBMIT_STATE_RESET_DELAY_MS } from "./constants";

/** Hook configuration */
export interface UseWorldBuilderConfig {
  /** Project root for kernel integration */
  projectRoot?: string | null;
  /** Callback when kernel events arrive for active build */
  onKernelEvents?: (events: KernelEvent[]) => void;
}

/** Default blueprint for new worlds */
const DEFAULT_BLUEPRINT: BlueprintDraft = {
  name: "",
  runtime: "godot",
  outputs: ["viewer"],
  gates: [],
  tags: [],
};

/** Generate issue tags from blueprint */
function blueprintToTags(blueprint: BlueprintDraft): string[] {
  // Use Set for O(1) duplicate checks
  const tagSet = new Set<string>();

  // Asset type
  tagSet.add("asset:world");

  // Runtime
  tagSet.add(`runtime:${blueprint.runtime}`);

  // Outputs
  for (const output of blueprint.outputs) {
    tagSet.add(`output:${output}`);
  }

  // Gates
  tagSet.add("gate:fab-realism");
  if (blueprint.runtime === "godot" || blueprint.runtime === "hybrid") {
    tagSet.add("gate:godot");
  }
  for (const gate of blueprint.gates) {
    tagSet.add(`gate:${gate}`);
  }

  // User tags
  for (const tag of blueprint.tags) {
    tagSet.add(tag);
  }

  return Array.from(tagSet);
}

/** Create initial build state */
function createInitialBuildState(
  issueId: string,
  prompt: string,
  blueprint: BlueprintDraft
): WorldBuildState {
  return {
    issueId,
    status: "queued",
    prompt,
    blueprint,
    isSpeculating: false,
    agents: [],
    generation: 0,
    bestFitness: 0,
    refinements: [],
    startedAt: Date.now(),
  };
}

function recentStatusToBuildStatus(status: RecentWorld["status"]): WorldBuildStatus {
  switch (status) {
    case "building":
      return "generating";
    case "paused":
      return "paused";
    case "complete":
      return "complete";
    case "failed":
      return "failed";
    case "canceled":
      return "failed";
    case "evolving":
      return "complete";
    default:
      return "queued";
  }
}

export interface WorldBuilderState {
  // Mode
  builderMode: WorldBuilderMode;
  setBuilderMode: (mode: WorldBuilderMode) => void;

  // Console
  promptText: string;
  setPromptText: (text: string) => void;
  consoleFocused: boolean;
  setConsoleFocused: (focused: boolean) => void;

  // Blueprint
  blueprintDraft: BlueprintDraft;
  updateBlueprint: (partial: Partial<BlueprintDraft>) => void;
  resetBlueprint: () => void;

  // Template
  selectedTemplateId: string | null;
  selectedTemplate: WorldTemplate | null;
  selectTemplate: (id: string | null) => void;
  templates: WorldTemplate[];

  // Recent worlds
  recentWorlds: RecentWorld[];
  addRecentWorld: (world: RecentWorld) => void;
  removeRecentWorld: (id: string) => void;
  updateRecentWorld: (id: string, update: Partial<RecentWorld>) => void;
  mostRecentWorld: RecentWorld | null;
  openRecentWorld: (world: RecentWorld) => Promise<void>;

  // Fork source
  forkSourceId: string | null;
  setForkSourceId: (id: string | null) => void;

  // Submit
  submitState: WorldSubmitState;
  submitError: string | null;
  createWorld: () => Promise<string | null>;
  resetSubmitState: () => void;

  // Active Build State
  activeWorldBuild: WorldBuildState | null;
  isBuilding: boolean;
  startWorldBuild: (
    issueId: string,
    init?: { prompt?: string; blueprint?: BlueprintDraft; recentName?: string }
  ) => Promise<void>;
  cancelWorldBuild: () => Promise<void>;
  dismissWorldBuild: () => void;
  pauseWorldBuild: () => Promise<void>;
  resumeWorldBuild: () => Promise<void>;
  retryWorldBuild: () => Promise<void>;
  processKernelEvents: (events: KernelEvent[]) => void;

  // Refinements
  queueRefinement: (text: string) => Promise<void>;
  applyRefinementNow: (refinementId: string) => Promise<void>;

  // Playtest
  runPlaytest: () => Promise<void>;

  // Motion
  prefersReducedMotion: boolean;

  // Computed
  canSubmit: boolean;
  isSubmitting: boolean;
  hasKernelIntegration: boolean;
}

export function useWorldBuilder(config: UseWorldBuilderConfig = {}): WorldBuilderState {
  const { projectRoot, onKernelEvents } = config;

  // Mode
  const [builderMode, setBuilderMode] = useState<WorldBuilderMode>("scratch");

  // Console
  const { promptText, setPromptText, consoleFocused, setConsoleFocused } = usePromptState();

  // Blueprint
  const {
    blueprintDraft,
    setBlueprintDraft,
    updateBlueprint,
    resetBlueprint,
  } = useBlueprintDraft();

  // Ref for async cleanup
  const submitTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (submitTimeoutRef.current) {
        clearTimeout(submitTimeoutRef.current);
      }
    };
  }, []);

  const applyTemplate = useCallback((template: WorldTemplate) => {
    setPromptText(template.promptText);
    setBlueprintDraft({
      name: "",
      ...template.blueprintDefaults,
    });
    setBuilderMode("template");
  }, [setBlueprintDraft, setBuilderMode, setPromptText]);

  const clearTemplate = useCallback(() => {
    setBuilderMode("scratch");
  }, [setBuilderMode]);

  // Template
  const { selectedTemplateId, selectedTemplate, selectTemplate, templates } =
    useTemplateSelection({
      templates: WORLD_TEMPLATES,
      onApplyTemplate: applyTemplate,
      onClearTemplate: clearTemplate,
    });

  // Recent worlds
  const {
    recentWorlds,
    addRecentWorld,
    updateRecentWorld,
    removeRecentWorld,
    upsertRecentWorld,
    mostRecentWorld,
  } = useRecentWorlds();

  // Fork source
  const [forkSourceId, setForkSourceId] = useState<string | null>(null);

  // Submit
  const [submitState, setSubmitState] = useState<WorldSubmitState>("idle");
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Active build state
  const [activeWorldBuild, setActiveWorldBuild] = useState<WorldBuildState | null>(null);
  const activeIssueIdRef = useRef<string | null>(null);

  const { activeJobIdRef, startWorldBuild, stopActiveJob } = useWorldBuildJob({
    projectRoot,
    promptText,
    blueprintDraft,
    setActiveWorldBuild,
    upsertRecentWorld,
    createInitialBuildState,
  });

  // Motion preference
  const prefersReducedMotion = useMemo(() => {
    if (typeof window === "undefined") return false;
    if (typeof window.matchMedia !== "function") return false;
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    return mediaQuery?.matches ?? false;
  }, []);

  // Kernel integration available
  const hasKernelIntegration = Boolean(projectRoot);

  // Keep active issue ref in sync (avoids stale closure in event handlers)
  useEffect(() => {
    activeIssueIdRef.current = activeWorldBuild?.issueId ?? null;
  }, [activeWorldBuild?.issueId]);

  const { processKernelEvents } = useWorldBuildEvents({
    activeIssueIdRef,
    activeJobIdRef,
    onKernelEvents,
    setActiveWorldBuild,
    updateRecentWorld,
  });

  const { queueRefinement, applyRefinementNow } = useRefinements({
    activeWorldBuild,
    projectRoot,
    createInitialBuildState,
    blueprintToTags,
    setActiveWorldBuild,
    startWorldBuild,
    stopActiveJob,
    updateRecentWorld,
    upsertRecentWorld,
  });

  // Playtest
  const { runPlaytest } = usePlaytest({
    projectRoot,
    activeWorldBuild,
    setActiveWorldBuild,
  });

  // Helper to schedule submit state reset with cleanup
  const scheduleSubmitReset = useCallback(() => {
    if (submitTimeoutRef.current) {
      clearTimeout(submitTimeoutRef.current);
    }
    submitTimeoutRef.current = setTimeout(() => {
      setSubmitState("idle");
      submitTimeoutRef.current = null;
    }, SUBMIT_STATE_RESET_DELAY_MS);
  }, []);

  // Create world - with real kernel integration when projectRoot available
  const createWorld = useCallback(async (): Promise<string | null> => {
    if (!promptText.trim()) {
      setSubmitError("Please describe your world");
      return null;
    }

    setSubmitState("submitting");
    setSubmitError(null);

    const worldName = blueprintDraft.name || `World ${Date.now().toString(36).slice(-6)}`;

    try {
      // If kernel integration available, create real issue
      if (projectRoot) {
        const tags = blueprintToTags(blueprintDraft);

        const issue = await createIssue({
          projectRoot,
          title: worldName,
          description: promptText,
          tags,
          dkPriority: "P1",
          dkRisk: "medium", // Keep world builds linear (no speculate+vote)
          dkSize: "M",
          dkToolHint: null, // Let routing decide
        });

        // Add to recent worlds with real issue ID
        addRecentWorld({
          id: issue.id,
          name: worldName,
          status: "building",
          lastPrompt: promptText,
          updatedAt: Date.now(),
        });

        // Initialize build state
        setActiveWorldBuild(createInitialBuildState(issue.id, promptText, blueprintDraft));

        setSubmitState("success");
        scheduleSubmitReset();
        return issue.id;
      } else {
        // Fallback: mock mode when no project root
        await new Promise((resolve) => setTimeout(resolve, 800));

        const worldId = `world-${Date.now().toString(36)}`;

        addRecentWorld({
          id: worldId,
          name: worldName,
          status: "building",
          lastPrompt: promptText,
          updatedAt: Date.now(),
        });

        // Create mock build state
        setActiveWorldBuild(createInitialBuildState(worldId, promptText, blueprintDraft));

        setSubmitState("success");
        scheduleSubmitReset();

        return worldId;
      }
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Failed to create world");
      setSubmitState("error");
      return null;
    }
  }, [promptText, blueprintDraft, projectRoot, addRecentWorld, scheduleSubmitReset]);

  // FIX: Use default blueprint instead of capturing current blueprintDraft
  // This avoids the stale closure bug where opening a recent world
  // would use whatever blueprint was active at the time
  const openRecentWorld = useCallback(async (world: RecentWorld) => {
    const prompt = world.lastPrompt ?? "";
    // Use default blueprint - the world's original blueprint is in the build state
    // or will be retrieved from the issue when the build starts
    const worldBlueprint = DEFAULT_BLUEPRINT;
    const baseState = createInitialBuildState(world.id, prompt, worldBlueprint);
    const status = recentStatusToBuildStatus(world.status);

    setActiveWorldBuild({
      ...baseState,
      status,
      generation: world.generation ?? 0,
      bestFitness: world.fitness ?? 0,
      startedAt: world.updatedAt || baseState.startedAt,
    });

    if (!projectRoot || world.status !== "building") return;

    try {
      const activeJobs = await listActiveJobs();
      const matchingJob = activeJobs.find((job) =>
        job.command?.includes(`--issue ${world.id}`)
      );
      if (matchingJob) {
        activeJobIdRef.current = matchingJob.jobId;
        return;
      }

      await startWorldBuild(world.id, {
        prompt,
        blueprint: worldBlueprint,
        recentName: world.name,
      });
    } catch (error) {
      console.error("Failed to attach to active world build:", error);
    }
  }, [projectRoot, startWorldBuild, activeJobIdRef]);

  // Cancel world build (user intent: stop and return to builder)
  const cancelWorldBuild = useCallback(async () => {
    await stopActiveJob();

    // Update recent world status
    if (activeWorldBuild) {
      updateRecentWorld(activeWorldBuild.issueId, {
        status: "canceled",
        lastRunOutcome: null,
      });
    }

    // Clear build state
    setActiveWorldBuild(null);
    setSubmitState("idle");
  }, [activeWorldBuild, stopActiveJob, updateRecentWorld]);

  // Dismiss build UI without changing recent-world status (used after complete/failed)
  const dismissWorldBuild = useCallback(() => {
    activeJobIdRef.current = null;
    setActiveWorldBuild(null);
    setSubmitState("idle");
  }, [activeJobIdRef]);

  // Pause world build (best-effort stop; can be resumed/retried)
  const pauseWorldBuild = useCallback(async () => {
    if (!activeWorldBuild) return;
    await stopActiveJob();
    setActiveWorldBuild((prev) => (prev ? { ...prev, status: "paused" } : null));
    updateRecentWorld(activeWorldBuild.issueId, { status: "paused", lastRunOutcome: null });
  }, [activeWorldBuild, stopActiveJob, updateRecentWorld]);

  const resetBuildForRestart = useCallback((build: WorldBuildState): WorldBuildState => {
    return {
      ...createInitialBuildState(build.issueId, build.prompt, build.blueprint),
      refinements: build.refinements,
    };
  }, []);

  const resumeWorldBuild = useCallback(async () => {
    if (!activeWorldBuild || activeWorldBuild.status !== "paused") return;
    if (!projectRoot) return;

    const issueId = activeWorldBuild.issueId;
    const { prompt, blueprint } = activeWorldBuild;

    setActiveWorldBuild(resetBuildForRestart(activeWorldBuild));
    updateRecentWorld(issueId, { status: "building", lastRunOutcome: null });
    await startWorldBuild(issueId, { prompt, blueprint });
  }, [activeWorldBuild, projectRoot, resetBuildForRestart, startWorldBuild, updateRecentWorld]);

  const retryWorldBuild = useCallback(async () => {
    if (!activeWorldBuild || activeWorldBuild.status !== "failed") return;
    if (!projectRoot) return;

    const issueId = activeWorldBuild.issueId;
    const { prompt, blueprint } = activeWorldBuild;

    setActiveWorldBuild(resetBuildForRestart(activeWorldBuild));
    updateRecentWorld(issueId, { status: "building", lastRunOutcome: null });
    await startWorldBuild(issueId, { prompt, blueprint });
  }, [activeWorldBuild, projectRoot, resetBuildForRestart, startWorldBuild, updateRecentWorld]);

  // Reset submit state
  const resetSubmitState = useCallback(() => {
    setSubmitState("idle");
    setSubmitError(null);
  }, []);

  // Computed: can submit
  const canSubmit = useMemo(() => {
    return promptText.trim().length > 0 && submitState === "idle";
  }, [promptText, submitState]);

  // Computed: is submitting
  const isSubmitting = submitState === "submitting";

  // Computed: is building
  const isBuilding = Boolean(
    activeWorldBuild &&
    activeWorldBuild.status !== "complete" &&
    activeWorldBuild.status !== "failed"
  );

  // Memoize return object to prevent unnecessary re-renders in consumers
  return useMemo(() => ({
    // Mode
    builderMode,
    setBuilderMode,

    // Console
    promptText,
    setPromptText,
    consoleFocused,
    setConsoleFocused,

    // Blueprint
    blueprintDraft,
    updateBlueprint,
    resetBlueprint,

    // Template
    selectedTemplateId,
    selectedTemplate,
    selectTemplate,
    templates,

    // Recent worlds
    recentWorlds,
    addRecentWorld,
    removeRecentWorld,
    updateRecentWorld,
    mostRecentWorld,
    openRecentWorld,

    // Fork source
    forkSourceId,
    setForkSourceId,

    // Submit
    submitState,
    submitError,
    createWorld,
    resetSubmitState,

    // Active Build State
    activeWorldBuild,
    isBuilding,
    startWorldBuild,
    cancelWorldBuild,
    dismissWorldBuild,
    pauseWorldBuild,
    resumeWorldBuild,
    retryWorldBuild,
    processKernelEvents,

    // Refinements
    queueRefinement,
    applyRefinementNow,

    // Playtest
    runPlaytest,

    // Motion
    prefersReducedMotion,

    // Computed
    canSubmit,
    isSubmitting,
    hasKernelIntegration,
  }), [
    // Mode
    builderMode,
    setBuilderMode,
    // Console
    promptText,
    setPromptText,
    consoleFocused,
    setConsoleFocused,
    // Blueprint
    blueprintDraft,
    updateBlueprint,
    resetBlueprint,
    // Template
    selectedTemplateId,
    selectedTemplate,
    selectTemplate,
    templates,
    // Recent worlds
    recentWorlds,
    addRecentWorld,
    removeRecentWorld,
    updateRecentWorld,
    mostRecentWorld,
    openRecentWorld,
    // Fork source
    forkSourceId,
    setForkSourceId,
    // Submit
    submitState,
    submitError,
    createWorld,
    resetSubmitState,
    // Active Build State
    activeWorldBuild,
    isBuilding,
    startWorldBuild,
    cancelWorldBuild,
    dismissWorldBuild,
    pauseWorldBuild,
    resumeWorldBuild,
    retryWorldBuild,
    processKernelEvents,
    // Refinements
    queueRefinement,
    applyRefinementNow,
    // Playtest
    runPlaytest,
    // Motion
    prefersReducedMotion,
    // Computed
    canSubmit,
    isSubmitting,
    hasKernelIntegration,
  ]);
}

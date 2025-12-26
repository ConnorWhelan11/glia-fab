import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type {
  BlueprintDraft,
  KernelEvent,
  RecentWorld,
  WorldBuildState,
  WorldTemplate,
} from "@/types";

export interface UsePromptStateOptions {
  initialPrompt?: string;
  initialFocused?: boolean;
}

export interface PromptState {
  promptText: string;
  setPromptText: Dispatch<SetStateAction<string>>;
  consoleFocused: boolean;
  setConsoleFocused: Dispatch<SetStateAction<boolean>>;
}

export interface UseBlueprintDraftOptions {
  initial?: BlueprintDraft;
}

export interface BlueprintDraftState {
  blueprintDraft: BlueprintDraft;
  setBlueprintDraft: Dispatch<SetStateAction<BlueprintDraft>>;
  updateBlueprint: (partial: Partial<BlueprintDraft>) => void;
  resetBlueprint: () => void;
}

export interface UseTemplateSelectionOptions {
  templates: WorldTemplate[];
  onApplyTemplate?: (template: WorldTemplate) => void;
  onClearTemplate?: () => void;
}

export interface TemplateSelectionState {
  selectedTemplateId: string | null;
  selectedTemplate: WorldTemplate | null;
  selectTemplate: (id: string | null) => void;
  templates: WorldTemplate[];
}

export interface UseRecentWorldsOptions {
  storageKey?: string;
  maxItems?: number;
}

export interface RecentWorldsState {
  recentWorlds: RecentWorld[];
  addRecentWorld: (world: RecentWorld) => void;
  updateRecentWorld: (id: string, update: Partial<RecentWorld>) => void;
  removeRecentWorld: (id: string) => void;
  upsertRecentWorld: (world: RecentWorld) => void;
  mostRecentWorld: RecentWorld | null;
}

export interface UseWorldBuildEventsOptions {
  activeIssueIdRef: MutableRefObject<string | null>;
  activeJobIdRef: MutableRefObject<string | null>;
  onKernelEvents?: (events: KernelEvent[]) => void;
  setActiveWorldBuild: Dispatch<SetStateAction<WorldBuildState | null>>;
  updateRecentWorld: (id: string, update: Partial<RecentWorld>) => void;
}

export interface WorldBuildEventsState {
  processKernelEvents: (events: KernelEvent[]) => void;
}

export interface UseWorldBuildJobOptions {
  projectRoot?: string | null;
  promptText: string;
  blueprintDraft: BlueprintDraft;
  setActiveWorldBuild: Dispatch<SetStateAction<WorldBuildState | null>>;
  upsertRecentWorld: (world: RecentWorld) => void;
  createInitialBuildState: (
    issueId: string,
    prompt: string,
    blueprint: BlueprintDraft
  ) => WorldBuildState;
}

export interface WorldBuildJobState {
  activeJobIdRef: MutableRefObject<string | null>;
  startWorldBuild: (
    issueId: string,
    init?: { prompt?: string; blueprint?: BlueprintDraft; recentName?: string }
  ) => Promise<void>;
  stopActiveJob: () => Promise<void>;
}

export interface UseRefinementsOptions {
  activeWorldBuild: WorldBuildState | null;
  projectRoot?: string | null;
  createInitialBuildState: (
    issueId: string,
    prompt: string,
    blueprint: BlueprintDraft
  ) => WorldBuildState;
  blueprintToTags: (blueprint: BlueprintDraft) => string[];
  setActiveWorldBuild: Dispatch<SetStateAction<WorldBuildState | null>>;
  startWorldBuild: (
    issueId: string,
    init?: { prompt?: string; blueprint?: BlueprintDraft; recentName?: string }
  ) => Promise<void>;
  stopActiveJob: () => Promise<void>;
  updateRecentWorld: (id: string, update: Partial<RecentWorld>) => void;
  upsertRecentWorld: (world: RecentWorld) => void;
}

export interface RefinementsState {
  queueRefinement: (text: string) => Promise<void>;
  applyRefinementNow: (refinementId: string) => Promise<void>;
}

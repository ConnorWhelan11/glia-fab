/**
 * Build State Updaters
 *
 * Decomposed state update functions for kernel events.
 * Each function handles a specific event type or update concern.
 */

import type { AgentState, BuildEvent, KernelEvent, WorldBuildState } from "@/types";
import {
  extractToolchain,
  extractFitness,
  extractError,
  extractPreviewUrls,
  extractGlbUrl,
  extractGodotUrl,
} from "./kernelEventGuards";
import { EVENT_MESSAGE_MAX_LENGTH } from "../constants";

// ============================================================================
// Helper functions
// ============================================================================

function formatKernelEventMessage(event: KernelEvent): string | null {
  const data =
    event.data && typeof event.data === "object"
      ? (event.data as Record<string, unknown>)
      : null;
  if (!data) return null;

  const trim = (value: unknown): string | null => {
    if (typeof value !== "string") return null;
    const cleaned = value.trim();
    if (!cleaned) return null;
    return cleaned.length > EVENT_MESSAGE_MAX_LENGTH
      ? `${cleaned.slice(0, EVENT_MESSAGE_MAX_LENGTH)}…`
      : cleaned;
  };

  if (event.type.startsWith("telemetry.")) {
    const kind = event.type.replace("telemetry.", "");
    if (kind === "response_chunk" || kind === "response_complete" || kind === "thinking") {
      return (
        trim(data.content) ||
        trim(data.output) ||
        trim(data.prompt) ||
        trim(data.message)
      );
    }
    if (kind === "tool_call") {
      return `tool call: ${trim(data.tool) ?? "unknown"}`;
    }
    if (kind === "tool_result") {
      return `tool result: ${trim(data.tool) ?? "unknown"}`;
    }
    if (kind === "bash_command") {
      return trim(data.command) ? `$ ${trim(data.command)}` : "bash command";
    }
    if (kind === "bash_output") {
      return trim(data.output) ?? "bash output";
    }
    if (kind === "file_read") {
      return trim(data.path) ? `read ${trim(data.path)}` : "file read";
    }
    if (kind === "file_write") {
      return trim(data.path) ? `write ${trim(data.path)}` : "file write";
    }
    if (kind === "error") {
      return trim(data.error) ?? "error";
    }
    if (kind === "started") {
      return "started";
    }
    if (kind === "completed") {
      return trim(data.status) ? `completed (${trim(data.status)})` : "completed";
    }
  }

  return null;
}

// ============================================================================
// State updaters - each handles a specific concern
// ============================================================================

/**
 * Handle workcell.created event - add new agent to tracking
 */
export function handleWorkcellCreated(
  state: WorldBuildState,
  event: KernelEvent
): WorldBuildState {
  if (event.type !== "workcell.created" || !event.workcellId) return state;

  const toolchain = extractToolchain(event);
  const newAgent: AgentState = {
    id: event.workcellId,
    toolchain: toolchain as AgentState["toolchain"],
    status: "running",
    fitness: 0,
    events: [],
  };

  const isSpeculating =
    state.agents.length > 0 || event.workcellId.includes("spec-");

  return {
    ...state,
    isSpeculating,
    agents: [...state.agents, newAgent],
  };
}

/**
 * Handle fab.critic.result event - update agent fitness
 */
export function handleCriticResult(
  state: WorldBuildState,
  event: KernelEvent
): WorldBuildState {
  if (event.type !== "fab.critic.result" || !event.workcellId) return state;

  const fitness = extractFitness(event);
  const updatedAgents = state.agents.map((agent) =>
    agent.id === event.workcellId ? { ...agent, fitness } : agent
  );

  const bestFitness = Math.max(
    state.bestFitness,
    ...updatedAgents.map((a) => a.fitness)
  );

  const leadingAgent = updatedAgents.reduce((best, agent) =>
    agent.fitness > best.fitness ? agent : best
  );

  return {
    ...state,
    agents: updatedAgents,
    bestFitness,
    leadingAgentId: leadingAgent.id,
  };
}

/**
 * Handle issue.completed event - mark build as complete
 */
export function handleIssueCompleted(
  state: WorldBuildState,
  event: KernelEvent,
  nextStatus: WorldBuildState["status"]
): WorldBuildState {
  if (event.type !== "issue.completed" || nextStatus !== "complete") return state;

  return {
    ...state,
    status: nextStatus,
    completedAt: state.completedAt ?? Date.now(),
  };
}

/**
 * Handle issue.failed event - mark build as failed
 */
export function handleIssueFailed(
  state: WorldBuildState,
  event: KernelEvent,
  nextStatus: WorldBuildState["status"]
): WorldBuildState {
  if (event.type !== "issue.failed" || nextStatus !== "failed") return state;

  return {
    ...state,
    status: nextStatus,
    error: extractError(event),
  };
}

/**
 * Handle fab.iteration.complete event - increment generation
 */
export function handleIterationComplete(
  state: WorldBuildState,
  event: KernelEvent
): WorldBuildState {
  if (event.type !== "fab.iteration.complete") return state;

  return {
    ...state,
    generation: (state.generation ?? 0) + 1,
  };
}

/**
 * Handle fab.stage.* events - update current stage
 */
export function handleStageChange(
  state: WorldBuildState,
  event: KernelEvent
): WorldBuildState {
  if (!event.type.startsWith("fab.stage.")) return state;

  const stage = event.type.replace("fab.stage.", "");

  // Update agent stage if workcellId present
  let agents = state.agents;
  if (event.workcellId) {
    agents = state.agents.map((agent) =>
      agent.id === event.workcellId ? { ...agent, currentStage: stage } : agent
    );
  }

  return {
    ...state,
    currentStage: stage,
    agents,
  };
}

/**
 * Handle any workcell event - append to agent event log
 */
export function handleWorkcellEvent(
  state: WorldBuildState,
  event: KernelEvent
): WorldBuildState {
  if (!event.workcellId) return state;

  const buildEvent: BuildEvent = {
    id: `${event.type}-${Date.now()}`,
    agentId: event.workcellId,
    type: event.type.includes("error")
      ? "error"
      : event.type.includes("critic")
        ? "critic"
        : event.type.includes("vote")
          ? "vote"
          : "agent",
    message: formatKernelEventMessage(event) ?? event.type,
    timestamp: event.timestamp ? new Date(event.timestamp).getTime() : Date.now(),
    metadata: event.data as Record<string, unknown>,
  };

  return {
    ...state,
    agents: state.agents.map((agent) =>
      agent.id === event.workcellId
        ? { ...agent, events: [...agent.events, buildEvent] }
        : agent
    ),
  };
}

/**
 * Handle preview URL updates from any event
 */
export function handlePreviewUrls(
  state: WorldBuildState,
  event: KernelEvent
): WorldBuildState {
  if (!event.data || typeof event.data !== "object") return state;

  const previewUrls = extractPreviewUrls(event);
  const glbUrl = extractGlbUrl(event);
  const godotUrl = extractGodotUrl(event);

  const hasUpdates =
    Object.keys(previewUrls).length > 0 || glbUrl !== null || godotUrl !== null;

  if (!hasUpdates) return state;

  return {
    ...state,
    previewUrls: {
      ...state.previewUrls,
      ...previewUrls,
    },
    ...(glbUrl && { previewGlbUrl: glbUrl }),
    ...(godotUrl && { previewGodotUrl: godotUrl }),
  };
}

/**
 * Apply status transition from FSM
 */
export function applyStatusTransition(
  state: WorldBuildState,
  nextStatus: WorldBuildState["status"]
): WorldBuildState {
  if (nextStatus === state.status) return state;
  return { ...state, status: nextStatus };
}

/**
 * Compose all updaters for a single event
 */
export function applyEventToState(
  state: WorldBuildState,
  event: KernelEvent,
  nextStatus: WorldBuildState["status"]
): WorldBuildState {
  let updated = state;

  // Apply status transition
  updated = applyStatusTransition(updated, nextStatus);

  // Apply event-specific updates
  updated = handleWorkcellCreated(updated, event);
  updated = handleCriticResult(updated, event);
  updated = handleIssueCompleted(updated, event, nextStatus);
  updated = handleIssueFailed(updated, event, nextStatus);
  updated = handleIterationComplete(updated, event);
  updated = handleStageChange(updated, event);
  updated = handleWorkcellEvent(updated, event);
  updated = handlePreviewUrls(updated, event);

  return updated;
}

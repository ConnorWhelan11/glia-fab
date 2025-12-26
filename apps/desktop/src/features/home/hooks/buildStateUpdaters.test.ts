/**
 * Unit tests for buildStateUpdaters
 *
 * Tests individual state update functions for kernel events.
 */

import { describe, it, expect } from "vitest";
import type { KernelEvent, WorldBuildState, BlueprintDraft } from "@/types";
import {
  handleWorkcellCreated,
  handleCriticResult,
  handleIssueCompleted,
  handleIssueFailed,
  handleIterationComplete,
  handleStageChange,
  handleWorkcellEvent,
  handlePreviewUrls,
  applyStatusTransition,
  applyEventToState,
} from "./buildStateUpdaters";

const createMockBuildState = (overrides?: Partial<WorldBuildState>): WorldBuildState => ({
  issueId: "test-issue-1",
  status: "generating",
  prompt: "Test prompt",
  blueprint: {
    name: "Test",
    runtime: "godot",
    outputs: ["viewer"],
    gates: [],
    tags: [],
  },
  isSpeculating: false,
  agents: [],
  generation: 0,
  bestFitness: 0,
  refinements: [],
  startedAt: Date.now(),
  ...overrides,
});

const createMockEvent = (overrides?: Partial<KernelEvent>): KernelEvent => ({
  id: "event-1",
  type: "telemetry.started",
  timestamp: new Date().toISOString(),
  issueId: "test-issue-1",
  ...overrides,
});

describe("buildStateUpdaters", () => {
  describe("handleWorkcellCreated", () => {
    it("adds a new agent when workcell.created event received", () => {
      const state = createMockBuildState();
      const event = createMockEvent({
        type: "workcell.created",
        workcellId: "wc-123",
        data: { toolchain: "claude" },
      });

      const result = handleWorkcellCreated(state, event);

      expect(result.agents).toHaveLength(1);
      expect(result.agents[0]).toMatchObject({
        id: "wc-123",
        toolchain: "claude",
        status: "running",
        fitness: 0,
      });
    });

    it("marks as speculating when second agent added", () => {
      const state = createMockBuildState({
        agents: [{ id: "wc-1", toolchain: "claude", status: "running", fitness: 0, events: [] }],
      });
      const event = createMockEvent({
        type: "workcell.created",
        workcellId: "wc-2",
        data: { toolchain: "codex" },
      });

      const result = handleWorkcellCreated(state, event);

      expect(result.isSpeculating).toBe(true);
      expect(result.agents).toHaveLength(2);
    });

    it("marks as speculating for spec- prefixed workcell ID", () => {
      const state = createMockBuildState();
      const event = createMockEvent({
        type: "workcell.created",
        workcellId: "spec-wc-123",
        data: { toolchain: "claude" },
      });

      const result = handleWorkcellCreated(state, event);

      expect(result.isSpeculating).toBe(true);
    });

    it("defaults to claude toolchain if not specified", () => {
      const state = createMockBuildState();
      const event = createMockEvent({
        type: "workcell.created",
        workcellId: "wc-123",
        data: {},
      });

      const result = handleWorkcellCreated(state, event);

      expect(result.agents[0].toolchain).toBe("claude");
    });

    it("returns unchanged state for non-workcell.created events", () => {
      const state = createMockBuildState();
      const event = createMockEvent({ type: "other.event" });

      const result = handleWorkcellCreated(state, event);

      expect(result).toBe(state);
    });
  });

  describe("handleCriticResult", () => {
    it("updates agent fitness from critic result", () => {
      const state = createMockBuildState({
        agents: [{ id: "wc-1", toolchain: "claude", status: "running", fitness: 0, events: [] }],
      });
      const event = createMockEvent({
        type: "fab.critic.result",
        workcellId: "wc-1",
        data: { fitness: 0.85 },
      });

      const result = handleCriticResult(state, event);

      expect(result.agents[0].fitness).toBe(0.85);
      expect(result.bestFitness).toBe(0.85);
      expect(result.leadingAgentId).toBe("wc-1");
    });

    it("updates leading agent to highest fitness", () => {
      const state = createMockBuildState({
        agents: [
          { id: "wc-1", toolchain: "claude", status: "running", fitness: 0.8, events: [] },
          { id: "wc-2", toolchain: "codex", status: "running", fitness: 0.6, events: [] },
        ],
        bestFitness: 0.8,
        leadingAgentId: "wc-1",
      });
      const event = createMockEvent({
        type: "fab.critic.result",
        workcellId: "wc-2",
        data: { fitness: 0.9 },
      });

      const result = handleCriticResult(state, event);

      expect(result.leadingAgentId).toBe("wc-2");
      expect(result.bestFitness).toBe(0.9);
    });

    it("returns unchanged state for non-matching workcell", () => {
      const state = createMockBuildState({
        agents: [{ id: "wc-1", toolchain: "claude", status: "running", fitness: 0.5, events: [] }],
      });
      const event = createMockEvent({
        type: "fab.critic.result",
        workcellId: "wc-unknown",
        data: { fitness: 0.9 },
      });

      const result = handleCriticResult(state, event);

      // Agent array is mapped but no changes made to existing agent
      expect(result.agents[0].fitness).toBe(0.5);
    });
  });

  describe("handleIssueCompleted", () => {
    it("sets completedAt timestamp on completion", () => {
      const state = createMockBuildState({ status: "generating" });
      const event = createMockEvent({ type: "issue.completed" });

      const result = handleIssueCompleted(state, event, "complete");

      expect(result.status).toBe("complete");
      expect(result.completedAt).toBeDefined();
      expect(typeof result.completedAt).toBe("number");
    });

    it("preserves existing completedAt if already set", () => {
      const existingTimestamp = Date.now() - 1000;
      const state = createMockBuildState({
        status: "generating",
        completedAt: existingTimestamp,
      });
      const event = createMockEvent({ type: "issue.completed" });

      const result = handleIssueCompleted(state, event, "complete");

      expect(result.completedAt).toBe(existingTimestamp);
    });

    it("returns unchanged state if nextStatus is not complete", () => {
      const state = createMockBuildState();
      const event = createMockEvent({ type: "issue.completed" });

      const result = handleIssueCompleted(state, event, "generating");

      expect(result).toBe(state);
    });
  });

  describe("handleIssueFailed", () => {
    it("sets error message on failure", () => {
      const state = createMockBuildState();
      const event = createMockEvent({
        type: "issue.failed",
        data: { error: "Build timed out" },
      });

      const result = handleIssueFailed(state, event, "failed");

      expect(result.status).toBe("failed");
      expect(result.error).toBe("Build timed out");
    });

    it("uses reason field as fallback error", () => {
      const state = createMockBuildState();
      const event = createMockEvent({
        type: "issue.failed",
        data: { reason: "Gate failed" },
      });

      const result = handleIssueFailed(state, event, "failed");

      expect(result.error).toBe("Gate failed");
    });

    it("uses default error message if none provided", () => {
      const state = createMockBuildState();
      const event = createMockEvent({
        type: "issue.failed",
        data: {},
      });

      const result = handleIssueFailed(state, event, "failed");

      expect(result.error).toBe("Build failed");
    });
  });

  describe("handleIterationComplete", () => {
    it("increments generation counter", () => {
      const state = createMockBuildState({ generation: 3 });
      const event = createMockEvent({ type: "fab.iteration.complete" });

      const result = handleIterationComplete(state, event);

      expect(result.generation).toBe(4);
    });

    it("handles undefined generation", () => {
      const state = createMockBuildState();
      delete (state as any).generation;
      const event = createMockEvent({ type: "fab.iteration.complete" });

      const result = handleIterationComplete(state, event);

      expect(result.generation).toBe(1);
    });
  });

  describe("handleStageChange", () => {
    it("updates currentStage from fab.stage.* event", () => {
      const state = createMockBuildState();
      const event = createMockEvent({ type: "fab.stage.render" });

      const result = handleStageChange(state, event);

      expect(result.currentStage).toBe("render");
    });

    it("updates agent stage when workcellId present", () => {
      const state = createMockBuildState({
        agents: [{ id: "wc-1", toolchain: "claude", status: "running", fitness: 0, events: [] }],
      });
      const event = createMockEvent({
        type: "fab.stage.critics",
        workcellId: "wc-1",
      });

      const result = handleStageChange(state, event);

      expect(result.currentStage).toBe("critics");
      expect(result.agents[0].currentStage).toBe("critics");
    });

    it("returns unchanged state for non-stage events", () => {
      const state = createMockBuildState();
      const event = createMockEvent({ type: "other.event" });

      const result = handleStageChange(state, event);

      expect(result).toBe(state);
    });
  });

  describe("handleWorkcellEvent", () => {
    it("appends event to agent events list", () => {
      const state = createMockBuildState({
        agents: [{ id: "wc-1", toolchain: "claude", status: "running", fitness: 0, events: [] }],
      });
      const event = createMockEvent({
        type: "telemetry.bash_command",
        workcellId: "wc-1",
        data: { command: "npm test" },
      });

      const result = handleWorkcellEvent(state, event);

      expect(result.agents[0].events).toHaveLength(1);
      expect(result.agents[0].events[0].type).toBe("agent");
    });

    it("categorizes error events correctly", () => {
      const state = createMockBuildState({
        agents: [{ id: "wc-1", toolchain: "claude", status: "running", fitness: 0, events: [] }],
      });
      const event = createMockEvent({
        type: "telemetry.error",
        workcellId: "wc-1",
        data: { error: "Something failed" },
      });

      const result = handleWorkcellEvent(state, event);

      expect(result.agents[0].events[0].type).toBe("error");
    });

    it("categorizes critic events correctly", () => {
      const state = createMockBuildState({
        agents: [{ id: "wc-1", toolchain: "claude", status: "running", fitness: 0, events: [] }],
      });
      const event = createMockEvent({
        type: "fab.critic.result",
        workcellId: "wc-1",
        data: { fitness: 0.8 },
      });

      const result = handleWorkcellEvent(state, event);

      expect(result.agents[0].events[0].type).toBe("critic");
    });

    it("returns unchanged state without workcellId", () => {
      const state = createMockBuildState();
      const event = createMockEvent({ type: "system.info" });

      const result = handleWorkcellEvent(state, event);

      expect(result).toBe(state);
    });
  });

  describe("handlePreviewUrls", () => {
    it("extracts preview URLs from event data", () => {
      const state = createMockBuildState();
      const event = createMockEvent({
        type: "fab.stage.complete",
        data: {
          previewUrls: {
            concept: "/previews/concept.png",
            geometry: "/previews/geo.png",
          },
        },
      });

      const result = handlePreviewUrls(state, event);

      expect(result.previewUrls).toEqual({
        concept: "/previews/concept.png",
        geometry: "/previews/geo.png",
      });
    });

    it("extracts GLB URL from various field names", () => {
      const state = createMockBuildState();

      // Test previewGlbUrl
      let event = createMockEvent({
        data: { previewGlbUrl: "/models/preview.glb" },
      });
      let result = handlePreviewUrls(state, event);
      expect(result.previewGlbUrl).toBe("/models/preview.glb");

      // Test glbUrl
      event = createMockEvent({
        data: { glbUrl: "/models/model.glb" },
      });
      result = handlePreviewUrls(state, event);
      expect(result.previewGlbUrl).toBe("/models/model.glb");

      // Test glb_url (snake_case)
      event = createMockEvent({
        data: { glb_url: "/models/snake.glb" },
      });
      result = handlePreviewUrls(state, event);
      expect(result.previewGlbUrl).toBe("/models/snake.glb");
    });

    it("extracts Godot URL from various field names", () => {
      const state = createMockBuildState();

      // Test previewGodotUrl
      let event = createMockEvent({
        data: { previewGodotUrl: "/godot/preview.zip" },
      });
      let result = handlePreviewUrls(state, event);
      expect(result.previewGodotUrl).toBe("/godot/preview.zip");

      // Test godotUrl
      event = createMockEvent({
        data: { godotUrl: "/godot/build.zip" },
      });
      result = handlePreviewUrls(state, event);
      expect(result.previewGodotUrl).toBe("/godot/build.zip");
    });

    it("returns unchanged state if no preview data", () => {
      const state = createMockBuildState();
      const event = createMockEvent({
        data: { someOtherData: true },
      });

      const result = handlePreviewUrls(state, event);

      expect(result).toBe(state);
    });
  });

  describe("applyStatusTransition", () => {
    it("updates status when different", () => {
      const state = createMockBuildState({ status: "generating" });

      const result = applyStatusTransition(state, "rendering");

      expect(result.status).toBe("rendering");
    });

    it("returns same state if status unchanged", () => {
      const state = createMockBuildState({ status: "generating" });

      const result = applyStatusTransition(state, "generating");

      expect(result).toBe(state);
    });
  });

  describe("applyEventToState", () => {
    it("composes all updaters for a single event", () => {
      const state = createMockBuildState();
      const event = createMockEvent({
        type: "workcell.created",
        workcellId: "wc-1",
        data: {
          toolchain: "claude",
          previewUrls: { concept: "/preview.png" },
        },
      });

      const result = applyEventToState(state, event, "generating");

      // Should have applied workcell creation
      expect(result.agents).toHaveLength(1);
      expect(result.agents[0].id).toBe("wc-1");

      // Should have applied preview URLs
      expect(result.previewUrls?.concept).toBe("/preview.png");

      // Should have applied workcell event (appended to events)
      expect(result.agents[0].events).toHaveLength(1);
    });

    it("handles issue.completed event composition", () => {
      const state = createMockBuildState({
        agents: [{ id: "wc-1", toolchain: "claude", status: "running", fitness: 0.9, events: [] }],
        bestFitness: 0.9,
      });
      const event = createMockEvent({
        type: "issue.completed",
        workcellId: "wc-1",
      });

      const result = applyEventToState(state, event, "complete");

      expect(result.status).toBe("complete");
      expect(result.completedAt).toBeDefined();
    });

    it("handles issue.failed event composition", () => {
      const state = createMockBuildState();
      const event = createMockEvent({
        type: "issue.failed",
        data: { error: "Gate check failed" },
      });

      const result = applyEventToState(state, event, "failed");

      expect(result.status).toBe("failed");
      expect(result.error).toBe("Gate check failed");
    });
  });
});

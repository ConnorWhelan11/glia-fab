/**
 * Tests for useWorldBuilder hook
 *
 * Tests kernel integration, build state management, and refinement flow.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWorldBuilder } from "./useWorldBuilder";
import { mockTauriInvoke, clearTauriMocks } from "@/test/mockTauri";

// Mock templates
vi.mock("./templates", () => ({
  WORLD_TEMPLATES: [
    {
      id: "test-template",
      title: "Test Template",
      description: "A test template",
      icon: "\uD83E\uDDEA",
      promptText: "Test prompt text",
      blueprintDefaults: {
        runtime: "three",
        outputs: ["viewer"],
        gates: [],
        tags: [],
      },
      previewBullets: ["Test bullet"],
    },
  ],
}));

describe("useWorldBuilder", () => {
  beforeEach(() => {
    clearTauriMocks();
    // Clear localStorage
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Initial State", () => {
    it("should have correct initial state", () => {
      const { result } = renderHook(() => useWorldBuilder());

      expect(result.current.promptText).toBe("");
      expect(result.current.consoleFocused).toBe(false);
      expect(result.current.blueprintDraft).toEqual({
        name: "",
        runtime: "three",
        outputs: ["viewer"],
        gates: [],
        tags: [],
      });
      expect(result.current.selectedTemplateId).toBeNull();
      expect(result.current.submitState).toBe("idle");
      expect(result.current.activeWorldBuild).toBeNull();
      expect(result.current.isBuilding).toBe(false);
      expect(result.current.canSubmit).toBe(false);
    });

    it("should report hasKernelIntegration when projectRoot is provided", () => {
      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      expect(result.current.hasKernelIntegration).toBe(true);
    });

    it("should report no kernel integration without projectRoot", () => {
      const { result } = renderHook(() => useWorldBuilder());

      expect(result.current.hasKernelIntegration).toBe(false);
    });
  });

  describe("Prompt Management", () => {
    it("should update prompt text", () => {
      const { result } = renderHook(() => useWorldBuilder());

      act(() => {
        result.current.setPromptText("A cozy reading nook");
      });

      expect(result.current.promptText).toBe("A cozy reading nook");
    });

    it("should enable submit when prompt is non-empty", () => {
      const { result } = renderHook(() => useWorldBuilder());

      expect(result.current.canSubmit).toBe(false);

      act(() => {
        result.current.setPromptText("Test prompt");
      });

      expect(result.current.canSubmit).toBe(true);
    });

    it("should disable submit when prompt is only whitespace", () => {
      const { result } = renderHook(() => useWorldBuilder());

      act(() => {
        result.current.setPromptText("   \n\t  ");
      });

      expect(result.current.canSubmit).toBe(false);
    });
  });

  describe("Blueprint Management", () => {
    it("should update blueprint with partial updates", () => {
      const { result } = renderHook(() => useWorldBuilder());

      act(() => {
        result.current.updateBlueprint({ name: "My World" });
      });

      expect(result.current.blueprintDraft.name).toBe("My World");
      expect(result.current.blueprintDraft.runtime).toBe("three");
    });

    it("should update runtime in blueprint", () => {
      const { result } = renderHook(() => useWorldBuilder());

      act(() => {
        result.current.updateBlueprint({ runtime: "godot" });
      });

      expect(result.current.blueprintDraft.runtime).toBe("godot");
    });

    it("should reset blueprint to defaults", () => {
      const { result } = renderHook(() => useWorldBuilder());

      act(() => {
        result.current.updateBlueprint({
          name: "Modified",
          runtime: "godot",
          tags: ["custom"],
        });
      });

      act(() => {
        result.current.resetBlueprint();
      });

      expect(result.current.blueprintDraft).toEqual({
        name: "",
        runtime: "three",
        outputs: ["viewer"],
        gates: [],
        tags: [],
      });
    });
  });

  describe("Template Selection", () => {
    it("should select a template and apply its settings", () => {
      const { result } = renderHook(() => useWorldBuilder());

      act(() => {
        result.current.selectTemplate("test-template");
      });

      expect(result.current.selectedTemplateId).toBe("test-template");
      expect(result.current.promptText).toBe("Test prompt text");
      expect(result.current.builderMode).toBe("template");
    });

    it("should clear template and return to scratch mode", () => {
      const { result } = renderHook(() => useWorldBuilder());

      act(() => {
        result.current.selectTemplate("test-template");
      });

      act(() => {
        result.current.selectTemplate(null);
      });

      expect(result.current.selectedTemplateId).toBeNull();
      expect(result.current.builderMode).toBe("scratch");
    });
  });

  describe("Recent Worlds", () => {
    it("should add recent world", () => {
      const { result } = renderHook(() => useWorldBuilder());

      act(() => {
        result.current.addRecentWorld({
          id: "world-1",
          name: "Test World",
          status: "complete",
          lastPrompt: "Test prompt",
          updatedAt: Date.now(),
        });
      });

      expect(result.current.recentWorlds).toHaveLength(1);
      expect(result.current.recentWorlds[0].name).toBe("Test World");
    });

    it("should update recent world", () => {
      const { result } = renderHook(() => useWorldBuilder());

      act(() => {
        result.current.addRecentWorld({
          id: "world-1",
          name: "Test World",
          status: "building",
          lastPrompt: "Test prompt",
          updatedAt: Date.now() - 1000,
        });
      });

      act(() => {
        result.current.updateRecentWorld("world-1", { status: "complete", fitness: 0.9 });
      });

      expect(result.current.recentWorlds[0].status).toBe("complete");
      expect(result.current.recentWorlds[0].fitness).toBe(0.9);
    });

    it("should remove recent world", () => {
      const { result } = renderHook(() => useWorldBuilder());

      act(() => {
        result.current.addRecentWorld({
          id: "world-1",
          name: "Test World",
          status: "complete",
          lastPrompt: "Test",
          updatedAt: Date.now(),
        });
      });

      act(() => {
        result.current.removeRecentWorld("world-1");
      });

      expect(result.current.recentWorlds).toHaveLength(0);
    });

    it("should track most recent world", () => {
      const { result } = renderHook(() => useWorldBuilder());
      const now = Date.now();

      act(() => {
        result.current.addRecentWorld({
          id: "world-1",
          name: "Old World",
          status: "complete",
          lastPrompt: "Old",
          updatedAt: now - 10000,
        });
        result.current.addRecentWorld({
          id: "world-2",
          name: "New World",
          status: "complete",
          lastPrompt: "New",
          updatedAt: now,
        });
      });

      expect(result.current.mostRecentWorld?.id).toBe("world-2");
    });
  });

  describe("World Creation - Mock Mode", () => {
    it("should fail if prompt is empty", async () => {
      const { result } = renderHook(() => useWorldBuilder());

      let issueId: string | null = null;
      await act(async () => {
        issueId = await result.current.createWorld();
      });

      expect(issueId).toBeNull();
      expect(result.current.submitError).toBe("Please describe your world");
    });

    it("should create world in mock mode without projectRoot", async () => {
      vi.useFakeTimers();
      const { result } = renderHook(() => useWorldBuilder());

      act(() => {
        result.current.setPromptText("A cozy reading nook");
      });

      let issueId: string | null = null;
      await act(async () => {
        const promise = result.current.createWorld();
        vi.advanceTimersByTime(800);
        issueId = await promise;
      });

      expect(issueId).toMatch(/^world-/);
      expect(result.current.submitState).toBe("success");
      expect(result.current.activeWorldBuild).not.toBeNull();
      expect(result.current.recentWorlds).toHaveLength(1);

      act(() => {
        vi.advanceTimersByTime(900);
      });

      expect(result.current.submitState).toBe("idle");
      vi.useRealTimers();
    });
  });

  describe("World Creation - Kernel Integration", () => {
    it("should create issue via Tauri when projectRoot provided", async () => {
      const mockIssue = { id: "issue-123", title: "Test World" };
      const invokeMock = mockTauriInvoke({
        beads_create_issue: mockIssue,
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("A futuristic command center");
        result.current.updateBlueprint({ name: "Command Center", runtime: "godot" });
      });

      let issueId: string | null = null;
      await act(async () => {
        issueId = await result.current.createWorld();
      });

      expect(issueId).toBe("issue-123");
      // Service layer wraps params in { params: {...} }
      expect(invokeMock).toHaveBeenCalledWith("beads_create_issue", {
        params: expect.objectContaining({
          projectRoot: "/test/project",
          title: "Command Center",
          description: "A futuristic command center",
          tags: expect.arrayContaining(["asset:world", "runtime:godot", "gate:godot"]),
          dkPriority: "P1",
          dkRisk: "medium",
        }),
      });
      expect(result.current.activeWorldBuild).not.toBeNull();
      expect(result.current.activeWorldBuild?.status).toBe("queued");
    });

    it("should handle kernel error gracefully", async () => {
      mockTauriInvoke({
        beads_create_issue: () => Promise.reject(new Error("Kernel unavailable")),
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test prompt");
      });

      await act(async () => {
        await result.current.createWorld();
      });

      expect(result.current.submitState).toBe("error");
      expect(result.current.submitError).toBe("Kernel unavailable");
    });
  });

  describe("Build Lifecycle", () => {
    it("should start world build via kernel", async () => {
      const invokeMock = mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
        job_start: { jobId: "job-456", runId: "run-789" },
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test world");
      });

      await act(async () => {
        const issueId = await result.current.createWorld();
        if (issueId) {
          await result.current.startWorldBuild(issueId);
        }
      });

      expect(invokeMock).toHaveBeenCalledWith("job_start", {
        params: expect.objectContaining({
          projectRoot: "/test/project",
          command: "cyntra run --once --issue issue-123",
        }),
      });
      expect(result.current.activeWorldBuild?.runId).toBe("run-789");
      expect(result.current.activeWorldBuild?.status).toBe("scheduling");
    });

    it("should handle start build error", async () => {
      mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
        job_start: () => Promise.reject(new Error("Job failed to start")),
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test world");
      });

      await act(async () => {
        const issueId = await result.current.createWorld();
        if (issueId) {
          await result.current.startWorldBuild(issueId);
        }
      });

      expect(result.current.activeWorldBuild?.status).toBe("failed");
      // Error message is from the thrown error, not a generic message
      expect(result.current.activeWorldBuild?.error).toBe("Job failed to start");
    });

    it("should not start build without projectRoot", async () => {
      const consoleWarn = vi.spyOn(console, "warn").mockImplementation(() => {});

      const { result } = renderHook(() => useWorldBuilder());

      await act(async () => {
        await result.current.startWorldBuild("issue-123");
      });

      expect(consoleWarn).toHaveBeenCalledWith("Cannot start world build without projectRoot");
      consoleWarn.mockRestore();
    });

    it("should cancel build and update recent world", async () => {
      const invokeMock = mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
        job_start: { jobId: "job-456", runId: "run-789" },
        job_kill: true,
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test world");
      });

      await act(async () => {
        const issueId = await result.current.createWorld();
        if (issueId) {
          await result.current.startWorldBuild(issueId);
        }
      });

      expect(result.current.isBuilding).toBe(true);

      await act(async () => {
        await result.current.cancelWorldBuild();
      });

      expect(invokeMock).toHaveBeenCalledWith("job_kill", { params: { jobId: "job-456" } });
      expect(result.current.activeWorldBuild).toBeNull();
      expect(result.current.recentWorlds[0].status).toBe("canceled");
    });

    it("should pause build", async () => {
      const invokeMock = mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
        job_start: { jobId: "job-456", runId: "run-789" },
        job_kill: true,
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test world");
      });

      await act(async () => {
        const issueId = await result.current.createWorld();
        if (issueId) {
          await result.current.startWorldBuild(issueId);
        }
      });

      await act(async () => {
        await result.current.pauseWorldBuild();
      });

      expect(invokeMock).toHaveBeenCalledWith("job_kill", { params: { jobId: "job-456" } });
      expect(result.current.activeWorldBuild?.status).toBe("paused");
    });
  });

  describe("Kernel Event Processing", () => {
    it("should update status based on events", async () => {
      mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test");
      });

      await act(async () => {
        await result.current.createWorld();
      });

      act(() => {
        result.current.processKernelEvents([
          {
            type: "fab.stage.render",
            issueId: "issue-123",
            data: {},
            timestamp: new Date().toISOString(),
          },
        ]);
      });

      expect(result.current.activeWorldBuild?.status).toBe("rendering");
    });

    it("should track workcell agents", async () => {
      mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test");
      });

      await act(async () => {
        await result.current.createWorld();
      });

      act(() => {
        result.current.processKernelEvents([
          {
            type: "workcell.created",
            issueId: "issue-123",
            workcellId: "wc-spec-claude",
            data: { toolchain: "claude" },
            timestamp: new Date().toISOString(),
          },
        ]);
      });

      expect(result.current.activeWorldBuild?.agents).toHaveLength(1);
      expect(result.current.activeWorldBuild?.agents[0].toolchain).toBe("claude");
    });

    it("should update agent fitness from critic events", async () => {
      mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test");
      });

      await act(async () => {
        await result.current.createWorld();
      });

      act(() => {
        result.current.processKernelEvents([
          {
            type: "workcell.created",
            issueId: "issue-123",
            workcellId: "wc-001",
            data: { toolchain: "claude" },
            timestamp: new Date().toISOString(),
          },
        ]);
      });

      act(() => {
        result.current.processKernelEvents([
          {
            type: "fab.critic.result",
            issueId: "issue-123",
            workcellId: "wc-001",
            data: { fitness: 0.85 },
            timestamp: new Date().toISOString(),
          },
        ]);
      });

      expect(result.current.activeWorldBuild?.agents[0].fitness).toBe(0.85);
      expect(result.current.activeWorldBuild?.bestFitness).toBe(0.85);
      expect(result.current.activeWorldBuild?.leadingAgentId).toBe("wc-001");
    });

    it("should handle completion event", async () => {
      mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test");
      });

      await act(async () => {
        await result.current.createWorld();
      });

      act(() => {
        result.current.processKernelEvents([
          {
            type: "issue.completed",
            issueId: "issue-123",
            data: {},
            timestamp: new Date().toISOString(),
          },
        ]);
      });

      expect(result.current.activeWorldBuild?.status).toBe("complete");
      expect(result.current.activeWorldBuild?.completedAt).toBeDefined();
      expect(result.current.recentWorlds[0].status).toBe("complete");
    });

    it("should handle failure event", async () => {
      mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test");
      });

      await act(async () => {
        await result.current.createWorld();
      });

      act(() => {
        result.current.processKernelEvents([
          {
            type: "issue.failed",
            issueId: "issue-123",
            data: { error: "Max iterations exceeded" },
            timestamp: new Date().toISOString(),
          },
        ]);
      });

      expect(result.current.activeWorldBuild?.status).toBe("failed");
      expect(result.current.activeWorldBuild?.error).toBe("Max iterations exceeded");
    });

    it("should ignore events for other issues", async () => {
      mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test");
      });

      await act(async () => {
        await result.current.createWorld();
      });

      const initialStatus = result.current.activeWorldBuild?.status;

      act(() => {
        result.current.processKernelEvents([
          {
            type: "fab.stage.render",
            issueId: "other-issue",
            data: {},
            timestamp: new Date().toISOString(),
          },
        ]);
      });

      expect(result.current.activeWorldBuild?.status).toBe(initialStatus);
    });

    it("should call onKernelEvents callback", async () => {
      const onKernelEvents = vi.fn();
      mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project", onKernelEvents })
      );

      act(() => {
        result.current.setPromptText("Test");
      });

      await act(async () => {
        await result.current.createWorld();
      });

      const events = [
        {
          type: "fab.stage.render",
          issueId: "issue-123",
          data: {},
          timestamp: new Date().toISOString(),
        },
      ];

      act(() => {
        result.current.processKernelEvents(events);
      });

      expect(onKernelEvents).toHaveBeenCalledWith(events);
    });
  });

  describe("Refinements", () => {
    it("should queue refinement", async () => {
      mockTauriInvoke({
        beads_create_issue: (args: any) => {
          // args is { params: { ... } } due to service layer wrapping
          const tags = args?.params?.tags || [];
          if (tags.includes("refinement")) {
            return Promise.resolve({ id: "ref-issue-456" });
          }
          return Promise.resolve({ id: "issue-123" });
        },
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test");
      });

      await act(async () => {
        await result.current.createWorld();
      });

      await act(async () => {
        await result.current.queueRefinement("Add a potted plant");
      });

      expect(result.current.activeWorldBuild?.refinements).toHaveLength(1);
      expect(result.current.activeWorldBuild?.refinements[0].text).toBe("Add a potted plant");
      expect(result.current.activeWorldBuild?.refinements[0].status).toBe("queued");
      expect(result.current.activeWorldBuild?.refinements[0].issueId).toBe("ref-issue-456");
    });

    it("should not queue refinement without active build", async () => {
      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      await act(async () => {
        await result.current.queueRefinement("Add something");
      });

      // Should not throw, just return early
    });

    it("should apply refinement immediately", async () => {
      const invokeMock = mockTauriInvoke({
        beads_create_issue: (args: any) => {
          const tags = args?.params?.tags || [];
          if (tags.includes("refinement")) {
            return Promise.resolve({ id: "ref-issue-456" });
          }
          return Promise.resolve({ id: "issue-123" });
        },
        job_start: { jobId: "job-789", runId: "run-101" },
        job_kill: true,
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test");
      });

      await act(async () => {
        const issueId = await result.current.createWorld();
        if (issueId) await result.current.startWorldBuild(issueId);
      });

      await act(async () => {
        await result.current.queueRefinement("Make it brighter");
      });

      const refId = result.current.activeWorldBuild?.refinements[0].id;

      await act(async () => {
        await result.current.applyRefinementNow(refId!);
      });

      // applyRefinementNow cancels current build, then starts new one
      // Verify job_kill was called to cancel current build
      expect(invokeMock).toHaveBeenCalledWith("job_kill", { params: { jobId: "job-789" } });

      // Verify job_start was called for the refinement issue
      expect(invokeMock).toHaveBeenCalledWith("job_start", {
        params: expect.objectContaining({
          command: "cyntra run --once --issue ref-issue-456",
        }),
      });
    });
  });

  describe("Submit State Management", () => {
    it("should reset submit state", async () => {
      vi.useFakeTimers();
      mockTauriInvoke({
        beads_create_issue: { id: "issue-123" },
      });

      const { result } = renderHook(() =>
        useWorldBuilder({ projectRoot: "/test/project" })
      );

      act(() => {
        result.current.setPromptText("Test");
      });

      await act(async () => {
        await result.current.createWorld();
      });

      expect(result.current.submitState).toBe("success");

      act(() => {
        result.current.resetSubmitState();
      });

      expect(result.current.submitState).toBe("idle");
      expect(result.current.submitError).toBeNull();

      vi.useRealTimers();
    });
  });

  describe("Motion Preference", () => {
    it("should detect reduced motion preference", () => {
      // matchMedia is mocked in setup.ts
      const { result } = renderHook(() => useWorldBuilder());

      expect(typeof result.current.prefersReducedMotion).toBe("boolean");
    });
  });
});

/**
 * Integration tests for HomeWorldBuilderView
 *
 * Tests the conditional rendering between world builder console and building console.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HomeWorldBuilderView } from "./HomeWorldBuilderView";
import { mockTauriInvoke, clearTauriMocks } from "@/test/mockTauri";

// Ensure matchMedia is mocked
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock child components to simplify testing
vi.mock("./WorldBuilderConsole", () => ({
  WorldBuilderConsole: ({
    promptText,
    onPromptChange,
    onSubmit,
    isSubmitting,
    canSubmit,
  }: any) => (
    <div data-testid="world-builder-console">
      <textarea
        data-testid="prompt-input"
        value={promptText}
        onChange={(e) => onPromptChange(e.target.value)}
        disabled={isSubmitting}
      />
      <button
        data-testid="create-world-btn"
        onClick={onSubmit}
        disabled={!canSubmit || isSubmitting}
      >
        {isSubmitting ? "Creating..." : "Create World"}
      </button>
    </div>
  ),
}));

vi.mock("./TemplateGallery", () => ({
  TemplateGallery: () => <div data-testid="template-gallery">Templates</div>,
}));

vi.mock("./RecentWorldsRow", () => ({
  RecentWorldsRow: ({ worlds, onResume }: any) => (
    <div data-testid="recent-worlds-row" data-count={worlds.length}>
      {worlds.map((w: any) => (
        <button key={w.id} onClick={() => onResume(w)}>
          {w.name}
        </button>
      ))}
    </div>
  ),
}));

vi.mock("./BuildingConsole", () => ({
  BuildingConsole: ({
    buildState,
    onCancel,
    onViewInEvolution,
  }: any) => (
    <div data-testid="building-console" data-status={buildState.status}>
      <span data-testid="build-prompt">{buildState.prompt}</span>
      <button data-testid="cancel-btn" onClick={onCancel}>
        Cancel
      </button>
      <button
        data-testid="view-evolution-btn"
        onClick={() => onViewInEvolution?.()}
      >
        View in Evolution
      </button>
    </div>
  ),
}));

// Mock templates
vi.mock("./templates", () => ({
  WORLD_TEMPLATES: [],
}));

describe("HomeWorldBuilderView", () => {
  beforeEach(() => {
    clearTauriMocks();
    localStorage.clear();
  });

  describe("Initial Render", () => {
    it("should render WorldBuilderConsole by default", () => {
      render(<HomeWorldBuilderView />);

      expect(screen.getByTestId("world-builder-console")).toBeInTheDocument();
    });

    it("should render TemplateGallery", () => {
      render(<HomeWorldBuilderView />);

      expect(screen.getByTestId("template-gallery")).toBeInTheDocument();
    });

    it("should not render RecentWorldsRow when no recent worlds", () => {
      render(<HomeWorldBuilderView />);

      expect(screen.queryByTestId("recent-worlds-row")).not.toBeInTheDocument();
    });

    it("should not render BuildingConsole initially", () => {
      render(<HomeWorldBuilderView />);

      expect(screen.queryByTestId("building-console")).not.toBeInTheDocument();
    });
  });

  describe("World Builder Console Interaction", () => {
    it("should update prompt text", async () => {
      const user = userEvent.setup();
      render(<HomeWorldBuilderView />);

      const input = screen.getByTestId("prompt-input");
      await user.type(input, "A cozy room");

      expect(input).toHaveValue("A cozy room");
    });

    it("should enable create button when prompt is entered", async () => {
      const user = userEvent.setup();
      render(<HomeWorldBuilderView projectRoot="/test/project" />);

      const input = screen.getByTestId("prompt-input");
      const button = screen.getByTestId("create-world-btn");

      expect(button).toBeDisabled();

      await user.type(input, "Test prompt");

      expect(button).not.toBeDisabled();
    });
  });

  describe("World Creation - Kernel Mode", () => {
    it("should create issue and show building console", async () => {
      mockTauriInvoke({
        beads_create_issue: { id: "issue-123", title: "Test World" },
        job_start: { jobId: "job-456", runId: "run-789" },
        start_event_watcher: undefined,
        stop_event_watcher: undefined,
      });

      const user = userEvent.setup();
      render(<HomeWorldBuilderView projectRoot="/test/project" />);

      const input = screen.getByTestId("prompt-input");
      await user.type(input, "A medieval castle");

      const button = screen.getByTestId("create-world-btn");
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByTestId("building-console")).toBeInTheDocument();
      }, { timeout: 2000 });
    });
  });

  describe("CSS Classes", () => {
    it("should have home-world-builder class", () => {
      const { container } = render(<HomeWorldBuilderView />);

      expect(container.firstChild).toHaveClass("home-world-builder");
    });
  });

  describe("Data Attributes", () => {
    it("should set data-submit-state on container", () => {
      const { container } = render(<HomeWorldBuilderView />);

      expect(container.firstChild).toHaveAttribute("data-submit-state", "idle");
    });
  });

  describe("Recent Worlds", () => {
    it("should show RecentWorldsRow when recent worlds exist in localStorage", async () => {
      // Pre-populate localStorage with recent worlds
      localStorage.setItem(
        "cyntra:recent-worlds",
        JSON.stringify([
          {
            id: "world-1",
            name: "Previous World",
            status: "complete",
            lastPrompt: "Old prompt",
            updatedAt: Date.now(),
          },
        ])
      );

      render(<HomeWorldBuilderView />);

      // Need to wait for useEffect to load from localStorage
      await waitFor(() => {
        expect(screen.getByTestId("recent-worlds-row")).toBeInTheDocument();
      });
    });

    it("should open the building console when resuming a world", async () => {
      localStorage.setItem(
        "cyntra:recent-worlds",
        JSON.stringify([
          {
            id: "world-existing",
            name: "Existing World",
            status: "complete",
            lastPrompt: "Test",
            updatedAt: Date.now(),
          },
        ])
      );

      const user = userEvent.setup();
      render(<HomeWorldBuilderView projectRoot="/test/project" />);

      await waitFor(() => {
        expect(screen.getByText("Existing World")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Existing World"));

      expect(screen.getByTestId("building-console")).toBeInTheDocument();
      expect(screen.getByTestId("build-prompt")).toHaveTextContent("Test");
      expect(screen.getByTestId("building-console")).toHaveAttribute("data-status", "complete");
    });
  });

  describe("Cancel Build", () => {
    it("should return to WorldBuilderConsole after cancel", async () => {
      mockTauriInvoke({
        beads_create_issue: { id: "issue-123", title: "Test" },
        job_start: { jobId: "job-456", runId: "run-789" },
        job_kill: true,
        start_event_watcher: undefined,
        stop_event_watcher: undefined,
      });

      const user = userEvent.setup();
      render(<HomeWorldBuilderView projectRoot="/test/project" />);

      await user.type(screen.getByTestId("prompt-input"), "Test");
      await user.click(screen.getByTestId("create-world-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("building-console")).toBeInTheDocument();
      }, { timeout: 2000 });

      await user.click(screen.getByTestId("cancel-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("world-builder-console")).toBeInTheDocument();
        expect(screen.queryByTestId("building-console")).not.toBeInTheDocument();
      });
    });
  });

  describe("Navigation to Evolution", () => {
    it("should call onNavigateToWorld from building console", async () => {
      const onNavigateToWorld = vi.fn();

      mockTauriInvoke({
        beads_create_issue: { id: "issue-xyz", title: "Test" },
        job_start: { jobId: "job-1", runId: "run-1" },
        start_event_watcher: undefined,
        stop_event_watcher: undefined,
      });

      const user = userEvent.setup();
      render(
        <HomeWorldBuilderView
          projectRoot="/test/project"
          onNavigateToWorld={onNavigateToWorld}
        />
      );

      await user.type(screen.getByTestId("prompt-input"), "Test");
      await user.click(screen.getByTestId("create-world-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("building-console")).toBeInTheDocument();
      }, { timeout: 2000 });

      await user.click(screen.getByTestId("view-evolution-btn"));

      expect(onNavigateToWorld).toHaveBeenCalledWith("issue-xyz");
    });
  });
});

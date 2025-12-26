/**
 * Unit tests for usePlaytestStateMachine
 *
 * Tests FSM transitions for playtest status.
 */

import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { usePlaytestStateMachine } from "./usePlaytestStateMachine";

describe("usePlaytestStateMachine", () => {
  describe("transitionStatus", () => {
    it("allows idle -> running", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.transitionStatus("idle", "running")).toBe("running");
    });

    it("allows idle -> passed (direct pass)", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.transitionStatus("idle", "passed")).toBe("passed");
    });

    it("allows idle -> failed (direct fail)", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.transitionStatus("idle", "failed")).toBe("failed");
    });

    it("allows running -> passed", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.transitionStatus("running", "passed")).toBe("passed");
    });

    it("allows running -> failed", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.transitionStatus("running", "failed")).toBe("failed");
    });

    it("blocks running -> idle (must go through terminal)", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.transitionStatus("running", "idle")).toBe("running");
    });

    it("allows passed -> idle (reset for re-run)", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.transitionStatus("passed", "idle")).toBe("idle");
    });

    it("allows failed -> idle (reset for retry)", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.transitionStatus("failed", "idle")).toBe("idle");
    });

    it("blocks passed -> running (must reset first)", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.transitionStatus("passed", "running")).toBe("passed");
    });

    it("blocks failed -> running (must reset first)", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.transitionStatus("failed", "running")).toBe("failed");
    });

    it("returns same status for self-transition", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.transitionStatus("running", "running")).toBe("running");
      expect(result.current.transitionStatus("idle", "idle")).toBe("idle");
    });
  });

  describe("applyPlaytestEvent", () => {
    it("handles playtest.started event", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.applyPlaytestEvent("idle", "playtest.started")).toBe("running");
    });

    it("handles playtest.passed event", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.applyPlaytestEvent("running", "playtest.passed")).toBe("passed");
    });

    it("handles playtest.failed event", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.applyPlaytestEvent("running", "playtest.failed")).toBe("failed");
    });

    it("handles playtest.reset event", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.applyPlaytestEvent("passed", "playtest.reset")).toBe("idle");
      expect(result.current.applyPlaytestEvent("failed", "playtest.reset")).toBe("idle");
    });

    it("ignores unknown events", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.applyPlaytestEvent("running", "unknown.event" as any)).toBe("running");
    });
  });

  describe("statusForEvent", () => {
    it("maps playtest events to statuses", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());

      expect(result.current.statusForEvent("playtest.started")).toBe("running");
      expect(result.current.statusForEvent("playtest.passed")).toBe("passed");
      expect(result.current.statusForEvent("playtest.failed")).toBe("failed");
      expect(result.current.statusForEvent("playtest.reset")).toBe("idle");
    });

    it("returns null for unknown events", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.statusForEvent("unknown.event")).toBeNull();
    });
  });

  describe("canTransition", () => {
    it("returns true for valid transitions", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());

      expect(result.current.canTransition("idle", "running")).toBe(true);
      expect(result.current.canTransition("running", "passed")).toBe(true);
      expect(result.current.canTransition("running", "failed")).toBe(true);
      expect(result.current.canTransition("passed", "idle")).toBe(true);
      expect(result.current.canTransition("failed", "idle")).toBe(true);
    });

    it("returns false for invalid transitions", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());

      expect(result.current.canTransition("passed", "running")).toBe(false);
      expect(result.current.canTransition("failed", "running")).toBe(false);
      expect(result.current.canTransition("running", "idle")).toBe(false);
    });

    it("returns true for self-transitions", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());

      expect(result.current.canTransition("idle", "idle")).toBe(true);
      expect(result.current.canTransition("running", "running")).toBe(true);
    });
  });

  describe("isTerminal", () => {
    it("identifies passed as terminal", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.isTerminal("passed")).toBe(true);
    });

    it("identifies failed as terminal", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.isTerminal("failed")).toBe(true);
    });

    it("identifies idle as non-terminal", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.isTerminal("idle")).toBe(false);
    });

    it("identifies running as non-terminal", () => {
      const { result } = renderHook(() => usePlaytestStateMachine());
      expect(result.current.isTerminal("running")).toBe(false);
    });
  });
});

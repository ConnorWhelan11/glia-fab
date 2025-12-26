import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useBuildStateMachine } from "../useBuildStateMachine";

describe("useBuildStateMachine", () => {
  it("should advance from rendering to critiquing", () => {
    const { result } = renderHook(() => useBuildStateMachine());

    const next = result.current.applyKernelEvent("rendering", "fab.stage.critics");

    expect(next).toBe("critiquing");
  });

  it("should allow repair to loop back to critiquing", () => {
    const { result } = renderHook(() => useBuildStateMachine());

    const next = result.current.applyKernelEvent("repairing", "fab.stage.critics");

    expect(next).toBe("critiquing");
  });

  it("should ignore kernel events once complete", () => {
    const { result } = renderHook(() => useBuildStateMachine());

    const next = result.current.applyKernelEvent("complete", "fab.stage.render");

    expect(next).toBe("complete");
  });

  it("should keep paused status on non-terminal events", () => {
    const { result } = renderHook(() => useBuildStateMachine());

    const next = result.current.applyKernelEvent("paused", "fab.stage.render");

    expect(next).toBe("paused");
  });

  it("should allow terminal events while paused", () => {
    const { result } = renderHook(() => useBuildStateMachine());

    const next = result.current.applyKernelEvent("paused", "issue.failed");

    expect(next).toBe("failed");
  });

  it("should ignore unknown events", () => {
    const { result } = renderHook(() => useBuildStateMachine());

    const next = result.current.applyKernelEvent("generating", "unknown.event");

    expect(next).toBe("generating");
  });
});

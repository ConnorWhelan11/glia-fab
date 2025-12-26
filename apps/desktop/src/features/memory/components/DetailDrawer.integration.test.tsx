import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { MemoryItem } from "@/types";
import { MemoryAtlasContext, useMemoryAtlas } from "../hooks/useMemoryAtlas";
import { DetailDrawer } from "./DetailDrawer";

function Harness({ memories }: { memories: MemoryItem[] }) {
  const ctx = useMemoryAtlas(memories, { layout: "lifecycle" });
  return (
    <MemoryAtlasContext.Provider value={ctx}>
      <button type="button" onClick={() => ctx.actions.selectMemory(memories[0].id)}>
        Select First
      </button>
      <DetailDrawer />
    </MemoryAtlasContext.Provider>
  );
}

describe("Memory detail integration", () => {
  it("selecting a tile updates detail drawer and shows links", async () => {
    const user = userEvent.setup();

    const memories: MemoryItem[] = [
      {
        id: "mem-a",
        type: "pattern",
        agent: "claude",
        scope: "collective",
        importance: 0.9,
        content: "Alpha memory",
        sourceRun: "001",
        accessCount: 3,
        createdAt: "Run #001",
        links: [{ type: "supersedes", targetId: "mem-b", targetTitle: "Beta memory" }],
      },
      {
        id: "mem-b",
        type: "pattern",
        agent: "claude",
        scope: "collective",
        importance: 0.6,
        content: "Beta memory",
        sourceRun: "000",
        accessCount: 1,
        createdAt: "Run #000",
      },
    ];

    render(<Harness memories={memories} />);

    expect(screen.getByText("Select a memory from the atlas")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Select First" }));

    // Component uses curly quotes (&ldquo; &rdquo;) which render as " and "
    expect(screen.getByText(/Alpha memory/)).toBeInTheDocument();
    expect(screen.getByText(/Connections/)).toBeInTheDocument();
    expect(screen.getByText(/Supersedes/)).toBeInTheDocument();
    expect(screen.getByText(/Beta memory/)).toBeInTheDocument();
  });
});


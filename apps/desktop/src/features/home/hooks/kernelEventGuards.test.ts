/**
 * Unit tests for kernelEventGuards
 *
 * Tests type guards and safe data extractors for kernel events.
 */

import { describe, it, expect } from "vitest";
import type { KernelEvent } from "@/types";
import {
  hasToolchain,
  hasFitness,
  hasError,
  hasPreviewUrls,
  extractToolchain,
  extractFitness,
  extractError,
  extractPreviewUrls,
  extractGlbUrl,
  extractGodotUrl,
} from "./kernelEventGuards";

const createMockEvent = (data: unknown): KernelEvent => ({
  id: "event-1",
  type: "test.event",
  timestamp: new Date().toISOString(),
  issueId: "issue-1",
  data,
});

describe("kernelEventGuards", () => {
  describe("type guards", () => {
    describe("hasToolchain", () => {
      it("returns true for object with toolchain string", () => {
        expect(hasToolchain({ toolchain: "claude" })).toBe(true);
      });

      it("returns true for object without toolchain (optional)", () => {
        expect(hasToolchain({})).toBe(true);
      });

      it("returns false for non-object", () => {
        expect(hasToolchain(null)).toBe(false);
        expect(hasToolchain(undefined)).toBe(false);
        expect(hasToolchain("string")).toBe(false);
        expect(hasToolchain(123)).toBe(false);
      });

      it("returns false for invalid toolchain type", () => {
        expect(hasToolchain({ toolchain: 123 })).toBe(false);
        expect(hasToolchain({ toolchain: null })).toBe(false);
      });
    });

    describe("hasFitness", () => {
      it("returns true for object with numeric fitness", () => {
        expect(hasFitness({ fitness: 0.85 })).toBe(true);
        expect(hasFitness({ fitness: 0 })).toBe(true);
        expect(hasFitness({ fitness: 1 })).toBe(true);
      });

      it("returns false without fitness field", () => {
        expect(hasFitness({})).toBe(false);
      });

      it("returns false for non-numeric fitness", () => {
        expect(hasFitness({ fitness: "high" })).toBe(false);
        expect(hasFitness({ fitness: null })).toBe(false);
      });
    });

    describe("hasError", () => {
      it("returns true for object with error string", () => {
        expect(hasError({ error: "Something failed" })).toBe(true);
      });

      it("returns true for object with reason string", () => {
        expect(hasError({ reason: "Gate check failed" })).toBe(true);
      });

      it("returns false without error or reason", () => {
        expect(hasError({})).toBe(false);
        expect(hasError({ message: "error" })).toBe(false);
      });
    });

    describe("hasPreviewUrls", () => {
      it("returns true for any object", () => {
        expect(hasPreviewUrls({})).toBe(true);
        expect(hasPreviewUrls({ previewUrls: {} })).toBe(true);
      });

      it("returns false for non-objects", () => {
        expect(hasPreviewUrls(null)).toBe(false);
        expect(hasPreviewUrls("string")).toBe(false);
      });
    });
  });

  describe("extractors", () => {
    describe("extractToolchain", () => {
      it("extracts toolchain from event data", () => {
        const event = createMockEvent({ toolchain: "codex" });
        expect(extractToolchain(event)).toBe("codex");
      });

      it("returns claude as default", () => {
        const event = createMockEvent({});
        expect(extractToolchain(event)).toBe("claude");
      });

      it("returns claude for non-string toolchain", () => {
        const event = createMockEvent({ toolchain: 123 });
        expect(extractToolchain(event)).toBe("claude");
      });

      it("handles null/undefined data", () => {
        expect(extractToolchain(createMockEvent(null))).toBe("claude");
        expect(extractToolchain(createMockEvent(undefined))).toBe("claude");
      });
    });

    describe("extractFitness", () => {
      it("extracts fitness from event data", () => {
        const event = createMockEvent({ fitness: 0.92 });
        expect(extractFitness(event)).toBe(0.92);
      });

      it("returns 0 as default", () => {
        const event = createMockEvent({});
        expect(extractFitness(event)).toBe(0);
      });

      it("handles edge cases", () => {
        expect(extractFitness(createMockEvent({ fitness: 0 }))).toBe(0);
        expect(extractFitness(createMockEvent({ fitness: 1 }))).toBe(1);
        expect(extractFitness(createMockEvent({ fitness: "high" }))).toBe(0);
      });
    });

    describe("extractError", () => {
      it("extracts error message", () => {
        const event = createMockEvent({ error: "Build failed" });
        expect(extractError(event)).toBe("Build failed");
      });

      it("falls back to reason field", () => {
        const event = createMockEvent({ reason: "Gate check failed" });
        expect(extractError(event)).toBe("Gate check failed");
      });

      it("prefers error over reason", () => {
        const event = createMockEvent({
          error: "Primary error",
          reason: "Secondary reason",
        });
        expect(extractError(event)).toBe("Primary error");
      });

      it("returns default message when no error info", () => {
        const event = createMockEvent({});
        expect(extractError(event)).toBe("Build failed");
      });
    });

    describe("extractPreviewUrls", () => {
      it("extracts all preview URL types", () => {
        const event = createMockEvent({
          previewUrls: {
            concept: "/concept.png",
            geometry: "/geo.png",
            textured: "/textured.png",
            final: "/final.png",
          },
        });
        const urls = extractPreviewUrls(event);

        expect(urls.concept).toBe("/concept.png");
        expect(urls.geometry).toBe("/geo.png");
        expect(urls.textured).toBe("/textured.png");
        expect(urls.final).toBe("/final.png");
      });

      it("handles partial preview URLs", () => {
        const event = createMockEvent({
          previewUrls: {
            concept: "/concept.png",
          },
        });
        const urls = extractPreviewUrls(event);

        expect(urls.concept).toBe("/concept.png");
        expect(urls.geometry).toBeUndefined();
      });

      it("ignores non-string values", () => {
        const event = createMockEvent({
          previewUrls: {
            concept: "/concept.png",
            geometry: 123,
            textured: null,
          },
        });
        const urls = extractPreviewUrls(event);

        expect(urls.concept).toBe("/concept.png");
        expect(urls.geometry).toBeUndefined();
        expect(urls.textured).toBeUndefined();
      });

      it("returns empty object for missing previewUrls", () => {
        const event = createMockEvent({});
        expect(extractPreviewUrls(event)).toEqual({});
      });
    });

    describe("extractGlbUrl", () => {
      it("extracts from previewGlbUrl", () => {
        const event = createMockEvent({ previewGlbUrl: "/preview.glb" });
        expect(extractGlbUrl(event)).toBe("/preview.glb");
      });

      it("extracts from glbUrl", () => {
        const event = createMockEvent({ glbUrl: "/model.glb" });
        expect(extractGlbUrl(event)).toBe("/model.glb");
      });

      it("extracts from glb_url (snake_case)", () => {
        const event = createMockEvent({ glb_url: "/snake.glb" });
        expect(extractGlbUrl(event)).toBe("/snake.glb");
      });

      it("prefers previewGlbUrl over others", () => {
        const event = createMockEvent({
          previewGlbUrl: "/preview.glb",
          glbUrl: "/other.glb",
        });
        expect(extractGlbUrl(event)).toBe("/preview.glb");
      });

      it("returns null when no GLB URL", () => {
        const event = createMockEvent({});
        expect(extractGlbUrl(event)).toBeNull();
      });

      it("returns null for empty string", () => {
        const event = createMockEvent({ previewGlbUrl: "" });
        expect(extractGlbUrl(event)).toBeNull();
      });
    });

    describe("extractGodotUrl", () => {
      it("extracts from previewGodotUrl", () => {
        const event = createMockEvent({ previewGodotUrl: "/godot/preview.zip" });
        expect(extractGodotUrl(event)).toBe("/godot/preview.zip");
      });

      it("extracts from godotUrl", () => {
        const event = createMockEvent({ godotUrl: "/godot/build.zip" });
        expect(extractGodotUrl(event)).toBe("/godot/build.zip");
      });

      it("extracts from godot_url (snake_case)", () => {
        const event = createMockEvent({ godot_url: "/godot/snake.zip" });
        expect(extractGodotUrl(event)).toBe("/godot/snake.zip");
      });

      it("returns null when no Godot URL", () => {
        const event = createMockEvent({});
        expect(extractGodotUrl(event)).toBeNull();
      });
    });
  });
});

/**
 * Type guards for kernel event data
 *
 * Provides type-safe access to kernel event payloads.
 */

import type { KernelEvent } from "@/types";

// ============================================================================
// Event data shape interfaces
// ============================================================================

export interface WorkcellCreatedData {
  toolchain?: string;
}

export interface CriticResultData {
  fitness?: number;
  scores?: Record<string, number>;
}

export interface IssueFailedData {
  error?: string;
  reason?: string;
}

export interface PreviewUrlsData {
  previewUrls?: {
    concept?: string;
    geometry?: string;
    textured?: string;
    final?: string;
  };
  previewGlbUrl?: string;
  glbUrl?: string;
  glb_url?: string;
  previewGodotUrl?: string;
  godotUrl?: string;
  godot_url?: string;
}

// ============================================================================
// Type guards
// ============================================================================

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function hasToolchain(data: unknown): data is WorkcellCreatedData {
  if (!isObject(data)) return false;
  return !("toolchain" in data) || typeof data.toolchain === "string";
}

export function hasFitness(data: unknown): data is CriticResultData {
  if (!isObject(data)) return false;
  return "fitness" in data && typeof data.fitness === "number";
}

export function hasError(data: unknown): data is IssueFailedData {
  if (!isObject(data)) return false;
  return (
    ("error" in data && typeof data.error === "string") ||
    ("reason" in data && typeof data.reason === "string")
  );
}

export function hasPreviewUrls(data: unknown): data is PreviewUrlsData {
  return isObject(data);
}

// ============================================================================
// Safe data extractors
// ============================================================================

export function extractToolchain(event: KernelEvent): string {
  if (!isObject(event.data)) return "claude";
  const data = event.data as Record<string, unknown>;
  return typeof data.toolchain === "string" ? data.toolchain : "claude";
}

export function extractFitness(event: KernelEvent): number {
  if (!isObject(event.data)) return 0;
  const data = event.data as Record<string, unknown>;
  return typeof data.fitness === "number" ? data.fitness : 0;
}

export function extractError(event: KernelEvent): string {
  if (!isObject(event.data)) return "Unknown error";
  const data = event.data as Record<string, unknown>;
  if (typeof data.error === "string") return data.error;
  if (typeof data.reason === "string") return data.reason;
  return "Build failed";
}

export function extractPreviewUrls(
  event: KernelEvent
): Partial<Record<"concept" | "geometry" | "textured" | "final", string>> {
  if (!isObject(event.data)) return {};
  const data = event.data as Record<string, unknown>;

  if (!isObject(data.previewUrls)) return {};
  const urls = data.previewUrls as Record<string, unknown>;

  const result: Partial<Record<"concept" | "geometry" | "textured" | "final", string>> = {};
  if (typeof urls.concept === "string") result.concept = urls.concept;
  if (typeof urls.geometry === "string") result.geometry = urls.geometry;
  if (typeof urls.textured === "string") result.textured = urls.textured;
  if (typeof urls.final === "string") result.final = urls.final;

  return result;
}

export function extractGlbUrl(event: KernelEvent): string | null {
  if (!isObject(event.data)) return null;
  const data = event.data as Record<string, unknown>;

  if (typeof data.previewGlbUrl === "string" && data.previewGlbUrl) {
    return data.previewGlbUrl;
  }
  if (typeof data.glbUrl === "string" && data.glbUrl) {
    return data.glbUrl;
  }
  if (typeof data.glb_url === "string" && data.glb_url) {
    return data.glb_url;
  }
  return null;
}

export function extractGodotUrl(event: KernelEvent): string | null {
  if (!isObject(event.data)) return null;
  const data = event.data as Record<string, unknown>;

  if (typeof data.previewGodotUrl === "string" && data.previewGodotUrl) {
    return data.previewGodotUrl;
  }
  if (typeof data.godotUrl === "string" && data.godotUrl) {
    return data.godotUrl;
  }
  if (typeof data.godot_url === "string" && data.godot_url) {
    return data.godot_url;
  }
  return null;
}

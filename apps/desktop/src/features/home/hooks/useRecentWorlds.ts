import { useCallback, useEffect, useMemo, useState } from "react";
import type { RecentWorld } from "@/types";
import type { RecentWorldsState, UseRecentWorldsOptions } from "./types";

const DEFAULT_STORAGE_KEY = "cyntra:recent-worlds";
const DEFAULT_MAX_ITEMS = 8;

function loadRecentWorlds(storageKey: string): RecentWorld[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveRecentWorlds(storageKey: string, maxItems: number, worlds: RecentWorld[]): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(storageKey, JSON.stringify(worlds.slice(0, maxItems)));
  } catch {
    // Ignore storage errors
  }
}

export function useRecentWorlds(
  options: UseRecentWorldsOptions = {}
): RecentWorldsState {
  const storageKey = options.storageKey ?? DEFAULT_STORAGE_KEY;
  const maxItems = options.maxItems ?? DEFAULT_MAX_ITEMS;
  const [recentWorlds, setRecentWorlds] = useState<RecentWorld[]>([]);

  useEffect(() => {
    setRecentWorlds(loadRecentWorlds(storageKey));
  }, [storageKey]);

  const persist = useCallback(
    (worlds: RecentWorld[]) => {
      saveRecentWorlds(storageKey, maxItems, worlds);
    },
    [storageKey, maxItems]
  );

  const addRecentWorld = useCallback(
    (world: RecentWorld) => {
      setRecentWorlds((prev) => {
        const filtered = prev.filter((w) => w.id !== world.id);
        const updated = [world, ...filtered].slice(0, maxItems);
        persist(updated);
        return updated;
      });
    },
    [maxItems, persist]
  );

  const updateRecentWorld = useCallback(
    (id: string, update: Partial<RecentWorld>) => {
      setRecentWorlds((prev) => {
        const updated = prev.map((w) =>
          w.id === id ? { ...w, ...update, updatedAt: Date.now() } : w
        );
        persist(updated);
        return updated;
      });
    },
    [persist]
  );

  const removeRecentWorld = useCallback(
    (id: string) => {
      setRecentWorlds((prev) => {
        const updated = prev.filter((w) => w.id !== id);
        persist(updated);
        return updated;
      });
    },
    [persist]
  );

  const upsertRecentWorld = useCallback(
    (world: RecentWorld) => {
      setRecentWorlds((prev) => {
        const existing = prev.find((w) => w.id === world.id);
        if (!existing) {
          const updated = [world, ...prev].slice(0, maxItems);
          persist(updated);
          return updated;
        }
        const merged = prev.map((w) =>
          w.id === world.id ? { ...w, ...world, updatedAt: Date.now() } : w
        );
        persist(merged);
        return merged;
      });
    },
    [maxItems, persist]
  );

  const mostRecentWorld = useMemo(() => {
    if (recentWorlds.length === 0) return null;
    return recentWorlds.reduce((latest, current) =>
      current.updatedAt > latest.updatedAt ? current : latest
    );
  }, [recentWorlds]);

  return {
    recentWorlds,
    addRecentWorld,
    updateRecentWorld,
    removeRecentWorld,
    upsertRecentWorld,
    mostRecentWorld,
  };
}

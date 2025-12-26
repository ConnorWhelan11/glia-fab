import { useCallback, useState } from "react";
import type { BlueprintDraft } from "@/types";
import type { BlueprintDraftState, UseBlueprintDraftOptions } from "./types";

export const DEFAULT_BLUEPRINT: BlueprintDraft = {
  name: "",
  runtime: "three",
  outputs: ["viewer"],
  gates: [],
  tags: [],
};

export function useBlueprintDraft(
  options: UseBlueprintDraftOptions = {}
): BlueprintDraftState {
  const [blueprintDraft, setBlueprintDraft] = useState<BlueprintDraft>(
    options.initial ?? DEFAULT_BLUEPRINT
  );

  const updateBlueprint = useCallback((partial: Partial<BlueprintDraft>) => {
    setBlueprintDraft((prev) => ({ ...prev, ...partial }));
  }, []);

  const resetBlueprint = useCallback(() => {
    setBlueprintDraft(DEFAULT_BLUEPRINT);
  }, []);

  return {
    blueprintDraft,
    setBlueprintDraft,
    updateBlueprint,
    resetBlueprint,
  };
}

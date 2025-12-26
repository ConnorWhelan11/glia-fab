import { useCallback, useMemo, useState } from "react";
import type { TemplateSelectionState, UseTemplateSelectionOptions } from "./types";

export function useTemplateSelection(
  options: UseTemplateSelectionOptions
): TemplateSelectionState {
  const { templates, onApplyTemplate, onClearTemplate } = options;
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);

  const selectedTemplate = useMemo(() => {
    if (!selectedTemplateId) return null;
    return templates.find((template) => template.id === selectedTemplateId) ?? null;
  }, [selectedTemplateId, templates]);

  const selectTemplate = useCallback(
    (id: string | null) => {
      setSelectedTemplateId(id);
      if (!id) {
        onClearTemplate?.();
        return;
      }
      const template = templates.find((item) => item.id === id);
      if (template) {
        onApplyTemplate?.(template);
      }
    },
    [onApplyTemplate, onClearTemplate, templates]
  );

  return {
    selectedTemplateId,
    selectedTemplate,
    selectTemplate,
    templates,
  };
}

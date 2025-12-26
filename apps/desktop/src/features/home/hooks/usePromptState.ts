import { useState } from "react";
import type { PromptState, UsePromptStateOptions } from "./types";

export function usePromptState(options: UsePromptStateOptions = {}): PromptState {
  const { initialPrompt = "", initialFocused = false } = options;
  const [promptText, setPromptText] = useState(initialPrompt);
  const [consoleFocused, setConsoleFocused] = useState(initialFocused);

  return {
    promptText,
    setPromptText,
    consoleFocused,
    setConsoleFocused,
  };
}

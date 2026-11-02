import { create } from "zustand";

export type Theme = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "cs-theme";
export const THEMES: readonly Theme[] = ["light", "dark", "system"];

function isTheme(value: unknown): value is Theme {
  return value === "light" || value === "dark" || value === "system";
}

/** Read the saved theme. Storage can be missing or throw (private windows), so fall back to system. */
export function readStoredTheme(): Theme {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isTheme(value) ? value : "system";
  } catch {
    return "system";
  }
}

function writeStoredTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Storage is only a convenience; the theme still applies for this session.
  }
}

/** Light and dark pin data-theme; system removes it so prefers-color-scheme decides. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", theme);
  }
}

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

export const useThemeStore = create<ThemeState>()((set) => ({
  theme: "system",
  setTheme: (theme) => {
    writeStoredTheme(theme);
    applyTheme(theme);
    set({ theme });
  },
}));

/** Restore the saved theme at startup. */
export function initTheme(): void {
  const theme = readStoredTheme();
  applyTheme(theme);
  useThemeStore.setState({ theme });
}

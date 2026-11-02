import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  THEME_STORAGE_KEY,
  applyTheme,
  initTheme,
  readStoredTheme,
  useThemeStore,
} from "../src/stores/theme";

describe("theme store", () => {
  beforeEach(() => {
    useThemeStore.setState({ theme: "system" });
  });

  it("defaults to system with no data-theme override", () => {
    expect(useThemeStore.getState().theme).toBe("system");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });

  it("sets data-theme for light and dark and clears it for system", () => {
    applyTheme("dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    applyTheme("light");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    applyTheme("system");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });

  it("test_studio_theme_toggle_persists_in_try_catch_storage", () => {
    useThemeStore.getState().setTheme("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(readStoredTheme()).toBe("dark");
  });

  it("keeps working when storage writes throw", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    expect(() => {
      useThemeStore.getState().setTheme("light");
    }).not.toThrow();
    expect(useThemeStore.getState().theme).toBe("light");
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
  });

  it("falls back to system when storage reads throw", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    expect(readStoredTheme()).toBe("system");
  });

  it("falls back to system for an unknown stored value", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "sepia");
    expect(readStoredTheme()).toBe("system");
  });

  it("initTheme restores the stored theme and applies it", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    initTheme();
    expect(useThemeStore.getState().theme).toBe("dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });
});

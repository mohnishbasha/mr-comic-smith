import { THEMES, useThemeStore } from "../stores/theme";

const LABELS = { light: "Light", dark: "Dark", system: "System" } as const;

export function ThemeToggle() {
  const theme = useThemeStore((state) => state.theme);
  const setTheme = useThemeStore((state) => state.setTheme);
  return (
    <div className="cs-theme" role="group" aria-label="Theme">
      {THEMES.map((value) => (
        <button
          key={value}
          type="button"
          aria-pressed={theme === value}
          onClick={() => {
            setTheme(value);
          }}
        >
          {LABELS[value]}
        </button>
      ))}
    </div>
  );
}

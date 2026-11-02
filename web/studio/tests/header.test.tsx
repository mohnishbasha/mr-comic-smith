import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { AppHeader } from "../src/components/AppHeader";
import { useThemeStore } from "../src/stores/theme";

function renderHeader(props: Parameters<typeof AppHeader>[0] = {}, path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppHeader {...props} />
    </MemoryRouter>,
  );
}

describe("AppHeader", () => {
  beforeEach(() => {
    useThemeStore.setState({ theme: "system" });
  });

  it("renders the banner landmark with the product name linking home", () => {
    renderHeader();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "mr-comic-smith" })).toHaveAttribute("href", "/");
  });

  it("hides project navigation outside a project", () => {
    renderHeader();
    expect(screen.queryByRole("navigation", { name: "Project views" })).not.toBeInTheDocument();
  });

  it("shows all six tabs inside a project and marks the current one", () => {
    renderHeader(
      { projectId: "puddle-a1b2", view: "strips", projectTitle: "Puddle" },
      "/p/puddle-a1b2/strips",
    );
    const nav = screen.getByRole("navigation", { name: "Project views" });
    const names = within(nav)
      .getAllByRole("link")
      .map((link) => link.textContent);
    expect(names).toEqual(["Story", "Cast", "Strips", "Pages", "Book", "Export"]);
    expect(within(nav).getByRole("link", { name: "Strips" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(nav).getByRole("link", { name: "Cast" })).not.toHaveAttribute("aria-current");
    expect(within(nav).getByRole("link", { name: "Cast" })).toHaveAttribute(
      "href",
      "/p/puddle-a1b2/cast",
    );
    expect(screen.getByText("Puddle")).toBeInTheDocument();
  });

  it("theme toggle switches light, dark, and system", async () => {
    const user = userEvent.setup();
    renderHeader();
    const group = screen.getByRole("group", { name: "Theme" });
    const system = within(group).getByRole("button", { name: "System" });
    expect(system).toHaveAttribute("aria-pressed", "true");

    await user.click(within(group).getByRole("button", { name: "Dark" }));
    expect(useThemeStore.getState().theme).toBe("dark");
    expect(within(group).getByRole("button", { name: "Dark" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");

    await user.click(within(group).getByRole("button", { name: "Light" }));
    expect(document.documentElement).toHaveAttribute("data-theme", "light");

    await user.click(within(group).getByRole("button", { name: "System" }));
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });
});

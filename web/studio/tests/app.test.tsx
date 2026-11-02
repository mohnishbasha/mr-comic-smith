import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App";

function renderApp(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Home", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json({ status: "ok", version: "0.0.1" }))),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("e2e_US002_empty_home_prompts_for_story_idea", async () => {
    renderApp("/");
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Your comics" })).toBeInTheDocument();
    expect(screen.getByText("Start with a story idea, a photo, or both.")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "New project" });
    expect(button).toBeDisabled();
    expect(screen.getByText(/arrives in Sprint 3/i)).toBeInTheDocument();
    expect(await screen.findByText("Version 0.0.1")).toBeInTheDocument();
  });

  it("does not show project tabs on Home", () => {
    renderApp("/");
    expect(screen.queryByRole("navigation", { name: "Project views" })).not.toBeInTheDocument();
  });

  it("renders a placeholder project view with tabs for /p/:projectId/:view", () => {
    renderApp("/p/demo-1/cast");
    expect(screen.getByRole("heading", { level: 1, name: "Cast" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cast" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText(/for project demo-1/)).toBeInTheDocument();
  });

  it("redirects /p/:projectId to the Strips view", () => {
    renderApp("/p/demo-1");
    expect(screen.getByRole("heading", { level: 1, name: "Strips" })).toBeInTheDocument();
  });

  it("shows a friendly page for an unknown view", () => {
    renderApp("/p/demo-1/nonsense");
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  });

  it("shows a friendly page for an unknown route", () => {
    renderApp("/nope");
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  });
});

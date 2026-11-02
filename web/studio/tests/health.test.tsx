import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHealth } from "../src/api/health";
import { Footer } from "../src/components/Footer";

function wrapper(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function mockFetch(impl: () => Promise<Response>) {
  const spy = vi.fn(impl);
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchHealth", () => {
  it("requests /v1/healthz and returns status and version", async () => {
    const spy = mockFetch(() => Promise.resolve(Response.json({ status: "ok", version: "0.0.1" })));
    await expect(fetchHealth()).resolves.toEqual({ status: "ok", version: "0.0.1" });
    expect(spy).toHaveBeenCalledWith("/v1/healthz", expect.anything());
  });

  it("rejects on a non-2xx response", async () => {
    mockFetch(() => Promise.resolve(new Response("nope", { status: 503 })));
    await expect(fetchHealth()).rejects.toThrow(/503/);
  });

  it("rejects when the body has the wrong shape", async () => {
    mockFetch(() => Promise.resolve(Response.json({ hello: "world" })));
    await expect(fetchHealth()).rejects.toThrow(/unexpected/i);
  });
});

describe("Footer version", () => {
  it("shows the version from /v1/healthz", async () => {
    mockFetch(() => Promise.resolve(Response.json({ status: "ok", version: "0.0.1" })));
    render(wrapper(<Footer />));
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(await screen.findByText("Version 0.0.1")).toBeInTheDocument();
  });

  it("says the version is unavailable when the server cannot be reached", async () => {
    mockFetch(() => Promise.reject(new TypeError("network down")));
    render(wrapper(<Footer />));
    await waitFor(() => {
      expect(screen.getByText("Version unavailable")).toBeInTheDocument();
    });
  });
});

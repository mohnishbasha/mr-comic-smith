export interface Health {
  status: string;
  version: string;
}

export const HEALTH_URL = "/v1/healthz";

function isHealth(value: unknown): value is Health {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const record = value as Record<string, unknown>;
  return typeof record["status"] === "string" && typeof record["version"] === "string";
}

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch(HEALTH_URL, {
    headers: { Accept: "application/json" },
    ...(signal ? { signal } : {}),
  });
  if (!response.ok) {
    throw new Error(`Health check failed with status ${String(response.status)}`);
  }
  const body: unknown = await response.json();
  if (!isHealth(body)) {
    throw new Error("Health check returned an unexpected body");
  }
  return body;
}

import { useQuery } from "@tanstack/react-query";

import { fetchHealth } from "./health";

export function useHealth() {
  return useQuery({
    queryKey: ["healthz"],
    queryFn: ({ signal }) => fetchHealth(signal),
    staleTime: 60_000,
  });
}

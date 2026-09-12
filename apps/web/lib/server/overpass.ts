// Overpass API loader (server side only): the browser never talks to
// Overpass directly, so one cached upstream request serves all visitors.
// Throws OverpassError on any failure — the cache layer turns that into
// stale-or-demo, never into stored data.

import { OVERPASS_URL, parseOverpassElements, type LayerPoint } from "../layers";

export class OverpassError extends Error {
  readonly status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "OverpassError";
    this.status = status;
  }
}

type FetchImpl = (
  input: string,
  init?: {
    method?: string;
    body?: string;
    headers?: Record<string, string>;
    signal?: AbortSignal;
  },
) => Promise<{ ok: boolean; status: number; json: () => Promise<unknown> }>;

/** POST an Overpass QL query; resolves to feature points or throws. */
export async function fetchOverpassPoints(
  query: string,
  fetchImpl: FetchImpl = fetch as unknown as FetchImpl,
  timeoutMs = 25000,
): Promise<LayerPoint[]> {
  const ctrl = new AbortController();
  let onTimeout = () => {};
  const timer = setTimeout(() => onTimeout(), timeoutMs);
  try {
    const res = await Promise.race([
      fetchImpl(OVERPASS_URL, {
        method: "POST",
        // Form content-type: without it Overpass answers 406 (verified).
        // Identifying User-Agent: required by the Overpass usage policy,
        // and requests without one are refused.
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "User-Agent": "home-finder/0.1 (parameter map cache)",
        },
        body: `data=${encodeURIComponent(query)}`,
        signal: ctrl.signal,
      }),
      new Promise<never>((_, reject) => {
        onTimeout = () => {
          ctrl.abort();
          reject(new OverpassError("overpass timeout"));
        };
      }),
    ]);
    if (!res.ok) throw new OverpassError(`overpass HTTP ${res.status}`, res.status);
    return parseOverpassElements(await res.json());
  } finally {
    clearTimeout(timer);
  }
}

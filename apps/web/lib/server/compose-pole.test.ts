// Compose pole wiring (issue #776). Hermetic: reads the repo's
// docker-compose.yml as text only (no yaml dep, no network, no
// containers) and pins the container-reachable pole path, so the
// web service can never silently regress to a loopback POLE_BASE_URL
// (inside a container 127.0.0.1 is the container itself).

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const compose = readFileSync(
  new URL("../../../../docker-compose.yml", import.meta.url),
  "utf-8",
);

/** The `web:` service block (up to the next same-indent key). */
function webBlock(): string {
  const start = compose.indexOf("\n  web:");
  expect(start, "compose has no web service").toBeGreaterThan(-1);
  const rest = compose.slice(start + 1);
  const end = rest.search(/\n\S|\n {2}\w[\w-]*:/);
  return end === -1 ? rest : rest.slice(0, end);
}

describe("compose pole wiring (#776)", () => {
  it("wires a container-reachable POLE_BASE_URL for web", () => {
    const line = webBlock()
      .split("\n")
      .find((l) => l.includes("POLE_BASE_URL:"));
    expect(line, "web sets POLE_BASE_URL").toBeTruthy();
    expect(line!).toContain("host.docker.internal:18001");
    expect(line!).not.toContain("127.0.0.1");
  });

  it("keeps host.docker.internal resolving on Linux docker too", () => {
    const web = webBlock();
    expect(web).toContain("extra_hosts:");
    expect(web).toContain("host.docker.internal:host-gateway");
  });
});

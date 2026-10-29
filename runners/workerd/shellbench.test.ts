// Copy into packages/computer/tests/ together with shellbench-cases.json (made by prepare.mjs).
// Prints one "SBRESULT <base64 JSON>" line per case; collect.mjs turns them into a results file.
import { SELF } from "cloudflare:test";
import { it } from "vitest";
import cases from "./shellbench-cases.json";

it("shellbench", async () => {
  for (const c of cases as Array<{ id: string } & Record<string, unknown>>) {
    let line: unknown;
    try {
      const res = await SELF.fetch(`http://shellbench/run?id=${encodeURIComponent(c.id)}`, {
        method: "POST",
        body: JSON.stringify(c),
      });
      line = res.ok ? { id: c.id, ...(await res.json()) } : { id: c.id, stdout: "", stderr: `HARNESS-HTTP-${res.status}: ${await res.text()}`, exitCode: -1, delta: {} };
    } catch (e) {
      line = { id: c.id, stdout: "", stderr: `HARNESS-EXCEPTION: ${String(e)}`, exitCode: -1, delta: {} };
    }
    console.log(`SBRESULT ${btoa(unescape(encodeURIComponent(JSON.stringify(line))))}`);
  }
  // Intentional: in this vitest-pool-workers setup the captured console output of a passing test
  // is not printed, so the run ends with a marked failure to make it print the SBRESULT lines.
  throw new Error(`SHELLBENCH-DONE ${cases.length} cases (intentional failure to flush console output)`);
}, 1_800_000);

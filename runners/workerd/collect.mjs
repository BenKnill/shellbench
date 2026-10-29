// Turn the vitest log's "SBRESULT <base64>" lines into a shellbench results file.
// usage: node runners/workerd/collect.mjs VITEST_LOG OUT.jsonl "version string"
import fs from "node:fs";

const [logP, outP, version] = process.argv.slice(2);
const rows = [];
for (const m of fs.readFileSync(logP, "utf8").matchAll(/SBRESULT ([A-Za-z0-9+/=]+)/g)) {
  const r = JSON.parse(Buffer.from(m[1], "base64").toString("utf8"));
  r.stdoutB64 = Buffer.from(r.stdout ?? "", "utf8").toString("base64");
  rows.push(JSON.stringify(r));
}
fs.writeFileSync(outP, rows.join("\n") + "\n");
fs.writeFileSync(outP + ".meta.json", JSON.stringify({ name: "cf-computer-workerd", version, cases: rows.length,
  note: "stdout captured as UTF-8 text (exec encoding utf8): invalid UTF-8 output bytes become U+FFFD" }, null, 1));
console.error(`${rows.length} results -> ${outP}`);

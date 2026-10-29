// Expand the suite into the request list the workerd host takes.
// usage: node runners/workerd/prepare.mjs suite/cases.jsonl suite/world.json OUT/shellbench-cases.json
import fs from "node:fs";
import path from "node:path";
import { CWD, ENV, ROOTS } from "../node/env.mjs";

const [casesP, worldP, outP] = process.argv.slice(2);
const worlds = JSON.parse(fs.readFileSync(worldP, "utf8"));
const out = [];
for (const line of fs.readFileSync(casesP, "utf8").split("\n").filter(Boolean)) {
  const c = JSON.parse(line);
  const dirs = new Set(["/home", "/home/user", CWD, "/tmp"]);
  const files = [];
  for (const [rel, v0] of Object.entries({ ...worlds[c.world], ...(c.files ?? {}) })) {
    const v = typeof v0 === "string" ? { text: v0 } : v0;
    const abs = path.posix.join(CWD, rel);
    for (let d = path.posix.dirname(abs); d !== "/"; d = path.posix.dirname(d)) dirs.add(d);
    if (v.dir) dirs.add(abs);
    else if (v.symlink !== undefined) files.push([abs, "symlink", v.symlink, 0]);
    else files.push([abs, "file", v.b64 ?? Buffer.from(v.text, "utf8").toString("base64"), v.mode ?? 0o644]);
  }
  files.sort((a, b) => (a[1] === b[1] ? (a[0] < b[0] ? -1 : 1) : a[1] === "file" ? -1 : 1));
  out.push({ id: c.id, dirs: [...dirs].sort(), files, script: c.script, cwd: CWD, env: ENV, roots: ROOTS });
}
fs.writeFileSync(outP, JSON.stringify(out));
console.error(`${out.length} cases -> ${outP}`);

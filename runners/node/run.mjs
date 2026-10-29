// shellbench subject runner: run every case through a shell adapter, one fresh file system per
// case, in worker processes that are killed and replaced when a case exceeds its time limit.
//
// usage: node runners/node/run.mjs --adapter runners/node/adapters/just-bash.mjs [--adapter-opts JSON]
//          --cases suite/cases.jsonl --world suite/world.json --out results/NAME.jsonl
//          [--workers 4] [--timeout 10000]
//
// An adapter module exports createSubject(opts) -> { name, version, load(seed, dirs, {mtime}), run(req) }:
//   seed: Map<absolute path, {content: Uint8Array, mode} | {symlink: target}>
//   dirs: absolute directory paths to create (parents of seeded paths included)
//   run({script, cwd, env, timeoutMs}) -> {stdoutB64, stderr, exitCode, delta}
//   delta: {added: {path: hash}, changed: {path: hash}, deleted: [path]} relative to the seed, where
//          hash is the first 16 hex digits of the file's SHA-256, "<dir>" or "<symlink>".
import fs from "node:fs";
import path from "node:path";
import { fork } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

import { CWD, ENV, HOME, MTIME, ROOTS } from "./env.mjs";

function args() {
  const a = process.argv.slice(2);
  const o = {};
  for (let i = 0; i < a.length; i++) if (a[i].startsWith("--")) o[a[i].slice(2)] = a[i + 1]?.startsWith("--") ? true : a[++i];
  return o;
}

function seedFor(c, worlds) {
  const entries = { ...worlds[c.world], ...(c.files ?? {}) };
  const seed = new Map();
  const dirs = new Set(["/home", HOME, CWD, "/tmp"]);
  for (const [rel, v0] of Object.entries(entries)) {
    const v = typeof v0 === "string" ? { text: v0 } : v0;
    const abs = path.posix.join(CWD, rel);
    for (let d = path.posix.dirname(abs); d !== "/" && !dirs.has(d); d = path.posix.dirname(d)) dirs.add(d);
    if (v.dir) dirs.add(abs);
    else if (v.symlink !== undefined) seed.set(abs, { symlink: v.symlink });
    else {
      const content = v.b64 !== undefined ? new Uint8Array(Buffer.from(v.b64, "base64")) : new Uint8Array(Buffer.from(v.text, "utf8"));
      seed.set(abs, { content, mode: v.mode ?? 0o644 });
    }
  }
  return { seed, dirs: [...dirs].sort() };
}

const inRoots = (p) => ROOTS.some((r) => p === r || p.startsWith(r + "/"));
function filterDelta(d = {}) {
  const pick = (o) => Object.fromEntries(Object.entries(o ?? {}).filter(([p]) => inRoots(p)));
  return { added: pick(d.added), changed: pick(d.changed), deleted: (d.deleted ?? []).filter(inRoots).sort() };
}

if (process.env.SHELLBENCH_WORKER) {
  // ---------------- worker ----------------
  process.env.TZ = "UTC";
  const o = JSON.parse(process.env.SHELLBENCH_WORKER);
  const worlds = JSON.parse(fs.readFileSync(o.world, "utf8"));
  const mod = await import(pathToFileURL(path.resolve(o.adapter)).href);
  const subject = await mod.createSubject({ ...(o.adapterOpts ?? {}), roots: ROOTS });
  process.send({ ready: true, name: subject.name, version: subject.version });
  process.on("message", async (c) => {
    let r;
    try {
      const { seed, dirs } = seedFor(c, worlds);
      await subject.load(seed, dirs, { mtime: MTIME });
      r = await subject.run({ script: c.script, cwd: CWD, env: { ...ENV }, timeoutMs: o.timeout });
    } catch (e) {
      r = { stdoutB64: "", stderr: `HARNESS-EXCEPTION: ${e?.message ?? e}`, exitCode: -1, delta: {} };
    }
    const out = Buffer.from(r.stdoutB64 ?? "", "base64");
    process.send({ id: c.id, stdout: out.toString("utf8"), stdoutB64: r.stdoutB64 ?? "", stderr: r.stderr ?? "",
      exitCode: r.exitCode, delta: filterDelta(r.delta), ...(r.aborted ? { aborted: true } : {}) });
  });
} else {
  // ---------------- supervisor ----------------
  const o = args();
  const workers = Number(o.workers ?? 4);
  const timeout = Number(o.timeout ?? 10000);
  const cases = fs.readFileSync(o.cases, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
  const queue = [...cases];
  const results = new Map();
  const cfg = { adapter: o.adapter, world: o.world, timeout, adapterOpts: o["adapter-opts"] ? JSON.parse(o["adapter-opts"]) : undefined };
  let meta = null;
  const t0 = Date.now();
  const slots = [];
  const fail = (id, kind) => ({ id, [kind]: true, stdout: "", stdoutB64: "", stderr: `HARNESS-${kind.toUpperCase()}`, exitCode: -2, delta: { added: {}, changed: {}, deleted: [] } });

  function spawn(slot) {
    const child = fork(fileURLToPath(import.meta.url), [], {
      env: { ...process.env, SHELLBENCH_WORKER: JSON.stringify(cfg) },
      stdio: ["ignore", "ignore", "inherit", "ipc"],
    });
    Object.assign(slot, { child, ready: false, current: null, timedOut: false });
    child.on("message", (msg) => {
      if (msg.ready) {
        meta ??= { name: msg.name, version: msg.version };
        slot.ready = true;
        next(slot);
        return;
      }
      clearTimeout(slot.timer);
      results.set(msg.id, msg);
      slot.current = null;
      next(slot);
    });
    child.on("exit", (code) => {
      if (!slot.ready) {
        console.error(`worker exited before ready (code ${code})`);
        process.exit(3);
      }
      if (slot.current && !slot.timedOut) results.set(slot.current.id, fail(slot.current.id, "crashed"));
      slot.current = null;
      if (queue.length) spawn(slot);
      else if (slots.every((s) => !s.current)) finish();
    });
  }
  function next(slot) {
    const c = queue.shift();
    if (!c) {
      slot.child.kill();
      return;
    }
    slot.current = c;
    slot.child.send(c);
    slot.timer = setTimeout(() => {
      results.set(c.id, fail(c.id, "timeout"));
      slot.timedOut = true;
      slot.current = null;
      slot.child.kill("SIGKILL");
    }, timeout + 5000);
  }
  let done = false;
  function finish() {
    if (done) return;
    done = true;
    const lines = cases.map((c) => JSON.stringify(results.get(c.id) ?? fail(c.id, "missing")));
    fs.writeFileSync(o.out, lines.join("\n") + "\n");
    fs.writeFileSync(o.out + ".meta.json", JSON.stringify({ ...meta, node: process.version, cases: cases.length,
      seconds: (Date.now() - t0) / 1000 }, null, 1));
    console.error(`done ${cases.length} in ${((Date.now() - t0) / 1000).toFixed(1)}s: ${meta?.version}`);
  }
  for (let i = 0; i < Math.min(workers, queue.length); i++) {
    const slot = {};
    slots.push(slot);
    spawn(slot);
  }
}

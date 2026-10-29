// shellbench adapter: just-bash (https://github.com/vercel-labs/just-bash) over its InMemoryFs,
// with default exec options, as a plain deployment would construct it.
//
// opts.package: a just-bash package directory with package.json and dist/bundle/index.js (an npm
// install such as node_modules/just-bash, or a source checkout after `pnpm build`). Required.
// opts.rev: the source revision to record when the package directory is a copy outside its repo.
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const sha16 = (b) => crypto.createHash("sha256").update(b).digest("hex").slice(0, 16);

export async function createSubject(opts = {}) {
  if (!opts.package) throw new Error("just-bash adapter: set adapter-opts {\"package\": DIR}");
  const pkgDir = path.resolve(opts.package);
  const pkg = JSON.parse(fs.readFileSync(path.join(pkgDir, "package.json"), "utf8"));
  const bundle = path.join(pkgDir, "dist/bundle/index.js");
  const { Bash, InMemoryFs, stdoutAsBytes } = await import(pathToFileURL(bundle).href);
  let rev = opts.rev ?? "";
  if (!rev && !pkgDir.includes(`${path.sep}node_modules${path.sep}`)) try {
    rev = execFileSync("git", ["-C", pkgDir, "rev-parse", "--short=8", "HEAD"], { stdio: ["ignore", "pipe", "ignore"] })
      .toString().trim();
  } catch { /* npm install: no git */ }
  const bundleSha = sha16(fs.readFileSync(bundle));
  const roots = opts.roots ?? ["/home/user", "/tmp"];
  let base = null;
  let mtime = new Date("2026-10-01T12:00:00Z");

  return {
    name: opts.name ?? "just-bash",
    version: `${pkg.name}@${pkg.version}${rev ? ` git ${rev}` : " (npm)"} bundle-sha256:${bundleSha}`,
    async load(seed, dirs, lopts = {}) {
      if (lopts.mtime) mtime = lopts.mtime;
      const init = {};
      const links = [];
      for (const [p, v] of seed) {
        if (v.symlink !== undefined) links.push([p, v.symlink]);
        else init[p] = { content: v.content, mode: v.mode ?? 0o644, mtime };
      }
      base = { init, dirs: [...dirs].sort(), links };
    },
    async run({ script, cwd, env, timeoutMs = 10000 }) {
      const vfs = new InMemoryFs(base.init);
      for (const d of base.dirs) vfs.mkdirSync(d, { recursive: true });
      for (const [p, t] of base.links) await vfs.symlink(t, p);
      for (const d of base.dirs) {
        try { await vfs.utimes(d, mtime, mtime); } catch { /* ignore */ }
      }
      for (const [p] of base.links) {
        const e = vfs.data.get(p); // InMemoryFs has no lutimes; pin the link's own mtime
        if (e && e.type === "symlink") e.mtime = mtime;
      }
      const bash = new Bash({ fs: vfs, cwd: "/", env: { ...env } });
      const before = new Map(vfs.data);
      const ac = new AbortController();
      const timer = setTimeout(() => ac.abort(new Error("timeout")), timeoutMs);
      let r;
      try {
        r = await bash.exec(script, { cwd, signal: ac.signal });
      } catch (e) {
        r = { stdout: "", stderr: `SHELL-EXCEPTION (exec threw): ${e?.message ?? e}`, exitCode: -1 };
      } finally {
        clearTimeout(timer);
      }
      const out = Buffer.from(stdoutAsBytes(r), "latin1");
      const inRoots = (p) => roots.some((x) => p === x || p.startsWith(x + "/"));
      const kindOf = (e) => (e.type === "directory" ? "<dir>" : e.type === "symlink" ? "<symlink>" : null);
      const delta = { added: {}, changed: {}, deleted: [] };
      const after = vfs.data;
      for (const [p, e] of after) {
        if (!inRoots(p)) continue;
        const b = before.get(p);
        if (b === e) continue;
        const k = kindOf(e);
        const h = k ?? sha16(await vfs.readFileBuffer(p));
        if (!b) delta.added[p] = h;
        else if (kindOf(b) !== k) delta.changed[p] = h;
        else if (!k && (b.content === undefined || sha16(b.content) !== h)) delta.changed[p] = h;
      }
      for (const p of before.keys()) if (inRoots(p) && !after.has(p)) delta.deleted.push(p);
      return { stdoutB64: out.toString("base64"), stderr: r.stderr ?? "", exitCode: r.exitCode, delta, aborted: ac.signal.aborted };
    },
  };
}

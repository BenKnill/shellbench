// shellbench host for Cloudflare Computer's worker-shell in local workerd (test-only, not deployed).
// Copy into a cloudflare/computer checkout as packages/computer/tests/shellbench-worker.ts.
// Mirrors tests/worker-backend-worker.ts from that repository: a host Durable Object owns a
// Workspace whose only backend is a WorkerShellBackend dialing a real Dynamic Worker through the
// Worker Loader binding. One Durable Object per case keeps every case's file system fresh.
import { DurableObject, WorkerEntrypoint } from "cloudflare:workers";
import curlModules from "@cloudflare/computer/shell/curl";
import jqModules from "@cloudflare/computer/shell/jq";
import { WorkerShellBackend } from "../src/backends/worker-shell/index";
import type { WorkspaceStub } from "../src/index";
import { Workspace } from "../src/index";

export { WorkspaceServiceProxy } from "../src/proxy";

export interface Env {
  HOST: DurableObjectNamespace<HostDO>;
  LOADER: WorkerLoader;
}

type SeedFile = [path: string, kind: "file" | "symlink", value: string, mode: number];
interface RunRequest { dirs: string[]; files: SeedFile[]; script: string; cwd: string; env: Record<string, string>; roots: string[] }

const SEED_TIME = Date.parse("2026-10-01T12:00:00Z");

async function sha16(bytes: Uint8Array): Promise<string> {
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(d.slice(0, 8), (b) => b.toString(16).padStart(2, "0")).join("");
}

export class HostDO extends DurableObject<Env> {
  readonly #workspace: Workspace;
  #seeding = true;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.#workspace = new Workspace({
      storage: ctx.storage,
      now: () => (this.#seeding ? SEED_TIME : Date.now()),
      backends: [
        new WorkerShellBackend({
          loader: env.LOADER,
          workspace: { binding: "HOST", id: ctx.id.toString() },
          ctx,
          commands: [jqModules, curlModules],
        }),
      ],
    });
  }

  async __getWorkspaceStub(): Promise<WorkspaceStub> {
    await this.#workspace.ready();
    return this.#workspace.stub();
  }

  async #snapshot(roots: string[]): Promise<Map<string, string>> {
    const fs = this.#workspace.fs;
    const out = new Map<string, string>();
    const walk = async (dir: string): Promise<void> => {
      let entries;
      try {
        entries = await fs.readdir(dir);
      } catch {
        return;
      }
      for (const e of entries) {
        const p = dir === "/" ? `/${e.name}` : `${dir}/${e.name}`;
        if (e.isSymbolicLink) out.set(p, "<symlink>");
        else if (e.isDirectory) {
          out.set(p, "<dir>");
          await walk(p);
        } else {
          const stream = (await fs.readFile(p)) as ReadableStream<Uint8Array>;
          out.set(p, await sha16(new Uint8Array(await new Response(stream).arrayBuffer())));
        }
      }
    };
    for (const r of roots) await walk(r);
    return out;
  }

  async run(req: RunRequest) {
    const fs = this.#workspace.fs;
    this.#seeding = true;
    for (const d of req.dirs) await fs.mkdir(d, { recursive: true });
    for (const [p, kind, value, mode] of req.files) {
      if (kind === "symlink") await fs.symlink(value, p);
      else {
        await fs.writeFile(p, Uint8Array.from(atob(value), (c) => c.charCodeAt(0)));
        if (mode !== 0o644) await fs.chmod(p, mode);
      }
    }
    const before = await this.#snapshot(req.roots);
    this.#seeding = false;
    const handle = await this.#workspace.runtime.exec(req.script, { cwd: req.cwd, env: req.env, encoding: "utf8" });
    const r = await handle.result();
    const after = await this.#snapshot(req.roots);
    const delta = { added: {} as Record<string, string>, changed: {} as Record<string, string>, deleted: [] as string[] };
    for (const [p, h] of after) {
      if (!before.has(p)) delta.added[p] = h;
      else if (before.get(p) !== h) delta.changed[p] = h;
    }
    for (const p of before.keys()) if (!after.has(p)) delta.deleted.push(p);
    return { stdout: r.stdout, stderr: r.stderr, exitCode: r.exitCode, delta, truncated: r.truncated ?? null };
  }
}

export default class extends WorkerEntrypoint<Env> {
  override async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const id = url.searchParams.get("id") ?? "default";
    const stub = this.env.HOST.get(this.env.HOST.idFromName(id));
    if (url.pathname === "/run") return Response.json(await stub.run(await request.json()));
    return new Response("not found", { status: 404 });
  }
}

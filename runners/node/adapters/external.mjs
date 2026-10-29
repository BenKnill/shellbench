// shellbench adapter hook: load a subject module that lives outside this repository.
//
// adapter-opts {"module": "/path/to/subject.mjs", ...}: the module must export createSubject(opts)
// with the interface documented in runners/node/run.mjs. All other options are passed through.
// Use it for any subject adapter kept outside this repository. (The published Cloudflare Computer
// host does not use it: it runs in workerd, see runners/workerd/run.sh.)
import path from "node:path";
import { pathToFileURL } from "node:url";

export async function createSubject(opts = {}) {
  if (!opts.module) throw new Error("external adapter: set adapter-opts {\"module\": PATH}");
  const mod = await import(pathToFileURL(path.resolve(opts.module)).href);
  const { module: _m, ...rest } = opts;
  const subject = await mod.createSubject(rest);
  // Normalize result shape: some hosts return stdout text only.
  return {
    ...subject,
    async run(req) {
      const r = await subject.run(req);
      const stdoutB64 = r.stdoutB64 ?? Buffer.from(r.stdout ?? "", "utf8").toString("base64");
      return { ...r, stdoutB64 };
    },
  };
}

// Copy into packages/computer/. Run: npx vitest run --config vitest.config.shellbench.ts
import { cloudflareTest } from "@cloudflare/vitest-pool-workers";
import { defineConfig } from "vitest/config";
import { shellModuleAliases } from "./test-helpers/shell-module-aliases";

export default defineConfig({
  plugins: [cloudflareTest({ wrangler: { configPath: "./tests/wrangler.shellbench.jsonc" } })],
  resolve: { alias: shellModuleAliases },
  test: { globals: true, include: ["tests/shellbench.test.ts"], testTimeout: 1_800_000, silent: false },
});

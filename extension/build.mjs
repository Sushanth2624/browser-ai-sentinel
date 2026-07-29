import { build } from "esbuild";
import { cpSync, mkdirSync, readFileSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const dist = `${root}/dist`;

if (existsSync(dist)) rmSync(dist, { recursive: true });
mkdirSync(dist, { recursive: true });

const entryPoints = [
  "src/background/service-worker.ts",
  "src/content-isolated/injection-scan.ts",
  "src/content-isolated/relay.ts",
  "src/content-isolated/platform-adapters/index.ts",
  "src/content-main/fetch-patch.ts",
  "src/popup/popup.ts",
];

await build({
  entryPoints: entryPoints.map((e) => `${root}/${e}`),
  outdir: dist,
  outbase: `${root}/src`,
  bundle: true,
  format: "esm",
  target: "chrome120",
  sourcemap: true,
  logLevel: "info",
});

// Static assets manifest/popup.html/icons don't go through esbuild — copy as-is.
mkdirSync(`${dist}/popup`, { recursive: true });
cpSync(`${root}/src/popup/popup.html`, `${dist}/popup/popup.html`);
cpSync(`${root}/icons`, `${dist}/icons`, { recursive: true });

const manifest = JSON.parse(readFileSync(`${root}/manifest.json`, "utf8"));
writeFileSync(`${dist}/manifest.json`, JSON.stringify(manifest, null, 2));

console.log(`\nBuilt extension to ${dist} — load unpacked from there in chrome://extensions`);

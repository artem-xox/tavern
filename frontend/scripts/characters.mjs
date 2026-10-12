import { cpSync, mkdirSync, rmSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const frontend = fileURLToPath(new URL("..", import.meta.url));
const source = join(frontend, "..", "characters");
const destination = join(frontend, "static", "characters");

rmSync(destination, { recursive: true, force: true });
mkdirSync(destination, { recursive: true });
for (const entry of readdirSync(source, { withFileTypes: true })) {
  if (entry.isDirectory()) cpSync(join(source, entry.name, "art"), join(destination, entry.name), { recursive: true });
}

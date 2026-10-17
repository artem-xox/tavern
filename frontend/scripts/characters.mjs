import { cpSync, mkdirSync, rmSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const frontend = fileURLToPath(new URL("..", import.meta.url));
const source = join(frontend, "..", "characters");
const destination = join(frontend, "static", "characters");

rmSync(destination, { recursive: true, force: true });
mkdirSync(destination, { recursive: true });
// characters/<cast>/<id>/art is published as /characters/<id>/: ids are unique across casts.
for (const cast of readdirSync(source, { withFileTypes: true })) {
  if (!cast.isDirectory()) continue;
  for (const entry of readdirSync(join(source, cast.name), { withFileTypes: true })) {
    if (entry.isDirectory()) cpSync(join(source, cast.name, entry.name, "art"), join(destination, entry.name), { recursive: true });
  }
}

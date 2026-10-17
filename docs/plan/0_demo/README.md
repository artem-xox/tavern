# Stage 0 — Demo (done)

**Goal:** check that model-driven agents can run a browser tavern at all.

**Built:** a Phaser/TypeScript client and a Python/FastAPI server with an authoritative world. Visitors
move by A*, drink, sit, chat, play darts, use the WC and go home. Jev scores their options from a
plain-language briefing; a local policy runs without a key. Sessions are saved to files and PostgreSQL.

The full task list, acceptance scenarios, contracts and measurements are in [archive.md](archive.md) (history; do not extend).

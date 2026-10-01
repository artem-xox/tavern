# The Last Inn

A small sandbox game about running a border inn alongside autonomous AI characters.
The browser demo puts three autonomous visitors in a tavern: they sit, chat,
share known places, drink beer, use the toilet, and play darts. Persistent agreements follow.

Run locally: `make install` once, then `make run`. Open http://127.0.0.1:5173.
The backend reads an optional `.env` for Jev; Ctrl+C stops both services.

- [Design](docs/DESIGN.md) — the game concept and prototype scope.
- [Plan](docs/PLAN.md) — implementation stages and success criteria.
- [Stage 0 demo](docs/stages/0_DEMO.md) — tasks, acceptance checks, and local launch instructions.
- [Agent instructions](AGENTS.md) — shared development guidelines.

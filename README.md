# The Story Tavern

A tavern between worlds where famous people, real and fictional, walk in for a drink, and nobody
scripts what happens next. Each guest is played by language models from a card of who they are,
what they want tonight, and what is in their backpack; the game keeps the rules. Every evening ends
with a retold story of the chaos.

Run locally: `make install` once, then `make run`. Open http://127.0.0.1:5173.
The backend reads an optional `.env` for Jev and Claude; Ctrl+C stops both services.

- [Design](docs/DESIGN.md) — the game concept and current scope.
- [Plan](docs/plan/README.md) — stages, tasks and their status; [tech debt](docs/plan/TECH_DEBT.md).
- [Mind](docs/MIND.md) — how a guest decides what to do and say.
- [Character catalog](docs/CHARACTER_CATALOG.md) — where characters live and how to add one.
- [PixelLab character pipeline](docs/CHARACTER_ART_PIPELINE.md) — 68 px characters, eight views per pose.
- [Tavern pixel art redesign](docs/PIXEL_ART_REDESIGN.md) — asset and renderer replacement plan.
- [Agent instructions](AGENTS.md) — shared development guidelines.

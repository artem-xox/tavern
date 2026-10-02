# The Last Inn

A small sandbox game about running a border inn alongside autonomous AI characters.
The browser demo opens an evening for six autonomous guests, described by a scenario
(`data/scenarios/first_evening.json`) apart from the room: they come in over time, pick
seats by their appeal, chat or quarrel, share known places, drink beer, watch the fire,
use the toilet, play darts, and go home when content, wronged, or the inn closes. Next: a believable
evening with four to six model-driven guests who queue, react, talk, and fight.

Run locally: `make install` once, then `make run`. Open http://127.0.0.1:5173.
The backend reads an optional `.env` for Jev; Ctrl+C stops both services.

- [Design](docs/DESIGN.md) — the game concept and prototype scope.
- [Plan](docs/PLAN.md) — implementation stages and success criteria.
- [Tavern pixel art redesign](docs/PIXEL_ART_REDESIGN.md) — asset and renderer replacement plan.
- [PixelLab character pipeline](docs/CHARACTER_ART_PIPELINE.md) — current 68 px cast, four-view rule, and future pose workflow.
- [Stage 0 demo](docs/stages/0_DEMO.md) — tasks, acceptance checks, and local launch instructions.
- [Stage 1 evening](docs/stages/1_EVENING.md) — believable-evening tasks and acceptance targets.
- [Agent instructions](AGENTS.md) — shared development guidelines.

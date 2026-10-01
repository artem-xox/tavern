# Stage 0 — Autonomous Tavern Demo

Build a small browser demo before Godot: three autonomous visitors move through a
tavern, obtain and drink beer, rest, and use a toilet. The test is whether an agent
can observe a need, choose an action, reach the correct place, change the world, and
adapt when that place is unavailable.

NPC conversations, trading, agreements, the yard, and property management come next.
This stage establishes the physical environment those interactions will use.

## Stack and boundaries

- Frontend: Phaser, TypeScript, Vite, and a plain HTML/CSS inspector.
- Backend: Python, FastAPI, WebSocket, and a fixed simulation tick.
- AI: Jev evaluates candidate actions; game code controls selection and execution.
- Data: one JSON map and JSON snapshots; no database or external agent framework.
- Tests: pytest for simulation, policy, and API; TypeScript build and browser checks
  for the frontend. Follow the repository's test-first workflow for business logic.

The server owns positions, routes, object availability, inventory, needs, and events.
The browser renders snapshots and sends commands. Each NPC has its own observations,
knowledge, memory, traits, inventory, and active action. AI receives that NPC's view,
never the complete world snapshot.

## Small demo world

One hall and a toilet room connected by a doorway, three visitors, a beer tap, and
several chairs. Initial map: 20 × 14 cells, rendered at 32 pixels per cell.

Movement uses four-way grid paths with smooth visual interpolation. Objects expose
explicit interaction spots. Choose spots by reachable route length. Reserve an
interaction spot while approaching or using it, and release it on completion,
failure, or cancellation. Handle occupied routes with waiting and replanning.

Needs use a 0–100 scale: larger values mean more urgent. Beer reduces thirst and
raises bladder need; resting reduces fatigue; using the toilet reduces bladder need.
Actions have durations and resource effects. Revalidate before interaction starts.

## Shared implementation contract

Use this contract to let the three implementation agents work independently.
Changes to it must be coordinated with the primary agent before affecting another
agent's files. All agents share the same checkout and must not commit or reset it.

### Files and ownership

- **Simulation agent:** `backend/tavern/world.py`, `backend/tavern/navigation.py`,
  `data/tavern.json`, `tests/test_world.py`, `tests/test_navigation.py`.
- **AI agent:** `backend/tavern/agents.py`, `backend/tavern/jev.py`,
  `tests/test_agents.py`, `tests/test_jev.py`.
- **Frontend agent:** everything under `frontend/`.
- **Primary agent:** project setup, package files, `backend/tavern/app.py`, API tests,
  saving/loading, documentation, and integration fixes after agents finish.

### World snapshot

The JSON-serializable world contains `schema_version`, `tick`, `time`, `paused`,
`speed`, `map`, `actors`, and `events`. Positions and paths use cell coordinates.

- `map`: `width`, `height`, `tile_size`, `blocked` as `[x, y]` pairs, and `objects`.
- Object: `id`, `kind` (`tap`, `toilet`, `chair`), `name`, `x`, `y`,
  `interaction_spots` as `[x, y]` pairs, `stock` (beer count for taps), and
  `reserved_by` (actor ID or null). Object cells are obstacles.
- Actor: `id`, `name`, `color`, `x`, `y`, `traits`,
  `needs` (`thirst`, `fatigue`, `bladder`), `inventory` (`beer`), `status`,
  `action`, `path`, `knowledge`, `memory`, and `decision`.
- Status: `idle`, `walking`, `interacting`, or `waiting`.
- Action: `id`, `verb`, and `target_id` (null for actions without a world target).
- Verb: `take_beer`, `drink`, `rest`, `use_toilet`, `inspect`, or `wait`.
- Event: `time`, `actor_id` (null for world events), `type`, and `message`.
- Decision: `source` (`local` or `jev`), `scores`, and `error` (null on success).
- Knowledge: `objects`, a dictionary of observed object records keyed by ID.
  An unknown tap's stock must not leak into candidates or AI state.

Runtime-only fields may be added for action timing and reservations if serializable.

### Python interfaces

Simulation exports:

```python
create_world(map_data: Mapping[str, Any], seed: int = 0) -> dict[str, Any]
step_world(world: dict[str, Any], dt: float) -> None
start_action(world: dict[str, Any], actor_id: str, action: Mapping[str, Any]) -> dict[str, Any]
observe_actor(world: Mapping[str, Any], actor_id: str) -> dict[str, Any]
```

`start_action` returns `{"accepted": bool, "reason": str | None}`. It owns
validation, route planning, reservations, and action lifecycle. `step_world` advances
movement, actions, and needs, honors `paused`, and applies `speed` internally.
`observe_actor` returns `actor` (own state), `objects` (known/visible records),
`memory` (personal outcomes), `map` (bounds), and `visible_cells` as `[x, y]` pairs.
It excludes other actors' private needs and inventory. Observation refreshes
individual knowledge as needed.

AI exports:

```python
build_candidates(observation: Mapping[str, Any]) -> list[dict[str, Any]]
async choose_action(observation: Mapping[str, Any], config: Mapping[str, Any], rng: Random) -> dict[str, Any]
```

`choose_action` returns `action`, `source`, `scores`, and `error`. Candidate IDs are
stable and unique. Config contains an explicitly passed `typesafe_api_key`, `model`,
`timeout`, and `temperature`; no credentials are included in snapshots or logs.
The local policy is an explicit offline mode and fallback, visibly labeled in the UI.

### HTTP and WebSocket

- `GET /health` reports availability.
- `GET /api/state` returns the current snapshot envelope.
- `/ws` sends `{"type": "snapshot", "state": world, "ai": metadata}` on connection
  and at approximately 10 Hz. Metadata reports configured mode without secrets.
- Client commands: `pause` (`paused`), `speed` (`value`), `refill` (`object_id`,
  `amount`), `block` (`x`, `y`, `blocked`), `force_action` (`actor_id`, `action`),
  `save`, `load`, and `reset`. Each includes `type` equal to the command name.
- Invalid commands return `{"type": "error", "message": "..."}` without corrupting
  state. Successful controls appear in world events.

Run AI requests asynchronously while the world advances. Allow one pending decision
per NPC. Reject stale results after a reset, load, or intervening forced action.
Reconsider at idle/task completion, failure, or a relevant event rather than each tick.

## Tasks

### Foundation — primary agent

- [x] **D00 — Project setup.** Add Python package/dependencies, pytest configuration,
  frontend integration instructions, and ignored local files. Done: imports and
  test collection work in a project environment.
- [x] **D01 — Freeze integration contract.** Record JSON shapes, function signatures,
  file ownership, and acceptance checks here. Done: all agents use this contract.

### Physical world — simulation agent

- [x] **D02 — Map and actors.** Add the small JSON room, three visitors, objects,
  interaction spots, initial needs, inventory, and serializable world state.
  Done: layout is valid and starts without overlapping actors or blocked spots.
- [x] **D03 — Navigation.** Implement four-way A* and reachable interaction-spot
  selection. Done: tests cover obstacles, unreachable targets, and a nearer object
  whose walkable route is longer.
- [x] **D04 — Action lifecycle.** Implement movement, waiting, reservations,
  interaction timing, failure, and cleanup. Done: two visitors cannot occupy the
  same reserved resource; blocked movement can recover or fail visibly.
- [x] **D05 — Resource effects.** Add taking/drinking beer, resting, toilet use,
  waiting, and inspection. Done: effects happen once after valid completion,
  with no negative stock or remote interaction.
- [x] **D06 — Individual observations.** Track visible/known objects and personal
  outcomes. Done: private state and unobserved stock are excluded from AI input.

### Decisions — AI agent

- [x] **D07 — Candidate actions.** Build typed action candidates from personal
  observation, known targets, and inventory. Done: IDs are unique, own beer can be
  drunk, and unknown objects/resources are not invented.
- [x] **D08 — Offline policy.** Add a small need/trait-based scorer and seeded
  stochastic selection. Done: decisions are reproducible under a fixed seed and
  urgent needs affect choices; this mode is labeled `local`.
- [x] **D09 — Jev adapter.** Evaluate candidates with Score on a shared rubric
  using TypeSafe's API. Done: mocked responses, malformed answers, and timeouts
  are tested; scores map to supplied actions only.
- [x] **D10 — Robust decision result.** Combine evaluation and selection; return
  diagnostics and explicit fallback on API failure. Done: errors do not freeze
  the world or silently claim a Jev decision. Live verification requires a key.

### Browser scene — frontend agent

- [x] **D11 — Scene.** Set up Phaser/Vite/TypeScript and render walls, furniture,
  visitors, and labels from snapshots. Done: scene matches map coordinates.
- [x] **D12 — State connection.** Connect WebSocket, interpolate movement, and
  show connection status. Done: reconnect obtains current server state.
- [x] **D13 — NPC inspector.** Click a visitor to see needs, inventory, action,
  knowledge, route, decision scores/source, and recent events. Done: the reason
  and physical outcome of a decision are inspectable.
- [x] **D14 — Environment controls.** Add pause, speed, refill, block/unblock by
  cell, forced action, save/load, and reset. Done: commands follow the contract
  and errors are visible; AI mode is always clearly labeled.

### Integration — primary agent

- [x] **D15 — Authoritative server.** Wire HTTP/WebSocket, the fixed tick, commands,
  and asynchronous NPC decisions. Done: three NPCs keep acting while one model
  call is slow, and stale results cannot override newer state.
- [x] **D16 — Persistence.** Save/load JSON world state, including current actions,
  needs, inventory, knowledge, memory, and reservations. Done: reload preserves
  consequences and resumes without duplicated effects or stuck reservations.
- [x] **D17 — Acceptance and instructions.** Run pytest, frontend type/build checks,
  and a browser smoke test; document exact launch commands and AI configuration.
  Done: the scenarios below pass and any unverified live API behavior is stated.

## Dependencies and dispatch

D00/D01 establish shared boundaries. Dispatch D02–D06, D07–D10, and D11–D14 to
three subagents immediately. Their interfaces let them work in parallel. The primary
agent implements D15/D16 against those interfaces and performs D17 after integration.
Each agent writes only its owned files and reports test evidence and limitations.
Dispatched implementation agents: `simulation` (D02–D06), `agents` (D07–D10),
and `frontend` (D11–D14). The primary agent owns foundation and integration.

## Follow-up tasks — primary agent

- [x] **D18 — One-command launch.** Add `make run` with automatic server-only `.env`
  loading and cleanup of both service process groups. Verified: both ports open on
  launch and both close after Ctrl+C. Add install, test, check, and build commands.
- [x] **D19 — Actual API cost.** Add `make benchmark` for a real one-visitor minute
  at 1×. Count provider-reported usage without changing policy or exposing secrets.
  Print requests, tokens, completions, errors, and cost at an explicit tariff.

## Verification

- Backend: **128 pytest tests passed**, including test-first regressions for malformed
  commands, save/load, resource reservations, route conflicts, and stale AI decisions.
- Frontend: TypeScript check and production build passed. Browser smoke test confirmed
  the map, all three Jev decision sources, pause, refill, saving, and loading. No browser
  console errors were observed.
- Offline stress scenario: 300 game seconds with an empty/refilled tap and a
  blocked/reopened doorway; all visitors completed beer, rest, and toilet actions,
  without overlapping positions or negative resources.
- Live Jev: verified with the key supplied through `.env`; real evaluations returned
  `source: jev` and no fallback errors. The preview is paused for inspection.

### Measured Jev cost — 2026-10-01

Isolated Mara from a fresh world for **60 game seconds at 1×** (61.01 wall seconds).
This measurement used the initial demo, before the final seating and conversation update.

- Actual model: `jev-1.13.0`; 22 requests, zero failed requests or missing usage records.
- Provider-reported tokens: **95,924 input**, **1,687 output**.
- Published tariff: **$0.042 per million input tokens**, output free.
- Calculated API cost: `95,924 / 1,000,000 × $0.042 = $0.004028808`.
- Equivalent hourly cost at that workload: approximately **$0.24 per NPC**.

This is a measured first-minute workload, not a constant price for every NPC/minute.
Decision frequency and context size change with behavior and accumulated memories.
Hosting and future dialogue-generation calls are outside this API-only calculation.
Repeat with `make benchmark`; update `--input-price` if the provider changes tariffs.
[Pricing source](https://typesafe.ai/blog/introducing-system-one-models-and-jev).

## Run locally

### Final room and social loop

- A compact WC, a separate 4×1 oak bar, two tables with six usable seats, and darts.
- `sit` keeps a chair occupied while idle, drinking, or chatting; leaving releases it.
- `talk` requires two visitors seated at the same table. Both gain a memory and
  satisfy their need for company; they can share remembered beer, WC, and darts locations.
- `play_darts` walks to the throwing spot and reduces boredom after playing.
- Conversations pause the recipient's autonomous choices until the exchange ends.
- Slower need growth and longer seated actions make the room feel like an evening
  in a tavern. Jev still evaluates the available actions; conversation text is scripted.
- Added rugs, windows, table candles, mugs, oriented chairs, and speech bubbles.
- Latest validation before PR: **156 pytest tests passed**, TypeScript check and
  production build passed. Real Jev visitors were observed sitting, chatting, playing
  darts, drinking, and using the WC.

From the repository root, install dependencies once and launch both services:

```sh
make install
make run
```

`make run` supervises the backend on port 8000 and Vite on port 5173. Ctrl+C
stops both services and their children. If either service fails, the other stops too.

For separate terminals, the equivalent backend command is:

```sh
.venv/bin/python -m uvicorn tavern.app:create_default_app --factory --host 127.0.0.1 --port 8000
```

In another terminal, start the browser client:

```sh
npm --prefix frontend run dev
```

Open [the local demo](http://127.0.0.1:5173). Without `TYPESAFE_API_KEY`, visitors
use the visibly labeled local utility policy. For Jev, copy `.env.example` to `.env`,
set the key there; `make run` loads it automatically. For the separate backend command,
add `--env-file .env`. Credentials stay
on the backend; they never enter browser snapshots or version control.

Checks:

```sh
make check
make build
```

Use one server process: in-memory world state is shared by every connected browser.
Saves live in `saves/demo.json`; they are created by the Save control and ignored by Git.

## Acceptance scenarios

1. Three visitors autonomously obtain beer, drink, rest, and use the toilet.
2. A route around furniture reaches the correct interaction spot; no effects occur
   through a wall or before arrival.
3. Two visitors compete for a single toilet or chair without overlapping use.
4. An empty tap produces a remembered outcome; refilling it becomes observable.
5. Blocking a route causes waiting/replanning/failure, and unblocking permits recovery.
6. A paused world does not advance; changing speed affects simulation time.
7. Saving and loading preserve inventory, needs, knowledge, and ongoing actions.
8. Jev-enabled and offline decisions are clearly distinguished; model errors and
   stale responses cannot corrupt the world.

## References

- [Phaser project templates](https://docs.phaser.io/phaser/getting-started/project-templates)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [TypeSafe API quick start](https://docs.typesafe.ai/introduction/quickstart)
- [Jev question primitives](https://docs.typesafe.ai/primitives)
- [A* navigation](https://www.redblobgames.com/pathfinding/a-star/introduction.html)

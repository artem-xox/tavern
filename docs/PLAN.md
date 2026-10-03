# The Last Inn — Prototype Plan

Build the smallest playable prototype that tests the central question in
[DESIGN.md](DESIGN.md). Each stage has an observable completion criterion.

## 0. Validate agents in a browser tavern — done

Phaser/TypeScript frontend and Python/FastAPI backend. Visitors move, drink, sit, chat,
play darts, use the WC, and go home, with Jev scoring their options from a plain-language
briefing. See [Stage 0](stages/0_DEMO.md).

## 1. A believable evening — in progress

Four to six guests from character cards spend one evening in the hall. They queue,
react to noise, talk through Claude Haiku 4.5 with speech acts, pass on news, get drunk,
and sometimes shove or fight. The player only sets up the evening and watches.
See [Stage 1 tasks](stages/1_EVENING.md).

**Status (2026-10-03):** M1–M3 done. Next, in order: the refactor R0–R7 (pays off
[tech debt](#tech-debt) D01–D08, approved 2026-10-03), U1 (no text labels in the hall), then D13 (Jev and
Claude health markers), then E18b (conversation memory), then M4 (news and conflict).

**Done when:** recorded live evenings meet the Stage 1 metrics, an observer can retell
a story from at least one of them, and its chronicle cites only logged events.

## 2. Staff and commands

Add a barkeep and a bouncer whose actions use the same activity system, and let the
player give them commands: serve, refill, calm someone down, throw someone out.

**Done when:** a player command changes how an evening's incident ends.

## 3. The inn's economy

Guests carry money; drinks and food have prices; supplies run out and are restocked;
tabs, tips, and damage cost or earn money.

**Done when:** an evening ends with a ledger the player can trace to guests' actions.

## 4. Several evenings and agreements

Guests return as regulars. The evening is summarized into memories, opinions persist,
and invitations from conversations can become validated obligations: debts, deliveries,
meetings. Saving and loading preserve them.

**Done when:** an agreement made in one evening changes a guest's behavior in the next
and creates a new situation for the player.

Expand property, the yard, and lodging after this loop works.

## Tech debt

Known problems that no current task owns. When a task leaves one behind, add it here
with its evidence. The commit that fixes it removes the row. Pay off debt that blocks the
next milestone before starting that milestone.

| ID | Problem | Evidence | Resolution |
|----|---------|----------|------------|
| D01 | Modules over the ~400-line limit | `app.py` 594, `world.py` 478, `briefing.py` 450, `persistence.py` 427; close to it: `agents.py` 386, `scene.ts` 397 | R4 (`scene.ts` before E24) |
| D02 | The door lets out one leaver at a time, so guests wait their turn after closing | 24–46 s stuck at closing in live seeds 5 and 1 (E15); `test_closing.py` specifies the current behavior | Not a problem yet. Revisit if acceptance scenario 1 or 5 fails in E28 |
| D03 | `agents.py` imports `jev.py`, and tests patch modules instead of passing fakes | `monkeypatch.setattr` on `tavern.agents.*` (`test_agents.py` ×2, `test_seating.py` ×5) and `tavern.app.*` (`test_database.py` ×2, `test_app.py`, `test_evening.py`) | R6 |
| D04 | The live and headless runners each implement the request loops for decisions, lines and intentions | `TavernRuntime` in `app.py` and `_Run` in `lockstep.py`, six loops in all. They already differ: only lockstep re-raises a replay miss for intentions | R5 |
| D05 | World state has no types | 247 `dict[str, Any]` in `backend/`. `World` and `Actor` have no `TypedDict`, statuses are bare strings, and underscored progress fields (`_spot`, `_remaining`) go into saves | R2 |
| D06 | Duplicated small helpers | `_number` in `app.py` and `observation.py` beside `validation.number`; actor lookup by ID ×4; `_log` in `turns.py` and `intentions.py` | R1. The seeded roll (`Random(f"{seed}:{tick}:…")` in `dozing.py`, `conversation.py`) gets abstracted on its third use, in E21 |
| D07 | Save validation is split between `persistence.py` and the concept modules | `persistence.py` checks actors, scenes, stimuli and lines itself, while `check_mind`, `check_invitations` and `check_saved_intention` live with their concepts | R4 |
| D08 | Rules are a 40-line dict literal inside `world.py` | `world._rules()`; every save carries a copy | R3 moves the literal. Taking rules out of saves changes the save format, so that waits for Stage 4 |
| D09 | Model wiring is written twice, and the copy in the entry point is untested | `app.create_default_app` and `scripts/evening.py` (`evaluators`, `turn_writer`, `mind`) | After R5 |
| D10 | `MODE=local` is not offline: Haiku still writes lines when `ANTHROPIC_API_KEY` is set, although intentions go offline | `make evening MODE=local` spent $0.06 on 38 turn calls (2026-10-03) | Small task: local means no model calls unless `--writer haiku` is given. Write the test first |
| D11 | Stage 0 leftovers still run | the derived `visit.grievances` view; quarrel dice rolled on beer counts (`quarrel_per_beer`), which Stage 1 replaces with speech acts and escalation | E20 |
| D12 | `observe_actor` deep-copies state for every decision | most of the headless wall time (E03) | When headless runs get too slow for E28's 20 offline evenings |
| D13 | **Model health is invisible.** Nothing loudly shows whether Jev and Claude are reachable, whether the accounts have credit, and whether the keys reached the environment. A missing key or an empty account quietly turns guests into the local policy and scripted lines | `/health` always returns `ok`; the snapshot's `ai.configured` only says a key string is present; `JevError("Jev HTTP 402")` and `ClaudeError("Claude HTTP 400")` (too little credit) end up as ordinary fallbacks in the log; `make evening` reports a missing key only in a metrics note | Add `model_health.py` (core): one status per service, `ok`, `no_key`, `unreachable`, `auth` (401/403), `no_credit` (402, or Anthropic's "credit balance is too low"), or `degraded` (recent failure rate), derived from the adapters' classified errors and a cheap probe at startup (Claude: `count_tokens`; Jev: the smallest scoring request). Show it in three places: `/health` returns both statuses (still 200, so the deploy check passes); the client header gets a colored badge per service (green, amber, red, with the reason on hover); `make evening` prints a `JEV: OK / CLAUDE: NO CREDIT` banner before playing and stops a `live` run whose service is `no_key`, `auth` or `no_credit`. Probes are wired only in the shell, and tests use fakes. Do before M4 |

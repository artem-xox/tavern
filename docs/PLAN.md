# The Last Inn — Prototype Plan

Build the smallest playable prototype that tests the central question in
[DESIGN.md](DESIGN.md). Each stage has an observable completion criterion.

## 0. Validate agents in a browser tavern — done

Phaser/TypeScript frontend and Python/FastAPI backend. Visitors move, drink, sit, chat,
play darts, use the WC, and go home, with Jev scoring their options from a plain-language
briefing. See [Stage 0](stages/0_DEMO.md).

## 1. A believable evening — in progress

Four to six guests from character cards spend one evening in the hall. A barkeep works
behind the bar: he pours every mug and chats with whoever leans on the counter. Guests
queue, react to noise, talk through Claude Haiku 4.5 with speech acts, pass on news, play
dice while others watch, get drunk, and sometimes shove or fight. The player only sets up
the evening and watches. See [Stage 1 tasks](stages/1_EVENING.md).

**Status (2026-10-05):** M1–M3, the refactor R0–R8, D13 (Jev and Claude health markers), U1
(no labels in the hall), E18b (conversation memory), E19 (facts and retelling), the dice game (G0–G5)
the barkeep (B0–B6) and E20 of M4 (hostile options) are done. Next: E21 (fight resolution).
The guest's mind was reworked in parallel, by [MIND.md](MIND.md) steps 0–5: the intention reaches
speech, a guest sets a typed goal the world checks, asks the mind far less often (live seed 7: 56
intentions became 26–33, goals reached 7 of 30 became 10 of 17), may promise to come over, and the
barkeep keeps to his duty. Saved worlds are version 12. Step 6 (memory between evenings) waits for
Stage 4; the giving ticket (H0–H5 in Stage 1) is next to be picked up.
**Done when:** recorded live evenings meet the Stage 1 metrics, an observer can retell
a story from at least one of them, and its chronicle cites only logged events.

## 2. Staff and commands

The barkeep of Stage 1 (B0–B6) takes the player's commands, and a bouncer joins him on
the same activity system: serve, refill, calm someone down, throw someone out.

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
| D01 | A client module over the ~400-line limit | `scene.ts` 397 (the backend is all under 376: `lifecycle.py` 375, `recording.py` 348, `scenes.py` 345) | Split `scene.ts` before E24 |
| D05 | Part of the world state still has no types | 80 `dict[str, Any]` remain: map objects, events, memories, `Activity` targets. Underscored progress fields (`_spot`, `_remaining`) are in saves | Type map objects and events when a task touches them (`World`, `Actor` exist since R2) |
| D08 | Every save carries a copy of the rules | `state.Rules` in `world["rules"]`, written by `rules.default_rules()` | Taking rules out of saves changes the save format, so that waits for Stage 4 |
| D09 | Model wiring is written twice, and the copy in the entry point is untested | `app.create_default_app` and `scripts/evening.py` (`evaluators`, `turn_writer`, `mind`) | After R5 |
| D10 | `MODE=local` is not offline: Haiku still writes lines when `ANTHROPIC_API_KEY` is set, although intentions go offline | `make evening MODE=local` spent $0.06 on 38 turn calls (2026-10-03) | Small task: local means no model calls unless `--writer haiku` is given. Write the test first |
| D12 | `observe_actor` deep-copies state for every decision | most of the headless wall time (E03) | When headless runs get too slow for E28's 20 offline evenings |
| D14 | CI does not run mypy | `make check` runs it, `.github/workflows/ci.yml` runs `pytest`, the frontend check and the build only | Add `- run: mypy` to the workflow (`.github/` is ask-first) |
| D15 | Small leftovers in the launch wiring | `create_default_app` builds the Claude port twice (`ask = _claude_port(...)` twice); `scripts/evening.py` repeats the wiring (D09) | Delete the duplicate line; merge the wiring with D09 |
| D16 | Some types cross an import cycle only for the checker | `TYPE_CHECKING` imports in `state.py`, `scripted.py`→`TurnResult`, `scenes.py`→`TurnResult` | Move `TurnResult` and the other cross-module records to the module that owns the concept when one gets a third user |
| D17 | Haiku misuses `share_news`: it picks the act for lines that are no news, or invents words under a real `fact_id` | live evenings, seeds 5 and 1 (2026-10-04): "Need to know if the fever's crept this far up yet." and "Fever's in the river villages too, three weeks now." as `share_news` | Not checkable by a rule (it is a meaning). Tighten the act's text and examples, or have E28 count them |
| D18 | Live turn fallbacks keep coming from two Haiku slips: an `invitation` on an `accept`, and a line over 160 characters | one of each in the two E19 live evenings (a fallback per evening) | Small task: accept (and drop) an invitation on `accept`/`decline`, or say so in the prefix; the length rule stays |
| D19 | Haiku's barkeep opens most chats with the same \"Evening. …\" formula (MIND.md step 5 stopped the darts and wagers: none in the 12 lines of live seed 7, 2026-10-05) | live evening, seed 5 (2026-10-04): lines at 220 s and 227 s to Edda, and 160 s, 67 s and 89 s | Not checkable by a rule. Say in rule 16 that the barkeep never offers games or money, or have E28 count them |
| D20 | A guest's save fails to load once their conversation has outlasted the talk's 8 s: a part in a scene is never clamped at zero, so `_remaining` goes negative and `check_saved_progress` rejects it | read in `lifecycle._interact` and shown by hand (`_remaining` of -3.0 gives "Invalid saved action timer"); not yet seen in a live autosave. A `game` and a `served` verb are clamped | Failing test first (save during a 12 s conversation), then clamp every held-open verb; a bug fix, in its own commit |
| D22 | Haiku never uses the `promise` act, so MIND.md's say-and-do cannot be measured | live seeds 7, 5 and 1 (2026-10-05): offered in 108 of 223 lines, used 0, and "I'll sit by the fire if you'll have me" went out as `small_talk` | Let a `talk_to` or `sit_with` goal said aloud become a commitment without an act, or promise more kinds once giving (H3) lands; then count `promises` in `metrics.json` |
| D23 | "A new fact on a topic" is not a reason to take stock: telling news logs no memory for the listener | `social/facts.tell` calls `log_event` for the speaker only; MIND.md step 3 | Record `news_heard` for the listener and add it to `intentions.SALIENT_EVENTS`; it changes recorded evenings, so replay-pinned tests move with it |

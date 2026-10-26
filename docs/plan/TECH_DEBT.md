# Tech debt

Known problems that no current task owns. When a task leaves one behind, add a row with its evidence.
The commit that fixes it removes the row. Pay off debt that blocks the next task before starting it.
Stage numbers in older evidence refer to the [Stage 1 archive](1_evening/archive.md).

## Problems

| ID | Problem | Evidence | Resolution |
|----|---------|----------|------------|
| D05 | Part of the world state still has no types | 80 `dict[str, Any]` remain: map objects, events, memories, `Activity` targets. Underscored progress fields (`_spot`, `_remaining`) are in saves | Type map objects and events when a task touches them (`World`, `Actor` exist since R2) |
| D08 | Every save carries a copy of the rules | `state.Rules` in `world["rules"]`, written by `rules.default_rules()` | Taking rules out of saves changes the save format: do it with the next approved schema bump |
| D09 | Model wiring is written twice, and the copy in the entry point is untested | `app.create_default_app` and `scripts/evening.py` (`evaluators`, `turn_writer`, `mind`) | After R5 |
| D10 | `MODE=local` is not offline: Haiku still writes lines when `ANTHROPIC_API_KEY` is set, although intentions go offline | `make evening MODE=local` spent $0.06 on 38 turn calls (2026-10-03) | Small task: local means no model calls unless `--writer haiku` is given. Write the test first |
| D12 | `observe_actor` deep-copies state for every decision | most of the headless wall time (E03) | When headless runs get too slow for S2-11's offline evenings |
| D14 | CI does not run mypy | `make check` runs it, `.github/workflows/ci.yml` runs `pytest`, the frontend check and the build only | Add `- run: mypy` to the workflow (`.github/` is ask-first) |
| D15 | Small leftovers in the launch wiring | `create_default_app` builds the Claude port twice (`ask = _claude_port(...)` twice); `scripts/evening.py` repeats the wiring (D09) | Delete the duplicate line; merge the wiring with D09 |
| D16 | Some types cross an import cycle only for the checker | `TYPE_CHECKING` imports in `state.py`, `scripted.py`→`TurnResult`, `scenes.py`→`TurnResult` | Move `TurnResult` and the other cross-module records to the module that owns the concept when one gets a third user |
| D17 | Haiku misuses `share_news`: it picks the act for lines that are no news, or invents words under a real `fact_id` | live evenings, seeds 5 and 1 (2026-10-04): "Need to know if the fever's crept this far up yet." and "Fever's in the river villages too, three weeks now." as `share_news` | Not checkable by a rule (it is a meaning). Tighten the act's text and examples, or have S2-05's story score count them |
| D18 | Live turn fallbacks keep coming from two Haiku slips: an `invitation` on an `accept`, and a line over 160 characters | one of each in the two E19 live evenings (a fallback per evening) | Small task: accept (and drop) an invitation on `accept`/`decline`, or say so in the prefix; the length rule stays |
| D19 | Haiku's barkeep opens most chats with the same \"Evening. …\" formula (MIND.md step 5 stopped the darts and wagers: none in the 12 lines of live seed 7, 2026-10-05) | live evening, seed 5 (2026-10-04): lines at 220 s and 227 s to Edda, and 160 s, 67 s and 89 s | Not checkable by a rule. Say in rule 16 that the barkeep never offers games or money, or have S2-05's story score count them |
| D22 | Haiku never uses the `promise` act, so MIND.md's say-and-do cannot be measured | live seeds 7, 5 and 1 (2026-10-05): offered in 108 of 223 lines, used 0, and "I'll sit by the fire if you'll have me" went out as `small_talk` | Let a `talk_to` or `sit_with` goal said aloud become a commitment without an act, or promise more kinds once giving (H3) lands; then count `promises` in `metrics.json` |
| D23 | "A new fact on a topic" is not a reason to take stock: telling news logs no memory for the listener | `social/facts.tell` calls `log_event` for the speaker only; MIND.md step 3 | Record `news_heard` for the listener and add it to `intentions.SALIENT_EVENTS`; it changes recorded evenings, so replay-pinned tests move with it |
| D24 | An invitee who chooses their own answer makes the evening quieter | live seeds 5, 7, 1, 2, 3 (2026-10-09), C7: accepted invitations 3.6 → 1.0 an evening, dice games about a quarter, with `AI_ANSWERS=true` | `AI_ANSWERS` is off. Raise the wish for company, give an invitation an inviter's pull, or ask for an answer only when a need presses or the inviter is disliked; then switch it on and rerun C8's table |
| D25 | Every arrival takes the same three first steps | offline seeds 0-9 (2026-10-09), C5: pairs of guests with the same first three choices per evening 1.9 → 8.2, since `settle_in` covers ale, chair and drink for each thirsty newcomer | Let a guest's character shape the plan (a loner takes the corner, a drinker the bar), or offer `settle_in` to some arrivals only |
| D26 | The `called` count of C2 is not logged, so how many wrongs go unanswered is counted by hand from the events | C2: `responses` in `metrics.json` has answers only | Log a `called` event when `think` makes a thought of a kind in `RESPONSES` about a guest in the hall |
| D27 | Offline evenings hold too little hostile material to measure fights: 1 fight in 20 scripted evenings (target 4-7), six live evenings (seeds 5, 4, 1, 2, 3 and a hot one) had none, and not one insult | seeds 0-19 offline and six live (2026-10-10): 4 insults and 8 quarrels in 20 offline evenings, none live; the gates are not what holds fights back, the lack of a cause is (hot gates and no cause needed: 6 of 20 offline) | Let hatred or drink start a fight without a fresh cause, or have the writers insult those with bad blood (the user's call), S2-09 owns the fix; this row closes with it |
| D28 | A quarrel has no way out: an insult only carries the talk on, so two rivals trade the same two jabs for minutes and nothing follows | live Guests evening, seed 5 (2026-10-25): Trump and Musk said 27 insults in a row over four minutes ("Dice, Elon!", "Your tower's a sandcastle"), 70 quarrels, no fight, no game | A scene heat that ends the talk in an event (a bet, a walk-off, a fight) after a few rounds; with [S2-09](2_story_evenings/09_chaos.md) |
| D30 | A guest sent to fetch someone an ale pours it and then sits down instead of carrying it | live Guests evenings with S2-13's hold (seeds 1 and 5, 2026-10-25): 5 of 7 drink errands failed, e.g. Sobchak took the beer for Musk at 277 s and chose `sit` at once | Hold the host's next choice to delivering the mug, as the hold keeps an invitation's two guests talking until the answer |

## Open Stage 1 tasks

Stage 1 closed with these tasks unticked in its [archive](1_evening/archive.md). Each is either taken over
by a Stage 2 task or waits here until an evening shows it matters.

| Task | What it was | Now |
|------|-------------|-----|
| E23–E25 | New poses, living-room rendering, observer UI | Mostly delivered by the fights, UI pass and inspector work; check the archive's text before reopening any part |
| E26 | Evening setup | Replaced by [S2-02 lineup screen](2_story_evenings/02_lineup_screen.md); custom cards are out of scope |
| E27 | Chronicle | Replaced by [S2-10 retelling](2_story_evenings/10_retelling.md) |
| E28 | Acceptance | Replaced by [S2-11 acceptance](2_story_evenings/11_acceptance.md) |
| L2 | Intentions every 60 s and at more events | Open: cost. Pick up when an evening of Guests costs more than S2-11's budget |
| L3 | Stock lines per character for recurring moments | Open: cost. Fits persona cards (S2-03) once catchphrases exist |
| L4 | A shorter line-writer context | Open: cost |
| U4 | iPhone Safari: taps that land and a screen that holds still | Open: bug |
| U11 | Lighter snapshots | Open, only if U4 shows they matter |
| MIND step 6 | Memory between evenings | Dropped with Stage 4; not planned |
| S2-05 | `fight_ended` has no outcome field, so the story score reads knockouts from its words (`story_score._KNOCKOUT_WORDS`) | Open: log the outcome as a field when S2-09 touches fights |

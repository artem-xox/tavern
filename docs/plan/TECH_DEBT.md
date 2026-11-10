# Tech debt

Known problems that no current task owns. When a task leaves one behind, add a row with its evidence.
The commit that fixes it removes the row. Pay off debt that blocks the next task before starting it.
Stage numbers in older evidence refer to the [Stage 1 archive](1_evening/archive.md).

## Problems

| ID | Problem | Evidence | Resolution |
|----|---------|----------|------------|
| D05 | Part of the world state still has no types | 148 `dict[str, Any]` remain (`grep -ro "dict\[str, Any\]" backend | wc -l`, 2026-11-08): map objects, events, memories, `Activity` targets. Underscored progress fields (`_spot`, `_remaining`) are in saves | Type map objects and events when a task touches them (`World`, `Actor` exist since R2) |
| D31 | Two files are over ~400 lines on purpose, left by the R series | `social/scenes.py` 418; `mind/turn_prompt.py` 505 (prompt text). R04: `test_facts::test_a_news_item_reaches_a_third_guest_in_other_words` moved from seed 1 to seed 2 by the owner's decision (2026-11-07), no case waits for the owner | Split `scenes.py` when it next grows; leave the prompt text |
| D08 | Every save carries a copy of the rules | `state.Rules` in `world["rules"]`, written by `rules.default_rules()` | Taking rules out of saves changes the save format: do it with the next approved schema bump |
| D12 | `observe_actor` deep-copies state for every decision | most of the headless wall time (E03) | When headless runs get too slow for S2-11's offline evenings |
| D16 | Some types cross an import cycle only for the checker | `TYPE_CHECKING` imports in `state.py` (~~`scripted.py`→`TurnResult`, `scenes.py`→`TurnResult`~~ fixed by S3-R10) | Move `TurnResult` and the other cross-module records to the module that owns the concept when one gets a third user |
| D17 | Haiku misuses `share_news`: it picks the act for lines that are no news, or invents words under a real `fact_id` | live evenings, seeds 5 and 1 (2026-10-04): "Need to know if the fever's crept this far up yet." and "Fever's in the river villages too, three weeks now." as `share_news` | Not checkable by a rule (it is a meaning). Tighten the act's text and examples, or have S2-05's story score count them |
| D19 | Haiku's barkeep opens most chats with the same \"Evening. …\" formula (MIND.md step 5 stopped the darts and wagers: none in the 12 lines of live seed 7, 2026-10-05) | live evening, seed 5 (2026-10-04): lines at 220 s and 227 s to Edda, and 160 s, 67 s and 89 s | Not checkable by a rule. Say in rule 16 that the barkeep never offers games or money, or have S2-05's story score count them |
| D22 | Haiku never uses the `promise` act, so MIND.md's say-and-do cannot be measured | live seeds 7, 5 and 1 (2026-10-05): offered in 108 of 223 lines, used 0, and "I'll sit by the fire if you'll have me" went out as `small_talk` | Let a `talk_to` or `sit_with` goal said aloud become a commitment without an act, or promise more kinds once giving (H3) lands; then count `promises` in `metrics.json` |
| D24 | An invitee who chooses their own answer makes the evening quieter | live seeds 5, 7, 1, 2, 3 (2026-10-09), C7: accepted invitations 3.6 → 1.0 an evening, dice games about a quarter, with `AI_ANSWERS=true` | `AI_ANSWERS` is off. Raise the wish for company, give an invitation an inviter's pull, or ask for an answer only when a need presses or the inviter is disliked; then switch it on and rerun C8's table |
| D25 | Every arrival takes the same three first steps | offline seeds 0-9 (2026-10-09), C5: pairs of guests with the same first three choices per evening 1.9 → 8.2, since `settle_in` covers ale, chair and drink for each thirsty newcomer | Let a guest's character shape the plan (a loner takes the corner, a drinker the bar), or offer `settle_in` to some arrivals only |
| D30 | A drink errand fails right after the pour when the invitee stands away from every table (at the bar, the fire, the stage): the host has no chair to take beside them | live Guests evenings (seeds 1 and 5, 2026-10-25): 5 of 7 drink errands failed, e.g. Sobchak took the beer for Musk at 277 s and failed at once. The `sit` in the log is the errand's own step; the hold (`fetching_a_drink`) works. An invitee standing at a table is now served (`errands._carry`) | Walk the host to the invitee's bar or fire spot, or refuse `buy_drink` before the pour when no one could reach them |
| D32 | The scripted player is a timed list, blind to the hall: 11 of 12 `say` steps were refused in four live evenings, and it cannot say a stage number | S3-12, `monroe_night` seeds 1, 2, 5, 7 (2026-11-08): `talk` at 70 s refused in 3 of 4, then `say` ×3 "Nobody is listening"; `give_speech` at 500 s left `stage_silent` for 25 s in seed 1 and was refused in seed 7. 1 line was spoken | Give steps a condition ("when in a scene", "when on the stage") or retry, and a `say` that works on the stage; then rerun the four seeds and recount the first measure of S3-12 |
| D33 | A line's effect cannot be told from live noise | S3-12: the same seed and lineup with and without the player differ from the first minutes (live models are not deterministic); seed 1's twin had no fight, seed 2's and 5's had one, so "the incident changed" cannot be read off a pair | Replay the no-player evening's `calls.jsonl` up to the line and let the player diverge from there, or count a line's effect over many seeds (guest reply, goal, quarrel within 120 s) instead of one incident |
| D34 | Played evenings leave a thin record: the `say` command writes no event, so Enter-to-line cannot be measured, and the world keeps only 200 events | S3-12: `player_counts` and the `turn` events carry game time only; `scripts/export_played.py` polls the snapshot every 3 s to rebuild the log | Log a `say` event (received at, text) in `player_commands.say`; keep the full chronicle in the debug save |
| D35 | `make evening PLAYER=…` with the default scenario plays an evening with nobody at the wheel and says nothing | S3-12 (2026-11-08): the first four runs with `CAST=guests PLAYER=data/players/monroe_meddles.json` refused all 8 steps ("the played guest is not in the hall"); only `player.refused: 8` showed it, after the run | Refuse at start when the scripted player is not in the scenario's guests |
| D36 | `ignored` is not a story moment | S3-12 decision: it counts, weight 1.0. Zero `silence` turns and zero `ignored` in four scripted evenings, so no evidence yet | Add `ignored` to `story_score` `_BY_TYPE` and `WEIGHTS`; check it against the owner's played evenings |

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

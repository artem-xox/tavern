# The Story Tavern — Plan

The one list of every stage and task. Read this file first, then only the task you work on.
What we build and why is in [DESIGN.md](../DESIGN.md).

## Stages

| Stage | Goal | Status |
|-------|------|--------|
| [0 — Demo](0_demo/README.md) | Agents move, drink, sit and talk in a browser tavern | done |
| [1 — A believable evening](1_evening/README.md) | The engine: bodies, minds, talk, news, dice, fights, the barkeep | done (foundation) |
| [2 — Story evenings](2_story_evenings/README.md) | Famous guests whose evenings turn into chaos worth retelling | **current** |
| [3 — The player at the bar](3_player/README.md) | The player plays one of the guests: walks, drinks, climbs the stage, and talks to the others in typed lines | R series done; tasks S3-01–S3-12 written |

Known problems that no task owns are in [TECH_DEBT.md](TECH_DEBT.md).

## Stage 2 tasks

| ID | Task | Needs | Status |
|----|------|-------|--------|
| S2-00 | [The Story Tavern](2_story_evenings/00_story_tavern.md): new name and setting in the UI, prompts and skill | — | done |
| S2-01 | [Two casts](2_story_evenings/01_casts.md): `characters/locals/`, `characters/guests/`, the barkeep as staff | — | done |
| S2-02 | [Lineup screen](2_story_evenings/02_lineup_screen.md): pick Locals or Guests, then 1–8 faces, before the evening | 01 | done |
| S2-03 | [Persona cards](2_story_evenings/03_persona_cards.md): public persona, catchphrases, obsessions, mute characters, parody names | 01 | done |
| S2-04 | [First guests](2_story_evenings/04_first_guests.md): three famous guests with full art and a scenario | 01, 03 | done |
| S2-05 | [Story score](2_story_evenings/05_story_score.md): count what is worth retelling in every evening | — | done |
| S2-06 | [Obsessions drive goals](2_story_evenings/06_obsessions.md): a guest's obsession becomes their goals and intentions | 03, 05 | done |
| S2-07 | [Fun](2_story_evenings/07_fun.md): a need that chaos, games and signature acts fill | 05 | done |
| S2-08 | [Signature items](2_story_evenings/08_signature_items.md): the mechanic (an item offers a verb to its carrier) and Kim's phone, `livestream` | 03, 05 | done |
| S2-09 | [Chaos](2_story_evenings/09_chaos.md): a quarrel that boils over, rivals, shouting, quarrels that escalate into fights | 04, 05 | done |
| S2-10 | [Retelling](2_story_evenings/10_retelling.md): a strong model retells the log; a closing screen shows it | 05 | done |
| S2-11 | [Acceptance](2_story_evenings/11_acceptance.md): live Guest evenings meet the story targets | all | todo |
| S2-12 | [The stage](2_story_evenings/12_stage.md): a small stage from which a guest addresses the whole room | 06, 07 | done |
| S2-13 | [Livelier talk](2_story_evenings/13_livelier_talk.md): no dice nudge on every line, no repeated invitations, a prompt that plays famous guests for satire, a `funny` judge | 03 | done |
| S2-14 | [Stage numbers](2_story_evenings/14_stage_numbers.md): toast, roast, pitch or confession, written by Haiku; a heckle from the floor and a comeback | 12, 13 | done |
| S2-15 | [A stage worth climbing](2_story_evenings/15_stage_look.md): a square 2-by-2 platform with a lectern and footlights that flare during a number | 14 | done |
| S2-16 | [Talk where you stand](2_story_evenings/16_standing_talk.md): two guests standing still near each other anywhere in the hall can start a conversation | — | done |
| S2-17 | [Walk up to someone standing](2_story_evenings/17_walk_up.md): `approach` reaches a guest on their feet, who waits for the walker | 16 | done |
| S2-18 | [Greta's protest sign](2_story_evenings/18_protest_sign.md): `raise_sign` at the guest she blames most, the whole hall hears | 08 | done |
| S2-19 | [Sobchak's microphone](2_story_evenings/19_interview.md): `interview_guest`, a conversation that plays as an interview | 08 | done |
| S2-20 | [Lukashenko and his potatoes](2_story_evenings/20_lukashenko_potato.md): a new guest who presses a potato into every hand near him | 08 | done |
| S2-21 | [Kim Jong Un's little flag](2_story_evenings/21_kim_flag.md): `brandish_flag` at the guest he dislikes most, a threat | 08 | done |

Order: 00, 01 and 05 can run in parallel. 05 lands before 06–09 so that each of them is measured
against a baseline. 08 and 09 both touch `activities.py`, `actions.py` and `local_policy.py`: do not run
them at the same time. 17 builds on 16's rule and touches the same three files as 08 and 09: run it
after 16 is merged and not alongside 08 or 09. 18 and 19 build on 08 and touch the same files: run them one at a time, after 08 is merged.

## Stage 3 prep: the R series

Cleanup and refactors before the player tasks are written, on the series branch `claude/s3-prep`. Why each
exists, the rules (golden check, approved test edits only), the parallel lanes, the waves and their merge order
are in [3_player/README.md](3_player/README.md#one-series-branch-parallel-lanes). `Needs` here is what must be
merged before a task starts; tasks whose needs are met run at once.

| ID | Task | Needs | Status |
|----|------|-------|--------|
| S3-R00 | [Golden evenings](3_player/r00_golden.md): `make golden`, the baseline every refactor diffs against | — | done |
| S3-R01 | [Delete dead code](3_player/r01_dead_code.md): 3 unused names, a retired tariff, the benchmark script, a duplicated plan file | R00 | done |
| S3-R02 | [Private names](3_player/r02_private_names.md): 19 module-local functions get an underscore | R00 | done |
| S3-R03 | [Retire the card compiler](3_player/r03_card_compiler.md): no client calls `POST /api/cards/compile` | R00 | done |
| S3-R04 | [Production switches](3_player/r04_production_switches.md): `lean`, `aims`, `projects` always on, so tests run the evening's path | R01, R03 | done |
| S3-R05 | [One event log](3_player/r05_event_log.md): one length (200), the logged event returned, one reader of new events | R02 | done |
| S3-R06 | [Rules read fields](3_player/r06_rules_read_fields.md): `verb`, `invitation`, `inviter_id` on events; save version 23 | R05 | done |
| S3-R07 | [Metrics read fields](3_player/r07_metrics_read_fields.md): actions, invitations, talk | R06, R10 | done |
| S3-R07b | [More metrics read fields](3_player/r07b_more_metrics_read_fields.md): aims, goals, responses, projects, speeches | R06 | done |
| S3-R08 | [One observation](3_player/r08_one_observation.md): built once, typed, `people` only | R04 | done |
| S3-R09 | [Whereabouts](3_player/r09_whereabouts.md): table, bar and reach move to `hall/whereabouts.py` | R02 | done |
| S3-R10 | [The turn view](3_player/r10_turn_view.md): to `mind/turn_view.py`; `TurnResult` out of the cycle (D16) | R02 | done |
| S3-R11 | [Candidates](3_player/r11_candidates.md): `mind/candidates.py` apart from choosing | R01, R04, R08 | done |
| S3-R12 | [Haiku's intention question](3_player/r12_haiku_intentions.md): `mind/haiku_intentions.py` | R00 | done |
| S3-R13 | [One wiring](3_player/r13_evening_wiring.md): config, Claude config, mind loop and end rule shared (D09) | R04 | done |
| S3-R14 | [The evening report](3_player/r14_evening_report.md): `evening/report.py`, tested | R04 | done |
| S3-R15 | [Shared test steps](3_player/r15_test_steps.md): 20 copied `advance` / `command` helpers go | R00 | done |
| S3-R16 | [Test audit](3_player/r16_test_audit.md): wording, data and tuning pins; twins merged | R00 | done |
| S3-R17 | [Pure pose and picking](3_player/r17_scene_logic.md): out of `scene.ts`, tested | — | done |
| S3-R18 | [Frontend tests in CI](3_player/r18_ci_frontend_tests.md): Node 24, `npm test` | — | done |
| S3-R19 | [Close the series](3_player/r19_close_the_series.md): AGENTS.md, tech debt, index, names, stale docs | all | done |

## Stage 3 tasks

The decisions behind them (owner, 2026-11-08), the principles and the order are in
[3_player/README.md](3_player/README.md).

| ID | Task | Needs | Status |
|----|------|-------|--------|
| S3-01 | [Split the verb table](3_player/01_verb_table_split.md): `activity.py`, `effects.py`, `activities.py` (D31) | — | todo |
| S3-02 | [Who steers a body](3_player/02_steering.md): `world.player`, `steered`, no model or script for a steered guest, `silence`, autopilot | — | todo |
| S3-03 | [The player's hands](3_player/03_hands.md): `act`, `options`, the `walk_to` verb | 01, 02 | todo |
| S3-04 | [The player's voice](3_player/04_voice.md): `say`, a model reads the text as a speech act, cutting in | 02 | todo |
| S3-05 | [Silence and typing](3_player/05_silence.md): typing holds the turn, silence makes the speaker feel ignored | 04 | todo |
| S3-06 | [The player on the stage](3_player/06_stage.md): the player's own number, a comeback to a heckle | 04, 05 | todo |
| S3-07 | [Take the wheel](3_player/07_take_the_wheel.md): "Play as", the "you" marker, autopilot, pause, the cheat sheet | 02 | todo |
| S3-08 | [Click to act](3_player/08_click_to_act.md): walk on a click, a menu of the verbs open now | 03, 07 | todo |
| S3-09 | [The chat](3_player/09_chat.md): the scene's lines, the input, "To:", "your turn" | 04, 05, 07 | todo |
| S3-10 | [A scripted player](3_player/10_scripted_player.md): headless evenings with a player, golden, replay, metrics | 03, 04 | todo |
| S3-11 | [The player in the story](3_player/11_story.md): the retelling and the closing screen know who was played | 04 | todo |
| S3-12 | [Acceptance](3_player/12_acceptance.md): played and scripted evenings meet the stage's "done when" | all | todo |
| S3-13 | [What the body may do](3_player/13_body_options.md): the player's options are what the world accepts (any free chair, a clicked table) | 03, 08 | done |

## How the plan is kept

- **One stage, one directory** (`<n>_<name>/`). Its `README.md` holds the goal, the decisions, and the
  "done when". It is short: no task bodies.
- **One task, one file** (`<nn>_<name>.md`), about one PR. Start from [TEMPLATE.md](TEMPLATE.md). A task
  file stays under about 150 lines. When it grows past that, split it into two tasks.
- **This file is the index.** When a task's status changes, its row here changes in the same commit.
  Statuses: `todo`, `doing`, `done`, `dropped`.
- **Closed stages keep an archive.** `0_demo/archive.md` and `1_evening/archive.md` are the old
  single-file plans, kept as history. Do not add to them. Read one only when a task links to a section of it.
- **Results go into the task file.** When a task is done, its file gets a short "Results" section: what was
  built, the numbers, and one moment from a log.

## Working on a task

The steps every task follows. [AGENTS.md](../../AGENTS.md) has the rules behind them.

1. **Read first.** Read the task file, the test file of every module you will touch (the tests are the spec),
   and the modules the task names. Grep for the concept before adding a helper.
2. **Freeze the shape.** Write the exact new fields (save, snapshot, model view, model answer) into the task
   file before writing code. If the code disagrees with the proposal, update the file first.
3. **Branch.** Work on `claude/s<stage>-<nn>-<name>` (for example `claude/s2-05-story-score`), off `main`.
   Set the task to `doing` here.
4. **Red, green, refactor.** One behavior at a time. Show the failing run before the fix. Refactors and
   behavior changes go in separate commits.
5. **Saves.** A field that must survive a reload bumps `schema_version` in `world.create_world` and
   `persistence.parse_world`, with a check function in the concept module (like `thoughts.check_mind`).
   `test_database.py` pins the version: name it in the commit as an approved behavior change. Ask the user
   before the first bump in a stage.
6. **Snapshot.** If the snapshot changes, change `frontend/src/types.ts` in the same commit and run `make build`.
7. **Model prompts.** The shared prefixes (`turn_prompt.shared_prefix`, `data/minds/intention_prefix.md`)
   stay byte-identical across calls and above 4,096 tokens. Per-character text goes in the second cached
   block (the card), per-moment text in `content`. Answers are checked at the boundary (`check_*`, `parse_*`).
8. **Check.** `make check` (plus `make build` if `frontend/` changed). For a task that changes an evening,
   also run an offline evening
   (`.venv/bin/python scripts/evening.py --seed 5 --mode local --writer scripted --out runs/<task>-offline`),
   a live one (`make evening SEED=5 OUT=runs/<task>-live`), and its replay
   (`MODE=replay CALLS=runs/<task>-live/calls.jsonl`); `cmp` the two `events.jsonl` files.
9. **Record.** Add "Results" to the task file and set it to `done` here. Add any problem you leave behind
   to [TECH_DEBT.md](TECH_DEBT.md).

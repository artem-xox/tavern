# The Story Tavern — Plan

The one list of every stage and task. Read this file first, then only the task you work on.
What we build and why is in [DESIGN.md](../DESIGN.md).

## Stages

| Stage | Goal | Status |
|-------|------|--------|
| [0 — Demo](0_demo/README.md) | Agents move, drink, sit and talk in a browser tavern | done |
| [1 — A believable evening](1_evening/README.md) | The engine: bodies, minds, talk, news, dice, fights, the barkeep | done (foundation) |
| [2 — Story evenings](2_story_evenings/README.md) | Famous guests whose evenings turn into chaos worth retelling | **current** |
| [3 — The player at the bar](3_player/README.md) | The player walks into the same room and talks to guests in typed lines | planned |

Known problems that no task owns are in [TECH_DEBT.md](TECH_DEBT.md).

## Stage 2 tasks

| ID | Task | Needs | Status |
|----|------|-------|--------|
| S2-00 | [The Story Tavern](2_story_evenings/00_story_tavern.md): new name and setting in the UI, prompts and skill | — | doing |
| S2-01 | [Two casts](2_story_evenings/01_casts.md): `characters/locals/`, `characters/guests/`, the barkeep as staff | — | done |
| S2-02 | [Lineup screen](2_story_evenings/02_lineup_screen.md): pick Locals or Guests, then 1–6 faces, before the evening | 01 | done |
| S2-03 | [Persona cards](2_story_evenings/03_persona_cards.md): public persona, catchphrases, obsessions, mute characters, parody names | 01 | doing |
| S2-04 | [First guests](2_story_evenings/04_first_guests.md): three famous guests with full art and a scenario | 01, 03 | doing |
| S2-05 | [Story score](2_story_evenings/05_story_score.md): count what is worth retelling in every evening | — | done |
| S2-06 | [Obsessions drive goals](2_story_evenings/06_obsessions.md): a guest's obsession becomes their goals and intentions | 03, 05 | todo |
| S2-07 | [Fun](2_story_evenings/07_fun.md): a need that chaos, games and signature acts fill | 05 | todo |
| S2-08 | [Signature items](2_story_evenings/08_signature_items.md): what is in the backpack, and the act it unlocks | 03, 05 | todo |
| S2-09 | [Chaos](2_story_evenings/09_chaos.md): rivals, shouting, quarrels that escalate into fights | 04, 05 | todo |
| S2-10 | [Retelling](2_story_evenings/10_retelling.md): a strong model retells the log; a closing screen shows it | 05 | doing |
| S2-11 | [Acceptance](2_story_evenings/11_acceptance.md): live Guest evenings meet the story targets | all | todo |

Order: 00, 01 and 05 can run in parallel. 05 lands before 06–09 so that each of them is measured
against a baseline. 08 and 09 both touch `activities.py`, `actions.py` and `local_policy.py`: do not run
them at the same time.

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

# Stage 3 — The player at the bar (prep)

**Goal:** the player walks into the same evening as a character and talks to the guests in typed lines.
The guests answer, remember it, and act on it.

The player tasks are not written yet. First comes the **R series** below: cleanup and refactors that make
the code ready for a third kind of actor. The outline of the player work:

- **An avatar in the room.** The player has a body on the same activity system: walk, sit, drink, play,
  shove. The world validates every player action as it does a guest's.
- **Typed lines.** The player writes free text; a model turns it into a speech act (ask, joke, insult,
  invite, give news) the world can validate. The text itself is what the guests hear.
- **Guests answer the player.** The player joins scenes like a guest; the line writer treats them as one,
  and their words reach thoughts, relationships and intentions.
- **The player in the story.** The story score and the retelling include what the player did.

**Done when:** a player line changes how an evening's main incident ends, and the retelling shows it.

## The R series: prepare the code for the player

Audit of 2026-11-07: 133 backend modules (23k lines), 197 test files (27k lines, 4,706 cases, about 2 minutes),
33 frontend modules. What it found, and the tasks that fix it:

| Finding | Tasks |
|---------|-------|
| Dead code, a dead feature (the card compiler has no client), a dead script, a duplicated plan file | R01, R03 |
| 19 public functions nothing else imports, against the `_private` rule | R02 |
| Tests run the AI switches `lean`, `aims`, `projects` **off**; every real evening runs them **on**. 23 cases fail when the defaults match production | R04 |
| `log_control` trims the event log to 100 while everything else keeps 200; 7 modules patch `world["events"][-1]`; two runners find "new events" two ways | R05 |
| Two rules and eleven metrics read event wording (`"from Ada"`, `" chose "`, `" talk"`, regexes) instead of fields | R06, R07, R07b |
| An observation is assembled in three places; `visitors` duplicates part of `people`, and readers merge the two again | R08 |
| "Where is someone" lives in `social/scenes.py`, so `body/` and `hall/` import scenes; `TurnResult` crosses an import cycle (D16); the writer's view sits in `social/` | R09, R10 |
| `agents.py` (547 lines) lists options **and** chooses; `intentions.py` (536) schedules, views, asks Haiku **and** applies | R11, R12 |
| Model wiring written twice, once untested (D09); the 38-key metrics report is assembled inside the entry point | R13, R14 |
| `advance` and `command` copied verbatim into 14 test files and `dice_hall.py`, beside the shared ones in `social_hall.py` | R15 |
| Tests that pin wording, data or a tuning number rather than a behavior; same-shape twins | R16 |
| Pose choice and click picking are logic inside the Phaser class (`scene.ts`, 397 lines); CI never runs the frontend tests | R17, R18 |
| AGENTS.md, plan index, tech debt, package names (`the-last-inn`) and a stale art plan out of date | R19 |

Left alone on purpose: `body/activities.py` (687 lines) is the verb table, one source by design; split it
when the first player verb is added. `mind/turn_prompt.py` (505) is prompt text.

### Tasks

Every test edit, removal and decision below was approved by the owner on 2026-11-07; each task file records it.

| ID | Task | Needs | Approved |
|----|------|-------|----------|
| S3-R00 | [Golden evenings](r00_golden.md) | — | — |
| S3-R01 | [Delete dead code](r01_dead_code.md) | R00 | a retired tariff becomes test data in 2 test files |
| S3-R02 | [Module-local functions get an underscore](r02_private_names.md) | R00 | — |
| S3-R03 | [Retire the card compiler](r03_card_compiler.md) | R00 | the feature and its 2 test files go |
| S3-R04 | [Lean, aims, projects always on](r04_production_switches.md) | R01, R03 | the switches go; 6 test deletions, 19 triaged adaptations |
| S3-R05 | [One event log](r05_event_log.md) | R02 | — (a bug fix, test first) |
| S3-R06 | [Rules read fields, not words](r06_rules_read_fields.md) | R05 | save bump 22 → 23 |
| S3-R07 | [Metrics read fields: actions, invitations, talk](r07_metrics_read_fields.md) | R06, R10 | new fields in hand-built test events |
| S3-R07b | [Metrics read fields: the rest](r07b_more_metrics_read_fields.md) | R06 | new fields in hand-built test events |
| S3-R08 | [One observation](r08_one_observation.md) | R04 | 12 `visitors` uses in tests; 4 triaged cases |
| S3-R09 | [Whereabouts](r09_whereabouts.md) | R02 | test import lines |
| S3-R10 | [The turn view](r10_turn_view.md) | R02 | test import lines |
| S3-R11 | [Candidates apart from choosing](r11_candidates.md) | R01, R04, R08 | test import lines |
| S3-R12 | [Haiku's intention question](r12_haiku_intentions.md) | R00 | test import lines |
| S3-R13 | [One wiring for both runners (D09)](r13_evening_wiring.md) | R04 | — |
| S3-R14 | [The evening report](r14_evening_report.md) | R04 | — |
| S3-R15 | [Shared test steps](r15_test_steps.md) | R00 | 20 copied helpers go |
| S3-R16 | [Test audit](r16_test_audit.md) | R00 | every row as written |
| S3-R17 | [Pure pose and picking](r17_scene_logic.md) | — | — |
| S3-R18 | [Frontend tests in CI](r18_ci_frontend_tests.md) | — | the `.github/` change |
| S3-R19 | [Close the series](r19_close_the_series.md) | all | the pixel art plan is history |

`Needs` lists only what must be **merged before a task starts**: a real dependency (R07 reads the fields R06
adds) or an edit of the same function (R05 edits `log_act`, which R02 renames). Two tasks that only touch
the same file at different places may run at once; they merge in the order given below.

### Rules of the series

- **No behavior change** unless the task names one. The proof is the golden check of [R00](r00_golden.md):
  before its first edit a lane records `make golden GOLDEN=runs/golden-base`, then after each step
  `make golden GOLDEN=runs/golden-now && diff -r runs/golden-base runs/golden-now` prints nothing.
  A task allowed to change the log says which files and fields may differ.
- **Test edits only where the task lists them.** A refactor that makes any other test fail is a refactor bug.
- **One commit per step**, refactors and behavior changes never in one commit.
- Moving code: move it verbatim with its comments and docstrings, then fix imports. Do not rename, reformat
  or "improve" on the way.
- Line numbers in the tasks are from 2026-11-07 ("about line N"): find the code by name if it moved.
- "Done" is `make check` (plus `make build` if `frontend/` changed) and the golden check, pasted into the
  task's Results. Where a task says "PR", read "Results": lanes merge into the series branch, not into `main`.

### One series branch, parallel lanes

- **The series branch** is `claude/s3-prep`, off `main`. The session that owns it (the integrator) starts the
  lanes, merges them, and keeps [the index](../README.md) up to date. Nothing reaches `main` until the owner
  says so: one PR at the end, or one per wave.
- **A lane** is one task in its own session and git worktree, on `claude/s3-r<nn>-<name>`, branched from the
  tip of `claude/s3-prep` when it starts. Up to six lanes at once: a full `make check` takes about 2.5
  minutes of one core.
- **A lane starts as soon as every task in its `Needs` is merged.** The waves below are the earliest
  schedule, not gates: R04 starts the moment R01 and R03 are in, even while the rest of wave 2 runs.

Lane checklist:

1. Worktree setup (a fresh worktree has no `.venv`, `node_modules` or `runs/`): from the worktree root,
   `ln -s <main checkout>/.venv .venv`, `ln -s <main checkout>/frontend/node_modules frontend/node_modules`,
   `mkdir -p runs`. Scripts need `PYTHONPATH=backend` or they run the main checkout's code; `make golden`
   sets it.
2. `make golden GOLDEN=runs/golden-base` before the first edit.
3. Work the task, one commit per step, each step's check.
4. Touch only the files the task names and the task's own file (status line and Results). Never the index
   (`docs/plan/README.md`) or another task's file: parallel lanes would collide there.
5. Done: `git merge claude/s3-prep` into the lane (the series has moved on), resolve the conflicts below,
   run `make check` again, fill Results, and report to the integrator. Do not merge into the series branch
   yourself.

The integrator: marks a task `doing` in the index when its lane starts and `done` when merged; merges with
`git merge --no-ff`, in the wave's merge order when several lanes are ready; runs `make check` on the tip after
every merge (a red tip goes back to the lane that broke it); runs `make build` at the end of a wave.

### Waves

| Wave | Start together | Merge order | Why |
|------|----------------|-------------|-----|
| 1 | R00; R17, R18 (they need nothing) | R00, R17, R18 | Every backend lane needs the golden target |
| 2 | R01, R02, R03, R12, R15, R16 | R01, R02, R03, R15, R16, R12 | No two edit the same function. R12 moves Haiku's question out of `intentions.py`, which nobody else edits until wave 4 |
| 3 | R04, R05, R09, R10 | R05, R09, R10, R04 | R05, R09, R10 edit code R02 renamed; R04 waits for R01 and R03. R10 merges after R09: both reshape `scenes.py` |
| 4 | R06, R08, R13, R14 | R06, R08, R14, R13 | R06 extends what R05 changed in `record_event`; R08 must triage on R04's production path; R13 and R14 rewrite lines R04 edits |
| 5 | R07, R07b, R11 | R07, R07b, R11 | R07 and R07b read R06's fields; R11 moves the part of `agents.py` that R01, R04 and R08 edit |
| 6 | R19 | — | Documents the finished series |

The critical path is R00 → R02 → R05 → R06 → R07 → R19: six merges in a row. Everything else fits beside it.

### Expected conflicts when a lane merges the series branch

These files are shared by tasks that run at once; the conflicts are textual, and the answer is "keep both":

| File | Tasks | Resolution |
|------|-------|------------|
| `frontend/src/types.ts` (`WorldEvent`) | R06, R07, R07b | keep every new optional field |
| `app.py`, `scripts/evening.py` (imports, config) | R03, R04, R12, R13, R14 | keep each side's edits; R13 and R14 own different functions of the script (`config` and the writers vs `main`'s report) |
| `.env.example` | R03, R04 | keep both removals |
| test import blocks | R09, R10, R11, R12, R15 | keep both sides' import lines, then `make test` |
| `hall/world.py` | R01 (imports), R06 (schema version), R08 (`observe_actor`) | keep both |
| `mind/intentions.py` | R12 (question code out), R07b (`deliver_intention`), R08 (`intention_view`) | keep both |
| `docs/plan/TECH_DEBT.md` | R10 (D16), R13 (D09) | keep both rows' edits |
| `AGENTS.md` | R11 (verb recipe), R16 (testing rubric) | keep both |

A conflict in any other file, or inside one function on both sides, is a surprise: stop and ask the integrator.

### First design question of Stage 3 (not a task yet)

Today `hall.staff.on_staff` answers two questions at once: what a body may do (staff cells, never a target)
and who decides for it (`decisions.free_to_decide`, intentions, line writing skip staff). A player is a guest's
body whose decisions, answers and lines come from a person. Decide that split when the first player task is
written; the R series leaves it alone.

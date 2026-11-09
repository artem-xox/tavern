# Stage 3 — The player at the bar

**Goal:** the player walks into the evening as one of the famous guests and plays them. They walk, pour a
beer, sit, play, climb the stage, and talk to the others in typed lines, to one guest or to the whole company.
The guests take them for the character they play: they answer, remember what was said, and act on it.

**Done when:** a player line changes how an evening's main incident ends, and the retelling shows it.

The R series (below) prepared the code. Tasks S3-01 to S3-12 build the player.

## Decisions (owner, 2026-11-08)

| Question | Decision |
|----------|----------|
| Whom the player plays | A guest from the catalog, picked on the lineup screen from that evening's guests ("Play as"). The body, card, persona, backpack and ties are that guest's, so the guests who are rivals of the player's Putin hate him from the first minute. A card of the player's own comes in a later stage |
| Who drives when the player does not | An autopilot switch. On autopilot, the guest's own mind (Jev, Haiku) plays them like any other guest. With the wheel, the player decides. The switch can be flipped at any moment |
| Time while the player types | When it is the player's turn, their scene waits for them while the rest of the hall goes on. The player can cut in at any moment: the line takes the scene's next free slot. Pause is always at hand for thinking |
| Silence | If the player neither types nor speaks for `rules.player.silence` real seconds, the turn passes, and whoever spoke to them feels ignored. That is story material |
| To whom | Inside a scene, as for guests: to one member or to everyone in it, and neighbours overhear by the hearing rules. To talk to someone outside the scene, the player first walks up to them (click the guest, then Talk). The stage reaches the whole hall |
| What the words do | A model reads the player's free text as a speech act, with its addressee, invitation kind or news, and the world validates it. There are no act buttons. The guests hear the player's text word for word. A reading the world refuses becomes a `remark` |
| Addressee | "To: auto" by default: the model picks the addressee from the text. The player may pick "everyone" or one member instead, in a picker or by clicking a face |
| The body | Click the floor to walk there. Click a thing or a person to get a menu of the verbs open now: the same legal options a guest's mind chooses from. The world validates every action |
| Language | English everywhere, as now |
| What the player sees | Everything an observer sees: the inspector, minds, moods. This is a story toy, not a game of hidden information |
| Goals | A cheat sheet from the card: obsessions, catchphrases, rivals. Nothing is checked or scored |
| Saves | Save-format bumps that reject older saves are approved for every Stage 3 task; each task names its own bump |

## Principles

1. **One body, two drivers.** The world does not care who decides. `hall/player.py` answers a single question,
   `steered`: does the player hold the wheel of this body right now? Every place that asks a model or a script
   for a guest (a decision, an intention, a line, an invitation answer, a number on the stage, a heckle) skips
   a steered body. Nothing else changes. This also answers the design question at the end of this file:
   `on_staff` still says what a body may do, and `steered` says who decides for it.
2. **Same rules.** The player's actions go through `start_action` and their lines through `check_turn`, like a
   guest's. Needs, drunkenness, wounds and thoughts run on their body as on anyone's. Since no decision is asked
   for them, nothing makes them act, but the world's own effects still land: a knock-out, a quarrel, a pressing
   need that others can see.
3. **No words in the player's mouth.** No model line and no scripted line is ever spoken for a steered guest:
   no scripted fallback for their turn, no scripted number on the stage, no heckle. Silence is a legal outcome.
4. **Text is untrusted.** A player line is 1–200 characters (`scripted.MAX_LINE`). It reaches other guests'
   prompts only as a quoted line of the scene, like a guest's line, and its reading is checked at the boundary
   (`check_turn`).
5. **One path for every runner.** The player's commands are core functions (`evening/player_commands.py`), and the
   live runtime only routes them there. Readings travel through the mind loop's courier. A headless evening with a
   scripted player (S3-10) therefore plays exactly the code a person plays, and it replays byte for byte.

## How a typed line travels

```
client ──say {text, to}──► player_commands.say ──► the scene's next slot is claimed for the player
                                   │                (an NPC's line in flight is dropped)
                                   ▼
                          MindLoop.read_line ──courier──► reader (Haiku; offline: a remark)
                                                                │ {act, addressee, topic, invitation?, fact_id?}
                                                                ▼
   scene speaks it when due ◄── player_lines.deliver_reading: line = the text, check_turn, refused → remark
   (hear_line, overhear_turn, the act's effect: as for any guest)
```

When the scene's next speaker is the steered guest, no writer is asked. The scene waits until the player's line
arrives, or until `rules.player.silence` passes with no typing, which plays a `silence` turn.

## New shapes, by task

| Shape | Task |
|-------|------|
| `world.player`: `{actor_id, steering}`; `rules.player.silence`; `Scenario.player`; the `steer` command; the `silence` act | S3-02 |
| The `walk_to` verb with `Action.cell`; the `act` and `options` commands; the `player_act` event | S3-03 |
| The `say` command; the `ReadLine` port; `turn` events from the player carry `player: true` | S3-04 |
| `world.player.typing_at`; the `typing` command; the `ignored` thought | S3-05 |
| The `ReadNumber` port; `say` on the stage | S3-06 |
| `start.player` from the lineup screen; the played guest comes in first | S3-07 |
| The snapshot's `player_turn` | S3-09 |
| Player scripts (`data/players/`); `player` in `metrics.json` | S3-10 |

## Tasks

| ID | Task | Needs |
|----|------|-------|
| S3-01 | [Split the verb table](01_verb_table_split.md): `activity.py`, `effects.py`, `activities.py` (D31), before the first player verb | — |
| S3-02 | [Who steers a body](02_steering.md): `world.player`, `steered`, no model or script for a steered guest, `silence`, autopilot | — |
| S3-03 | [The player's hands](03_hands.md): `act`, `options`, the `walk_to` verb | 01, 02 |
| S3-04 | [The player's voice](04_voice.md): `say`, a model reads the text as a speech act, cutting in | 02 |
| S3-05 | [Silence and typing](05_silence.md): typing holds the turn, silence makes the speaker feel ignored | 04 |
| S3-06 | [The player on the stage](06_stage.md): the player's own number, a comeback to a heckle | 04, 05 |
| S3-07 | [Take the wheel](07_take_the_wheel.md): "Play as" on the lineup, the "you" marker, autopilot, pause, the cheat sheet | 02 |
| S3-08 | [Click to act](08_click_to_act.md): walk on a click, a menu of the verbs open now | 03, 07 |
| S3-09 | [The chat](09_chat.md): the scene's lines, the input, "To:", "your turn" | 04, 05, 07 |
| S3-10 | [A scripted player](10_scripted_player.md): headless evenings with a player, golden, replay, metrics | 03, 04 |
| S3-11 | [The player in the story](11_story.md): the retelling and the closing screen know who was played | 04 |
| S3-12 | [Acceptance](12_acceptance.md): evenings played by a person and by scripts meet the stage's "done when" | all |
| S3-13 | [What the body may do](13_body_options.md): the player's options are what the world accepts, so any free chair and a clicked table seat them | 03, 08 |
| S3-14 | [Click a guest](14_click_a_guest.md): inspect anyone while playing; the dialogue popup in the middle, reply by clicking a guest | 08, 09 |
| S3-16 | [Cut the dead air](16_dead_air.md) (P5): the line shows at once, auto-pause for a person, skip ahead, a 10-minute played evening | 05, 09 |

Order: 01 and 02 can start together. Once 02 is merged, 04 and 07 can run beside 03, and 11 can start once 04
is in. 03, 04, 05 and 10 all
add handlers to `evening/player_commands.py` and commands to `frontend/src/types.ts`. The conflicts there are
textual: keep both sides. 05 and 06 both change when a steered guest's wait ends, so run 06 after 05. Client tasks
(07, 08, 09) can run beside the backend ones once their commands exist.

**Not in this stage:** a card of the player's own; several players in one evening; heckling from the floor or
shouting to the hall from outside a scene; goals that are checked or scored; other languages.

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

### First design question of Stage 3 (answered 2026-11-08)

Today `hall.staff.on_staff` answers two questions at once: what a body may do (staff cells, never a target)
and who decides for it (`decisions.free_to_decide`, intentions, line writing skip staff). A player is a guest's
body whose decisions, answers and lines come from a person. **Answer:** `on_staff` keeps the first question.
The second becomes `hall.player.steered` (principle 1 above, task [S3-02](02_steering.md)). Staff still never
decide, through their own routine; a steered guest never decides, because the player does it for them.

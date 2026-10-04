# Stage 1 — A Believable Evening

Four to six guests spend one evening in the hall. The test is whether model-driven
guests look like real people who came to relax, and whether the evening produces a
story an observer can retell, with every cause visible in the event log.

## Decisions

- **Player:** observer and administrator. Before the evening they pick the guests and
  the news; during it they watch and inspect. Debug controls stay, in a debug panel.
- **Scope:** one evening in the existing hall, four to six guests and one barkeep (B0–B6),
  closing time ends it. No other staff, prices, agreements, or memory between evenings yet.
- **Models:** Jev scores activities (choice layer); Claude Haiku 4.5
  (`claude-haiku-4-5`) writes conversation turns, intentions, card extraction, and the
  chronicle (mind layer) through structured outputs. Without keys, the labeled local
  policy and scripted lines run instead.
- **Violence:** shoves, fights, and knockouts with 5–10 new poses. Outcomes come from
  character stats plus seeded chance, in the spirit of RimWorld's social fights.
- **Drinks:** guests queue at the tap and the barkeep pours (B3); a hall without staff keeps
  the self-service tap.
- **Language:** English only: prompts, guests' lines, cards, news, and the chronicle.

## Engine

Layers, rules, and the “models decide what, the game decides how” boundary are in
[DESIGN.md](../DESIGN.md#how-a-guest-thinks). Stage 0 parts that stay: the
authoritative server world, A*, reservations, sessions and saves, the briefing, Jev
scoring with the near-best draw, stale-decision rejection, and the local policy.
Parts that are replaced: the scripted 8-second `talk`, the `grievances` list (by
thoughts), quarrel dice (by speech acts and escalation), and the three fixed visitors
(by a scenario).

### Data shapes

Exact fields are frozen in each task before implementation; this is the outline.

- **Activity:** `verb`, `roles`, `target_kinds`, `duration`, `interruptible`,
  `effects`, `stimulus` (`kind`, `loudness`), `pose`, model-facing `description` and
  `guidance`, and, for effects that need code, a direct reference to a core function
  (never a handler looked up by name).
- **Character card:** `id`, `name`, `sprite`, text (`occupation`, `background`,
  `temperament`, `speech`, `quirks`, `secret`, `goal`) and params in 0–1
  (`patience`, `temper`, `sociability`, `courage`, `strength`, `brawling`,
  `tolerance`, `comfort`, `curiosity`).
- **Scenario:** guest IDs with arrival times, starting relationships, news items,
  timed world events, closing time, and seed.
- **Thought:** `kind`, `about` (actor ID or null), `mood`, `opinion`, `expires_at`,
  `source_event`. Mood is the sum of active thoughts plus needs.
- **Relationship:** per ordered pair, `opinion` (−100…100), `familiarity`
  (`stranger`, `acquaintance`, `friend`), `knows_name`.
- **Stimulus:** `kind`, `source` (actor or cell), `loudness` (0–1), `time`,
  `event_id`. Hearing falls off with distance and walls.
- **Conversation:** `id`, `participants`, `topic`, `turns` (speaker, line, act),
  `next_turn_at`.
- **Turn result (Haiku):** `line`, `act`, `addressee`, `topic`, optional `fact_id` or
  `invitation`; validated against the speaker's knowledge and legal invitations.
- **Fact:** `id`, `topic`, `text`; each guest's copy keeps `heard_from`, `told_as`
  (the words they heard), and `confidence`.

### Determinism and cost

Stage 1 changes the saved-world format and adds the `anthropic` SDK; both need the
user's approval before the first task that does so ([AGENTS.md](../../AGENTS.md)).

Every model call goes through one gateway that records request, response, and usage.
Headless evenings run in lockstep with fixed virtual model latency, so a recorded
evening replays to the same event log. Live sessions keep asynchronous calls.

Haiku 4.5 costs $1 input / $5 output per million tokens; cached reads cost a tenth of
input. Its minimum cacheable prefix is 4096 tokens, so a shared prefix (world notes,
speech-act rules, style, examples) of at least that size goes first, then the speaker's
card behind a second breakpoint. Estimate: about $0.0025 per turn and 300–500 turns in
a 20-minute evening with five guests, so roughly $1 per evening; Jev adds about $0.10.
E16 measures this; E28 sets the budget.

## Status

M1–M3, the refactor R0–R8, the model health markers (D13), U1 (no labels in the hall) and E18b
(conversation memory) and E19 (facts and retelling) are done (2026-10-04). Next:

1. **Dice (G0–G5).** Guests agree to a game of dice, play it at a dice table, and others watch.
2. **The barkeep (B0–B6).** A barkeep keeps to four cells behind the bar, pours every mug,
   and chats with guests who lean on the counter. Dice and the barkeep may go in either
   order (see Order).
3. **M4, news and conflict (E20–E22).** E20 gives guests hostile options.

The door at closing (D02) is fixed: it takes as many leavers at once as it has spots (offline
seed 5: the last guest left 6.6 s after closing, was 42.8 s; stuck time 27.1 s → 6.1 s). The code now
lives in packages (`backend/tavern/hall`, `body`, `social`, `mind`, `evening`, `adapters`,
`server`); the task texts below name modules by their old flat file names, so find one with
`git ls-files | grep <name>.py`.

## Working on a task

The steps every task follows. [AGENTS.md](../../AGENTS.md) has the rules behind them.

1. **Read first.** Read the task below, the test file of every module you will touch
   (the tests are the spec), and the modules the task names. Grep for the concept before
   adding a helper.
2. **Freeze the shape.** Write the exact new fields (save, snapshot, model view, model
   answer) into the task text in this file before writing code. The shapes below are
   proposals; adjust them here first if the code disagrees.
3. **Branch.** Work on `claude/stage1-<task>` (for example `claude/stage1-e19`), off
   `main`.
4. **Red, green, refactor.** Write one behavior at a time. Show the failing run before
   the fix. Refactors and behavior changes go in separate commits.
5. **Saves.** A new field that must survive a reload bumps `schema_version` in
   `world.create_world` and `persistence.parse_world`, and needs a check function in the
   concept module, like `thoughts.check_mind`. Bumps that reject old saves are approved
   for all of Stage 1. `test_database.py` pins the version, so name it in the commit as
   an approved behavior change.
6. **Snapshot.** If the snapshot or `minds` changes, change `frontend/src/types.ts` in
   the same commit and run `make build`.
7. **Model prompts.** The shared prefix (`turn_prompt.shared_prefix`,
   `data/minds/intention_prefix.md`) must stay byte-identical across calls and above 4,096
   tokens. Per-guest text goes in the second cached block (the card); per-moment text goes
   in `content`. The answer schema stays fixed: say what may vary in words and enforce it
   in the `check_*` or `parse_*` function at the boundary, as `offered_acts` does.
   Changing the prefix invalidates the cache once, which is fine.
8. **Check.** Run `make check` (and `make build` if `frontend/` changed), then an offline
   evening:
   `.venv/bin/python scripts/evening.py --seed 5 --mode local --writer scripted --out runs/<task>-offline`.
   Pass `--writer scripted` explicitly, because `MODE=local` still calls Haiku (D10).
   Then run a live evening (`make evening SEED=5 OUT=runs/<task>-live`, Jev + Haiku from
   `.env`) and replay it (`MODE=replay CALLS=runs/<task>-live/calls.jsonl`). `cmp` the two
   `events.jsonl` files: they must be byte-identical.
9. **Record.** Append a results paragraph to the task, in the style of E14–E18: what was
   built (modules, fields, rules), the offline and live numbers (scenes, turns, stuck
   seconds, cost per evening and per call, cache hits), and one moment from the log that
   shows the feature. Tick the box. Add any problem you leave behind to the tech-debt
   table in [PLAN.md](../PLAN.md#tech-debt).
10. **Done** means `make check` passes and its output is pasted, plus `make build` if the
    frontend changed.

## Tasks

Write tests first for all business logic, as in [AGENTS.md](../../AGENTS.md).

### M1 — Foundations

- [x] **E01 — Activity table.** `world.py` is split by concept (`room`, `routes`, `sight`,
  `memory`, `conversation`, `arrival`, `validation`), and `activities.py` describes every
  verb once: targets, timing, preconditions, need changes, effects, briefing phrases, Jev
  wording, label, status, and pose. The world, briefing, Jev, saves, and the client (through
  the snapshot) read it. A new verb also needs its candidate rule and local utility in
  `agents.py` and its option sentence in `briefing.py`: those depend on the situation.
  Interruptibility and stimuli join the table with E06–E07.
- [x] **E02 — Model gateway.** `choose_action` receives evaluators as a port; `recording.py`
  records, replays, and prices calls as JSON lines keyed by request; metered Jev calls
  report token usage. A recorded evening replays to a byte-identical event log. The
  `agents.py` → `jev.py` import remains as the default for the Stage 0 tests that
  monkeypatch it; removing it means changing those tests.
- [x] **E03 — Headless evening runner.** `make evening` plays the first-evening scenario
  in lockstep (`decisions.py`, `lockstep.py`, `metrics.py`) with Jev when `.env` has a key,
  otherwise the labeled local policy; `MODE=replay CALLS=…` replays a recording. It writes
  the complete event log, recorded calls, and metrics with stuck time and cost. The
  chronicle comes with E27. A live six-guest evening (seed 5, 455 game s) took 110 wall s
  and cost $0.055 for 288 Jev decisions; most wall time is `observe_actor` copying state.
- [x] **E04 — Scenario.** `data/scenarios/first_evening.json`: six guests arriving at
  0–190 s, closing at 420 s, after which the only option is going home; saves are
  `schema_version` 2 and older saves open a fresh evening. Starting relationships, news,
  and timed events move to E12 and E19, where they are first used.

### M2 — Body and choice

- [x] **E05 — Queues.** Tap, WC, and darts get capacity and queue spots; guests join,
  advance, give up after patience, and leave the line on interrupt; `cut_in_line`
  gives thoughts to those behind. Done: five guests at one tap form a line without
  overlaps or stuck reservations; an impatient guest gives up. Also fixes a deadlock seen
  in a live evening: one guest on the WC spot and another in the WC doorway waiting for it
  block each other for minutes, since only idle guests step aside. `queues.py` keeps each
  place's line (`queue_spots` in `data/tavern.json`, `queue` in the world; capacity stays
  one per place, its single reservation); the front goes in only once nobody stands on the
  way in, so the WC deadlock is gone. Saves are `schema_version` 3; grievances stand in
  for thoughts until E12.
- [x] **E06 — Stimuli and hearing.** `hearing.py`: activities and events make sounds
  (quarrel 1.0, closing call 1.0, door and darts 0.25, chat 0.25, refusal 0.2, each with a
  reach). Heard loudness is `loudness × (1 − distance / reach) × 0.5^walls`; salience adds
  relevance (about me, my name; friends once E12 exists) and curiosity. Quiet sounds can
  never interrupt.
- [x] **E07 — Attention and interrupts.** `attention.py`: each tick a guest reacts to the
  most salient new sound: a glance from 0.15, an interrupt from 0.5. Interruptible
  activities (sit, rest, drink, watch, darts, wait, inspect) end and the guest turns to the
  source; the WC, pouring, talking, and leaving carry on. Pending decisions asked before the
  interrupt are dropped in both runners, and the briefing leads with what happened.
- [x] **E08 — Gaze and emotes.** `expression.py`: facing follows a gaze, then the
  conversation partner; emotes for alert, confusion, anger, and long waits (affection and
  sleep wait for E12 and E13). The scene turns sprites and draws a glyph above the head.
- [x] **E09 — Bounded choices.** `families.py`, `selection.py`: Jev first chooses among
  activity families, then among the actions within the chosen one; every request holds at
  most 8 options (11 before). Over 7 live seeds tokens per decision fell 6% (4,592 → 4,312)
  and cost per evening $0.043 → $0.040, but conversations fell 67 → 48 and darts 74 → 35.
  Two stages pay off clearly once a guest has more than about 11–15 options.

M2 result: a live six-guest evening (seed 5) had 12 s of stuck time in total (297 s before
the queues), no blocked routes, 7 interrupts, 34 glances, and cost $0.033. Open: the door
is still reserved by one leaver at a time, so guests wait a turn at closing; sharing it
changes the behavior `test_closing.py` specifies, so it needs a decision.

### M3 — Characters and conversation

- [x] **E10 — Character cards.** Schema, validation, and eight presets with distinct
  temperaments and goals, plus two starting relationships. Done: invalid cards fail
  loudly; the briefing includes the goal and temperament. `cards.py` validates a card
  (`id`, `name`, `sprite`, eight text fields, nine params in `params`); presets are in
  `data/characters/`. A scenario guest names its card (`"card": "edda"`), keeps its
  name, sprite and color, and takes the card's params as `traits`, so the trait names
  the local policy reads still work. Starting `relationships` (`old friends`, `rivals`,
  with a note) live in the scenario (`ties.py`, `Scenario.ties` for E12) and each guest
  holds its side; the briefing adds occupation, temperament, goal and ties
  (`portrait.py`). Saves are `schema_version` 4. Without the card library,
  `parse_scenario` reads only the schedule, because `test_first_evening.py` parses the
  repository scenario on its own.
- [x] **E11 — Card compiler.** Haiku extracts params from a free-text card through
  structured output; values are range-checked and shown for confirmation. Done:
  malformed or out-of-range answers are rejected; the offline mode is labeled.
  `claude.py` is the Claude adapter later tasks reuse: a `Question` (one to four cached
  system blocks, per-call content, schema) goes in through the `Ask` port
  (`questions.py`), and a JSON object comes out, with usage including cache reads and
  writes; failures raise `ClaudeError`. `recording.py` records, replays and prices
  Claude kinds with a `Tariff`. `POST /api/cards/compile` returns the proposed params
  (`compiled: false` and a note offline) using the server's key. Live: three cards
  compiled in 1.8–2.8 s for $0.0015 each; a 4,306-token prefix was written once and
  read from the cache on the next call.
- [x] **E12 — Thoughts, mood, opinions.** Events create timed thoughts with mood and
  opinion effects; opinions and familiarity are kept per pair. Replaces grievances.
  Done: stacking, expiry, and opinion changes are tested; the inspector lists thoughts.
  `thoughts.py`: a taken seat, a cut in line, a quarrel and a chat each leave a thought;
  repeats of one kind about one person stack up to three, and a fourth replaces the oldest.
  Mood (thoughts plus needs above 50) and opinion (base plus thoughts, −100…100) are
  derived; talking makes strangers acquaintances. `visit.grievances` stays as a derived
  view (latest five bad thoughts), so older readers and tests keep working. The briefing
  says "They are in a sour mood. They dislike Bea, who took their seat."; the local leave
  utility weighs the thoughts' mood; friends make sounds more salient; `seed_relations`
  turns `{a, b, kind}` starting relationships into base opinions, not yet wired to data.
- [x] **E13 — Drunkenness.** Beers raise drunkenness by tolerance; it decays slowly;
  stages change inhibitions, speech instructions, gait, and fight accuracy. A wasted
  guest may doze at the table. Done: parametrized stage and decay tests.
  `drunkenness.py`: 0.2 × (1.5 − tolerance) per beer (tolerance 0.5 until cards add it),
  −0.0005 per second; sober, tipsy (0.2), drunk (0.45), wasted (0.75). The briefing gets a
  speech sentence, the scene sways sprites, and `inhibition_modifier` and `fight_accuracy`
  wait for E20–E21. `dozing.py`: a wasted guest in their seat may nod off into an
  interruptible 30 s `doze` with the sleep emote. Quarrels still roll on beer counts,
  which the existing quarrel tests set. In a live evening (seed 5) guests drink two beers
  at most, so they get tipsy but nobody dozes.
- [x] **E14 — Intentions.** Haiku writes a one-sentence intention on arrival, after
  salient events, and every few minutes; the briefing shows it to Jev. Done: in a
  recorded evening an insult changes the target's intention and later choices.
  `intentions.py`: a guest's `intention` is `{thought, intention, written_at, trigger}`
  (`trigger` is `{kind, text, time}`). A guest takes stock on arrival, after an interrupt
  or alert, a `quarrel`, `seat_taken` or (once E17 adds it) `insult` thought, a scene
  ending or leaving one, closing time, and every 180 s (`INTENTION_RULES`; at least 3 s
  between asks, 180 s after a failure). Both runners ask asynchronously like decisions
  (lockstep: one virtual latency) and drop an answer a salient event overtook or whose
  guest left; a recorded evening replays byte-identically. The question is a ~5,100-token
  shared prefix (`data/minds/intention_prefix.md`), the guest's card as a second cached
  block, then the moment (trigger, previous intention, briefing paragraph, thoughts,
  drink). The briefing adds "Their intention: … (decided 40 s ago, after: …)" and Jev's
  guidance says to weigh options against it without ignoring urgent needs; the inspector
  shows thought and intention. Offline (no `ANTHROPIC_API_KEY`) nobody has one, and the
  snapshot (`ai.intentions`) and metrics say so. Saves are `schema_version` 5. The done
  test uses a quarrel (insults wait for E17), a fake writer and a fake Jev. Live: seeds 5
  and 1 wrote 63 and 45 intentions for $0.111 and $0.071 (about $0.0016 each, 0 failures;
  Jev $0.050 each); the prefix was written to the cache once and read on every later call.
  Seed 0 had one quarrel: Toren went from "sit back down with Edda" to "move to the Garden
  table away from her". A 900 s evening (seed 7, 110 intentions, $0.18) had four: Edda,
  after quarrelling with Calder, meant to make peace with Brida and go home, talked to
  Brida, then left at 659 s; Calder meant to settle it at darts and played darts.
- [x] **E15 — Conversation scenes.** `talk` starts a scene for seated tablemates or
  guests standing side by side (queue, fire); others join or leave; it ends by act,
  satisfied need, or interrupt. Done: a three-way conversation survives one member
  leaving for the WC. `scenes.py` keeps `world.conversations` (saves are `schema_version`
  4); `join_conversation` is a new `company` verb; starting any other action, a loud sound,
  closing time or a goodbye takes a member out, and members get no decisions. `turns.py`
  owns timing (`max(2.5, len/15)` s per line) and the `TurnWriter` port: runners claim the
  next turn when a line is spoken, ask the writer asynchronously (lockstep: one virtual
  latency) and hand the line back; stale lines are dropped, and failures or a claim
  unanswered 10 s past due fall back to `scripted.py`, the seeded offline writer. Acts
  (`conversation.ACTS`) carry relief, place sharing and quarrels (`_quarrels` unchanged).
  A partner pressed by a need declines, and is seen as in a hurry. Seed 5 offline: 14
  scenes, 32 turns, 6 s stuck (M2 code: 9 s). Live seeds 5 and 1: 9 and 8 scenes, 24 and
  20 turns, no joins, 6 departures each; 46 s and 33 s stuck, all of it guests refused the
  busy door after closing (every guest was still in; an M2 rerun of seed 5 also kept
  everyone and had 24 s), so the open door issue of M2 now dominates stuck time.
- [x] **E16 — Turns through Haiku.** The next speaker gets a turn after the previous
  line's reading time; the result is validated and shown as a bubble; failures fall
  back to scripted lines by act. Done: invalid schema and unknown facts are rejected;
  cache reads appear in usage; cost per turn is measured.
  `haiku_turns.py` asks one `Question` per turn: the shared prefix of `turn_prompt.py`
  (world notes, one rule per `conversation.ACTS` entry, answer fields, style, 19 good/bad
  examples; 4,857 tokens), then the speaker's card and portrait as a second cached block,
  then the scene, company (opinion, familiarity, thoughts), feelings, drink, needs, known
  places, goal and nudges (a pressing need, enough company, untold places, by the scripted
  thresholds; without them Haiku never left or shared places). The schema's `act` enum
  comes from the table; `parse_turn` rejects bad shape, unknown acts, absent addressees,
  lines over 160 characters or with stage directions, and `share_place` without known
  places (facts wait for E19). Runners use Haiku when `ANTHROPIC_API_KEY` is set
  (`--writer` overrides headless); turns are recorded as kind `turn` and a replay is
  byte-identical (seed 5); the snapshot's `ai.writer` shows as a badge, and `metrics.json`
  has `run.writer` and `writer` (calls, latency, cache hit rate, cost per turn). Live seeds
  5 and 1 (Jev + Haiku): 52 and 46 turns, 78 and 66 calls (a third are claims dropped when
  the scene ends first), no fallbacks, ~5,490 cached + ~355 fresh input and ~54 output
  tokens per call, 94% cache hits, latency p50 1.4 s / p95 2.0 s, $0.0017 per turn, $0.09
  and $0.08 per evening (Jev $0.04), so no pacing was needed.
- [x] **E17 — Speech-act effects.** One table maps acts to thoughts, opinions,
  familiarity, names, knowledge, and invitations (join the table, darts together, buy a
  drink, leave together). Done: the same line with no act changes nothing.
  `conversation.ACTS` adds `remark` (no effect), `introduce`, `compliment`, `boast`
  (admired by the patient or fond, tiresome to the impatient), `insult` (mood −6, opinion
  −20, offence to the target's friends in the scene, the existing quarrel dice; no hostile
  machinery yet), `apologize` (halves the latest unsoftened grudge), `agree`/`disagree`
  (±3), `invite`, `accept`, `decline`; effects live in `social_acts.py` and
  `invitations.py`. `offered_acts` gives the writer only the acts the situation allows:
  `insult` toward someone at −10 or less, `apologize` to someone holding a grudge,
  `introduce` while someone knows the speaker only by looks, `invite` while a kind is
  possible and none is pending, `accept`/`decline` to the invitee; `check_turn` rejects
  others. A turn result may carry `invitation` (only on an `invite` to someone, of an
  offered kind). The pending invitation lives in the scene (`invitation`, lapses when
  either leaves); an accepted one becomes an errand in `world.invitations` that
  `honor_invitations` starts through `start_action` each tick: the invitee sits at a
  free chair of the inviter's table, both go to the darts (one queues), the inviter
  pours an ale that goes to the invitee once poured (free, no hand-over walk yet), or
  the inviter leaves and the invitee follows once the door is free. The scripted writer
  answers invitations by need, introduces itself, invites once in a while, and spreads
  friendly lines over joke, compliment, agree and boast; the briefing and the local leave
  utility read invitations. Saves are `schema_version` 5. Seed 5 offline: 14 scenes, 40
  turns (6 introductions, 1 ale bought), 9 s stuck (E15: 32 turns, 6 s). Live seed 5
  (Jev, scripted lines): 24 scenes, 56 turns, 6 introductions, 2 quarrels, no
  invitations (scenes ended after two or three lines), 31 s stuck, $0.044.
- [x] **E18 — Overhearing and names.** Nearby guests receive the act and gist by
  distance; strangers are described by appearance until introduced. Done: an insult
  to a friend overheard at the next table creates a thought for the listener.
  `overhearing.py`: every spoken line is a sound from the whole company (talk 0.25 over
  10 cells, laughter 0.25 over 14, insult 0.4 over 14); a guest outside the scene with
  salience 0.08 notices the act, 0.15 makes out the words. An overheard introduction
  teaches the name; an overheard insult is remembered, and resented (`friend_insulted`,
  −12 toward the insulter) by anyone who counts the target a friend or thinks 20 or more
  of them. Cards get an optional short `looks` (all eight presets have one); a relation
  keeps `knows_name`, set by an introduction, by starting ties, by an overheard
  introduction, or passed on by an old friend present. Until then the briefing, Jev's
  view, the writer's participants (`known: false`) and new thought texts use the looks;
  a guest without looks is always named. The event log and personal memories still name
  everyone.

M3 result: a live evening (seed 5, 488 game s) with Jev choices, Haiku lines, and Haiku
intentions: six guests, 13 scenes, 32 lines with no scripted fallbacks, 50 intentions, two
quarrels, all guests home by closing, no errors; $0.205 in total (Jev $0.05, lines $0.06,
intentions $0.09), 92% cache hits, and a byte-identical replay. Seen in the log: old
friends Brida and Edda quarrel over the hearth seat, both resolve to make peace, and argue
it out in the next scene. Open issues and where each went: guests forget earlier
conversations, so they repeat greetings and topics (E18b); Haiku invents news (E19); the
door still serves one leaver at a time (tech debt D02).

### Before M4 — Refactor (done 2026-10-03)

This milestone pays off tech debt D01–D08 before M4 adds facts, fights and bystanders.
Every step preserves behavior, gets its own commit, and passes the same checks:

- `make check` is green.
- The offline golden evening is byte-identical:
  `.venv/bin/python scripts/evening.py --seed 5 --mode local --writer scripted --out runs/golden-now`,
  then `cmp runs/golden-offline/events.jsonl runs/golden-now/events.jsonl`.
- The live golden evening replays byte-identically:
  `make evening SEED=5 MODE=replay CALLS=runs/m3-full/calls.jsonl OUT=runs/replay-now`,
  then `cmp runs/m3-full/events.jsonl runs/replay-now/events.jsonl`. Verified on `main`
  on 2026-10-03.

R0–R5 need no test edits. A test that fails during them is a refactor bug, not a bad
test. R6 and R7 edit tests; the user approved exactly the edits listed there, and no
others. `runs/` is gitignored, so
the baselines exist only on this machine.

- [x] **R0 — Baselines.** On `main`, before any change, record
  `runs/golden-offline` with the offline command above, and confirm that the `runs/m3-full`
  replay is identical. No commit.
- [x] **R1 — Shared helpers (D06).** Replace `app._number`, `app._integer` and
  `observation._number` with `validation.number` and a new `validation.integer`. Where a
  test pins an error message, keep the message. Add `state.py` with `find_actor(world,
  actor_id)` and use it for the four lookups. Add `memory.log_event(world, actor_id,
  kind, message)` (event log only, no personal memory) in place of `turns._log`,
  `intentions._log` and whatever `decisions.log_control` duplicates. Leave the seeded
  roll alone until E21.
- [x] **R2 — Types (D05).** In `state.py`, add `TypedDict`s `World`, `Actor`, `Visit`,
  `Knowledge`, `Rules` (with nested `AttentionRules`, `ConversationRules`, …) and
  `Status = Literal["idle", "walking", "interacting", "waiting", "queued"]`. Annotate the
  core signatures with them in place of `dict[str, Any]`. Nothing changes at runtime, and
  saves stay JSON dicts. Add `mypy` to the `dev` extras and run `mypy backend/tavern` in
  `make check` (approved). Start non-strict and fix what it reports in the same step.
- [x] **R3 — Rules module (D08).** Move `world._rules()` to `rules.py` as
  `default_rules() -> Rules`, with its why-comments verbatim. Saves stay byte-identical.
- [x] **R4 — Split the oversized modules (D01, D07).** Every public name a test imports
  stays in its current module; only private code moves. One commit per file:
  - `world.py` (478 → about 200): the action state machine (`_activate`, `_line_up`,
    `_talk_in_line`, `_part`, `_finish_parts`, `_move`, `_wait_for_route`,
    `_begin_interaction`, `_interact`, `_apply_effect`, `_fail`, `_yield_idle_occupant`,
    `_clear_action`, `_reject`, `_notice_target`) moves to `lifecycle.py`.
    `start_action`, `step_world`, `create_world`, `observe_actor` and `observe_people`
    stay. `_in_sight` moves to `sight.py` as `people_in_sight`.
  - `briefing.py` (450 → about 220): the option sentences (`_option`, `_waiting`, `_cut`
    and the per-verb builders) and `in_use` and `line_place` move to `options.py`. The
    builder table becomes a module-level `_OPTIONS` dict, so it is not rebuilt on every
    call. `brief` stays. Update "Adding a verb" in AGENTS.md: the option sentence now goes
    in `options.py`.
  - `persistence.py` (427 → about 150): each check moves to the module that owns the
    concept, following `thoughts.check_mind`. That is `queues.check_saved_lines`,
    `scenes.check_saved_scenes`, `hearing.check_saved_stimuli`,
    `expression.check_saved_expression`, `arrival.check_saved_visit`,
    `room.check_saved_geometry` and `rules.check_rules`. `parse_world` calls them in the
    current order. Keep error messages verbatim.
  - `agents.py` (386 → about 230): the local policy (`_local_scores`, `_leave_utility`,
    `_wrongs`, `_local_seat_scores`, `_score_lines`, `_score_seats`) moves to
    `local_policy.py`. Update "Adding a verb" in AGENTS.md: the local utility now goes in
    `local_policy.py`.
  - `app.py` (594 → about 350, together with R5): the debug commands (pause, speed,
    refill, block, force action) move to `controls.py` as pure functions over the world.
- [x] **R5 — One request loop for both runners (D04).** Add `mind_loop.py` with a
  `MindLoop` class that owns the three kinds of model request in flight (decisions per
  guest, lines per claimed turn, intentions per guest) and, once per tick, runs: drop
  stale, apply due, ask, deliver lines, claim lines, intentions. Today both runners use
  this order; keep it. When an answer arrives comes from a `Courier` port (`Protocol`:
  `send(awaitable) -> ticket`, `ready(ticket, now) -> bool`,
  `outcome(ticket) -> Callable[[], T]`), which has two implementations:
  `TaskCourier` (asyncio tasks, live) and `LockstepCourier(latency)` (awaits at once and
  is due one virtual latency later). `TavernRuntime` and `run_evening` keep their
  signatures and delegate to `MindLoop`. Lockstep keeps its measurements (choices,
  spells, gazes) outside the loop. Make one of the two current intention-failure policies
  the shared one; the replay must stay identical.
- [x] **R6 — Close the seams (D03). Test edits approved.**
  `agents.choose_action` takes `evaluators` as a required argument and no longer imports
  `jev.py`; the shell wires `Evaluators(evaluate_actions, evaluate_seats)`. Test edits,
  with the reason "pass the port instead of patching the module":
  - `test_agents.py`, 2 tests, and `test_seating.py`, 5 tests: pass fake `Evaluators`.
  - `test_app.py`, 1 test, and `test_evening.py`, 1 test: pass a `decide` port to
    `TavernRuntime` or `create_app` instead of patching `tavern.app.choose_action`.
  - `test_database.py`, 2 tests: `TavernSessions` takes a `Store` port (`initialize`,
    `load`, `save`) with two adapters, files and PostgreSQL, instead of patched module
    functions.
- [x] **R7 — Packages by concept. Approved: it rewrites the import lines in about 60 test
  files and adds subpackages.** Move the modules
  with `git mv` and rewrite the imports with a script, in one mechanical commit. Every
  `__init__.py` stays empty (no re-exports):

  ```
  backend/tavern/
    world/     world lifecycle state rules room routes navigation sight arrival closing validation memory
    body/      activities actions queues hearing attention expression drunkenness dozing
    social/    thoughts ties names scenes conversation social_acts invitations overhearing turns
    mind/      observation briefing options agents local_policy families selection feelings portrait
               intentions cards card_compiler questions scripted haiku_turns turn_prompt
    evening/   scenario decisions mind_loop lockstep metrics recording
    adapters/  jev claude persistence database
    server/    app controls cards_api
  ```

  Add `tests/test_layers.py`, which walks the AST of every module and fails when a
  domain package (`world`, `body`, `social`, `mind`, `evening`) imports `adapters`,
  `server`, `fastapi`, `httpx`, `psycopg`, `anthropic` or `os`. This turns the layer rule
  in AGENTS.md into a check. Update AGENTS.md's Architecture section in the same commit.
- [x] **R8 — Decision: world and actors as objects.** Decided 2026-10-03: not in Stage 1.
  The world dict is also the save format, the snapshot and the spec of 367 test
  accesses. A dataclass world would need a serializer for about 40 fields plus a
  rewrite of the tests, and would gain little over R2's `TypedDict`s. Classes earn their
  keep where something has behavior and lifetime: `MindLoop` and its couriers,
  `TavernRuntime`, `TavernSessions`, `Store`, and the frozen dataclasses for new domain
  data (`Fact`, `Fight`). Revisit in Stage 4, when the save format changes for several
  evenings anyway.

- [x] **U1 — No text labels on furniture.** The hall shows only pixel art: no captions
  on objects. This task is frontend only, with no backend or snapshot change.
  - *Remove from `frontend/src/scene.ts`:* the plate under every table
    (`appealLabel`: "appeal 0.8 · fire · window") and the name plates above the tap, the
    WC and the darts board (`objectLabel`: "Tap · 12", "WC", "Darts"). Then remove
    whatever only those two used: the `labels` group, its `clear` in the redraw, and the
    two methods.
  - *Also remove:* the status tag under every guest ("walking", "interacting":
    `status` in `ActorView`, `createVisitor` and `updateVisitor`). The roster chips in
    the sidebar still show each guest's activity.
  - *Keep:* the hover line at the bottom (`hover`). It still names the object, its
    appeal and comforts, and whether it is reserved. Add the tap's stock to it, since the
    tap's plate was the only place that showed it. Also keep guests' names, speech
    bubbles and emotes.
  - *Check:* run `make check` and `make build`, then `make run`. Confirm in the browser
    that no caption is drawn over the furniture or under the guests, and that hovering a
    table or the tap still shows its details. Attach a screenshot.
  - *Result (2026-10-03):* `scene.ts` loses `appealLabel`, `objectLabel`, the `labels` group and the guests'
    status tag (-34 lines); the hover line gains the tap's stock ("House ale · available · 21 left · cell
    6, 1"). `make check` and `make build` pass; in the browser the furniture and guests carry no captions
    and only names, bubbles and emotes remain.

Refactor result (2026-10-03, branch `claude/stage1-refactor`, 12 commits): `make check` is green
at 1,500 tests (1,413 before; +87 for the new modules), and mypy reports no issues in 70
modules. After every commit the offline golden evening (seed 5) and the replay of `runs/m3-full`
(Jev + Haiku) were byte-identical, and the replay's metrics matched except for the mode labels.
What changed, step by step:

- R1 `validation.integer`, `state.find_actor` and `memory.log_event` replace the copies. `decisions.log_control`
  stays: it trims to 100 events and rebinds the list, unlike the others.
- R2 mypy joined `make check` and found 93 errors the code already had, in three groups: world
  parameters typed `Mapping` although the functions mutate them (now `World`), `TypedDict.update(**kw)`
  (now a dict literal) and places that indexed a possibly missing target, scene, line, seat or action
  (now a `ValueError`). `state.py` holds `World`, `Actor`, `Visit`, `Knowledge`, `Decision`, `Rules` and
  `HallMap`; `create_actor` and `create_world` build them through the TypedDict constructors, so key
  order and saves are unchanged. 80 `dict[str, Any]` remain, for map objects, events and memories.
- R3 `rules.default_rules()`.
- R4 `world.py` 478 → 199 (`lifecycle.py` 375 holds the action state machine), `briefing.py` 450 → 226
  (`options.py`, `hall_view.py`), `persistence.py` 427 → 171 (each check moved to its concept as
  `check_saved_*`; the geometry check stays, because it builds a world), `agents.py` 386 → 275
  (`local_policy.py`), `app.py` 594 → 73 with R7. Option sentences now go in `options.py` and local
  utilities in `local_policy.py`; AGENTS.md says so.
- R5 `mind_loop.MindLoop` plays the tick both runners shared; `TaskCourier` serves the live server and
  `lockstep.LockstepCourier` the headless run. The runners disagreed on replay misses (a missing line
  became a scripted fallback, a missing intention stopped the run); now a replay miss stops the evening
  everywhere.
- R6 `agents.py` no longer imports `jev.py`: its error is `agents.EvaluatorError` (`JevError` extends it),
  and a model key without evaluators fails loudly. Sessions keep worlds in a `Store` (`FileStore`,
  `DatabaseStore`). The tests edited, as approved: `test_agents.py` ×2, `test_seating.py` ×5,
  `test_app.py` ×1, `test_evening.py` ×1, `test_database.py` ×2 (two renamed). No test patches a
  module any more.
- R7 packages by concept, with `tests/test_layers.py` checking that no domain package imports an
  adapter, the server, `fastapi`, `httpx`, `psycopg`, `anthropic` or `os`. Differences from the proposal:
  the package of the world is `hall/` (not `world/`, which would read `tavern.world.world`); the shared
  helpers of the briefing are `hall_view.py`; `app.py` stays at the top as the launch wiring, so
  `.do/app.prod.yaml` needed no change; `controls.py` and `cards_api.py` sit in `server/`.

D13 result (2026-10-03): `mind/model_health.py` (pure) classifies a failed call by its HTTP status or words
(`auth` 401/403, `no_credit` 402, `unreachable` for a timeout, a lost connection or a 5xx, otherwise `degraded`)
and keeps a window of the latest 10 calls per service in a `HealthBoard`; a service without a key is `no_key`.
Adapter errors now carry `status`, and Claude's "credit balance is too low" (a 400) reads as 402. The shell
notes every Jev and Claude call on the board (`app.py`) and probes each service once at startup, in the
background (`adapters/probes.py`: Jev scores one action, Claude answers a one-field object, a real request
costing a fraction of a cent, because only one proves the account has credit). `/health` stays 200 and adds
`models`; the snapshot carries `ai.health`; the client header shows a coloured badge per service (green ok,
amber checking or degraded, red auth, no credit or unreachable, grey no key; the reason is the tooltip);
`make evening` probes, prints `JEV: OK  CLAUDE: OK` (OFF for a service the run does not ask) and stops a
live run whose service has no key, a refused key or no credit. Tried against the real services: both `ok`,
and with bogus keys both `auth`. Not done: a later top-up is noticed only by the next successful call,
there is no periodic re-probe.

- [x] **E18b — Conversation memory.** Guests remember the lines they spoke and heard
  tonight, and the turn writer and the intention writer see them. In-evening only; memory
  between evenings stays in Stage 4.
  - *Shape (freeze before coding):* `actor["heard"]` is a list of
    `{time, scene_id, speaker_id, speaker, line, act}`, where `speaker` is what the
    listener called the speaker at that moment (`names.called`). The newest 40 lines are
    kept (`rules.conversation.recall_lines`). Saves become `schema_version` 6, with
    `memory.check_heard`.
  - *Rule:* `turns._speak` appends each line to every member of the scene at that moment,
    the speaker included. A guest who joins later lacks the earlier lines. Overheard lines
    (E18) are out of scope for this task.
  - *Writer view:* `turn_view` adds `speaker.earlier`: lines from other scenes (the
    current scene is already in `conversation.turns`), newest last, grouped by scene as
    `{scene_id, with: [names], lines: [{speaker, line}]}`. The total is capped at 24
    lines. `haiku_turns.turn_content` renders it under "Earlier tonight". `intention_view`
    adds the latest 8 lines the same way.
  - *Prompt:* one rule in `turn_prompt.py`'s prefix: "Earlier tonight is what you already
    said and heard. Do not greet or introduce yourself again to someone you have talked
    with; pick up the thread or bring something new instead of repeating a subject." Add
    one good and one bad example. The prefix must stay above 4,096 tokens (it is 4,857
    today).
  - *Tests (`tests/test_heard.py`):* a spoken line reaches every member and no outsider;
    a late joiner lacks earlier lines; the cap keeps the newest; the view groups by scene,
    excludes the current scene and respects the cap; the question content holds the lines;
    a save round-trips and a malformed `heard` fails loudly. Use fakes for the writer.
  - *Done:* in a live evening (seed 5), no pair greets each other as strangers in a
    second scene, and the cost per turn grows by at most $0.0005 (it is $0.0017 today).
    Record the before and after numbers here.
  - *Built (2026-10-04):* `social/heard.py` owns the record, `earlier_lines` and `check_heard`
    (not `memory.py`, which holds the room's event log); tests are in `tests/test_heard.py`. The
    intention view's key is also `earlier` and its prompt line reads "What they said and heard
    lately"; it includes the current scene, which that writer sees nowhere else. `turn_content`
    reads `speaker.get("earlier") or []`, so a hand-made view without the field still renders. Saves
    are `schema_version` 6 and `rules.conversation.recall_lines` is 40. Example 20 and style rule 14
    teach the writer not to greet again.
  - *Live check (seed 5, Jev + Haiku, 490 game s, 13 scenes, no fallbacks):* the pairs who met
    again (Toren–Brida, Calder–Edda, Saye–Rurik) took up the thread ("Heard you talking about
    fever south of here…") and none introduced themselves again. Cost per turn on the same seed
    and day: $0.00211 on `main` (32 turns, 90.1% cache hits, ~470 fresh input tokens per call)
    against $0.00241 with E18b (28 turns, 88.6%, ~588 fresh): +$0.00030, under the $0.0005 limit.
    The $0.0017 above came from a longer evening, so it is not the baseline.

### M4 — News and conflict

Shared rules for M4. New concepts get their own pure modules (`facts.py`, `hostility.py`,
`fights.py`, `bystanders.py`), each with its own test file. Each one is wired into
`step_world`, `conversation.ACTS` or `activities.py` with one small edit. The proposed
fields below get frozen in the task text before coding (step 2 of "Working on a task").
Each task bumps `schema_version` once. Seeded chance goes through `chance.roll(world, *keys)`,
which G0 extracts from the `Random(f"{seed}:{tick}:…")` pattern before the dice make its third use.

- [x] **E19 — Facts and retelling.** Guests start with news by occupation; sharing
  stores the speaker's words as the listener's version, and retelling paraphrases it.
  Done: a fact reaches a third guest in a recorded evening, with drifted wording and
  its path visible in the inspector.
  - *Content:* the scenario gets `news`: `[{id, topic, text, known_by: [guest ids]}]`.
    Write four to six items about tolls, robberies, the margrave and the border, each
    held by the guests whose occupation would know it: Rurik (gate guard), Calder (post
    rider), Toren (cloth trader), Brida (manor cook), Edda (healer), Saye (storyteller).
    `parse_scenario` checks for unique IDs, `known_by` within the guest list, and text of
    200 characters or fewer. `world["news"]` keeps the originals for the inspector and
    the chronicle. Only the first holders' copies are ever built from the original text.
  - *A guest's copy:* `actor["knowledge"]["facts"][fact_id] =
    {topic, told_as, heard_from, heard_at, confidence, hops, overheard}`. For the first
    holders, `told_as` is the original text, `heard_from` is null, `confidence` is 1 and
    `hops` is 0. `facts.check_facts` validates saved copies.
  - *The act:* add `share_news` to `conversation.ACTS`. It is offered while the speaker
    holds at least one fact. The turn schema gets an always-present `fact_id`
    (string or null), so the schema stays fixed. `check_turn` rejects `share_news`
    without a `fact_id` the speaker holds, and a `fact_id` on any other act.
  - *The effect (`facts.tell`):* every other member who lacks the fact gets a copy:
    `told_as` is the spoken line, `heard_from` is the speaker, `hops` is the speaker's
    hops + 1, and `confidence` is the speaker's confidence × trust by familiarity
    (`rules.news.trust`, for example friend 0.9, acquaintance 0.75, stranger 0.6). A guest
    who already knows the fact keeps their first version. The event log records
    `news_told` with the fact, the teller and the listeners. Overhearing at word salience
    (≥ 0.15, E18) gives a copy with half the confidence and `overheard: true`.
  - *Drift:* the writer only ever sees the speaker's own `told_as`, never the original.
    The view's `speaker.news` is `[{id, topic, told_as, heard_from (as called),
    confidence in words}]`. Prefix rules: retell your version in your own words, shorter
    or coloured but with no new facts; share only news from your list; with no news, talk
    about yourself, the road or the room (this replaces today's invented news). Add two
    good and two bad examples. Offline, the scripted writer says
    "Heard from {source}: {told_as}", trimmed to 160 characters, so its wording does not
    drift.
  - *Inspector and metrics:* `minds[guest].news` lists each copy with its `heard_from`
    name and `hops`. The dashboard shows a fact's chain (Brida ← Edda ← start), and
    `types.ts` changes in the same commit. `metrics.json` gets `news`: per fact, its
    holders, its maximum hops, and the path of its first two-hop copy (acceptance
    scenario 3).
  - *Frozen shape (2026-10-04, before coding):*
    - *Module:* `social/facts.py` owns `parse_news`, `starting_facts`, `tell`, `overhear`, `chain`,
      `check_facts` and the news metrics; tests are in `tests/test_facts.py`.
    - *Ids:* `known_by` holds scenario guest IDs, not names: Edda `mara`, Rurik `ivo`, Toren `nell`,
      Brida `brannoc`, Calder `wenna`, Saye `osric`.
    - *Where copies start:* `open_evening` stores `world["news"]` (the originals; `[]` for a world
      without a scenario); `arrival.admit_arrivals` fills `knowledge["facts"]` from it by `known_by`
      when a guest comes in, so the scenario's `Guest` and `ExpectedGuest` keep their shape.
      `create_actor` starts with `knowledge["facts"] = {}`. Readers sort copies by ID (`facts.carried`,
      `facts.inspected`), so views and replays do not depend on the order they were heard in.
    - *Turn:* `fact_id` joins `TurnResult` and `scenes.Turn` (`NotRequired[str]`). The answer schema
      always requires `fact_id` (string or null); `parse_turn` drops a null, as it does for
      `invitation`. `facts.tell` reads `scene["turns"][-1]`, like `invitations.invite`, so `ActEffect`
      keeps its signature.
    - *Who gets a copy:* every other member of the scene who lacks the fact, whoever the line
      addresses (as `share_place`). The event is `news_told` through `log_event` (no sound, no emote).
      Overhearing uses `news_overheard`.
    - *Rules:* `rules.news.trust` = `{friend: 0.9, acquaintance: 0.75, stranger: 0.6}` and
      `rules.news.overheard` = 0.5 (the confidence factor), checked in `check_rules`.
    - *Writer view:* `speaker.news` is `[{id, topic, told_as, heard_from, confidence}]`, with
      `heard_from` as the speaker calls the source (`names.called`, looked up among `actors` and
      `departed`) and null at hops 0. `haiku_turns` turns the number into words (0.85 or more "you
      are sure of it", 0.55 "you believe it", below "a rumour you half believe"; the cut sits under 0.6
      so float products never tip a stranger's word over) and adds a nudge when
      the speaker holds news this company has not heard from them.
    - *Scripted writer:* `share_news` once per scene, the fact drawn by the seeded rule from those not yet told in the scene
      (sorted by ID); the line is
      "Heard from {source}: {told_as}" cut to 160 characters, a leading "Heard from …: " removed
      first so prefixes never nest; at hops 0 the line is `told_as` itself.
    - *Inspector:* `minds[guest].news` is `[{id, topic, told_as, heard_from, hops, confidence,
      overheard, chain}]`, where `chain` is the names from the guest back to the start ("Brida",
      "Edda", "start"), computed by `facts.inspected` over `actors + departed`; `types.ts` and the
      dashboard follow.
    - *Metrics:* `metrics.json` `news` is computed from the final world (not from event messages):
      per fact `{holders, max_hops, first_two_hop_path}`.
    - *Saves:* `schema_version` 7; `parse_world` checks `world["news"]` and every `knowledge.facts`
      (present and departed guests) with `facts.check_saved_news`, which also requires every teller to
      hold the news one hop nearer the start, so a path always leads back and never loops.
  - *Tests (`tests/test_facts.py`):* starting copies follow `known_by`; a share gives
    the listener the line as `told_as` with hops + 1; a second share keeps the first
    version; an unknown `fact_id` and a `fact_id` on `joke` are rejected; overhearing
    halves confidence; saves round-trip, and a malformed copy fails loudly. The done test
    is a lockstep evening with a fake writer that paraphrases: a fact reaches a third
    guest at hops 2 with words different from the original.
  - *Built (2026-10-04):* `social/facts.py` owns the news (`parse_news`, `starting_facts`, `tell`,
    `overhear`, `carried` for the writer, `inspected` for the inspector, `check_saved_news`);
    `share_news` joins `conversation.ACTS` (its effect tells, then eases the wish for company like
    `share_place`) and a turn carries `fact_id`. The scenario gets five items (`data/scenarios/first_evening.json`:
    salt toll, the Wolf's Bend robbery, the margrave's fever, closing the pass, deserters; `known_by` holds
    guest IDs), `world["news"]` the originals, `knowledge.facts` each guest's copies. Rules are
    `rules.news.trust` (friend 0.9, acquaintance 0.75, stranger 0.6) and `rules.news.overheard` (0.5).
    Saves are `schema_version` 7, with the approved bump named in the commit: `test_database.py` and
    `test_intention_saves.py` pin 7, and `test_haiku_turns.py`'s schema test (renamed) expects `fact_id`
    among the required fields. Hand-made views without `speaker.news` still render (`.get`), as with
    `earlier`. Prefix rule 15 and examples 21–22 teach retelling; style rule 10 no longer allows
    invented news, and the scripted line "Heard the pass is snowed in." (an invented news item) is gone.
    The prefix is 22,633 characters. `metrics.json` has `news` per item (holders, furthest hops, first
    two-hop path), read from the final world by `metrics.news_metrics`; `Mind.news`, `Actor.knowledge.facts`,
    `World.news` and `Turn.fact_id` are in `types.ts`, and the dashboard's mind panel lists each copy as
    "topic · Brida ← Edda ← start" with its words and belief.
  - *Results:* tests prove the done check: an offline lockstep evening with a paraphrasing writer carries
    news to a third guest on seeds 1 and 2 (`test_a_news_item_reaches_a_third_guest_in_other_words`).
    Offline scripted, seed 5: 28 scenes and 69 turns (main: 14 and 40), six guests home, five items
    reached 5/5/5/1/2 holders, and "salt toll" went two hops (Saye ← Brida ← Rurik); stuck time 27.1 s as
    about nine 3-s stalls, longest 3.1 s (main: 9.1 s), because there is more talking and sitting. Live (Jev +
    Haiku, 30 calls, 0 failed, a replay of seed 5 byte-identical): seed 5, 494 game s, 9 scenes, 23 turns,
    4 news tellings (one a Haiku misuse, below), 2 overheard, one fallback (an invitation attached to an
    `accept`), $0.00272 per turn against $0.00241 on `main` the same day (+$0.00031, under the $0.0005 limit),
    87.2% cache hits, p50 1.7 s, $0.19 per evening; seed 1: 477 s, 9 scenes, 22 turns, one fallback (a line
    over 160 characters), $0.00238 per turn, 91.0% cache hits, $0.17. **Neither live evening carried news
    two hops:** evenings were short (9 scenes) and each news item was told once, so the live check of this
    task's "done" is not met; acceptance scenario 3 (one item two hops over five live evenings) stays open
    for E28. Moments from the log: seed 5, 160 s, Edda to Rurik: "A fever's no tale—the margrave's been abed with
    one a week now, broth only." (the original: "...abed with a fever for a week, and the manor kitchen is
    told to send up nothing but broth"); at 222 s Toren's account of the robbery reached Calder (hop 1) and, from
    the next table, Rurik (overheard).
- [ ] **E20 — Hostile options.** Insults are speech acts; `shove` and `start_fight`
  appear only toward someone with low opinion, given temper, drunkenness, and a recent
  cause. Done: sober guests on good terms never receive hostile candidates.
  - *Gate (`hostility.py`, pure, from the observation only):*
    `hostile_targets(observation) -> list[actor_id]`. A target qualifies when they are in
    sight, the guest's opinion of them is −30 or lower, there is a recent cause (a
    thought about them of kind `insult`, `quarrel`, `seat_taken`, `friend_insulted` or
    `cut_in_line` within 120 s), and `temper × (1 + drunkenness.inhibition_modifier)`
    reaches the threshold. `start_fight` needs a higher threshold than `shove`. All
    thresholds go in `rules.hostility`.
  - *Verbs:* add `shove` and `start_fight` as `Activity` entries in a new `confront`
    family. A family appears only when it has candidates (check `families.py` and
    pin that with a test), so peaceful requests do not grow. Each verb also needs a
    candidate rule, a low local utility weighted by the urge, an option sentence, and Jev
    guidance that hostile acts are rare and have consequences. Until E21 lands, a
    `shove` is a loud sound (1.0) plus thoughts, and `start_fight` logs and makes a sound.
  - *Stage 0 leftovers (D11):* quarrels then come from insults, not beer dice, and
    `visit.grievances` goes away. Both change behavior that existing tests specify
    (the quarrel dice tests, and the grievances readers in `agents.py`, `feelings.py` and
    `observation.py`). List those tests and ask the user before replacing them.
  - *Tests:* a parametrized block in which sober guests with opinion ≥ 0 never get
    hostile candidates (cases: no cause, old cause, low temper, friend), and a block of
    positive cases.
- [ ] **E21 — Fight resolution.** Seeded exchanges with hit chance, damage,
  consciousness, yielding, and knockouts; a shove can stagger or knock down; a knocked
  out guest lies down, gets up groggy, and keeps thoughts. Done: parametrized outcome
  rates (a strong sober guest usually beats a weak drunk one) and seeded replays.
  - *Shape:* `world["fights"]` holds `{id, a, b, started_at, next_exchange_at,
    exchanges: [{time, attacker, hit, damage}], outcome}`. An actor gets `health`
    (0–100) and `condition` (`ok`, `staggered`, `down`, `out`, `groggy`) with `until`.
  - *Exchange (`fights.py`), every `rules.fight.exchange_seconds`:* the hit chance comes
    from the attacker's `brawling` against the defender's, times
    `drunkenness.fight_accuracy`. Damage comes from `strength` × a roll. At 15 health or
    less, the guest is knocked out: they lie 20–40 s, then are groggy for 60 s, and keep
    their thoughts. A guest yields below `50 × (1 − courage)` health. Bystanders can
    separate the fighters (E22). A shove rolls strength against strength: nothing, a
    stagger for 2 s, or knocked down for 6 s.
  - *Lifecycle:* fighters' actions are locked while the fight lasts (as scene members
    get no decisions). Every exchange is a loud stimulus, so E07 attention brings the
    room's heads round.
  - *Tests:* rates over 200 seeds as parametrized cases. A strong sober guest beats a
    weak drunk one at least 80% of the time; equal guests win 50 ± 15%; at least 20% of
    fights end without a knockout. A seeded fight replays identically.
- [ ] **E22 — Bystanders and aftermath.** Witnesses watch from a ring, cheer, intervene
  with a chance to separate, back away, leave, or help the fallen up; everyone involved
  gets thoughts; spilled drinks are lost. Done: a forced fight draws at least two kinds
  of reaction that follow the witnesses' traits.
  - *Reactions (`bystanders.py`):* a `react` family offered only while a fight or a
    fallen guest is in sight: `watch_fight` (a ring spot 2–3 cells from the fight's
    center, computed by the body), `cheer`, `intervene` (separation chance from strength
    and courage against the fighters'), `back_away`, `leave`, and `help_up` (after a
    knockdown or knockout).
  - *Aftermath:* thoughts `fought`, `was_attacked`, `saw_fight`, `was_helped` and
    `separated_us`, with opinion effects. A fighter's or shoved guest's beer is spilled
    (inventory to 0, with an event).
  - *Debug:* add a "force fight" command in the debug panel for the done check.
  - *Tests:* parametrized by traits. Witnesses with high courage and strength
    intervene more; those with low courage back away or leave. A forced fight in a
    seeded evening draws at least two kinds of reaction.
  - *Reuse:* `watch_fight` can stand on G4's `Activity.shared` and `Activity.game`, with the
    fight in place of the game.

### Dice — a game at the table (G0–G5)

Added 2026-10-04 at the user's request; it comes before E20 (see Order). Two guests agree in a
conversation to play dice, walk to the dice table together and play there seated, in the
talking pose, while others gather round to watch. A seeded roll picks the winner, with odds from
the players' traits and drunkenness. For the central test, a game is a small story with a cause
(the invitation), witnesses (the onlookers) and an outcome everyone remembers (a winner and a
loser).

Decisions for every G task (frozen 2026-10-04; change them here first if the code disagrees):

- **The place.** Two new object kinds. `dice_table` is a table with dice on it; its
  `interaction_spots` are where onlookers stand. `dice_chair` is walkable like a chair, with a
  `facing` and a `table_id` that must name a `dice_table`. A dice chair is not a `chair`: nobody
  owns it, it is never offered for `seating`, `sit` or `rest`, and playing never sets `seat_id`,
  so the seating, table-talk and dozing rules leave players alone. One dice table stands in the
  open middle of the hall (`data/tavern.json`, after the regular tables):

  ```json
  {"id": "dice-table", "kind": "dice_table", "name": "Dice table", "x": 10, "y": 8,
   "interaction_spots": [[10, 7], [10, 9], [8, 8], [12, 8]]},
  {"id": "dice-chair-1", "kind": "dice_chair", "name": "Dice table · west", "x": 9, "y": 8,
   "walkable": true, "table_id": "dice-table", "facing": "east", "interaction_spots": [[9, 8]]},
  {"id": "dice-chair-2", "kind": "dice_chair", "name": "Dice table · east", "x": 11, "y": 8,
   "walkable": true, "table_id": "dice-table", "facing": "west", "interaction_spots": [[11, 8]]}
  ```

- **Two verbs, both in the `pastime` family,** so no first-stage request grows. `play_dice`
  targets a dice chair. Only an accepted `dice_together` invitation (G3) or the debug panel's
  forced action starts it, so like `doze` it is never a candidate. `watch_dice` targets a dice
  table and is a candidate while a game is under way there (G4).
- **The game, not a timer, ends them.** A new `Activity.game` flag works as `partner` does for
  scenes: `lifecycle` never completes a `game` activity on its timer; `dice.settle_games` does.
- **The game record** lives on its table, as a line lives on its place: `create_map` gives every
  dice table `game: None`, and while guests sit at it `game` is
  `{"players": [IDs in the order they sat down], "since": when the first sat down,
  "ends_at": when the result falls, or None while one player waits}`.
- **Who wins.**

  ```
  form(guest)   = 0.4·patience + 0.3·curiosity + 0.3·courage − 0.6·drunkenness
  P(first wins) = clamp(0.5 + 0.5·(form(first) − form(second)), 0.2, 0.8)
  the first player (players[0]) wins when chance.roll(world, "dice", table_id, first, second) < P
  ```

  Patience keeps a cool head and does not chase a loss, curiosity reads the odds and the
  opponent, and courage bets boldly on the right throw. Drunkenness (0–1) already reflects
  tolerance, so tolerance is not counted again. A trait a guest lacks counts as 0.5, as
  `tolerance` does in `activities._drink`. The clamp keeps dice mostly luck: the sharpest player
  beats the dullest four times in five. Examples: equal guests 0.5; same traits but the opponent
  drunk (0.45) 0.635; all three traits 0.8 against 0.2, both sober, 0.8 (the cap). Every number
  here is a rule in `rules.dice` (G2).
- **The look.** Players use the pose `TalkingSeated` (the seated talking stills every sprite
  ships) and face across the table, along their chair's `facing`. Onlookers stand and face the
  table. The client draws the dice table as the ordinary table top with two dice in place of the
  candle and mugs, on a green rug, and draws its chairs like any chair. No captions (U1).
- **Out of scope:** stakes and money (Stage 3); talk during a game (players are in no scene, and
  nobody can start one with them, because they neither sit at a table nor stand by a view);
  onlookers chatting with each other; grudges or fights over a lost game (E20 may add
  `lost_at_dice` to its causes); new art.
- **Seed-sensitive tests.** G1 changes the hall and G3 the scripted writer, so whole evenings
  play differently (`test_a_news_item_reaches_a_third_guest_in_other_words` uses seeds 1 and 2;
  `test_first_evening.py`). If one fails, stop and report the seed and the failure. Do not
  change a seed or an assertion without the user's approval.

- [ ] **G0 — One roll, one list of kinds (refactor, no behavior change).**
  - *Roll:* `hall/chance.py` gets `roll(world, *keys: str) -> float`, a draw in [0, 1) from
    `Random(":".join([str(world["seed"]), str(world["tick"]), *keys]))`. It replaces the two
    inline rolls with the very same strings, so nothing replays differently:
    `conversation._quarrels` uses `roll(world, left["id"], right["id"])` and
    `dozing.nodding_off` uses `roll(world, actor["id"], "doze")`. `scripted.py` keeps its own
    `Random`, because the view seeds it, not the world. Add `chance` to the `hall/` list in
    AGENTS.md.
  - *Kinds:* `room.OBJECT_KINDS`, one tuple of object kinds, replaces the three copies in
    `room._validate_kind`, `sight.check_saved_knowledge` and `observation.known_objects`.
    Error messages stay as they are.
  - *Tests (`tests/test_chance.py`):* the same world and keys give the same number; another
    tick, seed or key gives another; one case pins the old string form.
  - *Check:* `make check`. Record a fresh offline baseline on `main` first (the hall's behavior
    changed after R0), then show that the offline evening and the replay of `runs/e19-live` are
    byte-identical, with the commands under "Before M4 — Refactor".
- [ ] **G1 — The dice table in the hall.** Furniture only; nobody plays yet.
  - *Data and validation:* add the three objects above. In `room.py`, `SEAT_KINDS = ("chair",
    "dice_chair")` may be walkable, and a seat's `table_id` must name a table of the matching
    kind (`chair` → `table`, `dice_chair` → `dice_table`). A dice table needs interaction spots
    (the existing rule demands them for every kind it does not exempt). Only `table` objects are
    rated for appeal, as now.
  - *Wording:* `hall_view.place_words` says "the dice table". `attention._landmark` and the
    briefing's "standing near" skip `SEAT_KINDS`, as they skip chairs today: a table names its
    place.
  - *Client:* `types.ts` adds both kinds. `furniture.ts` splits `drawTable` into the top and its
    props (a refactor: regular tables look the same) and adds `drawDiceTable`: the top plus two
    ivory dice with pips. `scene.ts` draws a `dice_chair` with `drawChair` and lays a green rug
    under the dice table. If `scene.ts` would pass 400 lines, first move `drawRugs` to
    `furniture.ts` (D01) in its own commit.
  - *Tests (`tests/test_dice_table.py`):* the repository hall has one dice table with a dice
    chair on each side, facing it; dice chairs never appear in `build_seat_candidates`, nor as a
    `sit` or `rest` target; observations and saved knowledge accept both kinds. Error cases: a
    dice chair naming a regular table, a chair naming a dice table, a walkable dice table, a dice
    table without spots.
  - *Check:* `make check` and `make build`; `make run` and a screenshot of the hall; the offline
    evening (seed 5): scenes and stuck time against E19's (28 scenes, 27.1 s), and guests route
    round the table.
- [ ] **G2 — A game at the table.** Two guests seated at the dice table play one game, and the
  formula above picks the winner.
  - *Refactor first (own commit):* take `lifecycle.complete_action(world, actor)` out of
    `_interact`: apply the effect and the needs, log `action_completed`, clear the action, look.
  - *Table:* `Activity.game: bool = False` ("a seat at, or a place round, a game: the game, not
    a timer, ends it"); `_interact` completes on the timer only when the activity is neither
    `partner` nor `game`. `play_dice`: `target_kinds=("dice_chair",)`, `duration=30.0`
    (nominal), `game=True`, `leaves_seat=True`, `interruptible=False`,
    `needs={"boredom": -70, "social": -20}`, `pose="TalkingSeated"`,
    `sound=Sound("dice", 0.25, 8.0, "dice rattling on a table")`, `label="Play dice"`,
    `status="dice"`, `doing="playing dice"`, `done="played dice"`, `family="pastime"`, and a
    `what` and `guidance` that say it is the seat at a game they agreed to.
  - *Module `social/dice.py`* (add it to AGENTS.md): `form`, `win_chance(first, second,
    rules)`, `settle_games(world) -> Settled` (frozen dataclass with `done` and `released`
    lists of actors) and `check_saved_games`. Each tick, per dice table in map order:
    1. A player whose action is no longer `play_dice` on one of its chairs, or who has left,
       drops out; a game broken off that way releases the other player with `dice_abandoned`
       ("Edda's game of dice broke off").
    2. A guest who has reached a chair (status `interacting`) joins `players`. The second sets
       `ends_at = now + game_seconds` and logs `dice_started` for both ("Rurik and Edda sat down
       to a game of dice").
    3. A player left alone for `wait_seconds` is released with `dice_abandoned` ("Edda gave up
       waiting for a game of dice").
    4. At `ends_at` the result falls: `dice_won` for the winner and `dice_lost` for the loser,
       both "Rurik beat Edda at dice", plus their thoughts. Both players are `done`, and `game`
       goes back to None.

    `world.step_world` calls it right after `honor_invitations`, then `complete_action` for
    `done` and `clear_action` for `released`.
  - *Rules:* `rules.dice = {"skill": {"patience": 0.4, "curiosity": 0.3, "courage": 0.3},
    "drink": 0.6, "edge": 0.5, "odds": [0.2, 0.8], "game_seconds": 25.0,
    "wait_seconds": 30.0}`, a `DiceRules` TypedDict in `state.py`, and `check_rules`: skill
    weights are trait names, at least 0 and sum to 1; `drink` is at least 0; the odds are
    symmetric round 0.5; the seconds are positive.
  - *Consequences:* `thoughts.THOUGHTS` gets `won_at_dice` (mood +5, opinion +2, 300 s, stack
    3, "lost to them at dice", acquaints) and `lost_at_dice` (mood −4, opinion −6, 300 s, stack
    3, "beat them at dice", acquaints). `hearing.EVENT_SOUNDS["dice_won"] = Sound("cheer", 0.3,
    12.0, "a whoop at the dice table")`, below the interrupt level, so it turns heads without
    breaking off what people do.
  - *Saves and snapshot:* `schema_version` 8 (approved for Stage 1; name the bump in the commit,
    since `test_database.py` and `test_intention_saves.py` pin it). `parse_world` calls
    `dice.check_saved_games`: `game` is None or has exactly the three keys; one or two distinct
    players who are present and whose action is `play_dice` on that table's chairs; `ends_at`
    is None exactly while one player waits; times lie between 0 and now, `since` ≤ `ends_at`.
    `types.ts` gets `WorldObject.game?: DiceGame | null`.
  - *Client:* a guest interacting with a target that has a `facing` faces that way
    (`updateVisitor`: `target.facing ?? facingTarget(...)`), so players face each other. The
    hover line adds "· Rurik and Edda playing" for a dice table with a game.
  - *Tests (`tests/test_dice.py`, with a small hall helper):* `win_chance` cases (equal guests,
    a drunk opponent, sharp against dull at the cap, missing traits as 0.5, and
    P(a, b) + P(b, a) = 1); error cases (drunkenness or a trait outside 0–1). Rates over 400
    seeded games: the 0.8 case wins 72–88%, equal guests 43–57%. Through `start_action` and
    `step_world`: the game starts only once both sit; neither player is free to decide during
    it; after `game_seconds` there is exactly one `dice_won` and one `dice_lost`, both players
    are idle with boredom relieved and a thought each; a lone player is released after
    `wait_seconds` without a thought; forcing another action on one player releases the other;
    the same seed gives the same winner; a save made mid-game round-trips; a malformed game fails
    loudly (three players, an absent player, `ends_at` before `since`, `ends_at` set while one
    waits).
  - *Check:* `make check` and `make build`. In `make run`, force `play_dice` for two guests from
    the debug panel and attach a screenshot: both seated in the talking pose facing each other,
    dice on the table, the hover showing the game, and the result in the event feed.
- [ ] **G3 — Agreeing to play.** The `dice_together` invitation sends both guests to the table.
  - *Refactor first (own commit, AGENTS.md "O"):* dice would be a third special case in
    `invitations._first_steps`, so first turn it into a table of one function per kind
    (`_FIRST_STEPS`), with no behavior change.
  - *Kind:* `KINDS["dice_together"] = "play a game of dice"`. `offered_kinds` offers it while the
    speaker knows a dice table and `dice.open_chairs(world, table_id)` returns its two chairs (no
    game, neither chair reserved). On `accept` the host starts `play_dice` on the first chair (map
    order) and the guest on the second; the errand ends there, as `darts_together`'s does. If the
    table was taken in between, the errand fails with `invitation_failed`. If only the host could
    start, they wait alone until G2's timeout releases them.
  - *Words:* `conversation.ACTS["invite"]` names `dice_together` (a game of dice at the dice
    table). The turn prefix's description of the hall mentions the dice table and gains one good
    example of a dice invitation; `data/minds/intention_prefix.md` adds "play dice with someone,
    or watch a game" to what guests do. Both prefixes only grow, so they stay above 4,096 tokens.
    `haiku_turns._nudges` adds "You are bored, and the dice table stands free." when boredom is
    50 or more and `dice_together` is on offer. Unnudged, the two E19 live evenings had three
    accepted invitations in all, two of them to darts, so a game would be rare without it.
  - *Scripted writer:* `INVITE_LINES["dice_together"] = "Care for a game of dice, {name}?"`. It
    wishes for dice before darts when boredom is 50 or more and courage 0.5 or more (a game of
    chance wants some nerve), and accepts when boredom is 30 or more, as for darts. `types.ts`
    adds the kind to `InvitationKind`.
  - *Tests:* offered or not (table unknown, a game under way, a chair reserved, open); accepting
    sends the two to different chairs; a table taken before the answer fails the errand;
    `check_invitations` accepts the kind; the scripted writer invites to dice when bored and
    bold and to darts when bored and timid; the nudge shows only when it should; the schema's
    enum holds the kind. Done test: a lockstep evening whose fake writer invites to dice plays a
    game to a result.
  - *Check:* `make check` and `make build`, the offline evening, and a live evening (seed 5)
    with its replay. Record the dice invitations Haiku made; none is a finding, not a failure.
- [ ] **G4 — Onlookers.** Guests who see a game may gather round to watch it.
  - *Table:* `Activity.shared: bool = False` ("many guests use the target at once, each from an
    interaction spot of their own; it is never reserved"): `actions._target_error` and
    `lifecycle.activate` skip the reservation for it, and `routes.plan_route` already keeps the
    spots apart. `watch_dice`: `target_kinds=("dice_table",)`, `shared=True`, `game=True`,
    `interruptible=True`, `duration=25.0` (nominal), `needs={"boredom": -45}`, no pose
    (standing), `label="Watch the dice"`, `status="watching dice"`,
    `doing="watching a game of dice"`, `done="watched a game of dice"`, `family="pastime"`.
  - *Game:* `settle_games` counts the guests watching a table as its onlookers. They are `done`
    when the result falls, and each remembers `dice_watched` ("Saw Rurik beat Edda at dice").
    An onlooker at a table with no game under way is released.
  - *Choice:* the candidate rule in `agents.py` offers `watch_dice` on every known dice table
    whose remembered `game` has two players (never after closing). Local utility in
    `local_policy.py`: `max(0, 0.1 + 0.5·boredom + 0.25·curiosity − 0.3·max(thirst, fatigue,
    bladder))`. Option sentence in `options.py`: "walk a few steps to the dice table and watch
    Rurik and Edda play dice", with the players named as the guest calls them. Jev guidance: a
    game draws a crowd; watching eases boredom, and curious guests love to see who wins; it means
    leaving their seat until the game ends.
  - *Tests:* offered only while a game is under way (no game, one player waiting, two playing,
    the inn closed); the option names the players as the watcher calls them; the utility grows
    with boredom and curiosity; two onlookers stand on different spots, and once every spot is
    taken the next is refused; onlookers finish with the game and remember the result; an
    onlooker who arrives after the result is released.
  - *Check:* `make check`, the offline evening, and `make run` with a forced game and a guest
    forced to watch: screenshot.
- [ ] **G5 — Numbers and the story.**
  - *Metrics:* `metrics.json` gets `dice`: `{games, abandoned, onlookers, wins: {actor_id: n}}`,
    counted from the `dice_won`, `dice_abandoned` and `dice_watched` events.
  - *Intentions:* `intentions.SALIENT_EVENTS` maps `dice_won` and `dice_lost` to a `dice`
    trigger, so a guest takes stock after a game. Check that saved intentions accept it.
  - *Done:* in a lockstep evening of the first scenario (seeds 1 and 2) with a writer that
    invites to dice whenever it can, a game reaches a result and `dice.games` counts it. Run the
    offline evening (seed 5) and a live one (Jev + Haiku, seed 5) with a byte-identical replay.
    Record games, abandoned games, onlookers, each winner with their chance, stuck time, the
    cost per evening against E19's $0.19, and one moment from the log (an invitation, the walk,
    the whoop, an onlooker's memory). Tick the boxes and update the status here and in
    [PLAN.md](../PLAN.md).

### The barkeep (B0–B6)

Added 2026-10-04 at the user's request; it comes before E20 (see Order). The barkeep, Hob, works
behind the bar all evening. He keeps to four staff cells behind the counter and pours every mug
himself in the `PouringBeer` pose (the art is in `frontend/static/characters/bartender/`). He also
chats with guests who lean on the bar, but serving always comes first. He is a person in the hall
like any guest: he is seen, heard, talked to and remembered. No model decides for him, though: a
pure routine does, so he costs no Jev calls. For the central test he is a fixed point that every
guest passes, who hears news at the bar and may pass it on.

Decisions for every B task (frozen 2026-10-04; change them here first if the code disagrees):

- **The zone.** Four staff cells behind the counter, recorded on the bar. The bar, the tap, the
  tap's spot and its line stay where they are: tests pin the closing call at [5, 2], the line's
  cells and the free cell [2, 2]. So the zone is a rule, not a wall. Guests' routes treat the
  staff cells as walls, and a staff member's routes treat them as the only floor.

  ```
         x  0 1 2 3 4 5 6 7 8 9 10 11
    y 0     # # # # # # # # # # #  #
    y 1     # . S S S S T . . . .  .    S  staff cell (the barkeep's zone)   T  tap
    y 2     # . . B B B B . . . .  .    B  the Oak bar
    y 3     # . . b b b o . . . .  .    b  bar spot (B4: guests lean here)   o  the tap's spot (orders)
    y 4     W w . . . . . q q q q  q    q  the tap's line                    W w  window and its spot
  ```

  ```json
  {"id": "bar", "kind": "bar", "name": "Oak bar", "x": 3, "y": 2, "width": 4, "height": 1,
   "staff_cells": [[2, 1], [3, 1], [4, 1], [5, 1]], "staff_facing": "south"}
  ```

  The *pour cell* is the first staff cell in listed order that is orthogonally next to a tap:
  (5, 1). The barkeep starts the evening there and pours there.
- **Who is staff.** An actor gets `post`: the ID of the bar they work at, or None for a guest.
  `staff.on_staff(actor)` reads `actor.get("post")`, so hand-made test actors without the key are
  guests. Staff come from the scenario's new `staff` section, not through the door. They never
  leave and never get a decision or an intention, and their needs stay at 0 (never pressed, never
  thirsty). `world.start_action` refuses every action for staff ("Hob works behind the bar"), which
  also covers forced actions and invitations. Only `bartending.tend_bar` moves them, through
  `lifecycle.activate`.
- **The card** lives in `data/staff/hob.json` (the card schema of E10), not among the guest
  presets: `test_cards.py` pins six presets, and E26 must not offer the barkeep as a guest.
  `parse_scenario(data, cards=None, staff_cards=None)`: without staff cards, a staff member comes
  with no card and middling traits, as a guest does without the card library. Tests that load
  only `data/characters` keep working. The card's substance: Hob, "barkeep of the Last Inn"; looks
  "the bearded barkeep in a red waistcoat and green apron"; calm, watchful, slow to anger; few
  words and a dry humour, passing on what he hears with "they say"; polishes the same mug over and
  over, remembers everyone's usual; secret: he waters the ale when the cellar runs low; goal: keep
  the ale flowing and the peace kept, and hear what the road brings. Params: patience 0.8, temper
  0.3, sociability 0.7, courage 0.6, strength 0.7, brawling 0.5, tolerance 0.8, comfort 0.4,
  curiosity 0.8. The name is a placeholder the user may change.
- **Ordering a beer.** Guests keep `take_beer` and the tap's line. While someone is on staff, a
  guest who reaches the tap's spot waits there in the `TakeBeer` pose until the barkeep's
  `pour_beer` (3 s, `PouringBeer`) ends. Then the guest's own `take_beer` completes as today
  (stock −1, beer +1), so `buy_drink`, the line and the metrics keep working. Without staff the
  tap stays self-service, so halls and tests without a barkeep are unchanged.
- **His routine** (`body/bartending.py`, every tick, in priority order): hand over a finished
  pour; start a pour for a waiting order; (B5) step across to a guest at the bar; (B5) greet
  them. Starting a pour takes him out of any conversation.
- **The look.** Sprite `bartender`, with every pose the guests have plus `PouringBeer`. He faces
  `staff_facing` (south, toward the hall) unless a sound or a partner turns his head. The client
  draws the staff cells as darker duckboards, with no captions (U1).
- **Out of scope:** commands for the barkeep (Stage 2); prices and tips (Stage 3); breaking up
  fights (E22 may add it); drinks other than ale; the barkeep starting the evening with news (he
  learns it at the bar); pacing or wiping the bar while idle; a second staff member.
- **Seed-sensitive tests.** B1 changes routes, and B2–B5 change whole evenings
  (`test_a_news_item_reaches_a_third_guest_in_other_words` uses seeds 1 and 2). If one fails,
  stop and report the seed and the failure. Do not change a seed or an assertion without the
  user's approval.
- **Shared with the dice tasks.** B0's `lifecycle.complete_action` is G2's first refactor:
  whichever task comes first builds it, and the other reuses it. B4 reuses
  `Activity.shared_target`, which the D02 fix added for the door and which G4's `Activity.shared`
  would duplicate. B3's timer condition may meet G2's `Activity.game` (see B3). Each block's save
  bump takes the next free `schema_version`. The dice table at (10, 8) is far from the bar.

- [ ] **B0 — One way to finish an action (refactor, no behavior change).** Take
  `lifecycle.complete_action(world, actor)` out of `_interact`: apply the effect and the needs, log
  `action_completed`, clear the action, look. Skip B0 if `complete_action` already exists.
  - *Check:* `make check`. First record a fresh offline baseline on `main` (the hall's behavior
    has changed since R0). Then show that the offline evening (seed 5) is byte-identical, with the
    commands under "Before M4 — Refactor".
- [ ] **B1 — Staff cells behind the bar.** Floor only; nobody works there yet.
  - *Module `hall/staff.py`* (add it to the `hall/` list in AGENTS.md): `check_staff_cells(world_map)`,
    called by `room.create_map`, and `off_limits(world_map, actor) -> list[tuple[int, int]]`. In B1
    it returns every bar's staff cells; B2 adds the branch for staff.
  - *Validation* (a `ValueError` with its own message for each rule): only a `bar` has
    `staff_cells`. They are a nonempty list of distinct cells inside the map, each walkable (not
    blocked, not furniture). Consecutive cells are orthogonally adjacent, so they form one stretch.
    None is an interaction spot, a queue spot, or on a line's way in. At least one cell is
    orthogonally next to a `tap`. `staff_facing` is north, south, east or west, and it is present
    exactly when `staff_cells` are. With the staff cells counted as walls, no interaction spot is
    cut off from the others (as `room._check_nothing_cut_off` checks for lines).
  - *Routes:* `routes.plan_route` (and with it the inspection plan), `routes.replan` and
    `lifecycle._yield_idle_occupant` add `off_limits(world["map"], actor)` to their obstacles.
    `controls._validate_block` refuses staff cells: "Cells behind the bar cannot be changed".
  - *Data:* the bar in `data/tavern.json` gets the two fields above.
  - *Client:* in `types.ts`, `WorldObject` gains `staff_cells?: number[][]` and
    `staff_facing?: Facing`. `furniture.ts` gets `drawStaffFloor`, which lays darker duckboards on
    the staff cells; `scene.ts` makes one call to it where it draws the floor. `scene.ts` is at 387
    lines: if it would pass 400, first move `drawRugs` to `furniture.ts` (D01) in its own commit.
  - *Tests (`tests/test_staff.py`):* the repository bar has four staff cells, and (5, 1) is next to
    the tap. Error cases: staff cells on a table, on a blocked cell, on furniture, with a gap, on
    the tap's spot, on a queue spot, with no tap beside them, with a missing or unknown
    `staff_facing`, `staff_facing` without cells, cells that cut a place off. Behavior: a guest at
    (1, 1) routed to the tap's spot, and a guest sent to inspect, never step on a staff cell; an idle
    guest at (2, 2) is never yielded onto (2, 1); blocking a staff cell is refused.
  - *Check:* `make check` and `make build`; `make run` and a screenshot (duckboards behind the bar,
    guests keep out); the offline evening (seed 5) against a fresh run on `main` (6.1 s stuck
    since the D02 fix).
- [ ] **B2 — The barkeep on duty.** He stands behind the bar; guests still pour their own.
  - *Scenario:* `first_evening.json` gets
    `"staff": [{"id": "hob", "name": "Hob", "color": "#c98f4a", "sprite": "bartender", "card": "hob", "post": "bar"}]`.
    `parse_scenario` reads this optional section into `Scenario.staff: tuple[StaffMember, ...] = ()`.
    A `StaffMember` has id, name, color, sprite, traits, post and an optional card. It gets a
    guest's checks except `arrives_at`. IDs are unique across guests and staff. Staff are not in
    `relationships` or `news`, whose checks keep using guest IDs only.
  - *Opening:* `open_evening` calls `staff.take_posts(world, scenario.staff)` before
    `admit_arrivals`. Each member becomes an actor (`create_actor`, all needs 0) on their post's
    pour cell, with `post` set. The arrival is logged as `on_duty` ("Hob took his place behind the
    Oak bar"), and the barkeep looks around. A post must be a bar with staff cells, with one member
    per bar. The card is `data/staff/hob.json`, as above.
  - *Actor:* `Actor.post: str | None`; `create_actor` reads `post`, which defaults to None.
  - *Staff rules* (one `on_staff` check each): `world.start_action` refuses;
    `decisions.free_to_decide` is False (no decisions, and no lockstep stalls);
    `intentions.intention_requests` skips staff; `lifecycle.step_actor` leaves their needs alone;
    `lockstep.evening_over` waits for guests only (`staff.guests(world)`), and `_track` lists only
    guests. `staff.off_limits` gives a staff member every cell outside their post's staff cells.
    `expression._facing` falls back to the post's `staff_facing`.
  - *Saves:* bump `schema_version` (approved for Stage 1). Name the bump in the commit, since
    `test_database.py` and `test_intention_saves.py` pin it. `parse_world` calls
    `staff.check_saved_staff`, which requires:
    - every present and departed actor has `post` (None or a string);
    - a staff member is present (never departed), holds no seat, and stands on a staff cell of
      their post, which is a bar with staff cells;
    - each post has one member;
    - no guest stands on a staff cell.
  - *Shell:* `app.create_default_app` (through `server/api.create_app`) and `scripts/evening.py`
    load `data/staff/*.json` as `staff_cards` (`--staff`, default `data/staff`).
  - *Client:* in `types.ts`, `Actor.post: string | null`. `sprites.ts` adds
    `bartender: { size: 68, lift: -16, poses: [...ALL_POSES, "PouringBeer"] }`.
  - *Test edit approved by the user (2026-10-04), and no other:* `tests/test_first_evening.py`'s
    `play` decides for every idle actor, and the test requires an empty hall at the end. With a
    barkeep who never leaves, `play` must skip staff (as `free_to_decide` does) and run while guests
    remain, and the end check must look at guests only. Name the test and the reason in the commit.
  - *Tests (`tests/test_staff.py`):*
    - Opening: Hob stands on (5, 1), faces south, has all needs at 0, and `on_duty` is logged.
    - Parse errors: an unknown card when staff cards are given, an ID shared with a guest, a
      missing post, an unknown field; a post that is not a bar with staff cells; two staff at one
      bar.
    - Over 300 s with guests, he never asks for a decision or an intention, his needs stay 0, and
      he never leaves his cells.
    - `start_action` and a forced action for him are refused.
    - A lockstep evening ends when the last guest leaves, although he stays.
    - A save round-trips. Malformed saves fail: staff on a non-staff cell, two staff at one post,
      a departed staff member, a guest on a staff cell, an actor without `post`.
  - *Check:* `make check` and `make build`; `make run` and a screenshot (Hob behind the bar,
    facing the hall); the offline evening (seed 5).
- [ ] **B3 — The barkeep pours.** Guests order at the tap and he serves them.
  - *Table:* `Activity.served: bool = False` ("while staff tend the bar, the bar's service, not a
    timer, completes it") and `Activity.staff_only: bool = False` ("only staff do it, and only the
    bar's service starts it; `actions.action_error` refuses it to a guest").
    - `take_beer`: `served=True`. Its `what` becomes "get a mug of ale at the tap {target} to
      carry; the barkeep pours it, or they pour their own when nobody tends the bar".
    - `pour_beer`: no target, `duration=3.0`, `served=True`, `staff_only=True`,
      `interruptible=False`, `pose="PouringBeer"`, `label="Pour a beer"`, `status="pouring"`,
      `doing="pouring ale behind the bar"`, `done="poured a mug of ale"`, `family="refreshment"`.
      Its `what` and `guidance` say that nobody chooses it, as for `doze`.
  - *Lifecycle:* `_interact` completes on the timer only when the activity is neither `partner`
    nor (`served` and `staff.tended(world)`). `tended` means someone on staff is present. If
    another flag such as `game` has already joined this condition, fold all of them into one
    `_ends_on_timer(world, activity)` in the same commit.
  - *Module `body/bartending.py`* (add it to the `body/` list in AGENTS.md):
    `order_at(world, tap) -> Actor | None` finds the guest who holds the tap's reservation and is
    interacting with `take_beer` on its spot. `tend_bar(world)` is called by `world.step_world`
    right after `honor_invitations`. For each staff member, in actor order:
    1. *Hand over:* his action is `pour_beer`, he is interacting, and its `_remaining` is 0 or
       less. If `order_at` still finds the guest, call `complete_action` for the guest (their
       `take_beer` effect pours: stock −1, beer +1) and log `served` ("Hob poured Edda a mug of
       ale"). Then call `complete_action` for him. If the guest is gone, only the pour ends and
       the stock stays.
    2. *Pour:* an order waits and he is not pouring. `activate` `pour_beer` with the route to the
       pour cell over his staff cells (`navigation.find_path`, with `impassable_cells` plus
       `off_limits` as obstacles). `activate` takes him out of a conversation, so serving comes
       first.
  - *Words:*
    - `sight.people_in_sight` adds `post` (the bar's name) only for someone on staff, so guests'
      records keep their keys.
    - `briefing._person` says "Hob, the barkeep, is pouring ale behind the bar", or "tending the
      bar" while he is idle.
    - With a barkeep in sight, `options._pour` says "walk … to the tap and ask Hob for a mug of ale
      (21 servings when last seen)", naming him as the guest calls him.
    - The prompts say a barkeep pours at the tap: the turn prefix's hall notes ("There is no
      barkeep tonight…"), and in `data/minds/intention_prefix.md` lines 15–16, 40 and 52–55 and the
      examples' "Pour an ale". Both prefixes stay above 4,096 tokens.
  - *Tests (`tests/test_bartending.py`, with a small hall helper):*
    - With a barkeep, a guest who reaches the tap holds no beer before `durations.pour_beer`
      seconds and one more beer after; the stock falls by one; there is one `served` event; both
      end idle.
    - The barkeep walks to the pour cell when he stands elsewhere.
    - The guest's `take_beer` outlasts its own 0.8 s timer. Without a barkeep, `take_beer` is
      self-service in 0.8 s as before.
    - A guest forced away mid-pour gets nothing, and the stock stays.
    - A barkeep in a scene leaves it to pour.
    - Two guests in line are served in turn.
    - A `buy_drink` errand still delivers the ale.
    - A guest cannot start `pour_beer`.
    - Options and the briefing name the barkeep, and `people` carry `post` only for staff.
  - *Check:* `make check` and `make build`. In `make run`, force a guest to take a beer and attach
    a screenshot of Hob pouring while the guest waits. Run the offline evening (seed 5) and compare
    beers served, give-ups in line and stuck time against B2.
- [ ] **B4 — Leaning on the bar.** Guests stand at the counter and can talk with the barkeep.
  - *Table:* reuse `Activity.shared_target` (added for the door in the D02 fix):
    `lifecycle.activate` never reserves such a target, and `routes.plan_route` already keeps the
    spots apart, so the bar's three spots are its capacity.
    - `stand_at_bar`: `target_kinds=("bar",)`, `shared_target=True`, `duration=12.0`,
      `interruptible=True`, `needs={"boredom": -20, "social": -10}`, no pose,
      `label="Stand at the bar"`, `status="at the bar"`, `doing="leaning on the bar"`,
      `done="stood at the bar"`, `family="company"`. Its `what` and `guidance` say they lean on
      the bar, where the barkeep chats with whoever stands there and hears all the news, and that
      it means leaving their seat.
    - `FAMILIES["company"]` becomes "chat with someone at their table or beside them, join a
      conversation, or lean on the bar".
  - *Data:* the bar gets `"interaction_spots": [[3, 3], [4, 3], [5, 3]]`. These leave out the
    tap's spot (6, 3), because someone chatting there would hold up the line.
  - *Side by side:* `scenes.side_by_side` is also True for two people at the same bar, whatever
    the distance between them. A person is at the bar when they are a guest standing on one of its
    interaction spots, or its staff member on one of its staff cells, neither walking nor seated.
    Only the exact spots count, unlike the cells around a view.
  - *Choice:* the candidate rule in `agents.py` offers `stand_at_bar` on a known bar with
    interaction spots when all of these hold: someone on staff is in sight, the guest does not
    already stand on one of its spots, at least one spot has no person in sight on it, and the inn
    is open. Local utility:
    `max(0, 0.05 + 0.45·social + 0.15·curiosity − 0.25·max(thirst, fatigue, bladder))`. Option
    sentence: "walk … to the bar and lean on it, where Hob tends it". `options._talk` for a staff
    partner: "chat with Hob across the bar". `test_social.py:170`, which says a bar without a
    barkeep offers nothing, stays green.
  - *Writers:*
    - `turn_view` adds `speaker.on_duty` (the post's name), and `participants` get
      `"on_duty": true`, both only for staff.
    - `invitations.offered_kinds` is empty for a speaker on duty, and `turns.check_turn` rejects an
      `invite` addressed to someone on duty.
    - His needs are 0, which the writers would read as "company enough". So the scripted writer's
      `_act` never has him take his leave on his own. `haiku_turns._nudges` replaces his need
      nudges with "The speaker is the barkeep at work: he stays while the guest does, and leaves
      only to pour." `turn_content` says "You are the barkeep, on duty behind the Oak bar", and
      `_scene` names him "Hob (the barkeep)".
    - The turn prefix gains one rule for a speaker on duty: he is the host behind the bar, who
      welcomes, listens and passes on in his own words what guests told him; he invites nobody and
      never leaves the bar. It also gains one good example.
    - The intention prefix adds "lean on the bar and chat with the barkeep" to what guests can do.
      Both prefixes stay above 4,096 tokens.
  - *Tests:*
    - `side_by_side` cases: a guest on a spot and the barkeep on a staff cell; two guests on
      spots; a guest on the tap's spot; one person walking; one seated.
    - `stand_at_bar` offered or not: no barkeep in sight, inn closed, every spot taken, already
      standing there.
    - Two guests take different spots, and a fourth is refused.
    - A guest on a spot can start `talk` with him.
    - No invitation is offered to him or by him.
    - The scripted barkeep does not say goodbye first, and the nudge text is right.
  - *Check:* `make check` and `make build`; the offline evening (seed 5), where some guest leans on
    the bar and talks with Hob.
- [ ] **B5 — The barkeep greets.** He steps over to a guest at the bar and opens the talk.
  - *Routine:* `tend_bar` gets two more steps, after hand-over and pour. They apply to a staff
    member who is idle and in no scene, while the inn is open. The guest he looks to is the first,
    in actor order, who stands at his bar, is in no scene, is not `pressed`, and whom he has not
    heard speak (his `heard`) within `rules.bartending.chat_gap`.
    3. *Step across:* if he is not on the staff cell across from that guest, he walks there with
       `wait`, as `_yield_idle_occupant` does. The cell across has the guest's x; failing that, it
       is the nearest by |dx|, the first listed on a tie.
    4. *Greet:* on that cell, he starts `talk` with them: `action_error`, then `activate` with no
       route, as `start_action` does for a partner verb.
  - *Rules:* `rules.bartending = {"chat_gap": 60.0}`, a `BartendingRules` TypedDict, checked in
    `check_rules` (positive).
  - *Tests:*
    - The barkeep steps across, then greets.
    - He does not greet the same guest again within `chat_gap`, and greets again after it.
    - An order breaks off his chat.
    - He does not greet after closing, nor a guest who is pressed or already in a scene.
  - *Check:* `make check` and `make build`; `make run` and a screenshot of a chat across the bar;
    the offline evening; a live evening (seed 5) with a byte-identical replay.
- [ ] **B6 — Numbers and the story.**
  - *Metrics:* `metrics.json` gets `bar`: `{served, opened, lines, news_told}`. `served` counts
    `served` events; `opened`, `lines` and `news_told` count `conversation_started`, `turn` and
    `news_told` events whose actor is on staff (staff IDs come from the final world).
  - *Done:* in lockstep evenings of the first scenario (seeds 1 and 2):
    - every beer was poured by the barkeep (`served` equals the `take_beer` completions);
    - he never stands outside his staff cells;
    - he holds at least one conversation.
  - *Live run:* run the offline evening (seed 5) and a live one (Jev + Haiku, seed 5) with a
    byte-identical replay. Record:
    - beers served and the longest line;
    - stuck time;
    - scenes and lines with the barkeep;
    - the news he passed on, and whether an item went two hops through him (acceptance scenario 3);
    - the cost per evening against E19's $0.19;
    - one moment from the log.

    Tick the boxes and update the status here and in [PLAN.md](../PLAN.md).

### M5 — Presentation and acceptance

- [ ] **E23 — New poses.** Generate fight stance, punch, shove, hit, knocked out,
  getting up, cheer, and asleep at the table through the
  [character pipeline](../CHARACTER_ART_PIPELINE.md). Done: each pose is reviewed at
  game scale for every guest sprite.
- [ ] **E24 — Living room rendering.** Facing, emotes, real-line bubbles, drunk sway,
  visible queues, and a fight ring. Done: a browser check of a recorded evening.
- [ ] **E25 — Observer UI.** Event feed; inspector with card, goal, intention, mood and
  thoughts, relationships, knowledge, drunkenness, and the last trigger and scores;
  debug controls in their own panel. Done: an incident's cause is traceable in the UI.
- [ ] **E26 — Evening setup.** Choose four to six guests from presets and custom
  cards, write a custom guest, pick the news, and start. Done: a custom guest appears
  in the evening with confirmed params.
- [ ] **E27 — Chronicle.** After closing, Haiku writes a short chronicle that cites
  event IDs; claims without a logged event are rejected. Done: runner and UI show it.
- [ ] **E28 — Acceptance.** Run the scenarios below; record cost, latency, and
  metrics; set the per-evening budget. Done: results are written to this file.

## Order

M1 comes first: E01 is a refactor under the existing tests, and E02–E03 make every later
task measurable. Within M2–M4 the body (E05–E08) and characters (E10–E13) can proceed
in parallel; conversation (E15–E18) needs cards and thoughts; conflict (E20–E22)
needs stimuli, attention, thoughts, and drunkenness. Art (E23) can start at once.

After M3: refactor R0–R7, then D13 (model health), then E18b
(memory), then E19. E19 comes before E20–E22 because the chronicle and acceptance
scenario 3 need news. E20 → E21 → E22 is strict. D13 can also run in parallel with the
refactor, since it touches only the adapters, the shell and the dashboard. E18b is easier
after R7, because it touches `turns.py` and `haiku_turns.py`, which R7 moves.

After E19: dice (G0–G5) and the barkeep (B0–B6), both at the user's request (2026-10-04), then
E20–E22. The two blocks may go in either order. G0 → G1 → G2 → G3 → G5 is strict; G4 needs only G2
and may come before G3. B0 → B1 → B2 → B3 → B4 → B5 → B6 is strict. Whichever block comes second
reuses what the first built: `lifecycle.complete_action` (G2's first refactor, B0) and the next
free `schema_version`. B4, and G4 in place of its `Activity.shared`, reuse the door's
`Activity.shared_target`. E21 then rolls through G0's `chance.roll`; E22's `watch_fight` can reuse
G4's sharing and `Activity.game`, and its
bystanders can later let the barkeep step in, since he already stands on the activity system.

## Acceptance scenarios

Initial targets, to be tuned in E28:

1. Twenty offline evenings with four to six guests finish with every guest gone by
   closing, no overlaps, no negative resources, the barkeep never off his staff cells, and
   no guest idle without a decision for more than 30 seconds.
2. Two or more guests wanting the tap or the WC form a queue; a loud event in earshot
   gets a glance or an interrupt within 0.5 seconds of game time.
3. Across five live evenings: at least twelve distinct activities per evening, at least
   four conversations with six or more turns, one news item traveling two hops, and a
   relationship that changes category.
4. Conflict is occasional: hostile acts in about half the evenings, a fight in at least
   one of five, and not every fight ends in a knockout.
5. A live evening with five guests costs about $1 or less, and no guest stands frozen
   for more than 3 seconds while a model call is pending.
6. An observer retells a story from at least one live evening; every claim in the
   chronicle maps to a logged event.

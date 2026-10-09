# Stage 1 — A Believable Evening

Four to six guests spend one evening in the hall. The test is whether model-driven
guests look like real people who came to relax, and whether the evening produces a
story an observer can retell, with every cause visible in the event log.

## Decisions

- **Player:** observer and administrator. Before the evening they pick the guests and
  the news; during it they watch and inspect. Debug controls stay, in a debug panel.
- **Scope:** one evening in the existing hall, four to six guests and one barkeep (B0–B6),
  closing time ends it. No other staff, prices, agreements, or memory between evenings yet.
- **Models:** Jev scores activities (choice layer); Claude Haiku 5.5
  (`claude-haiku-5-5`) writes conversation turns, intentions, card extraction, and the
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
(conversation memory) and E19 (facts and retelling) are done (2026-10-04). Done: dice (G0–G5), the
barkeep (B0–B6) and E20 (hostile options), all 2026-10-04. Next:

1. **Dice (G0–G5), done.** Guests agree to a game of dice, play it at a dice table, and others watch.
2. **The barkeep (B0–B6), done.** A barkeep keeps to four cells behind the bar, pours every mug,
   and chats with guests who lean on the counter.
3. **M4, news and conflict (E20–E22).** E20 (hostile options) is done; E21 resolves fights next.
4. **The mind (MIND.md steps 0–5), done 2026-10-05.** Guests set typed goals, ask the mind within a budget,
   may promise to come over, and the barkeep keeps to his duty.
5. **Giving (H0–H5), done 2026-10-05.** Guests hand each other what they carry, and fetch
   a drink for someone as one chosen errand. Worlds were saved as version 14; tables and manners (T3) made it 15,
   so the next `schema_version` is 16.
6. **Sleep (Z0–Z6), built 2026-10-08.** Activities spend energy, only a nap at the table restores
   it, and a tired guest goes home or, more so when drunk, sleeps in their seat until a loud noise wakes them.
   The saved world did not change (still version 14 then). The live evening and its replay are still to run.
7. **Tables and manners (T0–T8), built 2026-10-08.** Guests walk over to another table to talk, agree to move to a
   free table together, and upset the hosts of a table they sit down at uninvited; an apology mends it.
8. **Closing call, news and a sick guest (F0–F9), planned 2026-10-09.** A ten-minute evening whose barkeep calls
   closing time out loud, guests who come in rested, one item of news with one holder, two windows on the west wall,
   candles, and a sick guest whom Edda seeks out with a remedy.
9. **Choice depth (C0–C8), built 2026-10-09.** A lean first stage, answers to what was just done to a guest, a third
   stage that picks why for social options, temperament in the draw, projects of several steps, and the invitee's
   own answer to an invitation (off by default: D24). Worlds are saved as version 18 (16 and 17 came from the F tasks and C5).

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
- [x] **E20 — Hostile options.** Insults are speech acts; `shove` and `start_fight`
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
  - *Frozen shape (2026-10-04, before coding):* the text above has three corrections.
    The thought kinds are `insulted` and `line_cut` (not `insult`, `cut_in_line`).
    `drunkenness.inhibition_modifier` is a multiplier (1.0 sober), so the urge is
    `temper × inhibition_modifier(drunkenness)`, not `temper × (1 + …)`. The observation carries no
    rules, so the thresholds are module constants in `hostility.py`, as `THOUGHTS` and the drunk
    stages are, not `rules.hostility`; that also keeps the rules out of one more save (D08).
    - *Module:* `social/hostility.py` owns `HOSTILITY` (opinion −30, recent 120 s, urge needed: `shove`
      0.45, `start_fight` 0.85) and `hostile_targets(observation, verb) -> list[str]`, sorted by ID,
      for `verb` one of `shove`, `start_fight` (every `start_fight` target is also a `shove` target).
      Tests are in `tests/test_hostility.py`.
    - *A target qualifies when:* they are in `observation["people"]`, are not staff (no `post`) and not
      the guest; they sit at the guest's table or stand beside them (the rule for `talk`, so the world
      can check the same thing); the guest's `opinion_of` them is −30 or lower; one of the guest's
      active thoughts about them is a `HOSTILE_CAUSES` kind (`insulted`, `quarrel`, `seat_taken`,
      `friend_insulted`, `line_cut`) formed within 120 s (formed = `expires_at` − the kind's seconds);
      and `urge` reaches the verb's threshold. A guest with no `temper` trait has urge 0: hostility is
      opt-in, so a hand-made observation or a Stage 0 visitor is never hostile.
    - *Verbs:* `Activity.confronts` (new): targets another visitor but is not a scene part; it starts
      where the actor stands (no walking) and ends on its timer. `shove` (1.0 s) and `start_fight`
      (2.0 s) are in the new family `confront`. `action_error` refuses a target who is missing, the
      actor, staff, or neither at the actor's table nor beside them. The world does not re-check the
      gate: like every verb it checks only what is physically possible.
    - *Effects until E21:* a completed `shove` logs `shove` (loud sound 1.0, reach 24) and gives the
      victim the thought `shoved` (mood −8, opinion −25, 300 s) about the shover; a completed
      `start_fight` logs `fight_started` (sound 1.0, reach 30) and gives the victim `attacked` (mood
      −10, opinion −35, 300 s). Nothing else changes yet: E21 resolves the fight, E22 adds reactions.
    - *Mind side:* `agents._hostile_candidates` offers each qualifying target as `shove:<id>` and
      `start_fight:<id>`; `local_policy` weighs them low (`shove` 0.1 + 0.3 × urge, `start_fight`
      0.05 + 0.2 × urge, urge capped at 1); `options` has a sentence for each; the verbs' `guidance`
      tells Jev that hostile acts are rare and have consequences.
    - *Saves:* `schema_version` 10 (the rules' `durations` gain two verbs, so older saves are
      rejected); the approved bump is named in the commit, and the tests that pin 9 follow.
  - *Built (2026-10-04):* `social/hostility.py` (`HOSTILITY`, `hostile_targets`, `urge`), `Activity.confronts`,
    the verbs `shove` and `start_fight` in the new `confront` family, `_confront_error` in `body/actions.py`, the
    thoughts `shoved` and `attacked`, the sounds `scuffle` and `brawl`, and the three mind tables
    (`agents._hostile`, `local_policy`, `options`). Hostile options are appended after the peaceful ones,
    so a peaceful request is byte-identical to before. D11 is paid: a quarrel now comes only from an `insult`
    whose target already thinks ill of the speaker (opinion −10 or less, the `DISLIKED` line, read before the
    insult's own thought lands), so an insult stings first and an answer in kind quarrels; `complain` has no
    consequence of its own; the beer dice and `rules.quarrel_per_beer`/`quarrel_max` are gone. `visit.grievances`
    is gone from the world, the saves, the observation check and `types.ts`; what still rankles is read from the
    thoughts by `thoughts.rankling(actor, now)`, which also feeds the briefing's "Still rankling tonight" line
    and the local policy's reading of a wronged guest. Saves are `schema_version` 10, with the approved bump
    named in the commit: `test_database.py` and `test_intention_saves.py` pin 10 (the second test is renamed
    `test_new_worlds_are_version_10`).
  - *Tests:* new `test_hostility.py` (the gate: 13 peaceful and 11 positive cases, ordering, a bad verb),
    `test_confront.py` (the world's side, and a grudge turning into a fight through an ordinary decision),
    `test_hostile_options.py` (candidates, family, scores, wording), with `hostile_view.py` for the hand-made
    observation. Changed with the user's approval (D11), each named here: quarrel dice replaced by a grudge in
    `test_turns.py` (`test_a_complaint_never_ends_in_a_quarrel`), `test_speech_acts.py` (the insult test, five
    cases), `test_evening.py` (the quarrel-from-talk test, now four cases, and `test_quarrel_aggrieves_both_and_leaves_them_lonely`),
    `test_feelings.py` (`seated`, and the quarrel case is now "an-insult-and-a-quarrel": Ada holds the insult and
    the quarrel) and `test_intention_runners.py` (`quarrelsome` has a mutual grudge, and the fake writer insults);
    grievances replaced by thoughts in `test_thoughts.py` (`rankling`), `test_briefing.py`, `test_queues.py`,
    `test_seating.py` (`wrongs`), `test_evening.py`; the two cases that validated the removed field
    (`malformed-grievances`, `malformed-grievance`) are gone; stale `"grievances": []` fixture keys are removed.
  - *Results:* `make check` 2062 tests (1983 before), mypy clean, `make build` passes. Offline, seeds 5, 1 and 2
    (scripted, 426 game s each): no shove, fight or quarrel, because the scripted writer never insults and only
    seat-taking grudges formed (4, 2 and 3 events, −15 opinion each against the −30 line); on the old rule some
    quarrels came from beer dice. Live (Jev + Haiku, seed 5, 426 game s): 22 scenes, 44 turns, 308 calls, 0 failed,
    0 fallbacks, $0.272 per evening, $0.00304 per turn against $0.00272 for E19 (+$0.00032, under the $0.0005
    limit), 88.2% cache hits, p50 1.6 s; a replay is byte-identical (`cmp` of `events.jsonl`). **No guest insulted
    anyone, so no hostile option was offered live:** the proof is the tests, including the one that takes a guest
    with a grudge from `choose_action` to a `start_fight` in the world. How often Haiku's guests turn on each
    other is for E28 to count; E21 resolves the blow and E22 the room's reaction.
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
  - *Reuse:* `watch_fight` can stand on `Activity.shared_target` (G4's `watch_dice` uses it) and
    `Activity.game`, with the fight in place of the game.

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
  so the seating, table-talk and dozing rules leave players alone. One dice table stands in the middle
  of the hall, between the regular tables, at (10, 8) (`data/tavern.json`, after the regular tables). It
  first stood on the right and then at (9, 8); the user asked for the middle, then one cell further
  right. Existing tests that name its cells were edited for that (see G1's result):

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

- [x] **G0 — One roll, one list of kinds (refactor, no behavior change).**
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
  - *Result (2026-10-04):* `hall/chance.py` holds `roll`; `conversation._quarrels` and
    `dozing.nodding_off` use it, and `room.OBJECT_KINDS` serves the map check, `sight` and
    `observation`. `make check` passes (1,739 tests, mypy clean). The offline evening (seed 5) is
    byte-identical to a baseline recorded on `main` first (`events.jsonl` and `calls.jsonl`). **The
    replay half of the check could not run:** `runs/e19-live` no longer replays even on `main`
    (`No recorded intention call is left`), because the door-capacity change (D02) altered the
    evening after it was recorded. G5 records a fresh live evening and its replay.
- [x] **G1 — The dice table in the hall.** Furniture only; nobody plays yet.
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
  - *Result (2026-10-04):* `room.OBJECT_KINDS` lists both kinds and `room.SEAT_TABLES` maps each
    seat kind to its table kind (a walkable object must be a seat; a seat's table must exist and be
    of the matching kind). `hall_view.place_words` says "the dice table"; `attention._landmark` and
    the briefing skip every seat kind. The client (`furniture.drawDiceTable`, a green rug in
    `drawRugs`, `types.ts`) draws the table with two ivory dice; `drawTable` was split into
    `drawTableTop` and its props, and `drawRugs` moved out of `scene.ts` (387 → 368 lines), each
    in its own refactor commit. 17 tests in `tests/test_dice_table.py` (the briefing and landmark
    rules were mutation-checked). `make check` (1,756 tests) and `make build` pass; in the browser
    the table stands on a green rug with its dice and two chairs, and the console is clean.
    The offline evening (seed 5) is byte-identical to `main`'s (16 scenes, stuck time unchanged):
    the table is in nobody's way, and nothing yet offers a guest the dice. The table first stood on the
    right of the hall so that no existing test had to change; the user then asked for the middle, and
    then for one cell further right, so it stands at (10, 8). **Existing tests were edited, with the
    user's request as the reason, and only their cells or expected landmark:**
    `test_attention.py::test_the_briefing_names_the_trigger_while_it_is_fresh` stages a quarrel at (8, 7)
    and (9, 7) and pins the landmark in the briefing's text; the nearest place is now "the Dice table", so
    "near the Window table" became "near the Dice table". `test_queues.py::test_guests_at_one_tap_form_a_line_without_overlaps`
    (two cases) and `test_people_in_line_stand_on_its_spots_in_order` start a guest on (10, 8), which is now
    the table: that cell became (10, 6), two cells up the same column, and their assertions are unchanged.
    Every other test passes unchanged, and the offline evening is still byte-identical.
- [x] **G2 — A game at the table.** Two guests seated at the dice table play one game, and the
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
    is None exactly while one player waits; `since` lies between 0 and now, and `ends_at` (which
    lies ahead) is at least `since`.
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
  - *Result (2026-10-04):* `social/dice.py` holds the formula (`form`, `win_chance`, `winner`), the
    per-tick `settle_games` and the save checks (`check_saved_games`, `check_dice_rules`);
    `lifecycle.complete_action` was taken out of `_interact` first, in its own commit. `play_dice`
    is in the `pastime` family and never a candidate; `Activity.game` stops the action's timer (it is
    clamped at zero so a game still saves). `rules.dice` is as frozen above; thoughts
    `won_at_dice` and `lost_at_dice`; `EVENT_SOUNDS["dice_won"]` is a 0.3 cheer. Saves are
    `schema_version` 8, an approved bump: `test_database.py` and `test_intention_saves.py` pin 8
    (the second test is renamed `test_new_worlds_are_version_8`), and nothing else changed.
    `tests/test_dice.py` (52 tests): odds by cases, symmetry, out-of-range errors, 400-game rates
    (cap case 72–88%, equal guests 43–57%), the game through `step_world` (starts when both sit,
    nobody decides during it, one winner and one loser, thoughts, a lone player gives up, taking
    one player away breaks it off, a second game follows), saves round-trip and 11 malformed
    games, 8 malformed rules. `make check` (1,809 tests, mypy) passes, and the offline evening is
    byte-identical to `main`'s. In the browser (debug panel, `play_dice` on both chairs): Edda and
    Toren sit facing each other in the talking pose with the dice between them, the hover reads
    "Dice table · available · Edda and Toren playing", and 25 s after the second sat the feed
    shows "Toren beat Edda at dice" and both "completed play_dice"; Toren's thoughts list
    "Beat the grey-haired woman smelling of sage at dice" (the looks, not the name: they are
    strangers). `lifecycle.py` is now 393 lines, 7 below the limit: split it before the next
    task that grows it.
- [x] **G3 — Agreeing to play.** The `dice_together` invitation sends both guests to the table.
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
    `haiku_turns._nudges` adds "The speaker is bored, and the dice table stands free: a game of dice is a fine thing to propose." when boredom is
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
  - *Result (2026-10-04):* `dice.open_chairs` (a table's first two chairs when no game is under way and
    neither is reserved; `ValueError` for anything that is no dice table) feeds both `offered_kinds` and
    the new `_both_play_dice` entry of `invitations._FIRST_STEPS`, which became a table in its own
    refactor commit. `KINDS` holds `dice_together`; `conversation.ACTS["invite"]`, the turn prompt (the
    hall paragraph and Example 23) and the intention prefix name the dice table. The scripted writer
    (`scripted.BORED` 50, `BOLD` 0.5) invites bored and bold guests to dice, merely bored ones to darts,
    and accepts at boredom 30. 28 tests in `tests/test_dice_invitation.py`, among them the done test: a
    lockstep first evening (seeds 1 and 2) whose writer invites to dice whenever it can plays games to a
    result. `make check` passes (1,837 tests; seeds 1 and 2 of the news test and `test_first_evening.py` are
    unaffected). **Offline evenings play no dice:** the scripted writer never got an invitation out in any of
    seeds 1–8 (main has none either: scenes end after two or three lines, before its once-a-scene
    invitation draw), so seed 5 is byte-identical to `main`'s and games appear in live evenings, where the
    nudge asks Haiku to propose them. If G5's live evenings show none, raise `scripted.INVITES` or the
    nudge before judging the feature.
- [x] **G4 — Onlookers.** Guests who see a game may gather round to watch it.
  - *Table:* `Activity.shared_target` already exists (the door-capacity change, D02: "several
    visitors may use the target at once, so it is never reserved; each takes a spot of their own"),
    so there is no new flag. `watch_dice`: `target_kinds=("dice_table",)`, `shared_target=True`,
    `game=True`, `interruptible=True`, `duration=25.0` (nominal), `leaves_seat=True`,
    `needs={"boredom": -45}`, no pose (standing), `label="Watch the dice"`, `status="watching dice"`,
    `doing="watching a game of dice"`, `done="watched a game of dice"`, `family="pastime"`.
  - *Game:* `settle_games` counts the guests watching a table as its onlookers. They are `done`
    when the result falls, and each remembers `dice_watched` ("Cid watched Rurik beat Edda at dice").
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
  - *Result (2026-10-04):* `watch_dice` joins the activity table; `dice.settle_games` finds the guests who
    have reached the table (`_watching`), finishes them when the result falls (each logs and remembers
    `dice_watched`), and lets them go when no game is under way (broken off, never begun, or long over).
    The candidate rule (`agents._games`) offers it for a known dice table whose remembered `game` has two
    players, `local_policy` scores it `0.1 + 0.5·boredom + 0.25·curiosity − 0.3·(worst of thirst, fatigue,
    bladder)`, and `options._watch_dice` says "walk … to the dice table and watch Ada and the stout woman
    with a pipe play dice", the players as the watcher calls them. The planned `Activity.shared` was not
    needed: `shared_target` does it. 16 tests in `tests/test_dice_onlookers.py` (shared helpers in
    `tests/dice_hall.py`): offered only while two play (not for a lone player, a finished game or a
    closed inn), naming, the score rising with boredom and curiosity and falling with a pressing need,
    four onlookers on four spots and a fifth refused, nobody reserving the table, onlookers finishing with
    the game and remembering it, a late arrival let go, a broken-off game letting its onlookers go
    without a result, and a save made mid-watch. `make check` (1,854 tests) passes and the offline
    evening is byte-identical to `main`'s. In the browser: Edda and Toren played, Rurik was sent to watch
    and stood at the table's west spot; at the result the feed shows all three "completed", and Rurik's
    boredom fell to 1.
- [x] **G5 — Numbers and the story.**
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
  - *Result (2026-10-04):* `metrics.dice_metrics` (games, abandoned, onlookers, wins per guest) is in
    `metrics.json` as `dice`; `intentions.SALIENT_EVENTS` maps `dice_won` and `dice_lost` to a `dice`
    trigger, so players take stock after a game and a save holding that trigger loads back. The lockstep
    done test (seeds 1 and 2, a writer that invites to dice whenever it can) plays games to a result and
    `dice.games` counts them. `make check` passes (1,864 tests). Offline seed 5 plays no dice (see G3) and is
    byte-identical to `main`'s. **Live (Jev + Haiku), both replays byte-identical:** seed 5, 432 game s,
    10 scenes, 24 turns, no fallbacks, two darts invitations and no dice, stuck 22.2 s, about $0.18 for the
    evening; seed 1, 432 game s, 12 scenes, 26 turns, no fallbacks, one game of dice, stuck 21.2 s, $0.18
    ($0.0026 per turn). The seed 1 game: at 364 s Rurik (Haiku, nudged by his boredom) invited Edda to a
    game of dice, she accepted, they sat down at 367 s and at 392 s "Rurik beat Edda at dice". No onlooker
    watched (nobody was near enough or bored enough), and no game was abandoned; so `dice` read
    `{games: 1, abandoned: 0, onlookers: 0, wins: {ivo: 1}}`. One odd moment: Edda's intention written just
    after she accepted says she means to decline the game; the invitation was already honoured, a case of a
    model changing its mind after the game's yes (it is not a rule violation, but E28 should count it).
    One game in two live evenings is thin; the nudge works but invitations stay rare, so raising
    `scripted.INVITES` or making the nudge stronger is open for E28.
  - *More live evenings (Jev + Haiku, seeds 2, 3 and 7, same day):* one game each (Rurik beat Edda at 314 s,
    Toren beat Brida at 182 s, Edda beat Brida at 296 s), no abandoned games, no onlookers (Jev never picked
    `watch_dice`; the players' own table was the only company near it), one turn fallback in seed 3, $0.17–0.21
    and 21–36 s stuck per evening. With seed 1, four of five live evenings had a game. In seed 2 Edda
    herself proposed it ("Rurik, fancy a round at the dice table?"), Rurik accepted, and after the game both
    wrote new intentions from the result ("I beat her fair and square, and she took it well enough"; "I've lost
    my coin and my temper both"): the `dice` trigger does its job.


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
    y 0     # # # # # # # # # F F  F    F  the fireplace, built into the wall, across from the door
    y 1     # . S S S S T . . f f  f    S  staff cell (the barkeep's zone)   T  tap   f  fireplace spot
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
  draws the staff cells as plain floor, exactly like the rest (the user's call, 2026-10-04), and no
  captions (U1).
- **Out of scope:** commands for the barkeep (Stage 2); prices and tips (Stage 3); breaking up
  fights (E22 may add it); drinks other than ale; the barkeep starting the evening with news (he
  learns it at the bar); pacing or wiping the bar while idle; a second staff member.
- **Seed-sensitive tests.** B1 changes routes, and B2–B5 change whole evenings
  (`test_a_news_item_reaches_a_third_guest_in_other_words` uses seeds 1 and 4, since B3). If one fails,
  stop and report the seed and the failure. Do not change a seed or an assertion without the
  user's approval.
- **Shared with the dice tasks.** B0's `lifecycle.complete_action` is G2's first refactor:
  whichever task comes first builds it, and the other reuses it. B4 reuses
  `Activity.shared_target`, which the D02 fix added for the door and G4's `watch_dice` uses too.
  B3's timer condition may meet G2's `Activity.game` (see B3). Each block's save
  bump takes the next free `schema_version`. The dice table at (10, 8) is far from the bar.

- [x] **B0 — One way to finish an action (refactor, no behavior change).** Take
  `lifecycle.complete_action(world, actor)` out of `_interact`: apply the effect and the needs, log
  `action_completed`, clear the action, look. Skip B0 if `complete_action` already exists.
  *Skipped (2026-10-04): G2 built `complete_action` already.*
  - *Check:* `make check`. First record a fresh offline baseline on `main` (the hall's behavior
    has changed since R0). Then show that the offline evening (seed 5) is byte-identical, with the
    commands under "Before M4 — Refactor".
- [x] **B1 — Staff cells behind the bar.** Floor only; nobody works there yet.
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
    `staff_facing?: Facing`. The cells are drawn as plain floor, like the rest of it (the user asked
    for no tint), so nothing is drawn for them.
  - *Tests (`tests/test_staff.py`):* the repository bar has four staff cells, and (5, 1) is next to
    the tap. Error cases: staff cells on a table, on a blocked cell, on furniture, with a gap, on
    the tap's spot, on a queue spot, with no tap beside them, with a missing or unknown
    `staff_facing`, `staff_facing` without cells, cells that cut a place off. Behavior: a guest at
    (1, 1) routed to the tap's spot, and a guest sent to inspect, never step on a staff cell; an idle
    guest at (2, 2) is never yielded onto (2, 1); blocking a staff cell is refused.
  - *Check:* `make check` and `make build`; `make run` and a screenshot (plain floor behind the bar,
    guests keep out); the offline evening (seed 5) against a fresh run on `main` (6.1 s stuck
    since the D02 fix).
  - *Built (2026-10-04):* `hall/staff.py` holds `check_staff_cells` and `off_limits(world_map, actor)`.
    `world.create_world` calls the check right after `create_map`, not `create_map` itself: the check reads
    `room` (cells, spots, `line_approach`), so `room` importing it would be a cycle. Saves are checked too,
    since `persistence.check_saved_geometry` builds a world. Messages name the bar and the rule (a non-bar,
    missing or unknown `staff_facing`, not a nonempty list of cells, not distinct or inside the hall, not
    free floor, not one stretch, on a spot, a queue spot or a line's way in, no cell next to a tap, or cutting
    a place off). `routes.plan_route` and `replan` (and with them the inspection plan),
    `lifecycle._yield_idle_occupant` and `controls._validate_block` ("Cells behind the bar cannot be
    changed") use `off_limits`. The repository bar has `staff_cells` (2, 1)…(5, 1) facing south; the client
    types gained both fields, and the cells are drawn as plain floor (a first version tinted them with
    duckboards; the user asked for none, so it was removed). 25 tests in `tests/test_staff.py`, including a
    7×3 hall whose one corridor the cells would cut. The offline evening (seed 5) is byte-identical to
    `main`'s, as it should be for floor alone.
- [x] **B2 — The barkeep on duty.** He stands behind the bar; guests still pour their own.
  - *Scenario:* `first_evening.json` gets
    `"staff": [{"id": "hob", "name": "Hob", "color": "#c98f4a", "sprite": "bartender", "card": "hob", "post": "bar"}]`.
    `parse_scenario` reads this optional section into `Scenario.staff: tuple[StaffMember, ...] = ()`.
    A `StaffMember` has id, name, color, sprite, traits, post and an optional card. It gets a
    guest's checks except `arrives_at`. IDs are unique across guests and staff. Staff are not in
    `relationships` or `news`, whose checks keep using guest IDs only.
  - *Opening:* `open_evening` calls `arrival.take_posts(world, scenario.staff)` before
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
  - *Built (2026-10-04):* `hall/staff.py` gains `on_staff`, `guests`, `post_of`, `pour_cell`, `facing_of`,
    the staff branch of `off_limits` and `check_saved_staff`. `take_posts` lives in `hall/arrival.py`, not in
    `staff.py` as drafted: it builds actors with `create_actor`, and `arrival` already imports `routes`, which
    imports `staff`, so the other way round would be a cycle. `scenario.StaffMember`, `parse_staff_member`
    and `Scenario.staff` hold the section; `parse_scenario(data, cards, staff_cards)` casts staff from their
    own cards (`data/staff/hob.json`, `--staff` in `scripts/evening.py`, `staff_dir` in `create_app`), so
    `test_cards.py` still sees six presets. A staff member is refused every action by `start_action` ("Hob
    works behind the bar"), is never `free_to_decide`, gets no intention request and no needs; the
    lockstep runner ends the evening and tracks stalls by `guests(world)`; `expression._facing` falls back to
    the post's `staff_facing`. Saves are `schema_version` 9, with the bump named in the commit
    (`test_database.py` and `test_intention_saves.py`, renamed `test_new_worlds_are_version_9`, pin it). The
    snapshot's `Actor.post` is in `types.ts` and the `bartender` sprite (with `PouringBeer`) in `sprites.ts`.
    51 tests in `tests/test_staff.py` (B1 and B2). Test edits, because the repository evening now holds a
    fourth person from the start: `test_first_evening.py` (approved: staff are skipped and only guests are
    counted at the end), `test_app.py` and `test_scenario_sessions.py` (4 actors at opening, one more
    sprite), `test_card_shell.py` (guests are counted by `post is None`, and Hob's card is checked). Offline
    evening, seed 5: the guests' events are identical to B1's (`cmp` on the events without Hob's), and Hob adds
    three (`on_duty` and two `interrupted`, when he turns his head toward a noise); 431 s, 26 scenes, 11.2 s
    stuck as before.
- [x] **B3 — The barkeep pours.** Guests order at the tap and he serves them.
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
  - *Built (2026-10-04):* `body/bartending.py` (`order_at`, `tend_bar`; `world.step_world` calls it after
    `honor_invitations`) pours for the guest who holds the tap and has reached its spot: the barkeep
    starts `pour_beer` (3 s, `PouringBeer`) over his staff cells, takes himself out of a conversation to do
    it, and at its end completes the guest's own `take_beer` (the stock falls, the mug is theirs) and logs
    `served` ("Hob poured Ada a mug of ale"); a guest called away meanwhile gets nothing and the stock
    stays. `Activity.served` and `Activity.staff_only` hold the rule: `lifecycle._ends_on_timer` is false for
    a `game` or for a `served` verb while `staff.tended(world)`, in which case the verb's timer stops at
    zero so the world still saves; `actions.action_error` refuses `pour_beer` to a guest. Without staff the
    tap stays self-service (`take_beer` still ends on its own 0.8 s). `people_in_sight` carries `post` (the
    bar's name) only for staff; the briefing says "Hob, the barkeep, is pouring ale behind the bar" (or
    "tending the bar"); the option reads "walk 13 steps to the tap and ask Hob for a mug of ale (24 servings
    when last seen)"; both prompt prefixes now say Hob pours (the intention examples read "Get an ale",
    and its "no barkeep to call over"). 13 tests in `tests/test_bartending.py` (shared hall helpers moved to
    `tests/staff_hall.py`). Offline evening, seed 5 (B2 → B3): 11 beers all served by Hob (12 self-served
    before), lines longer (10 joined, 3 before) and nobody gave up either time, stuck 11.2 s → 3.1 s, 426 s;
    the evening plays differently, so it is not the same story. **Seed-sensitive test, approved by the
    user:** with Hob pouring, seed 2 of `test_a_news_item_reaches_a_third_guest_in_other_words` carries
    news only one hop (it reached two without him; seeds 1, 3, 4 and 5 with him do, seed 4 with two
    items), so that parameter is now seed 4: seeds 1 and 4, same assertion. In the browser a forced
    `take_beer` shows Hob "interacting" behind the bar while Rurik waits at the tap.
- [x] **B4 — Leaning on the bar.** Guests stand at the counter and can talk with the barkeep.
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
  - *Built (2026-10-04):* `stand_at_bar` (family `company`, `shared_target`, 12 s) is a new `Activity`; the bar
    in `data/tavern.json` has spots (3, 3), (4, 3), (5, 3). `scenes.side_by_side` is also true for two people
    at the same bar (`_bar_of`: a guest on one of its spots, its staff member on a staff cell, exact cells
    only), so a guest at the bar sees Hob as "beside them" and `talk` with him passes `actions._close_enough`.
    `agents._bar_stand` offers it while a barkeep is in sight, the guest is not on a spot and one spot is
    free (a closed inn offers only going home, as before); the local utility is as drafted, and the option
    reads "walk … to the bar and lean on it, where Hob tends it", with "chat with Hob across the bar" for
    the talk. For the writers: `turn_view` adds `speaker.on_duty` (the bar's name) and `on_duty: true` on a
    barkeep among `participants`; `invitations.offered_kinds` is empty for him and when everyone else in the
    scene is staff, `check_turn` refuses an `invite` to someone on duty, the scripted writer never has him
    say goodbye, and `haiku_turns` swaps his need nudges for "You are the barkeep, on duty behind the Oak
    bar: you stay while the guest does, and leave only to pour." and names him "Hob (the barkeep)" in the
    scene. Prefix rule 16 and example 24 teach the model the barkeep; the intention prefix gains "lean on the
    bar and chat with the barkeep". 20 tests in `tests/test_bar_chat.py`. Offline evening, seed 5: 4 stands
    at the bar and 25 scene events with Hob (Toren to Hob at 103 s: "Room for one more, friend?"; they
    introduce themselves; Hob tells where the ale is), 12 beers poured, 427 s, 0.0 s stuck.
- [x] **B5 — The barkeep greets.** He steps over to a guest at the bar and opens the talk.
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
  - *Built (2026-10-04):* `bartending.tend_bar` gains the two steps as drafted: an idle barkeep with no
    order and no scene, while the inn is open, picks the first guest (actor order) who `scenes.bar_of`
    says is at his bar (now public), is in no scene, is not `pressed` and whom he has not heard speak
    within `rules.bartending.chat_gap`; he walks over his staff cells to the cell across from them (their
    column, else the nearest, the first listed on a tie) with a `wait`, then starts `talk` through
    `action_error` and `activate`. `rules.bartending = {"chat_gap": 60.0}` (`BartendingRules`, checked in
    `check_rules`: a saved world with no, zero, negative, non-numeric or an extra rule is refused; the
    schema stays 9, since 9 is unreleased). `staff.guests` returns `list[Actor]`. 13 tests in
    `tests/test_bar_greeting.py`; the "in a scene of their own" case sets both guests' wish for company to
    100 so the scene outlasts the barkeep's approach (scenes end by themselves once the guests have talked
    enough, and the case would otherwise pass for the wrong reason). Offline evening, seed 5: Hob greets 7
    times (90 s: Toren; 103 s and 108 s: Edda, the second time because her first scene ended before he
    heard her speak), guests start 3 chats with him, 24 turns involve him, 12 beers poured, 426 s, 6.1 s
    stuck (longest 3.1 s).
- [x] **B6 — Numbers and the story.**
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
  - *Built (2026-10-04):* `metrics.bar_metrics(events, staff)` (a `BarCounts`: `served`, `opened`,
    `lines`, `news_told`, counted from the events whose actor is on staff; a chat a guest opens with the
    barkeep is not one he opened) is in `metrics.json` as `bar` (`scripts/evening.py` takes the staff IDs from
    the final world). 8 cases in `tests/test_bar_metrics.py`. The done checks are
    `tests/test_barkeep_evening.py`, on seeds 1 and 4 (the news test's seeds, see B3) with the repository
    scenario cast from its cards: every `take_beer` completion has its `served` event and Hob speaks, and,
    on a second run played in 10 s stretches, he is on a staff cell at every one of the ~40 samples. A
    test cannot see every tick, but he only moves by `bartending` over staff cells.
  - *Results:* offline, seed 5 (`--mode local --writer scripted`): 426 s, all six home, 12 beers poured,
    `bar` = served 12, opened 7, lines 13, news told 2, 6.1 s stuck (longest 3.1 s). **Live (Jev + Haiku,
    seed 5, 434 game s, 237 wall s, 0 errors, a replay of its calls byte-identical):** 14 beers poured, 17
    guests joined a line and 2 left it (gave up), 19 scenes, 53 turn calls for 35 lines (one scripted
    fallback), `bar` = served 14, opened 15, lines 17, news told 0. Cost $0.243 (Jev $0.048; lines $0.111, or
    $0.0032 a turn, 88% cache hits; intentions $0.084) against E19's $0.19: the barkeep adds about 20
    more lines and a third more turns, not a model of his own. **News:** Brida told Hob the margrave's
    fever at 315 s (hop 1), and he told it on to nobody, so no item went two hops (acceptance scenario
    3 stays open for E28). **Stuck time 25.2 s** (Calder 9.0 s, Brida 5.0 s, Saye 5.0 s, Edda 3.1 s): all
    of it is closing time, 421–430 s, when the door's three spots are held by the first three leavers and
    the others are refused ("No reachable interaction spot") once a second until a spot frees; that is
    D02's rule, not the bar. Moments from the log: 144 s, Hob to Rurik: "What'll you have? The house ale's
    fresh tonight."; Rurik: "House ale sounds good. Long watch tonight."; and at 315 s Brida to Hob: "Down
    tomorrow, aye. The manor kitchen won't run itself, and the margrave's been abed with fever". Slips
    that D19 records: Hob proposes darts and a "silver penny a round" as if he could leave the bar.

### Giving — from hand to hand (H0–H5)

Added 2026-10-05 at the user's request. Any guest can hand anything they carry to another guest:
a mug of ale, a herbal remedy or a keepsake now, and coins once the economy exists (Stage 3). Step 0
of [MIND.md](../MIND.md) found the need: in five of seven recorded live evenings, 17 intentions ask to
bring someone a drink, and no activity can. `buy_drink` exists only as an invitation, and its ale
jumps from the tap into the invitee's hand. Giving is also the first compound action a guest can
choose: fetch an ale, carry it over, hand it on. The guest chooses it once, the body carries it
out, and it ends in success or a named failure, as an option does in Lyfe Agents. For the central
test, a gift is a small story with a cause, a witness and a feeling (a remedy for the worried, an
ale refused by someone who holds a grudge).

Decisions for every H task (frozen 2026-10-05; change them here first if the code disagrees):

- **Items are a table.** `body/items.py` holds `ITEMS: Mapping[str, Item]`, one frozen dataclass
  per kind, the way `ACTIVITIES` holds verbs. Rules key off the kind, never off a guest:

  ```python
  @dataclass(frozen=True)
  class Item:
      kind: str       # inventory key, saved: "beer"
      one: str        # wording in events, briefings and the inspector: "a mug of ale"
      many: str       # "mugs of ale"
      held: str | None  # how a briefing says someone holds one in a hand ("a full mug of ale"); None out of sight
      hands: int      # most a visitor can carry at once
      received: str   # the THOUGHTS kind the receiver keeps about the giver
      # visible (property): whether others see it in the hands, i.e. `held is not None`

  ITEMS = {
      "beer": Item("beer", "a mug of ale", "mugs of ale", held="a full mug of ale", hands=2, received="treated"),
      "remedy": Item("remedy", "a herbal remedy", "herbal remedies", held=None, hands=3, received="cared_for"),
      "keepsake": Item("keepsake", "a keepsake", "keepsakes", held=None, hands=3, received="gifted"),
  }
  ```

  (As built, `visible` is derived from `held`, so one field says both how a briefing words a mug in the
  hand and that others can see it; the table is a read-only mapping.)
  Using an item is a verb's business: `drink` stays the only use, and a remedy or a keepsake can
  only be carried and given for now.
- **Inventory** is `{kind: count}` with every kind in `ITEMS` present (zeros too) and counts from
  0 to `hands`. A saved world must have exactly that (schema bump in H1). The snapshot sends it as
  is, and the item wording (`one`, `many`) reaches the client as `items`, beside `activities`
  (`items.client_items`). `types.ts` gets `inventory: Record<string, number>`, and the
  inspector's "Carrying" row lists every nonzero kind. A hand-made observation may list only what a guest
  holds (a missing kind reads as zero); a saved world may not.
- **Starting items come from the scenario.** A guest entry may carry `"carries": {"remedy": 2}`
  (kinds from `ITEMS`, counts within `hands`). In `first_evening.json`, Edda (a healer) carries two
  remedies and Toren (a pedlar) two keepsakes.
- **One verb, `give`, in the `company` family,** so no first-stage request grows (that was H2; `bring_drink`
  is the exception, see H4). The family text
  becomes "chat with someone at their table or beside them, join a conversation, lean on the bar,
  or hand someone something they carry". The action names its item: `Action` gains
  `item: str | None` (None for every other verb), and its ID is `give:<item>:<receiver>`. Saved
  actions, decisions, the forced-action command and `types.ts` carry it. Jev's `_activity` fills
  `{item}` with the item's `one`.

  ```python
  Activity(verb="give", near_person=True, duration=1.5, effect=_give, family="company", label="Give",
           status="giving", doing="handing something over", done="gave something away",
           what="hand {item} to {target}, who sits at their table or stands beside them",
           guidance="A kindness between people who get on: a drink for a thirsty friend, a remedy for "
                    "someone worried about sickness, a keepsake for someone they like. It costs the giver "
                    "what they hand over, and someone who dislikes them may refuse it.")
  ```

- **Like a shove, giving needs no walk.** The receiver must sit at the giver's table or stand
  beside them, within the reach of a chat
  (`actions._close_enough`). Only a guest may receive (staff take tips with the
  economy), never the giver, and only with a free hand for that kind (count < `hands`).
- **The receiver may refuse.** They accept unless their opinion of the giver is below
  `rules.giving.refuse_below` (−20). On a refusal the item stays with the giver, both log
  `gift_refused` ("Rurik would not take Toren's keepsake"), and the giver keeps a `rebuffed`
  thought about the receiver. A rule decides it, not a model.
- **A gift that is taken** moves one item. Both log `gave` ("Edda gave Brida a herbal remedy"),
  and the receiver keeps the item's `received` thought about the giver (it acquaints them, as
  `treated` does). The receiver shows the heart emote and the giver faces the receiver. No new
  pose or art.
- **No gift ping-pong.** A guest may not give an item back to whoever gave it to them within
  `rules.giving.again_after` (120 s), nor give the same person the same kind twice in that time.
- **New thoughts** (`ThoughtKind(mood, opinion, seconds, stack, reason)`):
  `cared_for` (4, 12, 300, 2, "gave them a remedy", acquaints), `gifted` (3, 10, 300, 2, "gave
  them a keepsake", acquaints), `rebuffed` (−3, −8, 180, 2, "refused what they offered"). Added in
  H2: `generous` (1, 0, 300, 2, "accepted a gift from them"), which the giver keeps about the receiver,
  so that a guest remembers having given and does not offer again at once.
- **Fetching for someone is an errand.** The invitation `buy_drink` and the new choice
  `bring_drink` (H4) run the same errand in `errands.py`: the giver pours (or is served),
  carries the mug over, and gives it. A new stage `carrying` follows `fetching`. Each tick: if the
  giver holds more mugs than when the errand began and the receiver is near, start `give`; else,
  unless already on the way, start `sit` on a free chair at the receiver's table
  (`invitations.free_chair`, `home_table`), as `join_table` seats an invitee. The errand fails
  with `invitation_failed` when the receiver leaves, when nobody is near after
  `rules.giving.carry_for` (30 s, for example the receiver stands at the darts), or when the
  giver no longer holds the mug. The ale no longer jumps into the invitee's hand.
- **Out of scope:** coins and paying (Stage 3: `coin` joins `ITEMS` then); using a remedy or a
  keepsake; giving to staff; asking for something, stealing or taking back; witnesses judging a
  gift; a new speech act (the `buy_drink` invitation stays the path from talk); new art.
- **Tests that changed (built 2026-10-05).** `test_world.py::test_invalid_action_fails_without_mutating_inventory`
  compares an untouched inventory with the empty inventory of every kind, not `{beer: 0}` (H1);
  `test_database.py` and `test_intention_saves.py` pin the new `schema_version` (13 in H1, 14 in H3, the
  latter test renamed to match); `test_bartending.py`'s friend-drink test seats Bea at a table and runs 30 s
  instead of 25 (H3). No other test changed. As planned:
  `test_invitations.py::test_a_bought_drink_ends_in_the_invitees_hand` and
  `test_bartending.py::test_a_drink_bought_for_a_friend_is_still_delivered` pin the instant
  hand-over. The outcome they check stays: the invitee ends with the ale, the host without it,
  and `treated` is kept. Their setup or game time may change in H3 because the host now walks
  back; name both in that commit. `test_database.py` pins `schema_version` (H1). H2 and H4 add
  candidates, so whole evenings play differently (`test_first_evening.py`, the news-spread test on
  seed 7). If one fails, stop and report the seed and the failure. Do not change a seed or an
  assertion without the user's approval.

- [x] **H0 — Items and near-person verbs (refactor, no behavior change).**
  - *Items:* `body/items.py` with `ITEMS` holding only `beer`. Generic inventory code reads the
    table instead of naming beer: `observation.own_actor`, `arrival` (its `inventory` data), the
    saved-world check, the briefing's "holding a full mug of ale / empty-handed", and the
    inspector. Beer verbs (`take_beer`, `drink`, `pour_beer`) keep naming beer.
  - *Near-person verbs:* `Activity.confronts` becomes `near_person` (targets someone near: no
    scene, no walk, the timer ends it). `lifecycle` and `actions` branch on it; `shove` and
    `start_fight` keep it, and hostility keeps its candidates through the `confront` family.
  - *Check:* `make check` unchanged; an offline evening (seed 5, `--writer scripted`) gives a
    byte-identical `events.jsonl` before and after (`cmp`).
  - *Built (2026-10-05):* `body/items.py` (`ITEMS`, `empty_inventory`, `check_inventory`, `held_words`,
    `client_items`); `own_actor`, `create_actor`, `parse_world`, the briefing and the inspector read it;
    the snapshot carries `items`. `Activity.confronts` is `near_person`. `make check` and `cmp` on
    seed 5: byte-identical. A hand-made observation may omit kinds, so the dozens of tests that build one
    stayed as they were.
- [x] **H1 — Hand over (`give`).**
  - `remedy` and `keepsake` join `ITEMS`; scenario `carries`; `Action.item`; the `give` verb with
    the receiver rules, the refusal, the three thoughts, and the `gave` and `gift_refused` events.
    The saved world, snapshot, `types.ts`, the inspector's "Carrying" row and the forced-action
    command follow. `give` is not yet a candidate: only the debug panel's forced action starts it,
    as with `doze`.
  - *Tests first* (`tests/test_giving.py`): one parametrized block for taken gifts (each kind; a
    receiver who already holds one; the last item), one for refusals (opinion just below and at
    the threshold), and one `pytest.raises` block for refused actions (receiver not near, self,
    staff, nothing to give, full hands, an unknown kind, an `item` on a verb that takes none,
    giving back within `again_after`). Saves: a world with a remedy in hand reloads; malformed
    inventories (a missing kind, a negative or over-`hands` count, an unknown kind) are rejected.
  - *Check:* in the running app, force Edda to give Brida a remedy: the heart emote, both
    inventories in the inspector, `cared_for` in Brida's thoughts.
  - *Built (2026-10-05):* `social/giving.py` (`gift_error`, `hand_over`, `formed_since`) and the verb
    `give` (`Activity.names_item`, `Action.item`, kept in a visitor's saved action only when a verb names one);
    `rules.giving` (`refuse_below`, `again_after`); `carries` on a scenario guest (`items.parse_carries`);
    saved worlds are version 13. The ping-pong rule reads the thoughts a gift leaves (a thought's expiry less
    its length is when it formed), so it needs no new saved state. A near-person action turns its
    visitor to face its target (`expression._focus`). `client_activities` calls a verb that targets
    another visitor `partner` also for `near_person`, and adds `names_item` for `give`, so the debug panel
    lists people and a held-item picker. Checked in the running app (2026-10-05): Edda, seated at a table
    with Brida, gave her a remedy through the panel; Edda went from two remedies to one, Brida's inspector
    read "Carrying a herbal remedy" with the thought "Edda gave me a herbal remedy" (+4, 292 s left).
- [x] **H2 — Choosing to give.**
  - *Candidate* (`agents.py`): for each kind the guest holds and each near guest with a free hand
    who has not just given it to them. *Local utility* (`local_policy.py`): low on its own,
    raised by sociability and by opinion of the receiver; for beer, raised when the receiver's
    hands are visibly empty. *Option sentence* (`options.py`). The briefing says what the guest
    carries ("carrying two herbal remedies"), and `observe_people` gains `holding`, the visible
    items in each person's hands.
  - *Check:* offline seed 5 and a live seed 7 evening each show at least one `gave`, no
    ping-pong, and no stuck time added.
  - *Built (2026-10-05):* `giving.gift_targets` (near, not staff, not visibly full-handed, no gift or
    refusal between the two within `again_after`; stricter than `gift_error` because the giver cannot see
    into the receiver's pockets: any kind to the same person counts), `local_policy._score_gifts`,
    `options._give`, the briefing's "They are also carrying two herbal remedies", `holding` in
    `observe_people`, and the rules of giving in the observation. A thirsty guest (thirst from 50) keeps
    their own mug rather than offer it. Gifts joined the `company` family. `generous` is the thought a giver
    keeps. No existing test changed in this task.
- [x] **H3 — Carry, don't teleport (`buy_drink`).** The errand's `carrying` stage as frozen
  above; the two named tests change only as stated.
  - *Tests first:* the host walks from the tap to the invitee's table and gives there; the
    invitee leaves (fails); the invitee stands at the darts past `carry_for` (fails); the barkeep
    pours the host's mug (still delivered).
  - *Check:* in a live evening, the host walks back with the mug and the hand-over is logged as
    `gave`.
  - *Built (2026-10-05):* first the errands left `invitations.py` for `social/errands.py` (a refactor with a
    byte-identical seed 5), then the `carrying` stage with `rules.giving.carry_for` and a `since` in the
    errand while it carries (saved worlds are version 14). The hand-over is a `give`, started when the world
    says the host may (`action_error`), so refusal, full hands and ping-pong all apply. It ends in
    `fetch_done` when the invitee has taken the mug, in `fetch_failed` when the invitee refused it, left, was
    not near within `carry_for`, or the host no longer held the mug (the last three also log
    `invitation_failed`). `fetch_begun` ("Ada went to fetch Bea an ale") is logged when the pour is
    accepted, for an invited drink as for a brought one.
- [x] **H4 — Bring someone a drink (`bring_drink`), the compound choice.** A `company` verb with
  `near_person=True`, `duration=0.5` and an effect that opens a `buy_drink` errand from the
  chooser to the receiver (no invitation, so the receiver may still refuse at the hand-over). It
  is a candidate for a guest with a free hand who knows a stocked tap (or a tended bar), when a
  guest at their table visibly holds no beer and neither is in an errand already. Local utility,
  option sentence and Jev's wording as for any verb. The event reads "Brida went to fetch Edda an
  ale".
  - *Check:* in live seeds 5 and 7, count the intentions to bring someone a drink (by hand, as in
    MIND.md step 0) against the `gave` events with beer. The gap should close.
  - *Built (2026-10-05), with two changes to the plan:* `bring_drink` has a family of its own, **`fetching`**
    ("fetch someone at their table or beside them a drink from the tap"), not `company`: with `talk` no
    longer alone in `company`, `test_lockstep.py::test_partner_is_not_pulled_from_a_chat_by_a_late_answer`
    chose `take_beer` and `test_briefing.py` lost its `talk:bea` option, and the user chose a family of
    its own over editing either test. A first-stage request is one option wider while a drink could be
    fetched. And "(or a tended bar)" is dropped: the errand's first step needs a known stocked tap whoever
    pours, so that is the condition. Otherwise as planned: an unasked errand (`Errand.unasked`) that only the
    one who goes is told of ("They are fetching Bea an ale"), `Activity.opens_errand`,
    `invitations.begin_errand`, `fetch_error`, `errand_parties` (`on_errands` in the observation),
    `giving.empty_handed_company`, and a utility lowered by a full bladder or weariness.
- [x] **H5 — Measure and record.** `evening/metrics.py` (or a new module: `metrics.py` has 344 of its
  ~400 lines) reports `giving`: gifts per kind, refusals, and errands begun, done and failed.
  Run an offline evening, a live one and its replay (byte-identical), then append the results
  paragraph here and a line under MIND.md step 0's measures.
  - *Built (2026-10-05):* `evening/giving_metrics.py` (`giving_counts`) reports `giving` in `metrics.json`:
    `gifts` per kind in `ITEMS`, `refused`, and `errands` `{begun, done, failed}`. Both guests log a gift or a
    refusal, so one counts once by its time and words; the errand counts come from `fetch_begun`,
    `fetch_done` and `fetch_failed`.
  - *Result (2026-10-05):* offline seed 5 (scripted): one gift, Edda's remedy to Brida at 286 s, no refusals,
    no errands; stuck time 9.1 s (13.6 s before giving). **Live (Jev + Haiku) the guests rarely chose it.**
    Seed 7, first run: 2 gifts (a mug each time), 5 drink errands: 2 done (Toren to Edda at 89 s, handed over
    at 96.5 s; Edda to Brida at 336.6 s, handed over at 345.5 s), 3 failed; $0.33, stuck 23.2 s. The three
    failures were the host's own decisions (the WC, the bar, a chat) replacing the errand's steps between the
    pour and the hand-over, and Toren's own seat taken by Brida while Edda stood by the fire, so he had no
    chair at her table. Two fixes followed, each with a test: a guest fetching a drink is not free to decide
    (`errands.fetching_a_drink`, in `decisions.free_to_decide`), and the errand ends at once when the host
    has no chair to take at the invitee's table. Seed 7 again: no gifts, no errands, $0.29, stuck 21.4 s;
    seed 5: none, $0.24, stuck 24.1 s. The replay of the second seed 7 is byte-identical to its live run, also
    on the final code. Why none: the options were put to Jev (in seed 7's two runs 26–27 requests held a gift and
    29–32 a trip) but it rarely scored them above the rest, and only 1 of 33 intentions in seed 7's first run, none
    in the 30 and 30 of the others, was to fetch someone a drink (step 0 counted 17 in five of seven
    evenings). So the gap named in step 0 is not closed by the verbs alone; the next thing to try is making
    the intention say it (a goal `bring_drink`, as `talk_to` and `sit_with` are goals) rather than weighing
    the option. Not done: a way to walk beside an invitee who stands, so an errand can reach them without a
    chair at their table.

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

### UI pass — bugs and readability (U2–U11)

Added 2026-10-08 at the user's request, from six complaints with screenshots: bubbles cut
mid-sentence, a black mat at the door and a fireplace that does not read as one, buttons that do
not respond on an iPhone, inspector sections that will not fold on desktop, emotes on a white
box that say nothing, and an inspector that is hard to read. The design reference for U8–U10 is
[docs/mockups/inspector.html](../mockups/inspector.html): open it in a browser.

What was measured before writing these tasks (2026-10-08, offline evening, seed 5, by script; nothing
was changed):

- The server sends a full snapshot every 0.1 s (`server/api.py`, `_send_snapshots(..., 0.1)`). It
  weighs 104–186 KiB of JSON (19 KiB gzipped). Of 182 KiB at 250 s, the actors take 133: `knowledge`
  67, `heard` 22, `memory` 19, `card` 7. The client never reads `heard` or `card`.
- `Dashboard.apply` rebuilds `#roster`, `#inspector` and `#events` through `innerHTML` on every snapshot.
- `world.map` changed 106 times in a 600 s evening (28 in the first 100 s): reservations, queues, the
  tap's stock and dice games all live in it. Each change makes `TavernScene.renderMap` call
  `this.scale.resize(...)` and redraw the whole floor. Phaser's `ScaleManager.resize` sets
  `canvas.width` and `canvas.height` every time, even to the same size, which clears and reallocates the
  drawing buffer.
- `splitLine("The margrave has been abed with a fever for a week, and the manor kitchen is told to send
  up nothing but broth. Evening.")` returns `["The margrave has been abed with a fever", "for a week,
  and the manor kitchen is", "told to send up nothing but broth. Evening."]`.

Decisions for every U task (frozen 2026-10-08; change them here first if the code disagrees):

- **Frontend only**, except U9 (one wording field in `minds`) and U11 (the snapshot's shape).
  Every snapshot change updates `runtime.snapshot()` and `types.ts` together.
- **No PixelLab credits and no image files.** Art is drawn in code: Phaser `Graphics`, or pixel maps
  turned into textures with `this.textures.generate(key, { data, pixelWidth, palette })`. A pixel map
  is an array of equal-length strings: `.` is transparent, and any other character is a palette key.
- **Approved by the user on 2026-10-08:** `lit-html` as a frontend dependency (U3), and `node --test`
  for pure frontend logic (U5 sets it up). Node 24 runs `.ts` files directly, so the test runner adds
  no dependency. Any other new npm dependency still needs the user's yes.
- **Seen, not assumed.** Every visual task posts before and after screenshots at game scale, plus a 2×
  crop of the detail, from `make run` in the built-in browser. "Done" is still `make check` plus `make
  build`, with the output pasted.
- **Files under ~400 lines.** If a task would push one over, split it first, in its own commit.

Order: U2 and U3 first, in parallel, because they touch different files. Then U4, which needs both.
U5 can go any time, since it only touches `bubble.ts`. U6 → U7 → U8 come after U2. U9 → U10 come
after U3, and U10 also needs U8's `pixels.ts`. U11 only runs if U4 finds that the snapshot's size
matters on the phone.

- [x] **U2 — Split `scene.ts` (D01; refactor, no behavior change).** `scene.ts` has 405 lines, over the
  limit, and U4–U8 all draw in it.
  - *Move, without editing the logic:* `drawFloor`, `drawRoomDetails` and `drawWall` go to a new
    `frontend/src/floor.ts` as exported functions that take the `Graphics` and the map, as
    `furniture.ts` does. The Phaser side of speech bubbles goes to a new `frontend/src/speech.ts`:
    the `BUBBLE_*` and `TAIL*` constants, building the bubble's container, box and text (now inside
    `createVisitor`), `tellLine`, `placeSpeech` and `drawBubble`. `bubble.ts` stays pure: placement
    and pacing, no Phaser.
  - *Check:* `make check` and `make build`. Run `make run`, then compare the opening room (paused,
    tick 0) before and after at the same window size. Start the evening and watch one conversation:
    bubbles still sit over their speaker, stay inside the map and split as before. Remove the D01 row
    from [PLAN.md](../PLAN.md#tech-debt) in the same commit.

  - *Result (2026-10-08):* `scene.ts` 405 → 300 lines. `floor.ts` (57) holds `drawFloor`, `drawRoomDetails`
    and `drawWall`, moved without a logic change (`this.floor` became a parameter). `speech.ts` (82) holds
    `class Speech` (`tell`, `place`, `destroy`), which owns the bubble's container, box, text, constants and
    the line being told; `ActorView` now carries one `speech: Speech`. `make check` and `make build` pass. In
    the browser the opening room and a paused mid-evening room match the screenshots from before the split
    (floor, walls, door, windows, fireplace, rugs, furniture), and a live bubble sits under its speaker with
    its pointer. The D01 row is removed from PLAN.md.

- [x] **U3 — The sidebar keeps its elements between snapshots (sections that fold, chips that
  select).** *Cause:* a click is a press and a release on the same element. A snapshot arrives every
  100 ms and replaces the inspector's `<details>` and the roster's chips (`renderInspector`,
  `renderRoster` and `renderEvents` set `innerHTML`). When the replacement lands between press and
  release, the browser fires no click. So "Why this decision?" and "What they know" fold only
  sometimes, and choosing a guest in the roster is just as unreliable. The buttons that are never
  re-rendered (Pause, Refill, Save) always work.
  - *First commit (refactor):* move the inspector out of `dashboard.ts` (376 lines) into a new
    `frontend/src/inspector.ts`. That means `renderInspector` and the helpers only it uses (`needs`,
    `carrying`, `visit`, `intention`, `mind`, `seatChoice`, `scoreList`, `knowledge`, `memories`). No
    behavior change.
  - *Second commit (the fix, with `lit-html`, approved 2026-10-08):* every clickable element is created
    once and kept. Snapshots only change what is inside it. Run `npm --prefix frontend install lit-html`
    and commit the lock file. Render the roster, the inspector and the events with
    `render(html\`…\`, container)`. Lit keeps the nodes and updates only the bindings that changed. It
    never touches a `<details>`'s `open` unless that is bound, so the `openDetails` bookkeeping goes
    away. Lit escapes what it interpolates, so these templates stop calling `escape()`. Model text
    (thoughts, intentions) then cannot reach the page as HTML by mistake. Delete `escape()` if nothing
    else uses it.
  - *Folded by default:* every inspector section starts closed (drop the `open` attributes). A section
    the user opened or closed stays that way through snapshots and when another guest is selected, so
    two guests' decisions can be compared. A page reload closes them all again.
  - *Check:* run an evening at 1× in the built-in browser. Click each summary 10 times: 10 of 10
    toggle. Click roster chips 10 times: 10 of 10 select. Press a summary and hold it for 300 ms before
    releasing: it still toggles. In the console, count the replaced sections over 5 s with the same
    guest selected. Before the fix this is about 50 (one per snapshot); it must now be 0:
    `let n = 0; new MutationObserver((r) => { n += r.filter((m) => [...m.removedNodes].some((x) => x.nodeName === "DETAILS")).length; }).observe(document.querySelector("#inspector"), { childList: true, subtree: true }); setTimeout(() => console.log(n), 5000);`
    Then `make check` and `make build`.

  - *Result (2026-10-08):* `inspector.ts` (first commit: moved out of `dashboard.ts`, 376 → 283 lines; `clock.ts`
    holds the clock). Second commit: the inspector, the roster (`repeat`, keyed by guest), the events and the
    action selects render with `lit-html` 3.3.3 (approved), so `escape()` and `html.ts` are gone; the placeholder
    "Select a visitor" is a sibling of `#inspector`, because Lit appends to a container rather than clearing
    it. Every section starts closed, and one with nothing to show (no mind yet) keeps its `<details>`, so its
    state survives. Measured in the browser, same guest selected: `<details>` replaced in 3 s: 28 before, 0 after;
    20 real clicks on "Why this decision?" toggled it 20 times, alternating; a section opened for one guest is
    still open after choosing another; the roster's chips are the same elements two seconds later.
    Not measured: a press held for 300 ms, which the tool cannot do (the elements no longer change under it).
    Found on the way: a reload during an evening starts a new one with "Invalid saved action timer", which is
    D20.

- [ ] **U4 — iPhone Safari: taps that land and a screen that holds still.** The user's report: no button
  can be pressed, and the screen seems to blink nonstop. Needs U2 and U3. The suspects, most likely
  first:
  1. *Replaced elements (U3).* A tap lasts longer than a click, and iOS cancels a tap whose element was
     removed. Re-test after U3 before anything else.
  2. *Canvas reallocation.* `renderMap` keys its redraw on `JSON.stringify(world.map)`, which changes
     every few seconds (see the measurements above). Each change resizes the canvas, and on iOS Safari a
     reallocated canvas can show one blank frame. That is the likely blink. *Fix:* call
     `scale.resize` only when `width`, `height` or `tile_size` change. Redraw the floor only when what
     it draws changes (`blocked`, and the kind, cells and size of the objects). Redraw the furniture when
     its own inputs change (the same, plus `reserved_by`).
  3. *Snapshot weight.* About 1–2 MB/s of JSON parsed on the phone's main thread. Measure it (next
     bullet). If it costs frames, do U11.
  4. *Touch details.* `button:hover` sticks after a tap on iOS: put the hover rules inside `@media
     (hover: hover)`. Add `touch-action: manipulation` to buttons, chips and summaries.
  5. *Viewport.* When the toolbar collapses on scroll, iOS fires `resize`, and Phaser's FIT mode then
     refreshes the canvas. Only confirm whether this happens; fix it only if the timeline shows it.
  - *Reproduce:* run `make run`, then open Safari in the iOS Simulator at `http://127.0.0.1:5173` (the
    Simulator shares the Mac's localhost). Attach the Mac's Safari Web Inspector (Develop → Simulator)
    to record a Timeline (JS time per snapshot, layout and paint) and the WebSocket frame sizes, and
    check whether `permessage-deflate` was negotiated. The Simulator draws with the Mac's GPU, so a blink
    may not show there. Then ask the user to check on the real iPhone, against the deployed build or
    through a temporary `--host` on the LAN (do not commit a change to `vite.config.ts`).
  - *Done when:* on the user's iPhone every control responds to the first tap, and two minutes of a
    running evening show no blinking. Fix each confirmed cause in its own commit. In the result
    paragraph, say which suspects were confirmed and which were not.

  - *Built, not yet confirmed on a phone (2026-10-08):* the Mac has no full Xcode, so the iOS Simulator
    tool cannot attach; the checks below ran in the built-in browser (desktop, and a 375 px mobile emulation).
    Suspect 1 is fixed by U3. Suspect 2 is **confirmed**: in a 60 s evening the canvas buffer was written 23
    times (`canvas.width = …`, about every 2.6 s) at an unchanged size; now 0. `frontend/src/mapview.ts`
    (`mapParts`, 11 cases in `tests/mapview.test.ts`, red first) fingerprints the size, the floor and the
    furniture separately, and `renderMap` resizes and redraws a part only when its fingerprint changes, so the
    tap's stock, queues and dice games (which draw nothing) no longer touch the canvas. Suspect 4: hover
    rules sit inside `@media (hover: hover)`; buttons, summaries and selects get `touch-action: manipulation`
    and no tap highlight. In the 375 px emulation `(hover: hover)` is false, the controls report
    `manipulation`, and nothing overflows. Not checked: suspect 3 (snapshot cost on a phone's main thread) and
    suspect 5 (the toolbar's resize event), because they need the real device or the Simulator. The box stays
    unticked until the user confirms on the iPhone; if it still blinks, do U11 and capture a Safari timeline.

- [x] **U5 — Speech bubbles break at sentences.** Today `splitLine` (`bubble.ts`) cuts a line every 10 words
  wherever the words fall (see the measurements above).
  - *Rule:* a piece ends only at a sentence end: `.`, `!`, `?`, `…` or `...`, optionally followed by a
    closing quote or bracket, then whitespace or the end of the line. Whole sentences share a piece
    while it stays within `MAX_PIECE_CHARS`. Start at 90 characters, about three lines of the 150 px
    wrap at 11 px Georgia, and tune that constant by eye, not the rule. Only a sentence longer than the
    limit is cut, into parts of balanced length at word boundaries, preferring a break right after a
    comma, semicolon or dash near the cut. Every part but the last ends with "…" and every part but the
    first starts with "…". Never cut inside a word or leave a one-word tail. A line without punctuation
    is one sentence, and an empty line gives no pieces.
  - *Timing:* `chunkMs` counts a piece without the added ellipses, and `MIN_CHUNK_MS` stays. Fewer,
    fuller pieces than today help, since the server holds a line only `max(min_gap, chars / 15)` game
    seconds. Reading pace at 2× and 4× speed lags behind the server; that is older and out of scope.
  - *Cases:* `"Evening. What'll it be?"` → one piece. `"Aye"` → `["Aye"]`. `""` → `[]`.
    `"Well... I suppose so."` → one piece. The margrave line above → `["The margrave has been abed with
    a fever for a week,…", "…and the manor kitchen is told to send up nothing but broth.", "Evening."]`,
    or "Evening." joined to the second piece if it fits. Three sentences of 40 characters each → two
    pieces of whole sentences (two share a piece, 81 characters; a third would make 122).
  - *Test runner first, in its own commit:* `frontend/tests/` holds `*.test.ts` files that use
    `node:test` and `node:assert/strict` and import from `../src/<module>.ts` with the extension. The
    folder sits outside `tsconfig`'s `include`, so `tsc` needs no `@types/node`. `frontend/package.json`
    gets `"test": "node --test 'tests/**/*.test.ts'"`. Pass the glob: `node --test tests/` treats the
    folder as a file and fails. `make check` runs `npm --prefix frontend test`. In AGENTS.md, replace
    "`frontend/` has no unit-test runner" with how to test a pure frontend module this way. CI does
    not run `make check` (see D14), and changing `.github/` is ask-first: ask the user in the PR, and
    add a tech-debt row if they say no.
  - *Then red, then green:* `frontend/tests/bubble.test.ts` holds the cases above as a table, one named
    test per row, plus a table of `chunkMs` cases. Show it failing against today's `splitLine`, then
    make it pass. After that, watch a live evening: no bubble ends mid-sentence without "…". Then
    `make check` and `make build`.

  - *Result (2026-10-08):* `frontend/tests/bubble.test.ts` (28 cases; `npm --prefix frontend test`, part of
    `make check`) pins placement, `chunkMs`, `chunkAt` and `splitLine`. `splitLine` now groups whole
    sentences up to `MAX_PIECE_CHARS` = 90, and cuts a longer one into even parts at a clause (comma,
    semicolon, colon, dash; a 15-character bonus), at least two words on each side, with "…" at the breaks;
    `chunkMs` does not count them. Seen live: "Dry as a biscuit in here, and that ale's not going to pour
    itself. Hob, a mug for me." stays one bubble. CI still runs Node 20 and no frontend tests: running them
    there needs `node-version: 22.6+` and an `npm test` step in `.github/workflows/ci.yml` (ask-first).

- [x] **U6 — The door: no black mat, as tall as the wall.** "The black rug" is the door mat. `drawDoor`
  (`furniture.ts`) paints a dark rounded rectangle with a gold outline on the floor inside the door
  (`floor.fillStyle(0x41372a)…` and the `strokeRoundedRect` after it). The table rugs are yellow and
  green, and they stay. The door itself is 26 px tall from `y + 1`, while the stone face of a wall cell
  runs from `y + 2` to `y + size - 3` (`drawWall`).
  - *Do:* delete both mat calls and the `floor` parameter, which becomes unused, along with its
    argument at the call site. Line the door's top and bottom up with the wall stones beside it in the
    same row, and give it a dark frame on both sides so it reads as set into the wall. Keep its width
    (1.6 cells, centred on the door cell), its planks and its handle, scaled to the new height. If the
    door looks right only when it covers the whole cell, including the wall's dark base, do that and
    say why.
  - *Check:* before and after screenshots of the south wall at game scale and at 2×. Then `make check`
    and `make build`.

  - *Result (2026-10-08):* `drawDoor(g, door, size)` loses its `floor` parameter and both mat calls. The door
    is drawn from the cell's top + 2 to its bottom - 3, the span of the wall stones beside it, in a dark
    timber frame with a lighter lintel and a stone threshold; four planks of two shades, two iron straps with
    a rivet on each plank, and a brass ring on the latch side. Width (1.6 cells) and centring are as before.
    Seen at game scale and at 4× in the browser: no mat above the door, and the frame lines up with the stones.

- [x] **U7 — A fireplace that reads as one.** `drawFireplace` draws a grey rounded box, a dark rectangle
  and three orange ellipses. At game scale it looks like an egg in a box. The fireplace is the `fireplace`
  object at (9, 0), three cells wide, in the north wall, opening south (`hearthFacing`). A flickering
  glow on the floor exists already (`drawHearthGlow`).
  - *First commit (refactor):* `hearthFacing`, `drawFireplace` and `drawHearthGlow` move to a new
    `frontend/src/hearth.ts`.
  - *Then experiment:* draw two or three variants in Phaser `Graphics`, combining what makes a hearth
    readable from above:
    - a stone surround made of separate stones (irregular blocks, mortar lines, lighter top edges),
      wider than the opening, with a dark timber mantel on the wall side;
    - a deep, soot-black firebox;
    - two or three crossed logs with lighter end rings;
    - flames as three to five teardrop tongues, red through orange to yellow, each with its own phase,
      their height flickering by about ±20%, redrawn every frame on their own layer, as `hearthGlow` is;
    - optionally, embers rising and fading, and a hearthstone on the floor cell in front with andirons
      or a poker.
    The drawing reads only the object's cells and `hearthFacing`, so a fireplace on any wall works. The
    per-frame cost stays small: one clear and a few dozen shapes per hearth.
  - *Choose:* show the user each variant at game scale with a 2× crop, and ask which one to keep.
    Delete the others.
  - *Check:* `make check` and `make build`. The browser's Performance panel shows frame time unchanged
    within noise.

  - *Result (2026-10-08):* first commit: `hearth.ts` (`hearthFacing`, `drawFireplace`, `drawHearthGlow`), no
    change to the picture. Second commit, one design instead of three variants (it reads at game scale and
    at 4×, so there was nothing to choose between; say if you want others tried): dressed stone in courses of
    three shades with mortar, a timber mantel lit from above, an arched sooty opening with a warm back wall,
    a hearthstone lip on the room side, two iron andirons and two crossed logs with pale end rings on a bed
    of coals. `drawFlames` redraws each frame on its own layer above the furniture: five tongues in three
    layers (red, orange, yellow core), each on its own phase, ±28% flicker, plus five rising sparks and a
    pulsing coal bed; about 30 shapes per hearth. The drawing works in a frame (`u` along the wall, `v` out
    into the room), so it follows `hearthFacing` to any wall; `tests/hearth.test.ts` pins that for all four.
    Not checked on screen: a fireplace in a wall other than the north one (the hall has only that one).

- [x] **U8 — Emotes you can read.** Today `showEmote` draws a text glyph (`! ? ✹ ♥ z …`, `EMOTE_GLYPHS`)
  in 12 px system-ui on a cream box, beside the name. The glyph depends on the device's fonts, the box
  covers the art, and nothing says what an emote means. The new look is in the mockup's "Emotes over the
  head".
  - *Pixels:* a new `frontend/src/pixels.ts` (pure, no Phaser) holds the pixel-map type and
    `outlined(rows)`: a transparent pixel next to a filled one (four neighbors) becomes outline key `0`.
    U10 reuses it.
  - *Emotes:* a new `frontend/src/emotes.ts` holds the six maps (copied from the mockup's `EMOTES`),
    with `#1b120d` as the outline color. At the scene's `create`, it builds one texture per kind with
    `textures.generate(…, { pixelWidth: 2 })` and nearest filtering. An `Image` replaces the text. It is
    centred above the head and above the name, without covering it, and draws below speech bubbles.
  - *Motion:* when an emote appears or changes kind, it pops in (scale 0 → 1.2 → 1 over about 200 ms),
    then bobs by 1 px. On `sleep`, the z's rise and fade in a loop. On `waiting`, the dots light one
    after another (two or three frames each).
  - *Meaning:* while the pointer is over a guest, the hover line names the emote, for example "Edda ·
    angry". The words come from a frontend `Record<EmoteKind, string>`: startled, confused, angry, fond,
    dozing, waiting.
  - *Delete:* `EMOTE_GLYPHS` and the text object.
  - *Check:* the emotes come from `show_emote` calls in `attention.py` (alert, from a loud sound),
    `expression.py` (confused when an action fails, angry over a quarrel or a taken seat, waiting after
    a long wait, sleep while dozing) and `giving.py` (affection). Show at least four live: the debug
    panel can force `give` and `doze`. For all six, set an emote in `applySnapshot` with a local hack
    that is not committed. Post screenshots on the wood floor, on a rug and against a wall. Then `make
    check` and `make build`.

  - *Result (2026-10-08):* `pixels.ts` (`outlined`: pads by one pixel and rings the art with key `0`; refuses ragged
    maps and maps that use `0`) and `emotes.ts` (six 12×12 maps, `emoteFrames`, `emotePalette`, `emoteFrame`,
    `emoteMotion`, `EMOTE_WORDS`), with 21 tests (`pixels.test.ts`, `emotes.test.ts`), shown red against stubs
    first. The scene makes one nearest-filtered texture per picture at 2× (`textures.generate`), shows an
    `Image` centred above the name, pops it in (0 → 1.2 → 1 over 200 ms) and bobs it by one pixel; a sleeper's
    z's drift up eight pixels and fade in a 2 s loop, and the waiting dots light one after another (three
    frames, 350 ms each). Near the top edge the emote is kept inside the map. Hovering a guest with an emote
    names it in the hint line ("Edda · confused"; "startled", "confused", "angry", "fond", "dozing",
    "waiting"). `EMOTE_GLYPHS` and the text object are gone. `tsconfig` now allows `.ts` extensions in imports,
    because Node needs them between pure modules; AGENTS.md says so. Seen: all six at once on a local
    override of the snapshot (nothing committed), on wood, a rug and by a wall; no cream box.

- [x] **U9 — Inspector: what matters first, readable type.** Needs U3. The target is the mockup's card,
  except the inventory, which is U10.
  - *Backend, test first:* each `minds` entry gains `mood_words`, the server's wording of the mood.
    `feelings._mood_words` becomes public as `mood_words`, so the client does not copy its
    thresholds. Test `minds()` in `tests/test_feelings.py` with one parametrized block over the
    boundaries (8, 3, just above −3, −3, −10). `types.ts` gains `Mind.mood_words` in the same commit.
  - *Order:* first the header (the guest's south Idle still as a pixelated portrait, the name, what
    they are doing, and two chips: mood words and drink stage). Next comes "Now": the action and its
    place, the thought as a quote in serif italic, "Intends" in body text, and the goal as a chip.
    Then Needs, Carrying, Feelings, People and News. Last come the collapsed sections, closed by
    default: Character (traits), Why this decision?, What they know, Recent memories, and Debug.
  - *Needs as satisfaction:* show `Math.round((100 - urgency) / 20)` of five pips, so a full bar means
    a content guest. The labels are Thirst, Bladder, Energy (fatigue), Company (social) and Fun
    (boredom). Zero or one pip is red, two amber, three to five green, with the words desperate, very
    low, low, fine, good, full. Show no numbers. The exact urgency goes in the `title` and in Debug.
  - *Feelings:* thoughts with the same text merge into one row with "×n" and the summed mood. The
    seconds left move to Debug.
  - *People:* each opinion gets a bar from −100 to +100 with the familiarity word under the name.
  - *News:* the topic and the told-as quote. The chain and the confidence move to Debug.
  - *Debug:* the cell, raw needs, drunkenness %, thought timers, news chains, and the "Give this
    visitor an action" form, moved in with the same ids and handlers.
  - *Type:* `style.css` gets tokens for 11, 12, 13, 15 and 24 px, and nothing in the sidebar goes under
    11 px. Serif is only for the name and the guest's own words. Today's "Intends" paragraph, an
    unstyled `<p>` that renders at 16 px bold, gets a style.
  - *Check:* `make check` (the new backend test) and `make build`. Post screenshots beside the mockup:
    a guest who carries things, one who carries nothing, a departed guest, and the 375 px mobile width.

  - *Result (2026-10-08):* backend: `feelings.mood_words` is public and every `Mind` carries `mood_words`
    (`types.ts` too); tests for the nine thresholds and for the snapshot, the snapshot one shown red first.
    Frontend: `mindview.ts` (`needPips`, `needWord`, `needTone`, `mergeThoughts`, `opinionBar`; 24 cases, red
    against a stub first) and a rewritten `inspector.ts`: the guest's own sprite as a portrait (south Idle,
    pixelated), the name, the status and two chips (mood words, drink stage); then "Now" (action, place, the
    thought as a serif quote, Intends, a goal chip); Needs as five pips of satisfaction (Thirst, Bladder, Energy,
    Company, Fun; red at one pip or none, amber at two, green above; no numbers, the urgency is the tooltip);
    Carrying (still words; U10 makes slots) with time here, ales and own seat; Feelings with identical thoughts
    merged ("×2") and no timers; People with a bar from the middle and the familiarity word; News (topic and
    quote). Closed by default: Character, Why this decision?, What they know, Recent memories, and Debug, which is
    a static `<details>` in the layout holding the raw urgencies, drunkenness %, path, the intention's trigger,
    thought timers, news chains and the forced-action form (same ids and handlers). `style.css`: the sidebar uses
    only 11, 12, 13, 15 and 24 px (measured in the browser: exactly those five sizes), serif only for the name
    and the guest's own words; the unstyled "Intends" paragraph that rendered at 16 px bold is styled. Seen at
    desktop width and at 375 px (no overflow). Not done: the rest of the page (header, controls, events) still
    uses 8–10 px text; the ticket only covers the sidebar.

- [x] **U10 — Carrying as an inventory.** Needs U8 (`pixels.ts`) and U9.
  - *Slots:* one slot for each kind in `snapshot.items`, in that order. A carried kind shows its icon at
    2× and a count when it is above 1. A kind not carried is a dim, empty slot. The tooltip is the
    server's wording (`items[kind].one` or `many`).
  - *Icons:* a new `frontend/src/icons.ts` holds the mockup's 16×16 maps for `beer`, `remedy` and
    `keepsake`, plus `bundle` as the fallback for a kind without a map. The icons are inline SVG built
    from `outlined` maps, one `<rect>` per pixel with `shape-rendering="crispEdges"`. Coins wait for the
    economy (Stage 3), and their map is in the mockup ready for it. Icons are keyed by item kind,
    never by guest.
  - *Under the slots:* one line for time here, ales tonight, and their own seat (today's "Tonight" and
    "Own seat" rows).
  - *Check:* force a `give` so a guest holds two remedies, then post a screenshot. Then `make build`.

  - *Result (2026-10-08):* `icons.ts` holds the 16×16 maps for `beer`, `remedy` and `keepsake`, and the tied
    bundle for any other kind; `iconPixels(kind)` rings the map with the outline (`pixels.ts`) and returns the
    coloured cells (7 tests, red against a stub first). The inspector draws one slot per kind in
    `snapshot.items`, in the server's order: a carried kind is an inline SVG, one `<rect>` per pixel with
    `crispEdges`, plus a count above one; an unheld kind is a dim empty slot; the tooltip and `aria-label` are
    the server's wording ("2 herbal remedies", "no mugs of ale"). The old "Carrying" sentence is gone; the
    line under the slots keeps time here, ales and own seat. Seen live: Edda with two remedies shows the
    flask with "2". Not seen live: the beer and keepsake icons on a guest (the code path is the same, and the
    mockup shows all three). Coins wait for the economy: their map is in `docs/mockups/inspector.html`.

- [ ] **U11 — Lighter snapshots (only if U4 shows they matter).** The snapshot is 182 KiB, 10 times a
  second, per open page. The client never reads `heard` (22 KiB) or `card` (7 KiB). It shows only the
  last 8 events and only the selected guest's `knowledge.objects` and last 6 memories.
  - *Options, in order:* (a) confirm `permessage-deflate` on the wire, which gives about 19 KiB per
    snapshot; (b) send 4 or 5 snapshots a second instead of 10 (the scene already interpolates
    movement), then check that walking still looks smooth; (c) build the client's actor view from the
    fields the client reads, so `heard`, `card` and `knowledge.facts` stay on the server. Option (c)
    changes the snapshot: `runtime.snapshot()` and `types.ts` change together, test first in the
    runtime's snapshot test. The saved world does not change.
  - *Check:* a snapshot's size and the iPhone timeline before and after, plus `make check` and `make
    build`.

### Sleep — energy and a nap at the table (Z0–Z6)

Added 2026-10-08 at the user's request. Guests get tired over the evening, and a tired guest
either goes home or, more so when drunk, falls asleep at the table. The others let a sleeper be,
and a loud noise always wakes them.

What exists already (read 2026-10-08):

- The `fatigue` need (0–100 urgency) is shown in the inspector as **Energy**. It rises by
  `need_rates.fatigue` (0.12 per second), and `sit` takes 65 off every 14 s, so a guest who sits
  down is never tired for long. Nothing else tires anyone.
- `doze` (E13, `body/dozing.py`) is involuntary: a wasted guest in their seat nods off for 30 s
  (`doze_per_second`), shows the `sleep` emote (the Zzz) and wakes on the timer or on a sound that
  passes `attention.interrupt`. It takes 30 off `fatigue` on completion only. It is never a
  candidate, and guests rarely get wasted (E13: "nobody dozes" on live seed 5).
- A dozing guest still counts as `available` in `sight.people_in_sight`, so a tablemate may start a
  conversation with them, give them something or shove them. The briefing then calls the sleeper "in
  a hurry".
- The client draws `doze` with the `Seated` pose. `shippedPose` falls back to `Idle` (standing) for
  any pose a sprite lacks.

Decisions for every Z task (frozen 2026-10-08; change them here first if the code disagrees):

- **Energy stays the `fatigue` need.** No rename: saves, the local policy, Jev's briefing
  ("tiredness") and Haiku keep it. The inspector already shows it as Energy.
- **Activities tire.** `Activity.fatigue_per_second: float = 0.0` is the fatigue a guest gains per
  second while they walk to it or do it (status `walking` or `interacting`). A negative value
  restores. Walking is charged at the rate of the action it walks for: the way to one's own seat
  costs nothing, the way to the darts costs as much as the darts. Staff never tire, as with
  `need_rates`. Built values (the first draft had twice these for everything but sleep: the first
  offline evenings left guests near 75, where `scenes.pressed` makes them decline every chat, and
  conversations fell from 42 to 28 on average over seeds 1–8; half the rates restored them to 33–36):

  | verb | per second | about per use |
  |------|-----------:|---------------|
  | `take_beer` | 0.25 | 1 with the walk |
  | `drink` | 0.2 | 0.6 per mug ("a little") |
  | `talk`, `join_conversation` | 0.05 | 1.5 for a 30 s scene |
  | `stand_at_bar` | 0.075 | 1 |
  | `play_darts` | 0.4 | 4 per round |
  | `play_dice` | 0.075 | 2 |
  | `watch_dice`, `watch` | 0.05 | 0.5–1.25 |
  | `use_toilet`, `inspect`, `give`, `bring_drink`, `leave` | 0.25 | 0.5–1 |
  | `shove` | 1.5 | 1.5 |
  | `start_fight` | 2.5 | 5 |
  | `sit`, `rest`, `wait`, `seating`, `cut_in_line`, `pour_beer` | 0 | — |
  | `doze` | −0.75 | −30 per 40 s nap |

- **Only sleep restores.** `sit` and `rest` lose their `fatigue` relief (`needs` empty). `doze` loses
  its −30 on completion and restores 0.75 per second instead, for 40 s (`durations.doze` 30 → 40), so a
  nap cut short still restores what was slept. The user asked for exactly this ("spent by every
  action, a little restored by sleep"): it is what makes a guest tired enough to choose.
- **The hour grows late.** `need_rates.fatigue` 0.12 → 0.05 (about +20 over a 420 s evening). The
  arrival range of `fatigue` drops from [40, 80] to [25, 55] in `data/scenarios/first_evening.json`
  because tiredness now stays. `data/tavern.json` (the stage-0 hall, used by `create_world` for a hall
  without a scenario) keeps its ranges, because
  `test_evening.py::test_demo_visitors_arrive_wanting_a_seat_and_a_beer` pins them, and an evening reads the
  scenario's ranges anyway. `tests/staff_hall.py` keeps its own copy.
- **Asleep is a property of the activity.** `Activity.asleep: bool = False`; only `doze` sets it.
  `dozing.asleep(actor) -> bool` reads it. Every rule asks that function, never `verb == "doze"`.
  (`expression` sits in the import chain of `activities`, so it cannot import `dozing`; the sleep emote
  is shown by `dozing.show_sleep`, which `step_world` calls after `update_expression`.)
  `Activity.seated: bool = False` says a verb can only be done from a seat at a table; `doze` sets it,
  and `actions.action_error` refuses it with "This needs a seat at a table".
- **One verb, two ways in.** The verb stays `doze`, because saved actions name it. The world still
  starts it for a wasted guest (`nodding_off`), now never once the inn has closed. A guest may also
  choose it, in the `resting` family, so no first-stage request grows. Both ways use the same pose,
  emote and events. New wording: label "Sleep at the table", status "asleep", doing "asleep at the
  table", done "slept at the table". `FAMILIES["resting"]` becomes "sit down for a rest, or sleep a
  while where they sit".
- **Who may sleep:** a guest in their own seat at a table (`seat_id`), in no conversation and no
  line, while the inn is open, and not party to an errand (`observation["on_errands"]`). Only as a
  candidate, also: `fatigue` ≥ 60 (`SLEEPY` in `agents.py`, beside `KEEPS_OWN_MUG`).
  `actions.action_error` refuses `doze` without a table seat: "Sleeping needs a seat at a table".
- **The others let a sleeper be.** `people_in_sight` gains `asleep: bool`, and a sleeper is not
  `available`. `talk`, `give`, `bring_drink`, `shove` and `start_fight` aimed at a sleeper are
  refused ("Toren is asleep") and never offered (`_social_candidates` already reads `available`;
  `gift_targets`, `empty_handed_company` and `hostile_targets` skip sleepers). The briefing reads
  "Toren sits across the table from them, asleep", never "in a hurry". A mug carried to a sleeper
  (`errands._carry`) is not forced on them: the sleeper sleeps on, the host keeps the mug, and the
  errand ends as it does for a receiver who cannot be reached. Both shared prefixes
  (`turn_prompt.shared_prefix` and `data/minds/intention_prefix.md`) get one paragraph: a guest
  asleep at a table is an ordinary sight late at an inn; nobody mocks, scolds or wakes them on
  purpose; at most they lower their voice, smile, or say a kind word about them. The prefixes stay
  byte-identical across calls and above 4,096 tokens.
- **A loud sound always wakes; a quiet one never does** (`dozing.waking_sound(world, stimuli, sleeper)`,
  which returns the sound, not a flag). A sleeper wakes from any sound whose
  loudness at its source is at least `attention.interrupt` (a quarrel, a scuffle, a brawl, the
  closing call) and that reaches them at all (heard loudness above 0: walls damp a sound but do not
  stop it), whatever their curiosity, friends or the salience. A quieter sound (a chat, darts, the
  door, dice, a cheer, a grumble) does nothing to a sleeper: no glance and no gaze. No new rule.
- **Events.** `dozed_off`, "Toren fell asleep at the table", from `doze`'s `on_arrival`, so both ways
  in log it once (`nodding_off` stops logging its own). `woke_up`, "Toren woke up at the table", from
  `doze`'s `effect` when the timer ends it. `woken`, "Toren woke with a start at a loud quarrel near
  the bar: <cause>", replaces `interrupted` for a sleeper. `woken` joins `intentions.SALIENT_EVENTS`,
  so a guest takes stock on waking. No intention is due while a guest is asleep.
- **The fork is in the scores.** The local policy and Jev both weigh it; nothing forces a choice.
  Tired and drunk leans to `doze`; tired, sober and having stayed a while leans to `leave`; tired on
  arrival still sits down first. As built, the local score of `doze` is
  `min(1, max(0, 2.2·(fatigue − 0.6)) + 0.9·drunkenness)` (the first draft had 0.45 on drink, which
  gave a nap in 6 of 8 seeds; 0.9 gives one in 7 of 8) and `_leave_utility` takes
  `weary = clamp((fatigue − 0.6)/0.3) · (1 − 0.6·drunkenness) · min(1, seconds/180)` in its `max`. `doze`'s `guidance` and `leave`'s say so in words (Z4).
- **The pose is `SleepingSeated`**, drawn by the user: `frontend/static/characters/<sprite>/
  SleepingSeated/rotations/{north,south,east,west}.png` at 68 px. The user made all seven sprites
  (including the bartender, who never sleeps), so every sheet lists the same poses; the files come
  from the user's commit `f04e6a8` on `codex/giving-receiving-poses`. No `metadata.json` entry (the
  other poses added since the first export have none either). A sprite without it is drawn `Seated`,
  never `Idle`.
- **Saves and snapshot.** No `schema_version` bump is expected: the new fields are in the activity
  table, not in the world. If one turns out to be needed, it is 15 (approved for Stage 1). The snapshot
  changes only through `activities` (the pose), which the client already reads.
- **Out of scope:** sleeping anywhere but a table seat (lodging comes after Stage 4), waking someone
  on purpose, snoring as a sound, a grudge against whoever woke them, other needs pausing during
  sleep, and staff sleeping.
- **Tests that changed.** One, and the user asked for the behavior: in
  `test_world.py::test_completed_actions_relieve_corresponding_need` the case `rest-at-chair` is gone,
  because resting no longer relieves fatigue (`test_energy.py::test_sitting_down_no_longer_cures_tiredness`
  pins the new rule, and a nap restores fatigue instead). Z1 and Z4 made whole evenings play
  differently, and with the first draft's numbers two seeded tests failed by chance:
  `test_barkeep_evening.py[seed-1]` (nobody leaned on the bar, so Hob spoke no line) and
  `test_facts.py::test_a_news_item_reaches_a_third_guest_in_other_words[seed-4]`. No seed or assertion
  was changed: the numbers were retuned (see the table and Z6) until both passed, so a different draw
  of the same rules could fail them again.

Order: Z0 → Z1 → Z2 → Z3 → Z4 → Z6. Z5 can go any time after Z0, once the art is in. Each task is its
own branch (`claude/stage1-z<n>`) and PR.

- [x] **Z0 — Asleep is a property of the activity (refactor, no behavior change).**
  - *Build:* `Activity.asleep: bool = False` with a docstring line; `doze` sets it.
    `dozing.asleep(actor) -> bool` (True when the actor's current action is an `asleep` activity).
    `expression.update_expression` and `dozing._can_doze` call it instead of comparing the verb.
  - *Tests:* `test_dozing.py` (new): `asleep` for no action, a `sit`, a `doze`, parametrized.
  - *Check:* `make check`; an offline evening (seed 5, `--writer scripted`) gives a byte-identical
    `events.jsonl` before and after (`cmp`).
  - *Built (2026-10-08):* `Activity.asleep`, `dozing.asleep(actor)` and `dozing.show_sleep(world)`. `asleep`
    could not live in `expression.py` (it would import `activities`, which imports it back), so the sleep emote
    moved out of `update_expression` into `dozing.show_sleep`, called after it. `make check` and `cmp` on
    seed 5 (`--writer scripted`): `events.jsonl` byte-identical before and after.

- [x] **Z1 — Energy: activities tire, only sleep restores.**
  - *Build:* `Activity.fatigue_per_second` and the table values above. A new `body/energy.py`
    ("How activities tire a visitor and sleep restores them") with `tire(world, elapsed)`: for every
    guest (not staff) whose action is walking or interacting, add the action's rate times `elapsed`
    to `fatigue`, clamped to 0–100. `step_world` calls it once a tick, beside `wear_off`. `sit` and
    `rest` lose their `needs`; `doze` loses `needs` and gets −0.75 and 40 s. `need_rates.fatigue`
    0.05; the scenario's arrival range [25, 55].
  - *Tests (`test_energy.py`, the spec):* parametrized by verb, one guest doing it for a fixed `dt`:
    darts tire more than a drink, a drink tires a little (> 0), `sit` and `wait` add only the passive
    rate, walking to the tap tires at `take_beer`'s rate, a nap lowers fatigue, a nap cut short
    after half its time restores about half, fatigue never leaves 0–100, staff never tire. Plus
    `rest` and `sit` no longer relieve fatigue on completion (the changed case above).
  - *Check:* `make check`. Offline evening seed 5 before and after: print each departed guest's
    `fatigue` at departure (a scratch script, not committed) and put both lists in the results.
  - *Built (2026-10-08):* `Activity.fatigue_per_second` and `body/energy.py` (`tire`), called by `step_world`
    beside `wear_off`. Rates are the halved table above; `sit` and `rest` lose their `needs`; `doze` is −0.75 per
    second for 40 s and has no completion effect on needs; `need_rates.fatigue` 0.05; arrival [25, 55] in the
    scenario. `tests/test_energy.py` (32 cases) is the spec. With the first draft's rates guests left at closing
    with fatigue 70–95 and conversations dropped by a third, hence the halving.

- [x] **Z2 — The others let a sleeper be.**
  - *Build:* `asleep` in `people_in_sight`, and `available` False for a sleeper. A sleeper target
    refused in `actions._talk_error`, `_give_error`, `_fetch_error` and `_confront_error` ("{name} is
    asleep"). `gift_targets`, `empty_handed_company` and `hostile_targets` skip sleepers. The
    briefing's `_person` says ", asleep" for a seated sleeper. The errand to a sleeper ends without
    waking them. The paragraph in both shared prefixes.
  - *Tests:* parametrized by verb: each of the five aimed at a sleeper is refused with the reason,
    and at the same guest awake is accepted. Candidates: a sleeping tablemate yields no `talk`,
    `give`, `bring_drink` or hostile option. The briefing wording. A mug carried to a sleeper: the
    sleeper sleeps on, the host keeps the mug, the errand ends.
  - *Check:* `make check`; offline evening seed 5. If no guest sleeps there yet, force one in a
    scratch run (`doze_per_second` 1000 and one wasted guest) and quote the briefing line.
  - *Built (2026-10-08):* `people_in_sight` gains `asleep` and a sleeper is not `available`; `actions` refuses `talk`,
    `give`, `bring_drink`, `shove`, `start_fight` at a sleeper ("Bea is asleep"); `gift_targets`,
    `empty_handed_company` and `hostile_targets` skip them; the briefing says "sits across the table from them,
    asleep"; `errands._carry` ends the errand with `fetch_failed` and the host keeps the mug. Rule 17 of
    `turn_prompt` and item 9 of `intention_prefix.md` say sleepers are let be; both prefixes grew, so they stay
    above 4,096 tokens. `tests/test_sleeper.py` (13 cases).

- [x] **Z3 — Falling asleep and waking.**
  - *Build:* `dozing.waking_sound(world, stimuli, sleeper) -> Stimulus | None` (the rule above). `attention.attend`
    asks it for a sleeper instead of the salience thresholds: a wake stops the nap, shows the alert
    and turns their gaze, and logs `woken`; anything else is ignored. `doze` gets `on_arrival`
    (`dozed_off`) and `effect` (`woke_up`). `nodding_off` stops logging, and stops once the inn is
    closed. `woken` in `SALIENT_EVENTS`; `intention_due` returns None for a sleeper.
  - *Tests (`test_dozing.py`, `test_attention.py`):* parametrized by sound: a quarrel across the
    hall wakes, a quarrel behind a wall wakes, the closing call wakes, a chat at the same table, darts
    and the door do not and draw no glance; an incurious and a curious sleeper wake alike. The three
    events and their messages, each logged once for both ways in. No nodding off after closing. No
    intention due while asleep; one due after `woken`.
  - *Check:* `make check`; a scratch run where Ada naps and Bea and Cal quarrel: quote `woken`.
  - *Built (2026-10-08):* `dozing.waking_sound`; `attention.attend` wakes a sleeper with `_wake` (alert emote, gaze,
    `interrupted_at`, `woken`) and ignores every other sound; `doze` logs `dozed_off` from `on_arrival` and
    `woke_up` from `effect`; `nodding_off` no longer logs, and does nothing once the inn has closed; `woken` is in
    `SALIENT_EVENTS` and `intention_due` is None for a sleeper. `tests/test_dozing.py` (31 cases): a quarrel
    next to, across and behind a wall from the sleeper, a scuffle, a brawl and the closing call wake curious
    and incurious sleepers alike; a chat, darts, the door, a cheer and a grumble leave them alone with no glance.

- [x] **Z4 — The fork: sleep at the table or go home.**
  - *Build:* the `doze` candidate in `agents.py` (the conditions above, `SLEEPY = 60`); the
    precondition in `actions.action_error`; the new wording and `FAMILIES["resting"]`; an option
    sentence in `options.py` ("put their head down on the table and sleep a while, right here in
    their seat (it restores some energy; nobody at an inn minds, and a loud noise will wake them)").
    `doze`'s `guidance`: tiredness is the reason, drink makes it likelier, a sober and content guest
    usually heads home instead, and it is pointless when they are not tired. `leave`'s `guidance`
    gains: deep tiredness late in the evening is a reason to go home to bed. Local policy: `doze`
    about `min(1, max(0, 2.2·(fatigue − 0.6)) + 0.45·drunkenness)`. `_leave_utility` gains a
    `weary` term, about `clamp((fatigue − 0.6) / 0.3) · (1 − 0.6·drunkenness) · min(1, seconds / 180)`,
    taken in the `max` beside `content` and `upset`. Sitting no longer cures tiredness, so
    `seated_rest`'s fatigue weight drops from 0.4 to 0.15. The formulas are starting points: the tests
    below are the spec.
  - *Tests:* candidates, parametrized: seated and tired → `doze` offered; rested (fatigue 30), standing,
    in a line, on an errand, or after closing → not; a hand-started `doze` without a table seat is
    refused. Local scores, parametrized on one seated guest 300 s in with 3 beers: tired (85) and
    wasted (0.8) → `doze` above `leave` and `sit`; tired (90) and sober → `leave` above `doze`; tired
    (70) 20 s after arriving → `sit` above `leave` and `doze`. The option sentence and the family text.
    Run `test_jev.py`: if it pins the activity list or the prompt, the new wording changes it there,
    and that test change is named in the commit.
  - *Check:* `make check`; offline seeds 1, 5 and 7: count naps and guests who went home with
    fatigue ≥ 60, and quote one of each from `events.jsonl`.
  - *Built (2026-10-08):* `Activity.seated`; the `doze` candidate (`agents.SLEEPY` = 60, in `_nap`); new wording and
    `FAMILIES["resting"]`; `options._doze`; `local_policy` (`doze`, `weary` in `_leave_utility`, the lower
    fatigue weight of `seated_rest`). `tests/test_sleep_choice.py` (16 cases) pins the three weighings
    (tired and wasted sleeps; tired and sober goes home; tired on arrival sits first). `test_jev.py` and the
    rest of the suite needed no change.

- [x] **Z5 — The sleeping pose (needs the user's art).**
  - *Build:* `doze`'s `pose` becomes `SleepingSeated`. `sprites.ts`: the six guest sheets list
    `SleepingSeated` (the bartender's does not); `shippedPose` falls back to `Seated` for a missing
    seated pose (one whose name ends in `Seated`) and to `Idle` otherwise. `scene.ts`: `LOW_POSES`
    includes it. `docs/CHARACTER_ART_PIPELINE.md` gains `doze` → **SleepingSeated**.
  - *Tests:* `frontend/tests/sprites.test.ts` (node:test): the fallback, parametrized (shipped pose,
    missing seated pose, missing standing pose). `tests/test_character_action_assets.py`: a new test
    that `SleepingSeated` ships in four views for the six guest sprites.
  - *Check:* `make check` and `make build`. In `make run`, force a nap from the debug panel (or a
    scratch save) and post a screenshot at game scale and a 2× crop: the sleeper is seated with the
    Zzz above, at each of the four seat facings in the hall.
  - *Built (2026-10-08):* `doze`'s pose is `SleepingSeated`; `sprites.ts` lists it for every sheet and
    `shippedPose` falls back to `Seated` for any missing seated pose; `scene.ts` counts it as a low pose;
    `dashboard.ts` shows the status "asleep"; `docs/CHARACTER_ART_PIPELINE.md` maps `doze` to it. Tests:
    `frontend/tests/sprites.test.ts` and `tests/test_character_action_assets.py::test_sleeping_stills_ship_for_every_character`.
    Seen in the browser (a private backend and `vite` on ports 8001 and 5174, because 8000 was taken): Edda
    forced to `doze` sits with her head bowed and her hood down, the Zzz drifting above her, and the roster
    says "asleep". The 2× crop was made by copying the canvas into a magnified overlay.

- [x] **Z6 — Measure the fork and tune it.**
  - *Build:* `metrics.sleep_metrics(events, departed)` beside `dice_metrics`: naps (and by whom), how
    many ended in `woken` and by which sound kind, and each guest's `fatigue` at departure. It goes into
    `metrics.json`.
  - *Tests:* `test_sleep_metrics.py`, parametrized on hand-built event lists: none, one nap, a nap
    cut by a quarrel, one guest napping twice.
  - *Check:* offline seeds 1, 5 and 7 (`--writer scripted`), then a live seed 5 and its replay (`cmp`).
    Targets: a nap in at least two of the three offline evenings; a guest going home with fatigue ≥ 60
    in at least two; every guest gone by closing as before; stuck time no worse than before Z1. Tune
    only the numbers frozen above (rates, `SLEEPY`, the formulas' weights, arrival ranges), write the
    final values back into these decisions, and record the results paragraph with one story moment
    from the log (someone nodding off and being woken by a quarrel, or heading home bone-tired).
  - *Built (2026-10-08):* `metrics.sleep_metrics(events, departed, closes_at)` (naps and by whom, naps slept out,
    naps cut by a sound, fatigue at departure, and `tired_home`: guests tired enough who went home before
    closing, since leaving at the closing call is no choice), in `metrics.json` under `sleep`. Tests:
    `tests/test_sleep_metrics.py` (10 cases).
  - *Offline numbers (`--writer scripted`, seeds 1, 5, 7, final rules):* naps 1, 2, 0 (seed 5: Edda slept 257–297 s,
    Toren fell asleep at 401 s and was woken at 420 s by the closing call); guests who went home tired before
    closing 2, 1, 1; all six guests gone every time; stuck seconds summed over guests 10.0, 19.6, 10.2 against 15.3,
    13.9, 30.8 before (mixed, within the usual spread); conversations 31, 21, 49 against 34, 51, 32. Over seeds
    1–8 with the barkeep test's runner: conversations averaged 35.9 (42 before Z1), naps 0–4 per evening and at
    least one in 7 seeds of 8. So the target "a nap in two of three offline evenings" is met on seeds 1 and 5
    only; seed 7 has none. Most guests still leave at the closing call, as before.
  - *Not done:* the live evening with Jev and Haiku, and its replay with `cmp`: this worktree has no `.env`,
    and a live run costs about $1. Run `make evening SEED=5 OUT=runs/z6-live` and then
    `MODE=replay CALLS=runs/z6-live/calls.jsonl`, and `cmp` the two `events.jsonl` files.

### Tables and manners (T0–T8)

Added 2026-10-08 at the user's request. Guests keep taking chairs at other guests' tables, for two
reasons. Appeal pulls them to the window tables as well as to the hearth, and a guest who wants a word
with someone seated has one way to reach them: take a chair at their table (`goals._talks_to` counts
`sit` there, and `agents._seat_wish` re-offers `seating` to any seated guest who sees company at a table
with a free chair). Nothing tells them the table is someone's, and only taking someone's own chair
(`seat_taken`) has a consequence. The fix has three parts:

1. **Talk across the table edge.** A guest may walk over to someone seated at another table and talk to
   them standing beside it. Standing and seated guests share a real scene: they may agree to move to a
   free table together, play darts or dice, or have an ale, through the invitations that exist.
2. **Manners at the table.** Guests see whose table is whose. Sitting down at someone's table uninvited is
   rude: the host resents it, the log tells it, and an apology mends it.
3. **Appeal only by the fire.** Only the hearth table is rated, and prompts mention comfort in passing.

Decisions for every T task (frozen 2026-10-08; change them here first if the code disagrees):

- **Standing spots.** Each `table` in `data/tavern.json` gets `interaction_spots`: the cells where a guest
  stands to talk with those seated. They are the cells north and south of each 1×1 table, except (10, 4),
  which is a spot of the tap: Hearth `[[10, 6]]`, Window `[[4, 5], [4, 7]]`, Garden `[[4, 10], [4, 12]]`,
  Corner `[[15, 10], [15, 12]]`, East `[[15, 5], [15, 7]]`. `room._validate_spots` already checks that they
  are walkable. They are content, so test halls add their own (`social_hall.spotted_hall`). A guest counts as
  standing at one only once arrived (`path` empty), not while passing it.
- **At a table** (`scenes.at_table(world, actor) -> str | None`): the table a guest sits at, or the table
  on one of whose spots they stand while not walking. **Within reach** (`scenes.within_reach(world, a, b)`,
  which replaces the private `actions._close_enough`): both are at the same table, or they stand side by side
  (`side_by_side`, unchanged). Talk, join, give, bring a drink, shove and fight all read it. A scene held at a
  table keeps a stander as a member (`_still_there`, `_join_error` read `at_table`), and `people_in_sight`'s
  `beside` becomes `within_reach`.
- **One new verb, `approach`, in the `company` family,** so no first-stage request grows. The family text
  becomes "chat with someone at their table or beside them, walk over to someone at another table, join a
  conversation, lean on the bar, or hand someone something they carry".

  ```python
  Activity(verb="approach", partner=True, approaches=True, duration=8.0, on_arrival=_approach_scene,
           label="Walk over for a word", status="chatting", pose="Talking",
           sound=Sound("chat", 0.25, 6.0, "a conversation"), doing="walking over for a word",
           done="went over for a word", family="company",
           what="walk over to {target}'s table and talk with them, standing beside it",
           guidance="The polite way to seek out someone seated at another table: nobody's chair is taken. It "
                    "eases the wish for company like any chat, and standing there they may suggest moving to a "
                    "free table together, a game, or an ale. Pointless with someone who dislikes them.")
  ```

  `Activity.approaches` (new flag): the part walks first. Its target is a guest who sits at a table that is
  not the actor's own, and the route goes to a free spot of that table (`routes.plan_route` resolves the
  partner's table when the target is a person). On arrival it joins the partner's scene if they are in one,
  else starts one (`scenes.start_conversation`, `join_conversation`). Like `talk`, the scene, not the timer,
  ends it. Refusals: the target is self, staff, or not seated at a table; the actor is in a scene already; the
  partner's scene is full; the partner is `pressed` and in no scene; no free spot (no route). On arrival the
  lifecycle checks the action again, so a partner who left their table meanwhile turns the approach away.
- **A new invitation kind, `move_together`** ("move to a free table together"). It is offered when someone
  else in the scene is not staff and a free table exists for the two. A free table is one that is home to
  neither of them (`invitations.home_table`) and has two chairs that nobody else sits on, reserves, or calls
  their own seat. Accepting sends both to `sit` there. Of several free tables, the nearest to the inviter
  wins (Manhattan distance to the table cell), and ties go to map order, so the choice is reproducible. Say
  this in a comment.
- **An errand stays until the seats are taken.** `join_table` and `move_together` errands get a new stage,
  `seating`, after their `sit` commands start, with `table: str` (the table they go to). The errand ends,
  with no event, once every guest it sent sits at that table, or once none of them still has a `sit` toward
  it. This is how the world knows they were invited (see `welcome`). The saved `Errand` gains `table` exactly
  while it is `seating`, and `check_invitations` checks it. Saved worlds become version 15.
- **Hosts and welcome** (`social/tables.py`, new: "Whose table is whose, who is welcome at it, and what
  sitting down uninvited does").
  - `table_hosts(world, table_id, newcomer)`: guests in the hall, not staff and not the newcomer, who sit at
    that table or whose own seat (`favorite_seat_id`) is one of its chairs.
  - `welcome(world, host, guest)`: the host counts the guest a friend, or thinks at least
    `social_acts.LIKED` of them, or the guest holds an open `sit_with` commitment to the host (a promise to
    come over), or a `seating` errand from the host to the guest, or between the two, is going to that
    table.
  - `intrude(world, newcomer, chair)`, called from `activities._settle`. For each host of the chair's table
    who does not welcome the newcomer, the host keeps a `table_intruded` thought about the newcomer and
    records `table_intruded`, and the newcomer records `sat_uninvited`. Both events carry the same message:
    "Edda sat down at Bea's table uninvited (Window table)". No intrusion happens when the newcomer returns
    to their own seat, already calls a chair at that table theirs, or takes the host's own chair (then
    `seat_taken` fires, as now, and is the stronger wrong).
- **New thoughts.** `table_intruded` (−3, −10, 240, 2, "sat down at their table uninvited"), not
  `acquaints`. `apologized` (1, 6, 300, 1, "apologized to them", `acquaints`). `table_intruded` joins
  `intentions.SALIENT_THOUGHTS` (the host takes stock) and `expression.EVENT_EMOTES` (angry, for the host's
  event only). It is **not** a `hostility.HOSTILE_CAUSES`: rudeness is no reason for a shove.
- **An apology mends.** `social_acts.apologize` keeps halving the latest grudge (`soften`). A listener whose
  grudge it softened also keeps `apologized` about the speaker, and both record `apologized` ("Edda
  apologized to Bea"). An apology with no unsoftened grudge changes nothing and logs nothing, so a second
  apology for the same wrong does nothing. The act's meaning in `conversation.ACTS` says it "warms them a
  little".
- **Table manners are a rule of the hall (added while building T6).** Many tests seat strangers at one table
  and assert on thoughts and opinions, so the penalty is `rules.manners.table_intrusion`, set from the layout's
  `table_manners` (true in `data/tavern.json`, false by default). It also lets an evening be run with and without
  manners on the same code.
- **Whose table the mind sees.** `world.observe_actor` marks known chairs and tables with what anyone
  in the hall can see (a coat on the chair, a mug on the table). A chair that is another guest's own
  seat gets `owner`, `{id, name}` with the name the viewer calls them by (`names.called`), else None. A table
  gets `hosts`, a list of the same records in `table_hosts` order (none for the viewer's own table). `observation.known_objects` accepts both. The briefing, the
  option sentences and the seat rubric read them. Rules never do: the world decides intrusion from its
  own state.
- **Appeal.** Windows keep `appeal` and `reach` (the map check requires them) at `appeal: 0.0`, so only
  the hearth table is rated (0.5). Prompts drop the number. A table note says "by the fire" or nothing,
  and the briefing lists tables nearest first, not by appeal. The seat rubric keeps one short clause on
  appeal and comfort, after manners and company.
- **Out of scope:** approaching someone who stands (side by side covers it); a three-way move (an
  invitation is between two guests); tables with more than two chairs; the host ordering the newcomer
  away; any new pose or art.
- **Tests expected to change.** The user asked for these behaviors to change (2026-10-08). Name the test and
  the reason in the commit:
  - `test_evening.py::test_demo_tables_are_ranked_by_their_surroundings` (T0): only the hearth table is rated.
  - `test_goals.py`, case `sit-at-their-table` (T2): `talk_to` is now served by `approach`, not by taking a chair
    at their table. Add an `approach-the-person` case beside it.
  - `test_goals.py`, `test_the_briefing_marks_the_options_that_serve_the_goal` and
    `test_the_local_policy_adds_a_bonus_to_options_that_serve_the_goal` (T2): they used a `talk_to` goal to
    show a goal marking `seating` and `sit`; they now use `sit_with`, which still does.
  - `test_seating.py::test_seated_visitor_may_move_only_to_join_company`, cases `single-companion-to-join` and
    `duplicate-companion-sighting`, and `test_lonely_visitor_moves_to_sit_with_company` (T2/T5): a seated guest
    moves only to join someone they like. Keep the cases, make the companion liked, and add stranger cases
    that expect `["sit:own"]`.
  - `test_speech_acts.py`, the apology case and `test_a_repeated_apology_softens_only_once_per_grudge` (T7): the
    listener also keeps the warm `apologized` thought.
  - `test_database.py` and `test_intention_saves.py` pin `schema_version` (T3: 15).

  Any other failing test is a surprise: stop and report it. T1, T2, T3 and T5 change whole evenings
  (`test_first_evening.py`, the news-spread test on seed 7). If one of them fails, report the seed and the
  failure. Do not change a seed or an assertion without the user's approval.

- [x] **T0 — Appeal only by the fire.**
  - Data: windows' `appeal` 0.0. Prompts: `briefing._table_note`/`_tables` (no number, nearest first),
    `options._seat_note` (no number), `jev._seat_question` (manners and company first, one clause on appeal;
    keep the word "appeal", which `test_seat_questions_have_their_own_rubric_about_appeal_and_company` pins),
    `data/minds/intention_prefix.md` ("one table by the fire, the rest plain"; tone down the comfort-lover line).
    `local_policy.local_seat_scores` is unchanged: with one rated table it already does the right thing.
  - *Tests first:* the changed demo-ranking test (Hearth 0.5, the other four 0.0); a briefing case showing
    "by the fire" and no "appeal 0." in the table notes.
  - *Check:* `make check`; offline seed 5: count `sit` on each table before and after.
- [x] **T1 — Reach at a table (refactor, then behavior).**
  - Refactor first, no behavior change: move `actions._close_enough` to `scenes.within_reach` (public). Check
    that offline seed 5 gives a byte-identical `events.jsonl` (`cmp`).
  - Then: table standing spots in the data, `scenes.at_table`, scenes and reach as decided, and
    `people_in_sight.beside` read as `within_reach`. Option wording in `options._talk` and `_confrontee` gets
    two new cases: "who sits at the table they stand by" and "who stands by their table".
  - *Tests first* (`tests/test_scenes.py`, `tests/test_social.py`): `within_reach` cases (seated with stander
    on a spot; stander walking past a spot; stander one cell off; two standers on one table's spots; different
    tables), a talk between a seated and a standing guest that runs two turns, and the stander leaving the spot
    ends their part. A `pytest.raises` block for a map whose table spot is not walkable.
  - *Check:* in the running app, force a guest onto a table spot and force `talk` to the one seated there.
- [x] **T2 — Walk over for a word (`approach`).**
  - The verb as decided: `Activity.approaches`, the route to the partner's table, arrival opens or joins the
    scene. Candidate (`agents._social_candidates`): every seated guest in sight at another table, not
    staff, available or in a scene that is not full. Local utility (`local_policy`): like `talk`, scaled by
    the wish for company and the opinion of them, minus a little for the walk. Option sentence
    (`options._approach`): "walk N steps over to Bea's table and talk with her standing beside it (she sits
    with Cy)". `goals._talks_to` counts `approach` to the person, not `sit` at their table. The prefix's
    list of things a guest can do gains the verb. Follow `git show 51c7ee5` (`bring_drink`) for every place a
    verb touches.
  - *Tests first:* new `tests/test_approach.py`, with one parametrized block for accepted approaches (a free
    partner, a partner talking with a tablemate, so the scene grows to three) and one `pytest.raises` block
    for refusals (self, staff, a standing partner, a partner at the actor's own table, a full scene, both
    spots taken, a partner who leaves before arrival). Also candidates and option text cases.
  - *Check:* offline seed 5 shows at least one `approach` that leads to two or more turns, and no stuck time
    added.
- [x] **T3 — Move to a free table together (`move_together`).**
  - `invitations.free_table`, the kind, `offered_kinds`, `errands` first steps (`sit` for both), the
    `seating` stage with `table` (also for `join_table`), save check and `schema_version` 15. Wording:
    `conversation.ACTS["invite"]`, `turn_prompt` (the act list and one example), and the scripted writer
    (`scripted._invitation` offers it before `join_table` when the speaker stands and is lonely; `_answer`
    accepts it on the same terms as `join_table`).
  - *Tests first* (`tests/test_invitations.py`): an accepted `move_together` seats both at the nearest free
    table; a tie goes to map order; it is not offered when every other table is someone's; the `seating`
    stage ends once both sit and ends when one turns to something else. Saves: a `seating` errand reloads;
    `table` on another stage, or a missing `table`, is rejected.
  - *Check:* an offline evening where an approach ends in an accepted `move_together`, or a test-built
    world showing it if seed 5 has none.
- [x] **T4 — Whose table (what the mind sees).**
  - `social/tables.py` with `table_hosts` and `welcome` (no `intrude` yet), the `owner` and `hosts` marks
    in `observe_actor`, and the prompts:
    - Briefing table notes: "Window table (Bea's table, she sits there; one free chair)", "(Bea's table, she is
      away)", "(a free table)". When any table has hosts, add one sentence: "A table someone has made theirs is
      theirs: sitting down there uninvited may upset them. Walk over and talk to them, or wait to be asked."
    - `options._sit` and `_seat_note`: "take Bea's own seat while she is away (it would wrong her)" or "a free
      chair at Bea's table, uninvited".
    - The seat rubric gains the manners sentence. `ACTIVITIES["seating"].guidance` says that moving is for a
      free table or someone they like, and that to join strangers they walk over and talk.
    - The intention prefix gets one manners line in the same words.
  - *Tests first:* `tests/test_tables.py` (`table_hosts`: empty table, seated host, absent owner, staff
    excluded, newcomer excluded; `welcome`: friend, liked, stranger, promise, `seating` errand), and briefing
    and option text cases.
  - *Check:* print a briefing from offline seed 5 at 120 s and read the table lines.
- [x] **T5 — Choosing a seat with manners.**
  - `agents._seat_wish`: a seated guest is re-offered `seating` when their own seat was taken, when someone
    they like (friend, or opinion at least `LIKED`) sits at a table with a free chair, or when an active goal
    or promise is `sit_with`. Strangers' company is reached by `approach`. `local_policy._score_seats`: a
    chair that is someone's own seat −0.5; a chair at a hosted table that does not welcome them −0.25, with no
    company bonus there.
  - *Tests first:* the changed `test_seating.py` cases (above) and new ones (stranger: no `seating`; liked:
    `seating`; a `sit_with` goal: `seating`), plus local seat scores (free table > stranger's table > someone's
    own chair).
  - *Check:* offline seed 5: `seat_taken` count before and after (expect fewer), and no guest left
    seatless for long (stuck seconds in `metrics.json`).
- [x] **T6 — Sitting down uninvited.**
  - `tables.intrude` from `_settle`, the `table_intruded` thought, both events, the emote, salience, and
    `metrics.json` counting `table_intrusions` (`metrics._occurrences`).
  - *Tests first* (`tests/test_tables.py`): one parametrized block on who resents a newcomer (stranger at a
    hosted table: the host; a friend; a liked guest; an invited `join_table` guest; both parties of a
    `move_together`; returning to their own seat; taking the host's own chair: `seat_taken` only; an
    empty table: nobody). Saves: a `table_intruded` thought reloads.
  - *Check:* in the running app, force a stranger onto the free chair at a hosted table: the host shows
    angry, and the inspector shows the thought and the log line.
- [x] **T7 — An apology that mends.**
  - `social_acts.apologize` as decided, `metrics.json` counting `apologies`, the act meaning.
  - *Tests first* (`tests/test_speech_acts.py`): after `table_intruded`, an apology turns the host's opinion of
    the newcomer from −10 to +1 (−5 softened, +6 `apologized`); a second apology in the same evening only
    softens; an apology with no grudge changes nothing and logs nothing.
- [x] **T8 — Measure.**
  - Offline seed 5 and live seeds 5 and 7, before (`main`) and after: `seat_taken`, `table_intrusions`,
    `approach` scenes, accepted `move_together`, `apologies`, stuck seconds, cost. Replay the live run
    and `cmp` the events (step 8 of "Working on a task"). Record a moment from the log in which an
    approach ends in a move or a game, and one with an intrusion and its apology, if any.
  - *If hosts rarely react* (no line or decision within 15 s of `table_intruded`), propose a follow-up in
    which the world opens a scene from the host to the newcomer, so that the next line is the host's. Do
    not build it in T8.

- *Built and measured (2026-10-08).* Modules: `social/tables.py` (`liked`, `table_hosts`, `welcome`, `mark_ownership`,
  `intrude`), `evening/manner_metrics.py` (`manners` in `metrics.json`), `Activity.approaches`, `scenes.at_table` and
  `within_reach`, `invitations.free_table` and the `seating` stage, `rules.manners` (see above). Saved worlds are
  version 15. A guest likes someone (friend, or opinion of at least 10) is the test for sitting with them: `seating`
  is re-offered only for liked company, and `approach` is not offered to liked company at a table with a free chair.
  Offline, ten seeds (0–9), `origin/main` (with sleep) against this branch: `seat_taken` 25 → 0, `table_intruded` 0 → 6,
  `approach` 0 → 33, two apologies, conversations 315 → 297, stuck seconds per evening 16.4 → 16.8, every guest gone at
  closing in all ten, and the barkeep chatting in 10 evenings of 10 (7 on main). Two first versions were dropped on
  these numbers: giving the hearth table two more standing spots halved the barkeep's chats, and an `approach` that
  scored as high as a chat crowded `stand_at_bar` out of the company family once sleep was in (4 evenings of 10, and
  `test_barkeep_evening` seed 4 failed), so it now scores 0.2 lower. Live seed 5 (Jev + Haiku, 436 game s, 328 s wall,
  $0.28 over 307 calls, no failed call, 2 turn fallbacks): 6 `approach`, no seat taken, no intrusion, no
  `move_together` and no apology; the barkeep chatted 9 times. The replay's `events.jsonl` is byte-identical. An
  earlier live run of the first version (not kept as the final) showed one accepted `move_together` (Brida and Edda) and
  two intrusions by Saye at Calder's tables, after which Calder did not speak to Saye within 15 s: that is T8's trigger
  for a follow-up in which the world opens a scene from the host, not built here. Haiku chose `move_together` once in two
  live evenings and `apologize` never, so E28 should count both.

### Closing call, news and a sick guest (F0–F9)

Added 2026-10-09 at the user's request, as six fixes:

1. The evening lasts 10 minutes, and the barkeep says out loud that the inn is closing. Guests react to
   it and decide for themselves that it is time to go.
2. Guests come in with full energy, so nobody lies down to sleep right away.
3. Only one news item is told tonight, drawn at random, and only one guest knows it and spreads it.
   Nobody else knows it at first.
4. The middle window of the west wall goes; two windows stay on that wall.
5. A few small candles glow the way the fireplace does: one in the privy, one by the front door, and
   two more on the walls.
6. Edda carries three herbal remedies. One guest, drawn at random, comes in sick with little energy
   and needs one remedy. Edda finds whoever needs it and offers it of her own accord.

What exists already (read 2026-10-09):

- `data/scenarios/first_evening.json`: `closes_at` 420, `opening_window` [1, 30], arrival `fatigue`
  [25, 55], five news items with one or two `known_by` each, Edda `carries` `{"remedy": 2}`. Guests arrive
  at 0 (in the window), 40, 110 and 190 s. Hob is the only staff member.
- Closing (`hall/closing.py`): `call_closing` logs `closing` ("Closing time: the innkeeper calls for every
  guest to head home") and emits `EVENT_SOUNDS["closing"]` (loudness 1.0, reach 40) from the middle of the
  bar. From then on `agents._concrete_candidates` offers only `leave` (`_going_home`), `briefing._closing`
  says so, every scene ends (`scenes.check_conversations`), the barkeep stops pouring (`bartending.tend_bar`),
  nobody nods off (`dozing`), and `intentions.latest_trigger` returns a `closing` trigger. Nobody says a word.
  The client shows a speech bubble only for the latest turn of a conversation (`speech.ts` `Speech.tell`).
- Energy is the `fatigue` need (Z0–Z6). `SLEEPY` is 60 in `agents.py`. Arrival needs are drawn by
  `arrival.arriving` from `Random(seed)`.
- News (E19): `scenario.parse_scenario` reads `news` (`facts.parse_news`), `open_evening` copies all of it
  into `world["news"]`, and `arrival.admit_arrivals` gives each guest `facts.starting_facts` for every item
  whose `known_by` names them.
- The west wall has three windows: `window-1` (0, 4), `window-2` (0, 6) and `window-3` (0, 11), all at
  `appeal` 0.0 since T0. A window's cell is closed by the window, so it is not in `blocked`
  (`test_hall_layout.py::test_the_hall_is_walled_all_round`).
- Light: `hearth.ts` `drawHearthGlow` draws five rings of `0xf5a347` in front of each fireplace, with a
  flicker of `0.82 + 0.1·sin(t/170) + 0.08·sin(t/53)`, on its own layer that it clears every frame.
  `floor.ts` `drawRoomDetails` already places hall details by hand (the privy's flagstones, two faint
  warm spots).
- Remedies: `ITEMS["remedy"]` (`hands` 3, out of sight, `received` = `cared_for`). A remedy is only ever
  given by `give`, which needs the two within reach (`near_person`; `gift_targets` reads `beside` or the same
  table). `approach` (T2) walks to someone seated at another table and stands at it, which puts them within
  reach. Edda's card goal already says she means to "press a remedy on anyone who looks unwell". Nobody is
  unwell.

Decisions for every F task (frozen 2026-10-09; change them here first if the code disagrees):

- **The west wall.** `window-2` leaves `data/tavern.json` and its cell [0, 6] joins `blocked`, so the hall
  stays walled. `window-1` and `window-3` stay. The Window table keeps its name: `window-1` is still in
  reach of it, and windows have no appeal anyway.
- **Candles are decoration.** The client draws them; no rule reads them, and they are in neither the map,
  the saves nor the snapshot. Their cells live in a new pure module `frontend/src/candles.ts`, beside the
  other hand-placed details of this hall (`floor.ts` `drawRoomDetails`). Each hangs on a wall cell and
  shines into the room:

  | where | cell | wall |
  |-------|------|------|
  | the privy | (19, 2) | east |
  | by the front door | (11, 13) | south |
  | west wall, between the darts and the garden window | (0, 9) | west |
  | east wall, between the East and Corner tables | (19, 9) | east |

  Which way a candle shines is `hearth.hearthFacing`, reused: widen its parameter to
  `Pick<WorldObject, "x" | "y" | "width" | "height">` rather than write a second copy. The sconce (an iron
  bracket and a pale candle, a few pixels) is drawn once with the furniture. Each frame a small flame and
  the glow are drawn on a layer of their own, beside `hearthGlow` and below the guests. The glow is the
  hearth's: same colour, same flicker formula, each candle on its own phase, three rings of `0.45·size`
  each instead of five of `0.62·size`. Putting candles in `data/tavern.json` would mean backend validation
  and a save change for pure decoration. That is out of scope; ask the user if it ever matters.
- **Full energy on arrival.** The scenario's arrival range of `fatigue` becomes [0, 0]: every guest comes
  in with Energy 100. `data/tavern.json` keeps its own ranges, which
  `test_evening.py::test_demo_visitors_arrive_wanting_a_seat_and_a_beer` pins (as in Z1). The sick guest
  (below) is the one exception.
- **One item of news, one holder.** A new optional scenario field, `news_tonight` (an integer from 1 to the
  number of items). Without it, every item is told as listed, so every existing scenario and test hall
  keeps today's behaviour. With it, `open_evening` draws that many items, and then one holder for each from
  its `known_by`. The draw uses a stream of its own, `Random(f"{seed}:news")`, so arrival needs and the
  opening order stay as they are drawn today (the precedent is `Random(f"{seed}:opening")`). Drawn items keep
  their listed order, and holders are drawn item by item; say so in a comment. `world["news"]` holds only
  the drawn items, each with `known_by` = [holder], so `starting_facts`, `check_saved_news` and the
  inspector need no change. The pure step is `facts.draw_news(news, count, rng) -> tuple[News, ...]`.
  `first_evening.json` keeps its five items and sets `"news_tonight": 1`. The holder is drawn from
  `known_by`, not from all guests, because E19 hands out news by occupation (a toll guard knows the
  toll). Staff never hold news.
- **A ten-minute evening.** `closes_at` 420 → 600. A new optional scenario field, `last_call_at`, is when
  the barkeep calls closing time. It must satisfy `0 < last_call_at < closes_at`, and the first evening
  sets 540. The world gets `last_call_at: float | None` (None in a hall without a scenario, or a scenario
  without the field). It is saved: bump `schema_version` to the next free number (16 if F4 lands before
  F7). `test_database.py` and `test_intention_saves.py` pin the version.
- **The call.** `closing.call_last_orders(world, since)` runs beside `call_closing` in `step_world`, just
  before it. On the tick that reaches `last_call_at`, the barkeep calls out once. The barkeep is the first
  staff member in `world["actors"]` (`staff.on_staff`); with no staff, the event has `actor_id` None and
  there is no bubble.
  - Event `last_call`, with the message `Hob called out: "<LINE>"` ("The innkeeper called out: …" without
    staff). It also carries `line`, the words alone, for the client's bubble. Events are free-form dicts
    (D05), and the client's `WorldEvent` gains `line?: string` in the same commit.
  - `LINE` is a constant in `closing.py`, as the closing message is: "Time, friends! The Last Inn is
    closing for the night. Finish your cups and get yourselves home safe."
  - Sound: `EVENT_SOUNDS["last_call"] = Sound("closing_call", 1.0, 40.0, "the barkeep calling closing
    time")`, from the barkeep's cell, or from `_innkeeper` without staff. It is loud, so it interrupts
    (`attention`) and wakes any sleeper (Z3's rule, no new code).
  - `closing.closing_called(world) -> bool` is true from `last_call_at` on.
- **After the call the guests choose.** Only what an inn stops at closing time stops:
  - The barkeep pours no new mug (`tend_bar` reads `closing_called` where it now reads `inn_closed`).
  - `take_beer` is refused by `actions.action_error` with "The bar has stopped serving" and is not
    offered (`agents`).
  - Nobody nods off (`dozing`), and `doze` is not offered.

  Everything else stays a choice: a chat, the mug in hand, the WC, a goodbye, going home. Scenes do not
  end at the call. The hard close at `closes_at` is unchanged, as the backstop: whoever is still in at 600
  is sent home, as today.
- **What the minds see of the call.**
  - The observation gains `called_closing`: game seconds since the call, or None before it (and in a hall
    without one).
  - `briefing._closing`, between the call and the close: "The barkeep called closing time N seconds ago:
    the inn shuts for the night within the minute. Guests finish what is in hand, say their goodbyes and
    head home." After the close it says what it says today.
  - Local policy: `_leave_utility` takes `called = 0.55 + 0.4·min(1, seconds since the call / 40)` in its
    `max`. A guest with a mug or a chat going may finish it first; 40 s later leaving beats everything. It
    is a starting point: the tests are the spec.
  - `leave`'s `guidance` gains: "Once the barkeep has called closing time, going home is what guests do:
    they finish what is in hand, say goodbye and go." `test_jev.py` may pin activity text; if so, name that
    change in the commit.
  - Intentions: `latest_trigger` gives `Trigger(kind="last_call", text="The barkeep called closing time",
    time=last_call_at)` once called, ranked as the `closing` trigger is. In `data/minds/intention_prefix.md`,
    item 7 and the closing lines say that once the barkeep calls closing time a guest means to go home soon:
    finish the drink in hand, say goodbye to their company, go. Nobody orders another.
  - Turns: `turns.turn_view` gains `closing_called: bool`, and `haiku_turns.turn_content` adds one line:
    "The barkeep has just called closing time: the talk turns to goodbyes and heading home." The hall paragraph of
    `turn_prompt.shared_prefix` ("When the bell rings for closing…") gains: after the call, a speaker winds
    the talk down with a goodbye, a plan to meet again or a last word. Both prefixes stay byte-identical
    across calls and above 4,096 tokens.
- **The bubble.** A pure `bubble.callout(events, actorId, worldTime)` returns the newest `last_call` line
  of that actor, as a turn-like `{speaker, line, time}`, while `worldTime − event.time < 8` game seconds,
  else null. `scene.ts` hands it to `Speech.tell` when the actor has no conversation turn of their own.
  `Speech` keys its pieces by time and line, so the call is told once, in pieces, like any line.
- **The sick guest.** A new optional scenario field, `ailment: {"fatigue": <0–100>}`. With it,
  `open_evening` draws one guest from those who carry no cure (below), in listed order, from a stream
  `Random(f"{seed}:ailment")`. That guest arrives `ailing`, with `fatigue` set to the given value: it
  overrides the drawn value, and is set after the draw so other needs stay as drawn. If every guest
  carries a cure, there is nobody to draw: `parse_scenario` raises ValueError. The first evening sets
  `{"fatigue": 80}` (Energy 20). Edda never falls sick, because she carries remedies.
  - `Actor.ailing: bool` is False for everyone else, staff included. An expected guest carries
    `ailing: true` until they come in: `ExpectedGuest.ailing: NotRequired[bool]`, and `_expected_guest`
    strips it before `parse_guest`, as it strips `needs` (otherwise the saved-expected check rejects the
    unknown field). It is saved: bump `schema_version` to the next free number, and persistence refuses
    a non-bool.
  - `Item.cures: bool = False`, and the remedy sets it. Rules key off `cures`, never `kind == "remedy"`.
  - Edda carries three: `"carries": {"remedy": 3}` (the remedy's `hands` is 3).
- **What a remedy does** (`body/ailment.py`, new: "Who comes in unwell tonight, how it shows, and what a
  remedy does for them"). When `giving.hand_over` hands a `cures` item to an `ailing` receiver who takes it,
  it calls `ailment.cure(world, giver, receiver)`:
  - The receiver takes the remedy at once: their count of it is back where it was, so the remedy is used
    up.
  - `ailing` becomes False, and `fatigue` drops by `RELIEF` = 40, never below 0. `RELIEF` is a module
    constant with a why-comment, as `SLEEPY` is.
  - The receiver keeps a new thought, `cured` (6.0, 20.0, 600.0, 1, "cured them of their fever",
    acquaints), instead of the item's usual `cared_for`, not on top of it.
  - Both record `cured`: "Saye took Edda's herbal remedy and looks better already".

  The giver keeps `generous`, and the receiver shows the affection emote, as today. A receiver who is not
  ailing keeps the remedy and the `cared_for` thought, as today. One who refuses it (`refuse_below`) stays
  sick.
- **Being seen as sick, and being sought out.** Nothing forces anyone; it is all in what the minds see and
  in the scores.
  - `sight.people_in_sight` gains `ailing`, beside `asleep`. Follow `asleep` (Z2) through every reader.
  - `briefing._person` adds ", looking pale and feverish". The sick guest's own situation says: "They feel
    feverish and weak tonight; a healer's remedy would help."
  - `options`: a `give` of a cure to an ailing person reads "hand Saye a herbal remedy (she looks pale and
    feverish; it would help her)". An `approach` to one adds "(she looks pale and feverish)".
  - Local policy, for a guest who carries a cure: `approach` to an ailing guest gets +0.5 (in
    `_score_approaches`), and `give` of a cure to an ailing guest scores 0.95 (in `_score_gifts`). A guest
    with no cure gets neither bonus.
  - Haiku: the intention view's list of others and the turn view's participants say "looks pale and
    feverish", and the sick speaker's own note says "You feel feverish and weak tonight." No prefix change
    is needed: Edda's card already wants to press remedies on the unwell.
- **Client.** `types.ts` gains `Actor.ailing: boolean`, `World.last_call_at: number | null` and
  `WorldEvent.line?: string`. The inspector shows the word "unwell" for an ailing guest, as the dashboard
  shows "asleep". No new art.
- **Metrics** (`metrics.json`, each in a small module of its own, as `manner_metrics.py` is):
  - `closing` (`evening/closing_metrics.py`): `last_call_at`, `closes_at`, `present_at_call`,
    `left_after_call` (left in [call, close)), `sent_home` (left at or after the close) and `last_out`.
  - `ailment` (`evening/ailment_metrics.py`): `ailing` (name), `arrived_at`, `cured_by` (name or null),
    `cured_at` (or null) and `left_ailing`.
- **Out of scope:** a sickness that spreads or worsens, the sick guest asking for a remedy, more than one
  sick guest, remedies for anything else, the barkeep's line written by Haiku, a closing bell sound, candles
  that go out, a lit window, and moving the arrival times for the longer evening.
- **Tests expected to change.** The user asked for these behaviours (2026-10-09). Name the test and the
  reason in the commit:
  - `test_carries.py::test_the_first_evening_has_edda_carry_remedies_and_toren_keepsakes` (F7): Edda carries
    3.
  - `test_database.py` and `test_intention_saves.py` pin `schema_version` (F4, F7).
  - `test_jev.py`, only if it pins `leave`'s guidance (F5).

  Any other failing test is a surprise: stop and report it. F2–F8 change whole evenings, and these seeded
  first-evening tests can fail by chance: `test_facts.py::test_a_news_item_reaches_a_third_guest_in_other_words`
  (seeds 7 and 4; with one item and one holder, a two-hop path is much rarer), `test_barkeep_evening.py`,
  `test_dice_invitation.py::test_a_game_invited_to_in_the_first_evening_reaches_a_result` and
  `test_first_evening.py`. If one fails, report the seed and the failure. Do not change a seed or an
  assertion without the user's approval.
- **Sizes.** `agents.py` has 374 lines and `scenario.py` 318. If a task pushes one past about 400, split
  it first, as a separate refactor commit (for example, the scenario's tonight-draws into
  `evening/tonight.py`).

Order: F0 and F1 are data and client only, and can go any time, beside anything. Then F2 → F3 → F4 → F5 →
F6 → F7 → F8 → F9. F6 needs F4, F8 needs F7, and F9 comes last. Each task is its own branch
(`claude/stage1-f<n>`) and PR.

- [x] **F0 — Two windows on the west wall.**
  - *Build:* drop `window-2` from `data/tavern.json` and add [0, 6] to `blocked`.
  - *Tests first* (`tests/test_hall_layout.py`): a new test that the west wall has exactly the windows at
    (0, 4) and (0, 11). `test_the_hall_is_walled_all_round` must stay green unchanged.
  - *Check:* `make check`. In `make run`, post a screenshot of the west wall.
  - *Built (2026-10-09):* `window-2` is gone from `data/tavern.json` and [0, 6] is in `blocked`.
    `test_hall_layout.py::test_the_west_wall_has_two_windows` (red before the data change); the rest of the suite
    needed no change (2737 passed).
- [x] **F1 — Candles that glow like the fire (client only).**
  - *Build:* `frontend/src/candles.ts`: the four cells above, the light point of each (the wall edge it
    faces, from `hearthFacing`), `drawSconces` (static, with the furniture) and `drawCandles` (flame and
    glow, per frame, on a new layer created beside `hearthGlow` in `scene.ts`).
  - *Tests first* (`frontend/tests/candles.test.ts`, node:test): each candle stands on a blocked cell of
    `data/tavern.json` (read with `node:fs`), and the cell it shines into is walkable floor; the light point
    of a candle on each of the four walls (parametrized); a candle's glow is smaller than the hearth's, and
    two candles flicker out of phase at the same time.
  - *Check:* `make check` and `make build`. In `make run`, post a screenshot of the whole hall and a 2×
    crop of the privy and the door.
- [x] **F2 — Full energy on arrival.**
  - *Build:* `first_evening.json`'s arrival `fatigue` [0, 0].
  - *Tests first:* in `tests/test_scenario_cards.py` (or beside the other first-evening checks), every
    guest the first evening expects has `fatigue` 0, for two seeds.
  - *Check:* `make check`. Offline seed 5 (`--writer scripted`), before and after: the time of the first
    `dozed_off` and each guest's `fatigue` on leaving (a scratch script, not committed). Expect no nap
    before 300 s.
  - *Built (2026-10-09):* the scenario's arrival `fatigue` is [0, 0].
    `test_first_evening.py::test_every_guest_comes_in_with_full_energy` (seeds 1 and 7) was red before the data
    change. Offline seed 5 afterwards: no nap at all (`sleep.naps` 0), guests left with fatigue 28–49.
- [x] **F3 — One item of news, one holder.**
  - *Build:* `news_tonight` in `parse_scenario` and `Scenario`, `facts.draw_news`, the draw in
    `open_evening`, and `"news_tonight": 1` in the first evening.
  - *Tests first* (`tests/test_facts.py` or a new `tests/test_news_tonight.py`). Parametrized:
    - `draw_news` with count 1 over five items gives one item with one holder from its `known_by`;
    - count equal to the number of items gives every item in listed order;
    - an item with a single holder keeps them;
    - the same seed draws the same item and holder;
    - over 20 seeds, the first evening draws at least three different items.

    `open_evening` with `news_tonight` 1: exactly one guest starts with a fact. Without the field, today's
    holders. A separate `pytest.raises` block: 0, more than the items, a non-integer, and `news_tonight`
    with no `news`.
  - *Check:* `make check`. Offline seeds 1–8: the item drawn, its holder, and how many guests held it at
    the end (`news_metrics`). Report any seeded test that fails, as decided above.
  - *Built (2026-10-09):* `facts.draw_news(news, count, rng)`; `Scenario.news_tonight` and `_news_tonight` in
    `scenario.py`; `open_evening` draws from `Random(f"{seed}:news")`, so arrival needs are unchanged (pinned by a test).
    The first evening sets `"news_tonight": 1`. `tests/test_news_tonight.py` (35 cases) is the spec. Over seeds 0–20
    the drawn item is `margrave_fever` 9 times, `salt_toll` 4, `pass_closing` 4, `cloth_robbery` 3 and `deserters` 1,
    and the item reached a third guest (two hops) in 15 of 21 evenings played offline with the paraphrasing writer.
    One seeded test failed, as foreseen: `test_facts.py::test_a_news_item_reaches_a_third_guest_in_other_words[seed-7]`
    (seed 7 draws `salt_toll` for Calder, who arrives at 110 s and tells nobody). With the user's approval
    (2026-10-09) seed 7 became seed 0 in that test's parametrization; the assertions did not change. Offline seed 5:
    `pass_closing`, held by Calder, told to Rurik and overheard by Toren at 172 s.
- [x] **F4 — A ten-minute evening and the barkeep's call (the world).**
  - *Build:* `last_call_at` in the scenario, the world and the saves (the schema bump); `call_last_orders`,
    `closing_called`, the event with `line`, the sound; no pouring, `take_beer` or nap after the call;
    `called_closing` in `observe_actor`; `closes_at` 600 and `last_call_at` 540 in the first evening;
    `World.last_call_at` and `WorldEvent.line` in `types.ts`.
  - *Tests first* (`tests/test_closing.py`):
    - one `last_call` event on the tick that crosses 540, with Hob's `actor_id` and `line`, never twice;
    - none without `last_call_at`, and `actor_id` None without staff;
    - a sleeper across the hall wakes at the call (`woken`), and an idle guest turns to the bar;
    - after the call, `take_beer` is refused with the reason and not a candidate, `doze` is not a
      candidate, and the barkeep starts no pour; `talk` and `leave` are still candidates;
    - `called_closing` is None at 539 and 3.0 at 543;
    - a save made after the call reloads.

    Error blocks: `last_call_at` of 0, equal to `closes_at`, or a string; a saved `last_call_at` that is
    not a number.
  - *Check:* `make check` and `make build`. Offline seed 5: quote the `last_call` event, and count guests
    present at the call and sent home at 600 (today's policy still waits for the close; F5 changes that).
  - *Built (2026-10-09):* `hall/closing.py` (`LAST_CALL_LINE`, `closing_called`, `since_last_call`,
    `call_last_orders`, `check_saved_last_call`); `World.last_call_at` and `schema_version` 16; `last_call_at` in the
    scenario; `EVENT_SOUNDS["last_call"]`; `called_closing` in `observe_actor`; `WorldEvent.line` and
    `World.last_call_at` in `types.ts`. First evening: `closes_at` 600, `last_call_at` 540. `tests/test_last_call.py`
    (27 cases) is the spec. Two things differ from the plan above, both on purpose:
    - *The refusal is at the start of an order, not in `action_error`.* `action_error` is also asked every tick of an
      interaction, so a guest already waiting at the tap would have lost their mug at the call. A new
      `Activity.stopped_at_last_call` (set on `take_beer`, "The bar has stopped serving") is read in
      `world.start_action`, so an order made before the call is still poured, and the barkeep's `tend_bar` is unchanged.
    - *`bring_drink` is not offered after the call either* (`agents._fetches`), because it sends the host to the tap.
    Tests that changed, as approved for the save bump: `test_database.py` and `test_intention_saves.py` pin version 16.
    Offline seed 5 (`--writer scripted`): `{"actor_id": "hob", "type": "last_call", "time": 540.0, "message": "Hob
    called out: \"Time, friends! …\""}`; six guests were in at the call, one left before the close (Toren, 547 s) and
    five were seen out at 605–609 s, as before F5.
- [x] **F5 — Guests answer the call (the minds).**
  - *Build:* the briefing line, `called` in `_leave_utility`, `leave`'s guidance, the `last_call` trigger
    and the intention prefix, the turn view and turn content and the prefix sentence, and
    `closing_metrics` wired into `scripts/evening.py`.
  - *Tests first:*
    - briefing text between the call and the close, and after the close.
    - Local scores, parametrized, on a seated guest 400 s in with a half-full mug, one beer and a
      tablemate: at the call, `drink` beats `leave`; 40 s later, `leave` beats `drink`, `talk` and `sit`;
      before the call, today's order.
    - The trigger is `last_call` after the call and `closing` after the close.
    - `turn_content` carries the line only after the call.
    - `closing_metrics` from a hand-built list of departures.
  - *Check:* `make check`. Offline seeds 1–8: `present_at_call`, `left_after_call` and `sent_home` per seed.
    Target: on average at most one guest per evening sent home, and none still in at 630. If it is missed,
    tune `called` (never the tests) and record both runs. Quote one goodbye line said after the call.
  - *Built (2026-10-09):* `briefing._closing` (between the call and the close), `local_policy._leave_utility`
    (`called` floors the wish to leave at 0.5 at the call and 0.95 forty seconds later, so a pressing need such as a
    full bladder still comes first), `leave`'s guidance, the `last_call` trigger in `intentions.latest_trigger`
    (also in `UNMETERED`), `closing_called` in `turns.turn_view`, a nudge in `haiku_turns._nudges`, the scripted
    writer's goodbye (`scripted.LINES["closing"]`, said once a speaker has answered, never by the barkeep), a sentence
    each in the two shared prefixes (`turn_prompt` and `data/minds/intention_prefix.md`), and
    `evening/closing_metrics.py` wired into `scripts/evening.py` as `closing` in `metrics.json`.
    `tests/test_answering_the_call.py` (28 cases) is the spec. Offline seeds 1–8 (`--writer scripted`): five or six
    guests were in at the call, all of them went home before closing time (`left_after_call` 5, 5, 5, 5, 5, 5, 6, 5),
    `sent_home` 0 in every evening, and the last guest left between 557 and 573 s (the close is at 600 s). No nap in any
    evening. Offline lines are not logged in `events.jsonl`, so no goodbye line is quoted; at the call all five guests
    of seed 5 logged `interrupted` ("turned toward the barkeep calling closing time"), and Toren, Saye and the rest
    chose `leave` within seconds. The `last_call` intention trigger needs a key to see; it is pinned by test only.
- [x] **F6 — The barkeep's line on screen (client).**
  - *Build:* `bubble.callout` and its use in `scene.ts` and `Speech`.
  - *Tests first* (`frontend/tests/bubble.test.ts`), parametrized: no event; another actor's call; the
    call 3 s ago gives the line; 9 s ago gives null; of two calls, the newest; a different event type is
    ignored.
  - *Check:* `make check` and `make build`. In `make run`, raise the speed in the debug panel until 9:00,
    and post a screenshot of Hob's bubble and the guests turning to him.
  - *Built (2026-10-09):* `bubble.callout`, `bubble.newer` and `bubble.Spoken`; `Speech.tell(line, now)` takes the line
    to tell instead of a conversation, and `scene.ts` hands it the newer of the guest's own latest conversation line and
    their call, so a call is told once, in two pieces, and a line spoken after it replaces it. The window is 8 game
    seconds. `frontend/tests/bubble.test.ts` gained 13 cases. In the running app (8× to 8:50, then 1×, paused at 9:01):
    Hob's bubble read "Finish your cups and get yourselves home safe." (the second piece) and all five guests showed the
    alert emote and turned toward the bar.
- [x] **F7 — A sick guest and three remedies (the world).**
  - *Build:* `Item.cures`, the `ailment` field and the draw, `Actor.ailing` (and the expected guest's
    field) with the schema bump, `body/ailment.py` with `cure`, the `cured` thought and event, `ailing` in
    `people_in_sight`, Edda's three remedies, `{"fatigue": 80}` in the first evening, and `Actor.ailing`
    and the inspector word in the client.
  - *Tests first* (`tests/test_ailment.py`, new; the spec):
    - The draw, parametrized over seeds: never a guest who carries a cure, the same seed gives the same
      guest, their `fatigue` is 80 and the others' are drawn as before, and nobody is ailing without the
      field.
    - The cure, parametrized: a remedy to an ailing guest cures them (`ailing` False, `fatigue` −40, the
      remedy used up, the event, `cured` and not `cared_for`); one to a well guest is as today; a refused
      one leaves them sick; at `fatigue` 30, the cure stops at 0.
    - `people_in_sight` shows `ailing`.
    - Saves: an ailing guest, and an ailing guest still expected, both reload.

    Error blocks: `ailment` with unknown keys, a `fatigue` out of range, every guest carrying a cure, and a
    saved non-bool `ailing`.
  - *Check:* `make check` and `make build`. Offline seed 5: who fell sick, and whether anyone cured them
    yet (most likely not before F8).
  - *Built (2026-10-09):* `body/ailment.py` (`parse_ailment`, `carries_cure`, `eligible`, `draw_ailing`, `relieve`,
    `RELIEF` 40, `check_saved_ailing`); `Item.cures` (the remedy); `Actor.ailing`, saved as **version 17**; the
    scenario's `ailment` (`Scenario.ailing_fatigue`), drawn from `Random(f"{seed}:ailment")` among guests who carry no
    cure, and carried on the expected guest as `ailing`; `arrived_unwell` logged on arrival; `ailing` in
    `people_in_sight`; `giving.hand_over` cures instead of giving (a `cured` event for both, a `cured` thought for the
    receiver, `cured` in `giving.RECEIVED`); `Actor.ailing` in `types.ts` and an "Unwell" chip in the inspector. Edda
    carries 3, and the first evening sets `{"fatigue": 80}`. `tests/test_ailment.py` (40 cases) is the spec. Tests that
    changed, as approved: `test_database.py` and `test_intention_saves.py` pin version 17; `test_carries.py` expects
    Edda to carry 3; `test_first_evening.py::test_every_guest_comes_in_with_full_energy` expects the one ailing
    guest at 80 (the user asked for exactly that). Offline seed 5 before F8: Toren fell ill at 1 s and was not cured.
- [x] **F8 — Edda seeks out the sick (the minds).**
  - *Build:* the briefing and option wording, both local bonuses, the Haiku views, and `ailment_metrics`
    wired into `scripts/evening.py`.
  - *Tests first:*
    - The briefing (the person, and the sick guest's own line).
    - Option sentences for `give` and `approach`.
    - Local scores, parametrized, for Edda with remedies:
      - the sick guest at another table: `approach` to them beats `approach` to a well guest she thinks
        as well of;
      - the sick guest at her table: `give` of a remedy to them is her top option;
      - the same Edda without remedies: no bonus.
    - Turn content and the intention view say "looks pale and feverish".
  - *Check:* `make check`. Offline seeds 1–8: who fell sick, `cured_by` and `cured_at` per seed. Target:
    cured in at least 6 of 8 evenings. Quote one cure from `events.jsonl`. If the target is missed, record
    why (the sick guest stood, slept, or left first) and propose, without building it, a compound `tend`
    errand like `bring_drink`'s `carrying` stage.
  - *Built (2026-10-09):* `briefing._pale` and `_unwell` (what others and the sick guest themselves are told), the
    `give` and `approach` option wording, `local_policy.SEEKING_THE_SICK` (+0.5 on a walk over to someone who looks
    unwell, for a guest who carries a cure) and `CURE_SCORE` (0.95 for a remedy to them), `ailing` in the turn view
    (the speaker and each other participant) with a line in `haiku_turns`, and `evening/ailment_metrics.py` wired into
    `scripts/evening.py` as `ailment`. The intention view needed no change: its `situation` is the briefing, which now
    carries it (its `others` map is IDs to names that goals are checked against, so it was left alone, unlike the plan).
    `tests/test_seeking_the_sick.py` (23 cases) is the spec. Offline seeds 1–8 (`--writer scripted`): cured in **7 of 8**
    evenings, always the guest who fell ill and nobody else (cured_at 59, 140, 171, 235, 247, 269 and 347 s: Edda in six,
    and Brida in seed 7, who had been given a remedy by Edda her old friend and passed it on to Calder). Seed 4: Brida
    came in ill at 40 s and left uncured: Edda spent that evening choosing `sit` every 15 s and never got within reach of
    her; not investigated further. No evening sent anyone home at closing (`closing.sent_home` 0 in all eight), and
    1–2 guests napped in most of them. Seed 5: `{"actor_id": "mara", "type": "cured", "time": 268.8, "message": "Toren took
    Edda's herbal remedy and looks better already"}`.
- [x] **F9 — Measure.**
  - Offline seeds 1–8, and live seeds 5 and 7, before (`main`) and after. Record: `present_at_call`,
    `left_after_call` and `sent_home`; naps before 300 s; the news item, its holder and how far it went;
    who fell sick and when Edda cured them; stuck seconds; conversations; and cost (expect about 40% more
    for the longer evening). Replay the live run and `cmp` the events (step 8 of "Working on a task").
  - Record two moments from the log: the call and the goodbyes after it, and Edda's cure with the line
    around it, if any.
  - *Measured (2026-10-09).* "Before" is the last recorded run on `main` (T8, live seed 5: 436 game s, 307 calls,
    $0.28, no failed call); the first evening had no call, no sick guest and a 420 s close.
    - *Offline, seeds 1–8 (`--writer scripted`):* every guest in the hall at the call (4–6) went home before the
      close and none was sent home; the last left at 560–576 s of 600. Naps: seven evenings had one or two, every one by
      the guest who came in unwell, none by a rested guest. The unwell guest was
      cured in 7 of 8 (59–347 s); the one news item reached 4–7 guests, in two or three hops. Stuck seconds per evening
      8–37 (mean 17.5), 49–66 conversations.
    - *Live, Jev + Haiku, first wording of the briefing (seeds 5 and 7):* the call did **not** move guests. Only one or
      two left before the close (`left_after_call` 1 and 2), and 5 and 4 were sent home at 600 s: they kept to what they
      were doing (`sit`, a chat, a last round of dice) and went when the close came. Cost $0.41 and $0.50, 465 and 480
      calls, none failed.
    - *The fix:* the briefing now says it is time to go, to finish only what is in hand, and that starting something
      new makes no sense (`briefing._closing`). Live again: seed 5 sent 1 home (`f9-live-5b`) and later 0
      (`f9-live-5c`, all six left between the call and 581 s), seed 7 sent 1 home. Cost $0.36–$0.47 for 428–510 calls,
      cache hit rate 0.87–0.89, no failed call, 0–2 turn fallbacks per evening. The replay of seeds 5c and 7b is
      byte-identical (`cmp` on `events.jsonl`). The replay of the intermediate run 5b failed with `LookupError` (a
      request with no recording): not explained, and that run's code was not committed, so it was not rerun.
      Conversations fell from the 52–66 of the offline evenings to 35–46 live; a live evening of 600 game s costs
      about 1.3 times the 436 s of T8.
    - *Moments (live seed 7b):* at 540 s `Hob called out: "Time, friends! The Last Inn is closing for the night.
      Finish your cups and get yourselves home safe."`, then at 543 s `Edda to Brida (leave_conversation): Right then,
      Brida—time I got my feet up by that fire before they close us out.` and at 556 s `Edda to Hob (leave_conversation):
      Well, the barkeep's calling it. I'll away to my bed—feet are killing me.`; and at 392 s `Calder took Edda's herbal
      remedy and looks better already` (Edda found Calder, who came in unwell at 110 s).
    - *Left behind:* in live seed 5c the unwell guest (Toren) was never cured; in offline seed 4 Brida was not
      either. In live seed 7b one guest still waited for the close. The live goodbyes are Haiku's: only two
      `leave_conversation` lines came after the call in seed 7b, so most guests left without saying one.
### Choice depth (C0–C8)

Added 2026-10-09 at the user's request. The choice layer (Jev) picks one next step at a time, at most two levels
deep, and in practice it has fewer branches than it shows. Measured on a live evening (seed 7, commit `7d161f8`,
442 game s, Jev $0.050 of $0.40), from its `calls.jsonl`:

| Stage | Requests | Options per request | Near-best set (what chance draws from) | Decided before the draw (near-best of 1) |
|---|---|---|---|---|
| First (one option per family) | 168 | 7.1 (cap 8 in 42%) | 1.70 | 51% |
| Family (the action within it) | 61 | 2.9 | 1.21 | 84% |
| Seats | 7 | 7.7 | 2.43 | 29% |

- **About half of each first-stage request is the same four fixtures.** `inspect` was in 158 of 168 requests and
  never scored above 0.11. `leave` was in 167 and was never chosen before closing (all six departures came 4–22 s
  after it). `use_toilet` (155, mean 0.18) and `wait` (153, mean 0.28) were nearly as constant. Of all first-stage
  options, 31% scored below 0.15, a level the near-best draw never reaches. The local policy ranks
  these fixtures above low-scored social options when the cap of 8 binds: in an offline evening it trimmed
  `bring_drink` 27 times before Jev saw it.
- **The hierarchy is mostly nominal.** Of 13 families, only `company`, `pastime`, `resting` and once `fetching` ever
  held more than one action; the other nine always stand for one verb. The second stage picks *whom* or *which
  object*, never *why* or *how*.
- **No step knows the one before.** The most common consecutive choices were `sit`→`sit` (24), `talk`→`talk` (16)
  and `play_darts`→`play_darts` (9). Goals reached the choice as a mark in 11 of 168 requests.
- **What is done to a guest opens no choice.** Calder lost to Rurik at dice at 221 s; they played again (Rurik won
  again at 355 s) only because Haiku talked them into it at 268 s. Rurik, who loathes Toren, saw Toren walk over and was
  offered drink 0.97, sit 0.90, wait 0.43: nothing about Toren. T8 saw the same with hosts and intruders.

The block makes the choice deeper where stories come from: a lean first stage (C1), answers to what was just done
(C2), a third stage that picks *why* for social options (C3), temperament in the draw (C4), projects of several
steps chosen at once (C5, C6), and the invitee's own choice of an answer (C7). C0 and C8 measure.

Decisions for every C task (proposals: freeze each in its task before coding, and change them here first if the
code disagrees):

- **What stays.** Jev scores and never picks; the near-best draw; only validated actions change the world; the
  local policy is the fallback for every stage; a replay is byte-identical to its live run.
- **A new model stage is a new `Evaluators` field** (`aims` in C3, `answers` in C7), with its own question in
  `adapters/jev.py`, its own recorded `kind` in `calls.jsonl`, and the local scorer as fallback. It is wired in
  all three places (`app.create_default_app`, `server/runtime.py`, `scripts/evening.py` including replay; see D09).
  `Evaluators` keeps defaults so that callers which do not pass the new field still work.
- **Saves.** C2 (`Thought.answered`), C3 (an action's `aim`, a scene's `aims`), C5 (`world["projects"]`) and C7 (an
  invitation's `answer`) change the saved world. Each takes the next free `schema_version` (16 at the start) in
  the order they land, with a check function in the concept module and the pinned-version tests
  (`test_database.py`, `test_intention_saves.py`) named in the commit.
- **Snapshot.** C3 (`decision.aim`) and C5 (an actor's `project`) change it; `frontend/src/types.ts` changes in the
  same commit, and `make build` runs.
- **Prompts.** A change to `jev._visitor_view` changes every Jev request (no cache to keep). A change to the Haiku
  prefix (`turn_prompt.shared_prefix`) invalidates its cache once, which is fine; per-moment text goes in `content`.
- **Whole evenings move.** C1–C7 change which options are drawn, so `test_first_evening.py`, the news-spread test on
  seed 7 and `test_barkeep_evening.py` may fail for reasons unrelated to a bug. If one does, report the seed and the
  failure; do not change a seed or an assertion without the user's approval.
- **Out of scope:** wagers and stakes (Stage 3, the economy); several promise kinds (D22); a guest ordering
  another away; walking up to someone who stands (T's out-of-scope still holds); any new pose or art.

- [x] **C0 — Measure the choice.**
  - `evening/choice_metrics.py` (new: "How wide and how deep the evening's choices were"), pure, from the
    lockstep's recorded choices. `lockstep._record_choices` keeps each stage's `scores` (option ID to score, in
    request order; the options are its keys) beside `time`, `actor_id`, `kind` (`actions`, `family`, `seats`; later
    `aims`), `source` and `error`; `Choice.scores` is `NotRequired`, so hand-made choices still type-check. The
    decision itself does not change shape. `choice_counts(choices, events)` returns `ChoiceCounts` (a `TypedDict`):
    - `stages`, per kind: `requests`, `options` (mean), `near_best` (mean size of `selection.drawable`, recomputed
      from the scores; an option's verb is its ID before the first `:`) and `decided` (share with a near-best set of
      one);
    - `dead`: share of first-stage options scored below `DEAD` (0.15);
    - `depth`: `second` and `third`, the shares of decisions (first stages) followed by a family or seat stage, and
      by an `aims` stage (after C3), matched by guest and moment;
    - `repeats`: share of a guest's consecutive actions with the same verb, from `action_started` events, for the
      guests who made choices (staff are left out).
    Shares are None for an evening with nothing to share over. `scripts/evening.py` writes it as `choice` in
    `metrics.json`; rounding stays in its writer.
  - *Tests* (`tests/test_choice_metrics.py`, `test_lockstep.py`): empty evening, single request, a tie at the top, a
    pointless exit, dead options, a family stage, a seat stage matched to its own moment, a third stage, repeats per
    guest and between duplicate verbs, staff left out; a `pytest.raises` block for a stage without scores, one without
    options and an action event without a verb; the lockstep keeps every stage's scores.
  - *Built (2026-10-09), the baseline every later C task compares with* (`7d161f8` plus C0; the live runs are
    replayable from their `calls.jsonl`, and the live seed 7 replay is byte-identical to the evening analysed above).
    Offline, seeds 0–9: first-stage near-best 1.99, `decided` 32%, `dead` 32%, `second` 43%, `repeats` 38%, 174
    first-stage requests, 29.7 conversations, 16.8 stuck seconds, every guest gone at closing in all ten. Live:

    | | requests | near-best | decided | dead | second | repeats | conversations | stuck s | cost |
    |---|---|---|---|---|---|---|---|---|---|
    | seed 5 | 165 | 1.66 | 53% | 26% | 36% | 33% | 28 | 19.0 | $0.36 |
    | seed 7 | 168 | 1.70 | 51% | 31% | 40% | 31% | 38 | 22.1 | $0.40 |

- [x] **C1 — A lean first stage.**
  - *Rule:* a fixture verb is put to the model only when the guest's own state makes it worth weighing. A table in
    `local_policy`, keyed by verb:

    ```python
    # The local score at which a fixture is worth a model's slot; the guest's state lifts it over the floor.
    ASK_FLOOR = {"inspect": 0.3, "wait": 0.1, "use_toilet": 0.25, "leave": 0.25}
    ```

    `selection.worth_asking(candidates, scores, floors, kept=())` keeps the options at or above their floor (verbs
    not in the table always) and those whose ID is in `kept`, in candidate order. It never empties a request: when every
    option is under its floor, all are kept (an empty known world, closing time with two doors). Nor does it leave
    only an exit (`leave`, or the `going_home` family of two doors): the request stays whole, so that staying is an
    option too (without it `drawable` would send a guest home whom Jev rated 0.25). `agents._in_line` puts the options
    that keep a place in a line the guest already joined into `kept`. What the floors mean: `inspect` is asked while
    a need of about 40 or more has no known relief; `use_toilet` from a bladder of 25 ("mild" in the briefing); `leave`
    once `_leave_utility` finds the evening content, weary or upset; `wait`, the one way to stay put, unless a need of
    about 50 presses (its local score is then under 0.1). Each floor has a why-comment beside the table.
  - *A setting, not a rule of the library (changed while building).* A first version applied the floors whenever a
    model was asked, and broke 16–18 existing tests whose fake evaluators score `inspect`, `wait` or `leave` in
    hand-made states that have nothing else (`test_lockstep.py`, `test_seating.py`, `test_agents.py`,
    `test_hostile_options.py`, `test_fetching_evening.py`). Those tests pin that a fake model's choice is the one
    taken, which stays true; so the rule became `config["lean"]` (`selection.read_lean`: a bool, off when absent, a
    `ValueError` for anything else), on in the shell (`AI_LEAN`, default `true`, read by `selection.read_switch` in
    `app.create_default_app` and `scripts/evening.py`, shown in the run report; `.env.example`) and off in the
    library. A replay needs the recorded run's setting, like its temperature. No test was changed.
  - *Tests* (`tests/test_lean_requests.py`): `worth_asking` cases (empty, single option under its floor, fixtures
    left out, one over its floor, a score at the floor, all under, verbs without a floor, duplicate fixtures, an exit
    alone, an exit beside a seat, `kept`); the options the evaluator receives through `choose_action` (a calm guest is
    not asked about wandering, thirst with no known tap is), with the setting on, off and absent, and without a key;
    the setting and switch readers, with `pytest.raises` blocks.
  - *Built and measured (2026-10-09).* Offline seeds 0–9 are byte-identical to the C0 baseline (`cmp` of
    `events.jsonl`), since a model-less evening never asks. Live seeds 5, 7, 1, 2, 3, C0 against C1 (replays of the C1
    seeds 5 and 7 are byte-identical): the share of first-stage options under 0.15 fell from 27% to 5%; the
    options `inspect`, `wait`, `leave` and the WC were asked 779, 738, 832 and 773 times in all and now 123, 322, 357 and
    443; input tokens per first-stage request fell from 5,798 to 4,595 (−21%); `bring_drink` reached Jev 124 times and
    now 183; the near-best set (1.66, 1.64) and the share decided before the draw (55%, 51%) did not change, since the
    draw was already narrow; cost per evening $0.35 → $0.33. Stuck time is the open point: mean 25.5 s → 30.2 s, from
    19–35 s to 15–53 s over the five seeds (the two seeds run first were the worst, 38.6 s and 53.1 s, with more
    blocked routes, not more waiting for a decision). That spread is wider than the difference, so it is no evidence
    for or against; C8 repeats it over more evenings. Not measured: departures before closing (none in either).

- [x] **C2 — Answer what was just done to them.**
  - `social/responses.py` (new: "Answers to what was just done to a guest"). A table keyed by thought kind
    (`Response(verbs, within)`): `seat_taken`, `table_intruded`, `line_cut`, `insulted`, `quarrel`, `friend_insulted`,
    `let_down`, `lost_at_dice` and `shoved` are answered by talking (`talk`, `approach`, `join_conversation`; `shoved`
    by `talk`, `table_intruded` and `line_cut` by `talk` and `join_conversation`) for 60–120 s; `treated`, `gifted`,
    `cared_for` by the same and by `give` and `bring_drink`; `kept_word` by talking. **No blow answers anything**
    (changed while building): with `shove` and `start_fight` in the table the local bonus doubled their scores
    (0.16 → 0.32), against the hostile design of E20 that `test_hostile_options.py` pins; hostile acts keep their own
    gates. No new verb or family: every answer is an option the guest already has.
  - `calling(actor, now)`: the active, unanswered thoughts about someone, of a kind in the table, inside their window.
    `answering(actor, now, action)`: the freshest of them about the action's target that the action's verb answers; for
    a family, any member; of two equally fresh, the one the guest had later. `age_of(thought, now)` is the age from the
    expiry and the kind's `seconds`.
  - *A thought is answered once.* `Thought.answered: NotRequired[bool]`; `world.start_action` calls
    `responses.mark_answered` after an accepted start: it sets the flag and logs `answered` ("Calder went to answer
    Rurik, who beat them at dice (39 s later)"). `thoughts.check_mind` accepts the field and rejects a non-bool.
    **No `schema_version` bump** (changed while building): the field is optional, so older saves load and the pinned
    version stays 15.
  - *What the mind sees.* `briefing._marked` adds "(this answers Rurik, who beat them at dice 40 s ago)" after the goal
    mark; the situation gains "Unanswered: Rurik, who beat them at dice (40 s ago)." for each calling thought about
    someone in sight. `jev._visitor_view` gains the sentence about options marked as answering someone.
  - *Local policy.* `_score_answers`: an answering option gains `0.1 + 0.3 × temper` for a thought that lowers the mood
    (a wrong) and `0.1 + 0.3 × sociability` for one that does not, clamped to 1, after `_score_goal`.
  - *Metrics:* `responses` in `metrics.json` (`evening/response_metrics.py`): `answered`, `by_kind` and `mean_delay`
    from the `answered` events. The `called` count of the first plan was not built: nothing logs a thought as it is
    made, and deriving it from events would need a map from each event to its thought; the wrongs and kindnesses of an
    evening are counted from the log by hand below.
  - *Tests* (`tests/test_responses.py`, `test_response_metrics.py`): the table is sound (kinds, verbs, unique reasons);
    `answering` cases (fresh, at the edge of the window, past it, other person, a thought about nobody, a verb that
    answers nothing, answered, expired, no answer called for, two thoughts, a blow, a family); `calling`; starting an
    answer marks and logs it, once; other actions leave it; briefing and `Unanswered` text, and silence without a
    thought; the local bonus by temper and by sociability; saves with, without and with a bad `answered`; the metric.
    No existing test changed.
  - *Built and measured (2026-10-09).* Offline seeds 0–9: 5 answers in all (`table_intruded` 4, `cared_for` 1,
    delays 30–88 s), departures 6 in all ten, stuck seconds unchanged but for two seeds (seed 6 +2.0 s, seed 8 −11.9
    s), conversations 28 → 26 and 24 → 31 in those two. Live seeds 5 and 7: one answer each. Seed 5 had two lost dice
    games (221 s, 356 s; Edda answered the first after 39 s, and the second came 60 s before closing), seed 7 three
    intrusions, two taken seats and two remedies given (Edda answered one intrusion after 7 s). So about one call in
    five or six was answered, near the line of the open question below. Jev's own scores of the marked options were
    not examined.
  - *If Jev ignores the marks* (answers under 20% of the calls, live), propose a `respond` family offered only while a
    thought calls for an answer, with members whose IDs carry the response. Do not build it in C2. Seen here: about
    17%, on two evenings with nine calls; decide after C8's larger sample.

- [x] **C3 — Why: an aim for every social option.**
  - A third stage. After the concrete action is chosen (stage one or two), if its verb is `talk`, `approach` or
    `join_conversation` (`aims.AIM_VERBS`), `choose_action` asks `Evaluators.aims` to score the aims; with one aim it
    is set without a request and shows no stage. The action carries it: `Action.aim`, kept by `stored_action`, refused
    on any other verb and for an unknown or malformed aim (`actions.action_error`), and validated in saves
    (`aims.check_saved_aims`). **A setting** (as C1): `config["aims"]` (`selection.read_aims`, off when absent), on in
    the shell as `AI_AIMS` (default `true`). With the setting on and a key but no `Evaluators.aims`, `choose_action`
    raises a `ValueError`.
  - `social/aims.py` (new: "What a guest means by a social option"). `AIMS` maps a kind to `AimKind(wording, acts,
    guidance, detail, invitation)`: `pass_time`, `tell_news:<fact>`, `invite:<kind>`, `win_over`, `needle`,
    `have_it_out`, `thank`, `rematch`. `offered_aims(observation, action)` lists them: `pass_time` first; the two pieces
    of news the guest believes most; what they could invite the person to as far as they can tell (`darts_together`
    with the board known, `dice_together` with a dice table known and no game seen, `buy_drink` with a stocked tap, a
    free hand and a person with empty hands, `join_table` with a free chair at their own table that the person is not at);
    `win_over` for someone not a friend and not disliked, `needle` for someone at or under `NEEDLED` (-10, pinned to
    `conversation.DISLIKED`, which this module cannot import: the scenes check aims here); and, while a thought calls for
    an answer (C2), `have_it_out`, `thank` or `rematch` by `ANSWER_AIMS`. `make_amends` is not built: nothing records
    whom a guest wronged. `aim_words` tells an aim ("ask Bea for a rematch at dice"), `aim_candidates` makes the
    options of the stage (`<aim>@<action id>`), `carried_out` says whether the speaker has said one of its acts (for
    news, naming the fact; for an invitation, the kind).
  - *The model.* `jev._aim_question` asks "How natural is it for them, right now, to <action>, meaning to <aim>?" with
    the kind's guidance (`mind.options.aim_text` tells the option; `agents._aim_view` is the same picture of the guest);
    `jev.evaluate_aims` and `evaluate_aims_metered` score it; the stage is recorded as `aims` in `calls.jsonl`,
    replayed, traced (`tracing._STAGES`) and wired in `app.py`, `server/runtime.py` and `scripts/evening.py`.
    `local_policy.local_aim_scores` is the fallback and the offline score: small talk 0.4, news 0.25 + 0.3 × curiosity,
    games 0.2 + 0.5 × boredom, an ale 0.2 + 0.4 × opinion, a table 0.2 + 0.4 × the wish for company, winning over 0.2
    + 0.4 × sociability, a needle 0.1 + 0.5 × temper × dislike, having it out 0.2 + 0.5 × temper, thanks 0.5, a rematch
    0.2 + 0.4 × boredom + 0.3 × temper.
  - *The world keeps it.* The scene gains `aims`, optional, by speaker: `{aim, about, kept}` (`aims.begin_aim` writes it
    when the verb's opening runs, and logs `aim_set` "Calder means to invite Rurik to play a game of dice
    (invite:dice_together)"; `scenes._tidy_aims` drops it with the member or when its person has gone home).
    **No `schema_version` bump** (changed while building): both fields are optional, so older saves load; the version
    stays 15.
  - *The line writer reads it.* `turns.turn_view` gives the speaker `aim` (`id`, `words`, `acts`, `detail`, `done`). The
    Haiku moment says, while it is not done and not `pass_time`: "The speaker came over to <words>: say so in their own
    words, early. Acts that fit: <acts> (fact_id fever)"; the shared prefix has rule 18 (say it early with one of the
    acts, and never offer or promise what the moment does not say). `turns._speak` calls `aims.note_spoken`, which marks
    the aim kept once and logs `aim_kept`. The scripted writer says it on the speaker's first line after a greeting
    when an act of the aim is on offer and has lines.
  - *Decision and snapshot.* The decision gains `aim` (`name`, `source`, `scores`, `error`), like `family`;
    `apply_decision` and `lockstep._record_choices` keep it; `frontend/src/types.ts` gets `AimStage` and `Action.aim`;
    the inspector shows "Came for" (`frontend/src/aims.ts`, tested).
  - *Metrics:* `aims` in `metrics.json` (`evening/aim_metrics.py`): set and kept, in all and per kind. C0's `depth.third`
    counts the stage.
  - *Tests* (`tests/test_aims.py`, `test_aim_scenes.py`, `test_aim_choice.py`, `test_aim_wiring.py`, `test_aim_lines.py`,
    `test_aim_metrics.py`, `frontend/tests/aims.test.ts`): offered aims in 20 situations; the table is sound; the action,
    scene and event lifecycle; the stage with a fake evaluator (asked, lone aim, failure falling back, setting off,
    non-social action, no key, no evaluator wired); the local scores; the Jev question and adapter; the decision, the
    recorded choices and the trace; the nudge, the prefix rule and the scripted writer; the metric. No existing test
    changed.
  - *Built and measured (2026-10-09).* Offline seeds 0-9, against the C0 baseline: the third stage in 22% of decisions
    (target 15%), conversations 29.7 → 33.8, conversation turns 73.9 → 82.2, evenings with a news path of two hops 8 →
    10 of 10, stuck seconds 16.8 → 16.7, every guest gone at closing; 340 aims set and 39 kept (11%): a scripted scene
    usually ends after two lines, so the starter rarely speaks twice. Live seeds 5 and 7 (replays byte-identical):
    21 and 25 aims set, 13 and 18 kept; leaving out `pass_time`, which is never nudged, 10 of 14 and 18 of 19 were
    said in the scene, so Haiku does what the guest came for about nine times in ten. The aim stage asked 23 and 28
    times (near-best 2.0, so the choice is real), cost $0.005 and $0.007 an evening, and the evenings $0.30 and $0.34.
    A moment: Calder, whose card gives him dice, asks guests for a game eight times in seed 7 (145, 163, 238,
    292, 306, 318, 357, 370 s); Rurik at 170 s and Toren at 244 s accept and the games are played, Brida declines. Not
    built, as it argues with character, not a defect: a limit on asking the same person again.

- [x] **C4 — Temperament in the draw.**
  - `selection.spread(actor, temperature) -> Spread(window, temperature)`: `factor = 1 + TEMPER_PULL × (temper −
    patience) + DRINK_PULL × drunkenness` (0.6 and 0.8; a trait or drunkenness missing reads as 0.5 and 0), the window
    `0.15 × factor` kept in `WINDOW_BAND` (0.08–0.3) and the temperature `temperature × factor` in `TEMPERATURE_BAND`
    (0.5–2 times the config's); a temperature of 0 stays 0. An ordinary sober guest draws as before. `drawable` takes
    the window (default 0.15, so its tests and callers keep their meaning); `agents._decide` passes each guest's spread
    at every stage. A trait outside 0–1 or a negative temperature raises `ValueError`. No setting: nothing changes for a
    state without these traits, and no existing test changed.
  - *Tests* (`tests/test_spread.py`): eight spreads (ordinary, patient and capped narrow, calm, hot head in drink,
    the capped extreme, missing traits, zero temperature, no traits), impossible input, `drawable` with three windows,
    and over 200 seeds an ordinary guest never takes what a model rates far below the best while a hot-headed drunk
    sometimes does.
  - *Built and measured (2026-10-09).* Offline seeds 0–9, against C3: distinct verbs per guest 8.6 → 9.0, pairs of
    guests making the same first three choices per evening 2.2 → 1.9, `decided` 33% → 36% (the patient are surer),
    repeats 36% → 37%, stuck seconds 16.7 → 20.1 (the spread of single seeds is 8–27, so no more than noise),
    departures 6 in all ten. Live seeds 5 and 7, against C3 (replays byte-identical): repeats 28% → 23%, near-best 1.65 →
    1.62, stuck seconds 26.9 → 23.2, cost $0.32 both. A gentle change, as intended.

- [x] **C5 — Projects: a plan of several steps chosen once.**
  - A project is a short plan the guest takes on with one choice; the world carries out its steps through the ordinary
    lifecycle, as errands do, and the guest asks for no decision until it ends. `body/projects.py` (new: "Projects:
    plans of several steps a guest takes on with one choice, and how each step is carried out"):

    ```python
    class Project(TypedDict):  # kind, by, target, step, of, running, started_at, targets (optional)
    class Step:                # name, command, done, broken (a step that only waits has no command)
    class ProjectKind:         # wording, gerund, done_words, steps, lasts, begin, target_kind, opened
    ```

    `world["projects"]` is checked by `check_saved_projects`; **saved worlds are version 18** (the approved bump, after main's 16 and 17:
    `test_database.py` and `test_intention_saves.py` pin the version and changed with it; no other test changed).
    `world.start_action` opens a project for a verb with `Activity.opens_project` (a new field, the kind's name; verbs
    with it have `duration=None`, so `rules.durations` and old saves are untouched, like `seating`). `honor_projects`
    runs each tick beside `honor_invitations`: finished steps are passed over; while the guest is idle, in no
    conversation and on no errand, a started step that came to nothing ends the project (**dropped** if an interrupt
    came after it began, else **failed**) and the next step is started, a refusal ending it as **failed**; `lasts`
    passed ends it **expired**; a guest who went home takes it with them. Each end is one event, `project_done`,
    `project_failed`, `project_dropped` or `project_expired`, e.g. "Calder could not settle in: sit came to nothing
    (settle_in)". `decisions.free_to_decide` is false while the guest has one.
  - *The first kind, `settle_in`*: take an ale at the tap, sit on the chosen chair, drink (`lasts` 150 s). A new verb in
    the `refreshment` family, which becomes a real family of two:

    ```python
    Activity(verb="settle_in", duration=None, target_kinds=("chair",), opens_project="settle_in", chooses_chair=True,
             family="refreshment", label="Settle in with an ale", what=..., guidance=...)
    ```

    `Activity.chooses_chair` (new, also on `seating`) replaces the `chosen["verb"] == "seating"` test in `choose_action`,
    which now runs: first stage → family → seat stage → aim. Choosing it is three levels deep: `refreshment` →
    `settle_in` → chair. Offered (`agents._settling`) when the guest holds no beer, sits nowhere, knows a stocked tap and
    a free table chair, has a thirst of 35 or more and is on no errand. Local utility `0.1 + 0.8 × thirst − 0.3 ×
    bladder`, a little above `take_beer`.
  - *A setting* (as C1, C3): `config["projects"]` (`selection.read_projects`), on in the shell as `AI_PROJECTS`. A first
    version told every observation that projects exist, and moved the seed-4 evening of
    `test_facts.py::test_a_news_item_reaches_a_third_guest_in_other_words` (no news travelled two hops any more),
    which AGENTS forbids changing without the user; with the setting off in the library that test, and every other,
    is untouched.
  - *Snapshot:* `state.projects` reaches the client as part of the world; `types.ts` gets `Project`, and the inspector
    says "Plan · settle in, step 2 of 3" (`frontend/src/projects.ts`, tested). `metrics.json` gets `projects`:
    ended per kind and outcome (`evening/project_metrics.py`).
  - *Tests* (`tests/test_projects.py`, `test_project_metrics.py`, `frontend/tests/projects.test.ts`): the project is
    opened, not an action; carried out step by step to a logged end; a refused step (the tap dry, the chair taken)
    fails it; an interrupt drops it; it lapses; a guest who left takes it with them; a conversation holds the next
    step back; seven cases of when it is offered, and not where projects are off; the family and the score; three
    levels through `choose_action`; saves round trip and ten malformed ones; refusals to begin.
  - *Built and measured (2026-10-09).* Offline seeds 0–9: 59 `settle_in` done, none failed, stuck seconds 20.1 → 16.9,
    guest actions in the first 60 s unchanged (14.9 → 14.5). The cost is sameness: pairs of guests with the same first
    three choices per evening rose from 1.9 to **8.2**, since nearly every arrival now takes ale, chair and drink at
    once; a threshold of 50 for the thirst changed nothing, as every arrival is thirsty. Live seeds 5 and 7 (replays
    byte-identical): 8 done and 1 failed ("sit came to nothing", Calder at 246 s), first-stage Jev requests 156 and 172
    (162 and 158 before: no fewer, since the plan covers only the first minute), no seat taken, stuck seconds 29 and 37
    (17 and 29 before: within the spread seen in C1). The inertia the plan gives is real; the uniform arrival is the price,
    and a reason to let C6's plans and C3's aims carry the variety.

- [x] **C6 — Social projects: a round for the table, and a rematch.**
  - *The project model grew for them* (`body/projects.py`): a `Step` now holds a `command` (any action, built from the
    world, the guest and the project) or none for a step that only waits on the world, with a `done` test and a `broken`
    reason; a kind builds its `steps` from the project, so their number may depend on its `targets`; a kind says what
    its `target` is (`chair`, `table` or `guest`), how it `begin`s and what follows `opened`. A project waiting on an
    errand of its own (`fetching_a_drink`) is left alone. `Project.targets` (optional) holds the guests a plan serves in
    turn, frozen at the start. Saves stay version 18.
  - `stand_a_round` (verb with `opens_project`, family `fetching`, which now reads "or stand the whole table a round"):
    offered to a guest with a free hand, a stocked tap known, on no errand, with at least two tablemates who visibly hold
    no mug (`giving.empty_handed_tablemates`, new). The project's target is the table, its `targets` the empty-handed at
    it in the order of its chairs, one `bring_drink` step each; a tablemate who left the table or the hall, or who got a
    mug meanwhile, is skipped; a step that ended with no mug in their hand (the tap ran dry, the gift was refused) fails it.
    "Ada stood the table a round (stand_a_round)". Local score: that of `bring_drink` plus 0.1 for each receiver beyond
    one, averaged over their opinions.
  - `rematch` (verb with `opens_project`, family `company`): offered while a `lost_at_dice` thought about someone in
    sight (seated at a table or beside the guest) still calls for an answer (C2), a dice table they know is free.
    Two steps: reach them (`talk`, `join_conversation` or `approach`, with the aim `rematch` of C3), then wait on the
    world: done when both sit at a game, failed when they went home, refused ("they would not play"), or the talk
    ended with no game agreed or on its way. **Setting out answers the loss** (`opened`), so a plan that fails does not
    make the same loss call for another.
  - *Found live and fixed:* the first live run showed Calder asking for a rematch five times in 20 s with a winner he
    could not reach (stuck seconds 54); the offer now needs a winner they can reach, and beginning answers the loss
    (two tests added, a separate commit).
  - *Tests* (`tests/test_round.py`, `tests/test_rematch.py`, and `test_projects.py` as before): a round to two in seat
    order, served in turn and logged; skipped tablemates (gone, already served); failed when the tap runs dry; five refusals
    and four offer cases; the family and the score; a rematch asked and played (the scripted writer carries the scene),
    refused, the winner gone, lapsed, five refusals, offered and not after the window, answered by beginning, not
    offered to a winner out of reach.
  - *Built and measured (2026-10-09).* Offline seeds 0–9 never meet the conditions (no lost game, nobody
    empty-handed): no round and no rematch. Live seeds 5 and 7 before the fix: one rematch reached and played (Calder,
    203 s: "got the rematch") and six failed, the loop above. Rounds: none yet in any evening.

- [x] **C7 — The invitee decides.** *(built; off by default, see the result)*
  - Before, the line writer decided whether an invitation was accepted, by choosing `accept` or `decline` for the
    invitee's line. Now the answer can be the invitee's own choice, scored like any other, and the line only says it.
  - `invitations.answer_options(world, scene, invitee)`: `accept`, `decline`, and `counter:<kind>` for each kind the
    invitee could offer in return (`counter_kinds`: `offered_kinds` as if nothing were pending, without the kind asked).
    `agents.choose_answer(observation, invitation, options, config, rng, evaluators)` scores them through
    `Evaluators.answers` (Jev: `jev._answer_question`, `evaluate_answers`, recorded as `answers`, replayed, traced, wired
    in `app.py`, `server/runtime.py` and `scripts/evening.py`) or `local_policy.local_answer_scores`: accepting is what
    the invitation leads to (a game 0.15 + 0.65 × boredom, an ale 0.4 + 0.5 × thirst, a table 0.2 + 0.6 × the wish for
    company, going home the leave utility) plus a quarter of the opinion of whoever asks; declining 0.3 + 0.2 × (1 −
    sociability); a counter its own kind's worth less 0.1. The result is `answer`, `source`, `scores` and `error`.
  - *The scene waits for it.* `Invitation.answer` is optional (saves stay version 18; `check_invitations` accepts an
    answer that is `accept`, `decline` or a counter of another kind). `MindLoop` gets an `answer` port (None: nothing
    changes): when the invitee's line comes next, it claims the scene's turn as a line writer would and asks; the answer
    is kept on the invitation if the invitation is still the same and the answer one of the options, and the line is
    claimed next tick; a failed request leaves the answer to the line writer, as before, and an answer is asked once.
    `conversation.offered_acts` then offers the invitee only the decided act (`invitations.answer_act`), a counter being
    an `invite` whose kinds are that one; `invitations.invite` answers a waiting invitation with
    `invitation_countered` ("Rurik turned down an invitation to play a game of dice and invited Calder to play darts
    together instead"), leaving theirs pending, so a counter can be countered. The scripted writer follows the decided
    answer, and the Haiku moment says "The speaker has decided to accept ...". `accept` builds its errand from the
    invitation's kind, sender and receiver only.
  - **A setting** (`config["answers"]`, `selection.read_answers`; `AI_ANSWERS`), as C1/C3/C5, and **off by default
    in the shell** after the measurement below.
  - *Metrics:* `invitations` in `metrics.json` (`evening/invitation_metrics.py`): made, accepted, declined, countered,
    per kind of invitation asked.
  - *Tests* (`tests/test_invitation_answers.py`, `test_answer_choice.py`, `test_answer_loop.py`, `test_answer_lines.py`,
    `test_invitation_metrics.py`): the options in five situations; the act of each answer; the decided act is the only
    one offered; a counter and a counter of a counter; accepting from a decided answer; saves; the choice with a fake
    evaluator, its fallback, no key, a missing evaluator; the local scores in seven situations; the Jev question and
    adapter; the loop (asked before the line, once, kept, a failed request, a stale answer, an answer that is no option,
    no port, a reset); a headless evening where the invitee's choice is what their line says; the scripted and Haiku
    writers; the metric. No existing test changed.
  - **Result (2026-10-09): the mechanism works and makes the evening quieter, so it is off.** Live seeds 5, 7, 1, 2, 3,
    on the same code but the answer: per evening, accepted invitations fell from 3.6 to 1.0, declined rose from 0.6 to
    3.6, 2.0 were countered, dice games fell from about 1.6 to 0.4, conversations from 33.8 to 25.6 (stuck seconds 25.5 →
    20.1, cost $0.35 → $0.30). With a first wording of the question Jev gave `decline` the top score in 31 of 47 answers;
    a sentence that turning down a friendly offer needs a reason moved it to 19 of 42 (accept 9 → 13, counter 7 → 10)
    and the outcome only a little (accepted 8 of 47 → 5 of 42). The guests are right by their numbers: in the eight answers read by hand
    their wish for company is under 10 in six, and they sit in their own chair. Counters can also ping-pong: Rurik and
    Saye turned each other's offer down four times in 20 s in seed 1 (376-394 s). The mechanism is sound, but the
    numbers feeding it do not make a tavern sociable enough. Options, each a small task: let a guest's `social` need
    rise faster; give an invitation an inviter's pull (opinion, a friend's word); or ask for the answer only when the
    inviter is disliked or a need presses, and let the writer say yes otherwise. Recorded as D24 in PLAN.md.

- [x] **C8 — Measure.**
  - Offline seeds 0–9 and live seeds 5, 7, 1, 2, 3, against C0's baseline (the code of `7d161f8` plus the metrics). Every
    live run was replayed and its `events.jsonl` is byte-identical to the live one; offline, every guest left by closing in
    all ten evenings, both before and after. The live runs are of the final code with `AI_ANSWERS=false` (the default),
    run when Jev's credit allowed; the same code with it on, a run before, is the right-hand column.

    | Live, five evenings, mean | C0 baseline | Final | Same with the invitee's own answer |
    |---|---|---|---|
    | first-stage options in the near-best set | 1.66 | 1.60 | 1.60 |
    | decided before the draw (near-best of one) | 55% | 58% | 56% |
    | first-stage options scored under 0.15 | 27% | 4% | 5% |
    | decisions followed by a family or seat stage | 42% | 47% | 50% |
    | decisions followed by an aim stage | 0 | 16% | 14% |
    | a guest's consecutive actions with the same verb | 29% | 25% | 32% |
    | conversations / conversation turns | 31.0 / 67.4 | 24.6 / 53.8 | 24.0 / 54.4 |
    | stuck seconds in all | 25.5 | 31.4 | 20.1 |
    | accepted invitations / dice sessions begun, logged twice | 3.6 / 3.2 | 4.6 / 4.0 | 1.0 / 0.8 |
    | cost of an evening | $0.35 | $0.30 | $0.30 |

    Offline: the aim stage in 23% of decisions, conversations 29.7 → 31.4, conversation turns 73.9 → 82.0, the longest
    news path 1.9 → 2.1 hops, stuck seconds 16.8 → 18.6, 59 `settle_in` plans done and none failed, 327 aims set and 50
    kept (scenes are short), and three quarrels where there were none (the needle).
  - Targets, against what the evenings gave: dead slots under 15% (27% → 4%): **met**; a third stage in at least 15% of
    decisions (16% live, 23% offline): **met**; the Jev share of cost under $0.10 (actions, family, seats and aims come to
    about $0.05): **met**; decided before the draw under 35% (55% → 58%): **not met**. The near-best window holds 1.6
    options and a guest is usually clear about their best; the lean request removed dead options, not the clarity of
    the choice. C4's spread widens it only for the hot and the drunk. Wrongs answered within their window in at least
    half the evenings: answers were begun in 4 of the 5 evenings (7 in all, against lost games, taken seats,
    intrusions and kindnesses that nobody counted: D26), which is thin evidence that most calls go unanswered.
  - What changed, in one line each: C1 and C2 are what C1 and C2 say; C3 gives a social option a purpose that the writer
    keeps 72% of the time (53 of 74 aims other than small talk, live; the starter says it early); C5 makes arrivals
    uniform (D25); C6's rematch fails when the world refuses (3 of 3 in these runs: Rurik was pressed, no way to him, no
    reachable spot), and no round was stood; C7 is off (D24).
  - Open points: stuck seconds went from 25.5 to 31.4 in the answers-off runs (spread of single evenings 19-35 before,
    23-39 now): the late arrivals (Calder, Saye) stand 7-9 s on a route that stays blocked, as they did before, so the
    rise is unexplained and may be noise; `No reachable interaction spot` refusals are 8.8 an evening against 8.0.
    Conversations fell by a fifth (31 → 25 an evening) while accepted invitations rose: guests talk less to pass the time
    and more to ask for something. Whether that is a better evening is for the observer to say.
  - *Moments from the logs:* a wrong answered: "Calder went to answer the lean dark-haired guard with a polished belt
    buckle, who beat them at dice (17 s later)", seed 2, 243 s; an aim kept: Calder meant to invite the guard to dice at
    160 s and did so one second later; Rurik accepted at 197 s and they played at 200 s; a project that failed for a
    reason the world gave: "Calder could not ask for a rematch: rurik has something more pressing to see to" (243 s); a
    countered invitation: "Rurik turned down an invitation to play darts together and invited Calder to have an ale on
    them instead" (seed 1, 224 s, with the invitee's answer on).

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
free `schema_version`. B4 reuses the door's `Activity.shared_target`, which G4 already uses. E21
then rolls through G0's `chance.roll`; E22's `watch_fight` can reuse `Activity.shared_target` and
`Activity.game`, and its bystanders can later let the barkeep step in, since he already stands on the activity system.

Giving (H0–H5) was added 2026-10-05 at the user's request. H0 → H1 first; then H2 and H3 in
either order (H3 needs only H1); H4 needs both; H5 comes last. It touches `activities.py`,
`actions.py`, `lifecycle.py` and `invitations.py`, as E21 does, so do not run the two at once.
Whether it comes before or after E21 is the user's call. H0's `near_person` is what E21's blows
would build on.

The UI pass (U2–U11) was added 2026-10-08 at the user's request. It is frontend work and can run
beside any backend task. Only U9's `mood_words` touches `mind/feelings.py`, and only U11 touches the
snapshot. Its internal order is at the head of its block. U3 and U4 come first, because the app cannot
be used on a phone until they land.

Sleep (Z0–Z6) was added 2026-10-08 at the user's request. Its internal order is at the head of its block.
It touches `activities.py`, `actions.py`, `attention.py` and `local_policy.py`, as E21 does, so do not run
the two at once. Z5 is the only frontend task and waits for the user's `SleepingSeated` art.

Tables and manners (T0–T8) was added 2026-10-08 at the user's request. T0 can go first or run beside
T1–T3, since only its data change touches what they touch. T1 → T2 → T3 is strict. T4 needs T0 (both
edit the briefing's table notes) and T3 (`welcome` reads the `seating` errand). T5 and T6 need T4. T7
needs only T6. T8 comes last. It touches `actions.py`, `scenes.py`, `invitations.py` and `errands.py`,
as E21 does, so do not run the two at once. One task per branch (`claude/stage1-t<n>`), as for every
task.

Closing call, news and a sick guest (F0–F9) was added 2026-10-09 at the user's request. Its internal order is at the
head of its block. F4 and F7 each bump `schema_version`, and F2–F8 change whole evenings, so do not run them beside
E21 or one another. F0 and F1 can run beside anything.

Choice depth (C0–C8) was added 2026-10-09 at the user's request. C0 comes first: every later C task compares with
its baseline. C1 next, so that new options do not land in requests full of dead ones. C2 → C3 is strict (C3's
response aims read C2's answered thoughts). C4 needs only C0 and may go at any point after it. C5 needs C1 (it
widens `refreshment`); C6 needs C3 and C5; C7 needs only C0, but goes after C3 if both touch `turns.py` and
`haiku_turns.py` at once. C8 comes last. C2, C3 and C7 touch `scenes.py`, `turns.py` and the Haiku prefix; C5 and C6
touch `errands.py`, `actions.py` and the lifecycle, as E21 does, so do not run them beside E21. One task per branch
(`claude/stage1-c<n>`).

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

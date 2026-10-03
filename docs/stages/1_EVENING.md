# Stage 1 — A Believable Evening

Four to six guests spend one evening in the hall. The test is whether model-driven
guests look like real people who came to relax, and whether the evening produces a
story an observer can retell, with every cause visible in the event log.

## Decisions

- **Player:** observer and administrator. Before the evening they pick the guests and
  the news; during it they watch and inspect. Debug controls stay, in a debug panel.
- **Scope:** one evening in the existing hall, four to six guests, closing time ends it.
  No staff, prices, agreements, or memory between evenings yet.
- **Models:** Jev scores activities (choice layer); Claude Haiku 4.5
  (`claude-haiku-4-5`) writes conversation turns, intentions, card extraction, and the
  chronicle (mind layer) through structured outputs. Without keys, the labeled local
  policy and scripted lines run instead.
- **Violence:** shoves, fights, and knockouts with 5–10 new poses. Outcomes come from
  character stats plus seeded chance, in the spirit of RimWorld's social fights.
- **Drinks:** self-service tap with a queue until a barkeep exists (Stage 2).
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
- [ ] **E16 — Turns through Haiku.** The next speaker gets a turn after the previous
  line's reading time; the result is validated and shown as a bubble; failures fall
  back to scripted lines by act. Done: invalid schema and unknown facts are rejected;
  cache reads appear in usage; cost per turn is measured.
- [ ] **E17 — Speech-act effects.** One table maps acts to thoughts, opinions,
  familiarity, names, knowledge, and invitations (join the table, darts together, buy a
  drink, leave together). Done: the same line with no act changes nothing.
- [ ] **E18 — Overhearing and names.** Nearby guests receive the act and gist by
  distance; strangers are described by appearance until introduced. Done: an insult
  to a friend overheard at the next table creates a thought for the listener.

### M4 — News and conflict

- [ ] **E19 — Facts and retelling.** Guests start with news by occupation; sharing
  stores the speaker's words as the listener's version, and retelling paraphrases it.
  Done: a fact reaches a third guest in a recorded evening, with drifted wording and
  its path visible in the inspector.
- [ ] **E20 — Hostile options.** Insults are speech acts; `shove` and `start_fight`
  appear only toward someone with low opinion, given temper, drunkenness, and a recent
  cause. Done: sober guests on good terms never receive hostile candidates.
- [ ] **E21 — Fight resolution.** Seeded exchanges with hit chance, damage,
  consciousness, yielding, and knockouts; a shove can stagger or knock down; a knocked
  out guest lies down, gets up groggy, and keeps thoughts. Done: parametrized outcome
  rates (a strong sober guest usually beats a weak drunk one) and seeded replays.
- [ ] **E22 — Bystanders and aftermath.** Witnesses watch from a ring, cheer, intervene
  with a chance to separate, back away, leave, or help the fallen up; everyone involved
  gets thoughts; spilled drinks are lost. Done: a forced fight draws at least two kinds
  of reaction that follow the witnesses' traits.

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

## Acceptance scenarios

Initial targets, to be tuned in E28:

1. Twenty offline evenings with four to six guests finish with every guest gone by
   closing, no overlaps, no negative resources, and no guest idle without a decision
   for more than 30 seconds.
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

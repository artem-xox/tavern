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
  `guidance`, and an optional named handler for effects that need code.
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

- [ ] **E01 — Activity table.** Move every verb's target kinds, duration, effects,
  interruptibility, model descriptions, and pose into one declarative table passed
  to the world; world, candidates, briefing, Jev, and frontend read it. Done: all
  existing tests pass unchanged; a new verb needs one entry and an optional handler.
- [ ] **E02 — Model gateway.** One async boundary for Jev and Claude with recording,
  replay, a test fake, and usage accounting. Done: a recorded evening replays to an
  identical event log; cost per call kind is reported.
- [ ] **E03 — Headless evening runner.** `make evening` runs a scenario to closing in
  lockstep (local, live, or replay) and writes the event log, metrics, chronicle, and
  cost. Done: an offline evening finishes in seconds and reports stuck time per guest.
- [ ] **E04 — Scenario.** Staggered arrivals, starting relationships, news, timed
  world events (a traveler with fresh news), and closing time that sends guests home.
  Done: a six-guest scenario arrives over time and the hall empties by closing.

### M2 — Body and choice

- [ ] **E05 — Queues.** Tap, WC, and darts get capacity and queue spots; guests join,
  advance, give up after patience, and leave the line on interrupt; `cut_in_line`
  gives thoughts to those behind. Done: five guests at one tap form a line without
  overlaps or stuck reservations; an impatient guest gives up.
- [ ] **E06 — Stimuli and hearing.** Activities and events emit stimuli; perception
  applies distance and wall damping; salience adds relevance (me, a friend, my name)
  and temperament. Done: parametrized cases show a fight heard from the WC and a quiet
  remark not heard across the hall.
- [ ] **E07 — Attention and interrupts.** Below the threshold a guest glances; above
  it, an interruptible activity pauses, the guest turns to the source, and a choice is
  requested with the trigger in the briefing. Done: a drinking guest turns within
  0.5 s of a shout; a guest in the WC finishes first.
- [ ] **E08 — Gaze and emotes.** Facing follows the current speaker, arrivals at the
  door, and stimulus sources; emotes mark alerts, confusion, anger, affection, sleep,
  and long waits. Done: tests on facing choice and emote lifetimes.
- [ ] **E09 — Bounded choices.** Jev chooses an activity family first and a target
  second, generalizing seating, so requests stay small as guests and verbs grow.
  Done: candidates per request stay under a fixed limit with six guests; tokens per
  decision are measured against Stage 0.

### M3 — Characters and conversation

- [ ] **E10 — Character cards.** Schema, validation, and eight presets with distinct
  temperaments and goals, plus two starting relationships. Done: invalid cards fail
  loudly; the briefing includes the goal and temperament.
- [ ] **E11 — Card compiler.** Haiku extracts params from a free-text card through
  structured output; values are range-checked and shown for confirmation. Done:
  malformed or out-of-range answers are rejected; the offline mode is labeled.
- [ ] **E12 — Thoughts, mood, opinions.** Events create timed thoughts with mood and
  opinion effects; opinions and familiarity are kept per pair. Replaces grievances.
  Done: stacking, expiry, and opinion changes are tested; the inspector lists thoughts.
- [ ] **E13 — Drunkenness.** Beers raise drunkenness by tolerance; it decays slowly;
  stages change inhibitions, speech instructions, gait, and fight accuracy. A wasted
  guest may doze at the table. Done: parametrized stage and decay tests.
- [ ] **E14 — Intentions.** Haiku writes a one-sentence intention on arrival, after
  salient events, and every few minutes; the briefing shows it to Jev. Done: in a
  recorded evening an insult changes the target's intention and later choices.
- [ ] **E15 — Conversation scenes.** `talk` starts a scene for seated tablemates or
  guests standing side by side (queue, fire); others join or leave; it ends by act,
  satisfied need, or interrupt. Done: a three-way conversation survives one member
  leaving for the WC.
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

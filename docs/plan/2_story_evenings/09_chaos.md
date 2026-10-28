---
id: S2-09
title: Chaos
status: done
needs: [S2-04, S2-05]
touches: [social/quarrels.py, social/conversation.py, social/turns.py, social/hostility.py, social/ties.py, social/social_acts.py, mind/fight_candidates.py, mind/turn_prompt.py, characters/guests/]
---

# S2-09 — Chaos

## Why

Two political rivals at one table should end up yelling at each other, and sometimes fighting. In Stage 1
fights were rare by design: six live evenings had none and not one insult (D27). The cause is missing, not
the gate: guests never start with bad blood, and the writers avoid insults.

Since S2-13 the Guests insult each other, but a quarrel has no way out (D28): an answered insult only carries
the talk on, so two rivals trade the same jabs for minutes and nothing follows (seed 5, 2026-10-25: Trump and
Musk, 27 insults in a row, 70 quarrels, no fight). More grudges without an exit would only make longer loops,
so the exit comes first.

## Scope

- In, first: a quarrel boils over. After a few answered insults between the same two, the talk ends in an
  event: a fight when one of them is hot enough for it, else one of them storms off. This closes D28.
- In: starting relationships between guests carry a grudge with a reason ("rivals", "owes me money"),
  and a grudge is enough cause for an insult or, when drunk, a fight. This closes D27.
- In: a `shout` act: a loud insult that every guest in earshot hears and turns to. It can become a
  shouting match between two guests.
- In: the line writer is told that rivalries are the point, and plays them; insults may be harsh.
- In: provocation: a guest can deliberately needle a rival to start something.
- Out: new fight mechanics (Stage 1 fights stay as they are). Out: settling a quarrel with a bet or a game of
  dice; it waits until the boil-over shows in live evenings how often a quarrel ends in a walk-off.

## Shape

### Boiling over (D28), in a new `social/quarrels.py`

- **Heat** is not stored: it is read from the scene's `turns`. It is the length of the run of `insult` turns at
  the end of the scene, spoken in turn by the same two guests, each to the other. Any other act breaks the run.
  The saved world does not change.
- `BOIL = 4`: the insult that makes the run 4 long (two each) boils the quarrel over, right after its own
  effect (`conversation._insult`, one call at its end).
- **How it ends**, decided by rules, with no randomness:
  1. A fight, when either of the two could start one against the other by the existing gate
     (`hostility`: drunk and hot, or hating and hot enough). If both could, the one with the greater `urge`
     attacks; if equal, the last insulter. The game opens it with `fights.open_fight`.
  2. Otherwise the one insulted last, who would answer next, storms off: they are left with the last word
     against them.
- Either way the scene ends unpleasantly (`end_conversation(pleasant=False)`), and both quarrel thoughts are
  marked `answered`, so neither goes straight back to start the same quarrel again.
- New event `stormed_off`, logged for both: "Musk stormed off from Trump". A fight logs `fight_started` as now.
- New `hostility.may_fight(actor, other_id, now) -> bool`: the existing `start_fight` gate for one person,
  without the observation, so the observation path and the boil-over share one rule.

### Model view

- `conversation.heat: int` in the turn view: how many insults the run holds. At `BOIL - 1` the line writer's
  per-moment text says one more insult boils the quarrel over, so it can land a last jab or back down. The
  insult meaning stops saying "a quarrel that ends the conversation" (it did not) and says what happens at `BOIL`.

### Score and metrics

- `stormed_off` joins `story_score.WEIGHTS` at 1.5, below a fight and a quarrel, so `metrics.json` counts it
  under `story.moments` with no change to `Metrics`. The client shows an unknown kind with its fallback chip.
- The longest insult run of an evening is not a metric: the log carries the acts only inside a `turn` event's
  words. A live run is checked by reading `events.jsonl`.

### Grudges (step 4, saves are version 20)

- An optional `grudge: string` (a reason in words, never empty) on a starting relationship: a shared tie
  (`Tie`, from a character's `relationships` or a scenario's), an entry of the regard matrix in
  `characters/guests/relationships.json` (`Regard`), and so on the tie a guest holds (`OwnTie`, saved in
  `actor["ties"]`). Absent when there is none, not `null`. The held tie is the only saved place, so the saved
  world is `schema_version` 20 (approved by the user), checked by `ties.parse_own_ties`.
- A grudge against someone is a cause that never goes stale: `hostility._caused` is true for them, so a shove
  or a fight needs no fresh insult or quarrel. The other gates are unchanged (an ill opinion, the urge,
  the same table or side by side), so a grudge alone makes nobody fight.
- Insults need no grudge: they are open to anyone who thinks `DISLIKED` of the other (`conversation`).

### Shout and the writer

- `shout`, an act of `ACTS` and an insult flung across the hall: it does what an insult does
  (`conversation._insult`, so the same thoughts, offence and answer in kind) and counts in the heat of a row
  (`quarrels.ROW_ACTS`). It is offered while the speaker thinks `DISLIKED` of someone present and a row is on
  (`quarrels.heat > 0`) or they hold a grudge against that person (`hostility.grudge_against`).
- It sounds as a shout: loudness 0.7 and reach 30 cells (`overhearing.TURN_SOUNDS`), past the interrupt level, so
  every head in the hall turns and what can be broken off is. An insult stays 0.4 and 14. An insult answered in
  kind also logs a `quarrel`, which is loud already; the shout matters for the one that is not answered.
- Far listeners take offence at a shout as at an insult (`overhearing._catch`).
- The shared prompt says a rivalry is played to the end and an insult may be harsh and personal, about the
  other's public record; the portrait of a guest tells the grudge they hold (`portrait`).
- Provocation needed no new rule: the `needle` aim (`aims.py`) already sends a guest who dislikes someone to
  needle them, and a grudge keeps that dislike alive.
- The famous guests bring six grudges (`characters/guests/relationships.json`): Putin and Zelensky of each other,
  Zelensky of Trump, Trump of Zuckerberg, and Musk and Zuckerberg of each other.

## Steps

1. Heat: a run of insults between the same two is counted; another act or a third speaker breaks it.
   Check: `pytest tests/test_quarrels.py -k heat`.
2. Boil-over: at `BOIL` the scene ends in a fight when the gate allows, else in a walk-off; below `BOIL`
   nothing changes. Check: `pytest tests/test_quarrels.py`, `tests/test_conversation.py`.
3. `heat` in the turn view and the writer's warning, the insult meaning, `stormed_off` in the score. Done.
   Check: `make check`; offline evenings seeds 1, 5, 7 unchanged (no scripted quarrel reaches the boil); a live
   seed 5 and its replay still wait for a key.
4. Grudges: a pair with a grudge has hostile options without a fresh cause; without one, nothing changes. Done
   (the field and the gate); which pairs hold one is data, still to fill.
5. `shout` act and its sound; far listeners react. Done.
6. Writer prompt and the portrait; provocation was already the `needle` aim. Done.
7. Five live Guests evenings: count quarrels, shouts, walk-offs and fights. Done (Results).

## Done when

- `make check` passes; no live Guests evening has an insult run longer than `BOIL` (read from `events.jsonl`).
- In five live Guests evenings at least four have a quarrel and two have a fight (Results).

## Results

Built (steps 1–6): the boil-over (`social/quarrels.py`), `heat` and a warning for the writer, `stormed_off` in the
story score, the `grudge` field with saves at version 20, six grudges in the data, the `shout` act, and the prompt
and portrait changes. `make check`: 4556 passed, mypy clean, 260 node tests.

Offline Guests evenings (scripted lines, seeds 1, 2, 3, 5, 7): unchanged by the grudges and the boil-over (the
scripted writer never reaches a run of four insults, and its drunk hotheads rarely stand by a rival).

Live Guests evenings (step 7, 2026-10-27, `make evening CAST=guests SEED=n`, seeds 1-5; Haiku lines, Jev decisions).
A quarrel and a fight log two events, one for each guest, so the fights below are halved:

| seed | `quarrel` events | fights | `shout` | `stormed_off` |
|------|------------------|--------|---------|---------------|
| 1    | 24               | 3      | 0       | 0             |
| 2    | 20               | 2      | 0       | 0             |
| 3    | 8                | 1      | 0       | 0             |
| 4    | 24               | 2      | 0       | 0             |
| 5    | 14               | 2      | 1       | 0             |

- All five evenings have a quarrel and a fight (done when: at least four and two). The replay of seed 5 gives a
  byte-identical `events.jsonl`.
- The boil-over works: in seed 1 Trump and Musk traded four insults and Trump hit Musk right after the fourth. No
  run of insults between two guests went past `BOIL`; the longest run seen (4 Tyson insults to Musk) had no answer.
- Not shown: `stormed_off` never happened (every boil-over found a hot fighter) and `shout` once. How often a
  quarrel ends in a walk-off, and the bet or dice settlement of the Scope, stay open.
- The cast of these evenings held Musk, Trump, Tyson, Sobchak, Vucic and Greta, so the grudges of Putin, Zelensky
  and Zuckerberg were not played; the fights came from the boil-over and the existing gate.

D27 and D28 are closed (their rows are out of `TECH_DEBT.md`).

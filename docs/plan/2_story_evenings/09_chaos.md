---
id: S2-09
title: Chaos
status: todo
needs: [S2-04, S2-05]
touches: [social/hostility.py, social/ties.py, social/social_acts.py, mind/fight_candidates.py, mind/turn_prompt.py, characters/guests/]
---

# S2-09 — Chaos

## Why

Two political rivals at one table should end up yelling at each other, and sometimes fighting. In Stage 1
fights were rare by design: six live evenings had none and not one insult (D27). The cause is missing, not
the gate: guests never start with bad blood, and the writers avoid insults.

## Scope

- In: starting relationships between guests carry a grudge with a reason ("rivals", "owes me money"),
  and a grudge is enough cause for an insult or, when drunk, a fight. This closes D27.
- In: a `shout` act: a loud insult that every guest in earshot hears and turns to. It can become a
  shouting match between two guests.
- In: the line writer is told that rivalries are the point, and plays them; insults may be harsh.
- In: provocation: a guest can deliberately needle a rival to start something.
- Out: new fight mechanics (Stage 1 fights stay as they are).

## Shape

- Relationship entry in `relationships.json` gains `grudge: string | null`.
- New act `shout` in the speech-act table with its loudness and thoughts.

## Steps

1. Test first: a pair with a grudge has hostile options without a fresh cause; without one, nothing changes.
2. `shout` act and its stimulus; bystanders react.
3. Writer prompt change.
4. Five live Guests evenings: count quarrels, shouts and fights.

## Done when

- `make check` passes; in five live Guests evenings at least four have a quarrel and two have a fight
  (Results).

## Results

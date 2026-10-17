---
id: S2-06
title: Obsessions drive goals
status: todo
needs: [S2-03, S2-05]
touches: [mind/intentions.py, mind/goals.py, data/minds/intention_prefix.md, mind/briefing.py]
---

# S2-06 — Obsessions drive goals

## Why

A famous guest should spend the evening chasing their obsession: the Trump parody tries to make someone
else pay, the Bush parody asks everyone who has oil. Today the mind sets typed goals from the card's single
`goal` sentence and the moment; obsessions are just text.

## Scope

- In: the intention prompt shows the guest's obsessions first and asks which one they pursue now.
- In: an intention names the obsession it serves; the inspector shows it.
- In: if an obsession needs a goal kind `goals.GOALS` lacks (for example "ask everyone about X"), add the
  smallest new kind, tested alone, in this task.
- Out: the fun an obsession brings when it is served (S2-07).

## Shape

- Intention answer gains `obsession: int | null` (index into the card's list), checked at the boundary.
- Saved intention keeps it; ask before the schema bump.

## Steps

1. Test first: `check_intention` accepts a valid index and `null`, rejects an index out of range.
2. Prompt change; prefix stays above 4,096 tokens.
3. Live Guests evening, seed 5: count intentions per obsession. Each guest pursues at least one obsession
   with an action the world validated.

## Done when

- `make check` passes; in a live Guests evening every guest acts on an obsession at least once (Results).

## Results

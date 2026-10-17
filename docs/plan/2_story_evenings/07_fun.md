---
id: S2-07
title: Fun
status: todo
needs: [S2-05]
touches: [body/activities.py, mind/local_policy.py, mind/briefing.py, mind/feelings.py]
---

# S2-07 — Fun

## Why

Guests should seek out the moments that make stories: a game, a show, a quarrel to watch, their own
signature act. Today `boredom` is a need that rises over time, and quiet activities relieve it as well as
loud ones, so the quiet ones win.

## Scope

- In: activities have a `fun` effect in the activity table: how much they relieve boredom. Watching a
  fight, cheering, playing together, a signature act and serving an obsession are high; sitting and
  drinking alone are low.
- In: the briefing says what would be fun; the local policy weighs it.
- Decide here, before code: reuse `boredom` (fun lowers it) or add a separate `fun` need. Prefer reuse
  unless a test shows the two must differ.
- Out: new activities.

## Shape

`Activity` gains `fun: float` (0–1), default 0. Freeze the values for every verb here as a table.

## Steps

1. Test first: an activity's `fun` lowers boredom by its amount over its duration.
2. Table values for every verb; the briefing words them.
3. Offline seeds 0–9 and live seed 5, both casts: story score before and after.

## Done when

- `make check` passes; the story score of both casts rises against the S2-05 baseline (Results).

## Results

---
id: S3-12
title: Acceptance
status: todo
needs: [S3-01, S3-02, S3-03, S3-04, S3-05, S3-06, S3-07, S3-08, S3-09, S3-10, S3-11]
touches: [docs/plan/3_player/12_acceptance.md, docs/plan/TECH_DEBT.md, data/players/]
---

# S3-12 — Acceptance

## Why

The stage's "done when" is a player line that changes how an evening's main incident ends, with the retelling
showing it. This task measures that, in evenings played by a person (the owner) and by scripts. It also checks
what makes a typed conversation feel alive or dead: readings the player would agree with, a short wait between
pressing Enter and the line being spoken, and no word ever said for the player.

## Scope

- In: three evenings played by the owner, four scripted live evenings, the measures below, and the findings
  written down here and in TECH_DEBT.md.
- Out: fixes. Every finding becomes its own task or a TECH_DEBT row.

## Shape

The measures, from `metrics.json` (`player`, S3-10), the event logs, and a reading by hand:

| Measure | Target | From |
|---------|--------|------|
| The main incident changed by a player line | in at least 2 of the 3 played evenings, and in 1 scripted evening | by hand: the incident (the quarrel, fight or stage moment the retelling builds on) and the player line that turned it, compared with a Guests evening of the same seed and lineup without a player |
| The retelling shows it | in each evening counted above | a chapter that cites that player line (S3-11) |
| Readings a person agrees with | at least 85% of the player's lines | the owner marks each read act right or wrong in a table (30+ lines) |
| From Enter to the line spoken | median under 2.5 s real time, 95th percentile under 5 s | timestamps of `say` and of the `turn` event, at speed 1 |
| Words said for the player | 0 | every `turn` event with `speaker` = the played guest has `player: true`, or is a `silence`, while steering |
| Silences that felt fair | the owner's call | the owner notes each `silence` turn: was the wait long enough? |
| Cost of a played evening | report it, no target yet | Claude usage in `metrics.json`, beside a Guests evening without a player |

## Steps

1. Scripted live evenings: `make evening CAST=guests SEED=<1,2,5,7> PLAYER=data/players/monroe_meddles.json`, plus
   one replay `cmp`. Record the measures.
2. The owner plays three evenings in the browser (`make run`) with a Claude key: Guests, a lineup of four to six
   with rivals among them, as a guest the owner picks. The runs are saved under `runs/s3-12-played-<n>/`: the
   event log, metrics and the retelling, through the debug panel's save or a small export, whichever exists.
3. For each evening: name the main incident and the player line that changed it (or say that none did); fill in
   the readings table and the silence notes.
4. Write the results, the measures table and three moments from the logs here. Add a TECH_DEBT row for each
   problem left behind (for example: a reading that keeps missing an act, a silence that comes too fast, a cost
   above the Guests budget). Decide whether `ignored` counts as a story moment.

## Done when

- The measures table is filled in and the first two rows meet their targets, or the owner accepts the gap in
  writing, here.
- The index marks Stage 3 done, or the remaining work is listed as new tasks.

## Results

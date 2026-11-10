---
id: S3-12
title: Acceptance
status: in-progress
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

Scripted half, 2026-11-08 (Jev + Haiku 5.5, Sonnet retelling; the owner authorized the Claude spend). The owner's
three played evenings are not done: their slots are empty below and the status stays `in-progress`. Stage 3 is not
marked done.

### How the scripted evenings were run

`make evening CAST=guests SEED=<n> PLAYER=data/players/monroe_meddles.json` **does not put Monroe in the hall**:
the Guests scenario has no Monroe, so all 8 script steps were refused (`the played guest is not in the hall`) and
`player.lines` was empty. Those four runs were thrown away (the command of step 1 needs a scenario, see D35). The runs below add
`SCENARIO=data/evenings/monroe_night.json` (Monroe, Putin, Trump, Tyson, Vucic, Sobchak), as `make golden` does, and
each seed has a twin with the same scenario and seed and **no** player (Monroe on her own mind).

Saved in `runs/s3-12-scripted-<seed>/` and `runs/s3-12-noplayer-<seed>/` (seeds 1, 2, 5, 7; `runs/` is gitignored,
copies are in the shared notes folder of the session) with `events.jsonl`, `metrics.json`, `calls.jsonl`,
`retelling.md`.

**Replay.** Seed 1: `make evening MODE=replay CALLS=runs/s3-12-scripted-1/calls.jsonl SEED=1 …` then
`cmp runs/s3-12-scripted-1/events.jsonl runs/s3-12-replay-1/events.jsonl`: identical (no output, exit 0).

### Measures, scripted

| Measure | Target | Seed 1 | Seed 2 | Seed 5 | Seed 7 |
|---------|--------|--------|--------|--------|--------|
| Script steps landed / refused (8 each; 3 of them are `say`) | – | 6 / 2 | 4 / 4 | 4 / 4 | 3 / 5 |
| Lines the player said (`player.lines`) | – | 1 (`compliment` to Putin, 74 s) | 0 | 0 | 0 |
| Main incident changed by a player line | 1 scripted evening | **no** (see below) | no line | no line | no line |
| Retelling cites a player line | where counted above | yes: chapter 1 cites #43, the line | no line | no line | no line |
| Words said for the player (`turn` of Monroe without `player: true`) | 0 | 0 | 0 | 0 | 0 |
| `silence` turns, `ignored`, `misread` | – | 0, 0, 0 | 0, 0, 0 | 0, 0, 0 | 0, 0, 0 |
| Claude usage (`metrics.json` `cost`, USD, no retelling) with the player | report | 0.105 (295 calls) | 0.152 (393) | 0.171 (484) | 0.118 (354) |
| The same seed and lineup, no player | report | 0.135 (369) | 0.173 (473) | 0.156 (412) | 0.151 (396) |

Cost: mean 0.137 with the player against 0.154 without; the player's evenings were cheaper in 3 of 4, because
nobody asks a model for the steered body (and the script said one line, one `reading` call). The retelling (Sonnet)
is not in `metrics.json`, so it is not in these numbers. No target exists yet.

**The target is missed.** "The main incident changed by a player line in 1 scripted evening": 0 of 4.

- Seed 1 is the only evening where a line landed. At 74 s Monroe told Putin "Vladimir, darling, you look lonely.
  Such a serious man." (`compliment`); at 78 s Putin answered (`boast`): "Sit, and I will show you how the people
  play dice", and at 222 s he set the goal "talk with Monroe". The retelling's first chapter cites the line (#43). But
  the evening's main incident was the pigeon-seat quarrel between Tyson and Sobchak (246 s) and Trump knocking
  Sobchak out (255-265 s, cause: drink), and nothing in the log ties that to the compliment. The twin without a
  player had no fight at all, but that is no evidence: the live models are not deterministic and the two evenings
  differ from the first minutes, so a difference cannot be put down to the line (D33).
- Seeds 2, 5 and 7: every `say` was refused with "Nobody is listening: join a conversation or climb the stage to say
  anything" (3 of 3 each), because the timed script's `talk` step at 70 s was itself refused (seeds 2 and 7: "Visitors
  must sit at one table or stand side by side"; seed 5: "Visitor is already in a conversation"). Of the 12 `say`
  steps in four evenings, 1 was spoken.
- The seed 7 `give_speech` at 500 s was refused ("Target is reserved by another visitor").

### Three moments from the logs

1. **A line answered (seed 1, 74-78 s).** Monroe's compliment, Putin's `boast` back, and a goal set 144 s later to go
   and talk with her. The guests take the typed line for the character and react to it; the effect stays local.
2. **Dead air on the stage (seed 1, 500-525 s).** The script chose `give_speech`; Monroe is steered, so no number is
   written for her (principle 3 held: 0 words), and the log says `stage_silent: Marilyn Monroe stood on the stage and
   said nothing` for 25 s. Correct by the rules, but a scripted player has no way to say a number (D32).
3. **A script that does not look (seeds 2, 5, 7, 70-130 s).** `talk` refused, then three `say` refused. The player
   spent the evening drinking, sitting and playing darts, an evening of an autopilot-less guest who says nothing.

### S3-11 live evidence

One chapter of a live retelling citing a player line (seed 1, `runs/s3-12-scripted-1/retelling.md`; `#43` in the
cited positions is the `turn` event `Marilyn Monroe to Vladimir Putin (compliment): Vladimir, darling, you look
lonely. Such a serious man.`, checked with `told(events)[43]`):

> The night began sweetly: Marilyn Monroe wandered in and grabbed a beer 🍺, then charmed the lonely-looking Vladimir
> Putin with a compliment 💋. Donald Trump arrived soon after and raised a toast to her as the woman who makes the
> tavern look like Mar-a-Lago 🥂.
> told from events #1, #5, #24, #43, #51

The chapter cites the line and names it as what it is ("charmed ... with a compliment"). The closing-screen
screenshot is not part of this evidence (see the open items).

### Played by the owner (to fill in)

How to export each evening (the debug panel's save keeps only the last 200 events and no retelling, so it is not
enough; `scripts/export_played.py` polls the server and keeps the whole log):

```bash
# browser console, once the evening starts:  localStorage.getItem('tavern.session')
PYTHONPATH=backend .venv/bin/python scripts/export_played.py --session <id> --out runs/s3-12-played-1
```

Start it at the beginning of the evening (the server keeps 200 events; the script polls every 3 s and loses
nothing unless the browser pauses for longer) and leave it running; it exits by itself when the retelling arrives and
writes `events.jsonl`, `metrics.json` (`player`, `story`), `retelling.md`, `snapshot.json`.

| Measure | Target | Played 1 | Played 2 | Played 3 |
|---------|--------|----------|----------|----------|
| Guest played and lineup | – | | | |
| Main incident changed by a player line (name incident and line) | 2 of 3 | | | |
| Retelling cites that line | each one counted | | | |
| Words said for the player (from `metrics.json`/log) | 0 | | | |
| Readings agreed (right / lines) | >= 85%, 30+ lines | | | |
| Enter to line spoken, median and p95 | < 2.5 s, < 5 s | | | |
| Silences: fair? (one note per `silence` turn) | the owner's call | | | |
| Claude usage | report | | | |

Enter-to-line latency is **not measurable from the logs**: the `say` command leaves no event, only the `turn`
(D34). Until it does, time ten lines with a stopwatch at speed 1 (Enter to the line in the chat) and write median and
worst here.

Readings table (one row per line the player typed; right = the act and the addressee were what the player meant):

| # | Line | To | Read as (act, addressee) | Right? |
|---|------|----|--------------------------|--------|
| | | | | |

### `ignored`: is it a story moment?

**Decision: yes.** `story_score` should count an `ignored` event as a moment, below a quarrel and equal to a heckle
(1.0). The stage's own rule says a guest left unanswered feels it ("that is story material"); a guest that was
spoken over, or not answered by the player they came to talk to, is the seed of a quarrel or a walk-off that the
score already counts, so leaving the seed out would make the retelling pick the effect and skip the cause. It
stays small because the player can farm it by doing nothing, and every `ignored` needs a witness (the guest who
was not answered), not just a quiet player. This is a decision from the design, not from evidence: the four
scripted evenings logged 0 `silence` turns and 0 `ignored`, because the script never held the turn open. The
owner's played evenings should show how often it fires; D36 holds the change.

### Open verification items for the owner

Nobody has looked at these in a browser:

- S3-09: the chat look (the scene's lines, the input, "To:", "your turn").
- S3-11: a live retelling on the closing screen with the gold bar and star on the chapter that cites the player's
  line, and the screenshot with the "You" face (the chapter text itself is in the evidence above).
- S3-07: the "you" arrow over the played guest.
- S3-08: the order menu on a click (the verbs open now).

### Findings

All in [TECH_DEBT.md](../TECH_DEBT.md): D32 (the timed script), D33 (no controlled twin), D34 (the `say` timestamp,
the played-evening log), D35 (`make evening PLAYER=` without a scenario), D36 (`ignored` as a moment).


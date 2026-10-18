---
id: S2-07
title: Fun
status: todo
needs: [S2-05]
touches: [body/activities.py, mind/local_policy.py, mind/briefing.py, mind/feelings.py, social/dice.py, body/drunkenness.py]
---

# S2-07 — Fun

## Why

Guests should seek out the moments that make stories: a game, a show, a quarrel to watch, their own
signature act, and a drink too many. Today `boredom` is a need that rises over time, and quiet activities
relieve it as well as loud ones, so the quiet ones win. Drinking follows thirst alone
(`drink: 0.9 × thirst + 0.1`), so nobody gets past tipsy: live g1–g4 have `fell_asleep: 0`. Dice are rare:
0–2 `played_together` an evening, and `dice_together` invitations score the same as darts.

## Scope

- In: activities have a `fun` effect in the activity table: how much they relieve boredom. Watching a
  fight, cheering, playing together, a signature act and serving an obsession are high; sitting and
  drinking alone are low.
- In: drinking in company and dice are pushed: guests drink past thirst when the company is good, and the
  bold and the drunk gamble.
- In: the briefing says what would be fun; the local policy weighs it.
- Decision: reuse `boredom` (fun lowers it). A separate `fun` need is added only if a test shows the two
  must differ.
- Out: new activities; signature acts (S2-08); escalation of quarrels (S2-09).

## Shape

`Activity` gains `fun: float` (0–1), default 0; the boredom an activity relieves is `fun × FUN_RELIEF`
over its duration, replacing its hand-set `boredom` entry in `needs`. Frozen values:

| Verb | fun | Verb | fun |
|------|-----|------|-----|
| `play_dice` | 0.9 | `watch_dice` | 0.6 |
| `play_darts` | 0.7 | `stand_a_round` | 0.7 |
| `drink` (with company at the table) | 0.4 | `drink` (alone) | 0.1 |
| `talk`, `join_conversation` | 0.3 | `stand_at_bar` | 0.3 |
| `watch` (fire or view) | 0.2 | `sit`, `rest`, `wait` | 0 |

`drink` in company needs a modifier; the table holds the alone value and `local_policy` adds company.
No save or snapshot change; the activity view for the client gains `fun` only if the inspector shows it.

## Steps

1. **Table.** Test first: an activity's `fun` lowers boredom by its amount over its duration; `fun` outside
   0–1 is refused when the table is built. Check: `pytest tests/test_activities.py -k fun`.
2. **Values.** Every verb gets its value from the table above; `needs["boredom"]` entries go. Check: the
   same test, parametrized over the table.
3. **Drinking past thirst.** `local_policy` `drink`/`take_beer`/`buy_drink` gain a conviviality term:
   `0.25 × company at the table + 0.2 × (1 − tolerance) × sociability`, capped once wasted (a wasted guest
   prefers `doze`). Tests: a sated sociable guest at a full table still drinks; the same guest alone does
   not; a wasted guest does not. Check: `pytest tests/test_local_policy.py -k drink`.
4. **Rounds.** `stand_a_round` and `invite:buy_drink` get the fun bonus when boredom is high; a guest who
   drank someone's round owes one (an existing `thank` aim gains "buy back"). Check:
   `pytest tests/test_local_policy.py -k round`.
5. **Dice over darts.** `dice_together` invitation worth `0.2 + 0.6 × boredom + 0.2 × courage + 0.3 × drunk`
   (drink loosens the purse, as `inhibition` already does for hostility); answers to a dice invitation use
   the same worth. A rematch after a loss at dice is likelier when drunk. Check:
   `pytest tests/test_local_policy.py -k dice`.
6. **Briefing.** One sentence of what would be fun now ("A game of dice is on at the green table";
   "Your table is drinking"). Check: `pytest tests/test_briefing.py -k fun`.
7. **Story score.** `played_together` (`dice_won`) and `fell_asleep` (`dozed_off`) already count; add a
   `round_stood` moment from the `gave` events of one `stand_a_round`, weight set in `story_score.py`. Check: `pytest tests/test_story_score.py`.
8. **Evenings.** Offline seeds 0–9 and live seed 5, both casts: story score, drinks per guest,
   `played_together`, guests who reached `drunk`/`wasted`, before and after.

## Done when

- `make check` passes; the story score of both casts rises against the S2-05 baseline.
- A live Guests evening, seed 5: at least one dice game, at least two guests reach `drunk`, and no guest
  drinks more than eight (Results).

## Results

Shipped ahead of the task: a drunk or wasted guest looks it in the client. Their bubble slurs the line
(`frontend/src/slur.ts`: an s goes to sh, a drawl, `*hic*`) and a faint amber glow with rising bubbles
hangs over them (`frontend/src/aura.ts`). Only the bubble changes; the log and the retelling keep the words.

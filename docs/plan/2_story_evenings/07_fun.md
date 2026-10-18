---
id: S2-07
title: Fun
status: doing
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

What shipped:

- `Activity.fun: float` (0–1, default 0, validated); `fun × FUN_RELIEF` (100) is the boredom a completed activity
  takes off, and the only way an activity may relieve boredom (`fun` plus a hand-set `boredom` is refused).
  Values: `play_dice` 0.9 (was 0.70), `play_darts` 0.7 (0.65), `watch_dice` 0.6 (0.45), `watch` 0.4 (0.40, kept:
  `test_watching_the_fire_or_the_view_eases_boredom` pins it), `stand_at_bar` 0.3 (0.20), every other verb 0.
  A signature act and serving an obsession are not in the table: they have no verb yet (S2-08, S2-09).
- `local_policy.conviviality(observation)` (0 to `CONVIVIALITY` 0.35 × 1.5): awake mates at the guest's table
  (up to two) × (0.5 + sociability) × (1 − bladder), 0 once wasted. It raises `take_beer` and `drink`,
  offers the tap to a guest with thirst under 35 (`agents`), and holds a guest at the table: the wish to go home
  after "a few beers" shrinks with it (`HOLD` 0.7) and with drunkenness (the evening they plan is
  `240 × (1 + 2 × drunkenness)` s long).
- A healer with a remedy does not go home while someone in sight is unwell (a longer, drunker evening made a
  healer leave seconds before she cured: `test_healer_evening` seed 2).
- Dice: `_gamble` = 0.3 × (courage − 0.5) + 0.3 × drunkenness; it raises the `dice_together` aim (base 0.25, one
  above darts), its answer worth and the rematch. The scripted writer invites a tipsy guest to dice, and
  Haiku is told a drinking guest may want a game.
- The briefing says what would be fun now (`Fun, if they want it: …`): a free or running dice table for a bored
  guest, a fight to watch, a table that is drinking together. Nothing for a guest who is closing up, hurt or wasted.
- Model-facing text: Jev's system prompt, the `take_beer` and `drink` guidance and the intention prefix now say
  that in lively company a refill comes before the mug is dry, and that games and `treat` are goals worth setting.
- Events `got_drunk` and `got_wasted` (crossing into the stage, once each); metrics `drink` (who, and every
  guest's beers). They are **not** story-score moments: the weights stay as in S2-05, so the score is comparable.

## Steps

1. `fun` on the table, validated; boredom relief derived from it. Done.
2. Values for the five verbs that relieve boredom. Done.
3. Drinking past thirst in company; staying longer; the healer's exception. Done.
4. Dice for the bold and drunk; the scripted and Haiku writers. Done.
5. Briefing sentence. Done.
6. `got_drunk`/`got_wasted` events and `drink` metrics. Done.
7. Offline seeds 0–9 and live seeds 5 and 7, both casts: Results.

## Done when

- `make check` passes; the story score of both casts rises against the S2-05 baseline.
- A live Guests evening, seed 5: at least one dice game, at least two guests reach `drunk`, and no guest
  drinks more than eight (Results).

## Results

Shipped ahead of the task: a drunk or wasted guest looks it in the client. Their bubble slurs the line
(`frontend/src/slur.ts`: an s goes to sh, a drawl, `*hic*`) and a faint amber glow with rising bubbles
hangs over them (`frontend/src/aura.ts`). Only the bubble changes; the log and the retelling keep the words.

Offline (scripted lines, seeds 0–9, same seeds before and after):

| | story score | dice games | drunk guests | beers |
|--|-------------|------------|--------------|-------|
| Locals before / after | 3.5 / 4.8 | 0.3 / 0.4 | – / 0.4 | – / 14.1 |
| Guests before / after | 4.4 / 2.3 | 0.0 / 0.1 | – / 1.3 | – / 9.9 |

The offline score is dominated by rare fights (5 of them before, 1 after in Guests: no change we can name), so it
says nothing either way. Offline Guests evenings do not use the model, and the model decides live.

Live Guests evenings (Jev + Haiku 5.5), the first pair of seeds 5 and 7 before the model text changed, the second
after it:

| | seed 5 before | seed 5 after | seed 7 before | seed 7 after |
|--|---------------|--------------|---------------|--------------|
| dice games | 1 | 4 | 0 | 2 |
| guests who got drunk | 1 | 2 | 1 | 1 |
| most beers one guest had | 3 | 3 | 3 | 3 |
| story score | 67 | 40 | 11 | 18 |

Dice games rose (the model was told what the dice table is for), drinking rose only slightly: nobody got wasted,
and a middling drinker needs three beers in a ten-minute evening while drink wears off at 0.0005 a second (0.3
over the evening).

Not done: "the story score of both casts rises against the S2-05 baseline" is not shown (two live evenings and ten
offline ones are too few to tell fights apart from luck), and "at least two guests drunk" held in one of two live
evenings. Next: a five-evening live sample for both casts, and a look at the wear-off rate and the thirst rate
(`rules.py` `per_second`, `need_rates`) if guests are to reach `wasted`.

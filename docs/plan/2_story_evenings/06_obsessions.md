---
id: S2-06
title: Obsessions drive goals
status: done
needs: [S2-03, S2-05]
touches: [mind/intentions.py, mind/goals.py, data/minds/intention_prefix.md, mind/briefing.py, mind/local_policy.py, evening/goal_metrics.py]
---

# S2-06 — Obsessions drive goals

## Why

A famous guest should spend the evening chasing their obsession: the Trump parody tries to make someone
else pay, Greta lectures everyone about the planet. Today the mind sets typed goals from the card's single
`goal` sentence and the moment; obsessions are just text. And `goals.GOALS` has only two kinds (`talk_to`,
`sit_with`), so most obsessions cannot become a goal the world can check. Live Guests evenings g1–g4: about
22 goals set, 7–16 done; every one of them is "talk" or "sit".

## Scope

- In: the intention prompt shows the guest's obsessions first and asks which one they pursue now.
- In: an intention names the obsession it serves; the inspector shows it.
- In: the goal kinds obsessions need (below), each tested alone in `goals.py`.
- In: goals that are plausible (the world can reach them from where the guest stands) and kept (the choice
  favours the option that serves the goal until it is done or lapses).
- Out: the fun an obsession brings when it is served (S2-07); new verbs (S2-08, S2-09).

## Shape

What shipped (the first plan changed where the code disagreed):

- Intention answer gains `obsession: int | null` (index into the card's `obsessions`), checked by
  `check_intention(answer, obsessions)` and `parse_stance`; an index past the card's list, a bool, a string
  or a fraction is refused. It is **optional** in the model's schema and in `Intention` (`NotRequired`), so an
  old save loads and **the schema version stays 19**: no save-format bump was needed.
- `intention_view` gains `obsessions` (the card's list) and `possible` (for each other guest, the goal kinds
  the hall can carry out now). `parse_stance` refuses a kind outside that guest's list.
- Three new goal kinds, built only from what the game already records (thoughts hold the person):

| Kind | Wording | Open when | Reached when the guest holds, formed after the goal | Lasts |
|------|---------|-----------|------------------------------------------------------|-------|
| `treat` | buy {name} an ale | a tap exists; they are not staff or asleep | `generous` about them | 240 |
| `play_with` | play a game of dice with {name} | a dice table exists; not staff or asleep | `won_at_dice` or `lost_at_dice` about them | 300 |
| `have_it_out` | have it out with {name} | not staff or asleep; opinion of them ≤ 0 | `quarrel` about them | 180 |

  `get_treated` and `drink_with` of the first plan were cut: nothing a guest does makes someone else buy them
  an ale, and no event says who drank with whom.
- Aims serve goals too (`GoalKind.aims`, `serving_aim`): `invite:buy_drink` for `treat`,
  `invite:dice_together` and `rematch` for `play_with`, `have_it_out` and `needle` for `have_it_out`.
- `deliver_intention` keeps an active goal while the new answer names the same obsession; the goal's pull in
  the local policy grows over its second half, from `GOAL_BONUS` 0.3 to `LATE_GOAL_BONUS` 0.5.
- The log line of an intention that serves an obsession ends `(after: …; chasing: <obsession>)`; metrics
  `goal_kinds` (goals set by kind) and `chased` (intentions per guest that served an obsession).
- The inspector shows "Chasing · <obsession>"; `types.ts` has `Intention.obsession` and `CharacterCard.obsessions`.
- Monroe, the Queen and Thatcher got persona cards with obsessions (they had none).

## Steps

1. Boundary: `check_intention` and `parse_stance` with an obsession index. Done.
2. Saves: the index survives save and load, a bad one is refused. Done (no version bump).
3. Goal kinds with `serves`, `reached`, `possible`; `open_kinds`; `serving_aim`. Done.
4. Stable pursuit: goal kept for the same obsession; pull grows late. Done.
5. Prompt: numbered obsessions in the moment, open kinds per guest, a section on obsessions with two examples,
   the answer shape. Prefix still above 4,096 tokens. Done.
6. Inspector and metrics. Done.
7. Evenings: live Guests, seeds 5 and 7. Done (Results).

## Done when

- `make check` passes.
- Live Guests evening, seed 5: every guest sets a goal from an obsession at least once and acts on it with
  an action the world validated; at least half of the obsession goals end `done`, under a fifth `expired`
  (Results, with the `by_kind` table).

## Results

Live Guests evenings (Jev + Haiku 5.5), seeds 5 and 7, each guest asked about their obsessions:

| | seed 5 | seed 7 |
|--|--------|--------|
| goals set / done / expired / failed | 20 / 13 / 2 / 0 | 19 / 12 / 0 / 2 |
| goals by kind | talk_to 10, have_it_out 7, treat 2, sit_with 1 | talk_to 10, have_it_out 6, play_with 2, treat 1 |
| intentions that chased an obsession | Musk 5, Tyson 5, Trump 5, Greta 5 | Musk 5, Tyson 5, Trump 5, Greta 5 |

Every guest chased an obsession in five intentions; 65% and 63% of goals ended `done`, 10% and 0% `expired`.
Before the prompt asked Haiku for games and rounds (first pair of the same seeds) only `talk_to` and
`have_it_out` were set. One moment: Greta's `have_it_out` with Trump came back after each quarrel it ended
(done at the quarrel, set again at the next intention) because the obsession was the same.

Not solved: `treat` goals often fail at the errand (`invitation_failed`, three times for Trump in seed 5):
the fetcher cannot take a chair at a full table to hand the mug over (`errands._carry`). A candidate for
`possible`: no `treat` for someone at a full table.

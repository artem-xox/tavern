---
id: S2-06
title: Obsessions drive goals
status: todo
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

- Intention answer gains `obsession: int | null` (index into the card's `obsessions`), checked at the
  boundary (`check_intention`, `parse_stance`).
- Saved intention keeps `obsession`; this is a schema bump: ask the user before it.
- New goal kinds, all with a person (`target`) and built only from verbs and events that exist today:

| Kind | Wording | Serves | Reached when the log shows | Lasts |
|------|---------|--------|---------------------------|-------|
| `get_treated` | get {name} to buy them a drink | `invite:buy_drink` aim or approach to them | `gave` (a drink) from the target to the guest | 240 |
| `play_with` | play dice or darts with {name} | `invite:dice_together`/`darts_together`, `play_dice` | `dice_won`/`dice_lost` between the two, or both finished `play_darts` together | 300 |
| `drink_with` | share a drink with {name} | `buy_drink`/`stand_a_round` to them, `sit_with` their table | both drank at one table since | 240 |
| `have_it_out` | have it out with {name} | `have_it_out`/`needle` aims to them | a `quarrel` event between them | 180 |

  The table is the spec; a kind whose `reached` cannot be read from events already logged is cut here.

## Steps

1. **Boundary.** Test first: `check_intention` accepts `obsession` as a valid index or `null`, rejects an
   index out of range, a string, a bool. Check: `pytest tests/test_intentions.py -k obsession`.
2. **Save.** Saved intention keeps `obsession`; `check_saved_intention` rejects a bad one; schema bump
   (after approval), `test_database.py` names it. Check: `pytest tests/test_persistence.py -k intention`.
3. **Goal kinds, one per commit.** For each kind in the table: a parametrized `serves` block and a
   `reached` block (done, not yet, the person left → failed). Check: `pytest tests/test_goals.py -k <kind>`.
4. **Plausible goals.** `check_goal` refuses a kind whose verbs are not open to the guest now (no dice table
   in the room, a target already at a game, the guest on duty). One parametrized error block.
   Check: `pytest tests/test_goals.py -k refused`.
5. **Prompt.** `intention_view` lists obsessions numbered, first; the prefix explains goal kinds with one
   example per obsession shape; prefix stays byte-identical and above 4,096 tokens. Check:
   `pytest tests/test_intentions.py -k prefix`.
6. **Stable pursuit.** Today `GOAL_BONUS = 0.3` only tips near ties, and a new intention every 180 s can
   replace an unfinished goal. Two changes, each with a test:
   - an active goal is kept across a new intention unless the answer names a different obsession
     (`deliver_intention`); test: the second answer with the same obsession keeps the first goal;
   - the bonus grows while the goal stays unserved (0.3 → 0.5 over its `lasts`), so a goal is not starved
     by a steady need; test: the serving option wins a near tie late in the goal and loses it early.
7. **Inspector.** Mind view shows "Chasing: <obsession>" and the goal; `types.ts` with it. Check:
   `npm --prefix frontend test`, `make build`.
8. **Metrics.** `goal_counts` gains `by_kind` and `by_obsession`. Check: `pytest tests/test_goal_metrics.py`.
9. **Evenings.** Offline seeds 0–9 (scripted writer picks the first obsession) and live seed 5, Guests.

## Done when

- `make check` passes.
- Live Guests evening, seed 5: every guest sets a goal from an obsession at least once and acts on it with
  an action the world validated; at least half of the obsession goals end `done`, under a fifth `expired`
  (Results, with the `by_kind` table).

## Results

---
id: S2-08
title: Signature items
status: todo
needs: [S2-03, S2-05]
touches: [body/items.py, body/activities.py, mind/agents.py, mind/local_policy.py, mind/options.py, frontend/src/]
---

# S2-08 — Signature items

## Why

Each famous guest arrives with something in their backpack that only they would bring, and using it
changes the room: a folding table set up at a distance from everyone, a deck of cards that starts a game,
a golden pen that signs a decree everyone hears. These are the moments players retell.

## Scope

This task builds the **mechanic** and one item end to end. Further items are one table entry and one
activity each, as later tasks.

- In: an item kind can offer activities to its carrier: `Item.offers: tuple[str, ...]` of verbs in
  `activities.py`. The candidate rule offers them only to whoever carries the item.
- In: one item end to end. Proposed first: `card_deck` → `deal_cards`, a joint game built on the dice game
  (invitation, table, watchers, a winner from traits and chance).
- In: a `signature_act` event for the story score.
- Out: the other items. Backlog, in the order to build them:
  - `golden_pen` → `sign_decree`: a loud announcement every guest hears, with a thought for each listener
    (outrage, glee) depending on who it targets. The decree is words only; the world does not change.
  - `folding_table` → `set_up_table`: places a temporary one-seat table at a free cell far from others.
    Needs the map to accept a placed object; the hardest one.
  - more as guests arrive: a witcher's silver sword (fight bonus), a pop star's microphone (a song the
    room watches).

## Shape

- `Item.offers` in `items.py`; the verb in `activities.py` with its `fun` (S2-07), wording, pose and family.
- Adding a verb follows [AGENTS.md](../../../AGENTS.md#extending): activity, candidate rule, local utility,
  option sentence.

## Steps

1. Test first: a verb an item offers is a candidate for its carrier only, and disappears when the item is
   given away.
2. `deal_cards` as a joint game: invitation, play, watchers, result, thoughts.
3. Client: the item in the inventory, the cards on the table.
4. Live Guests evening: the deck comes out at least once.

## Done when

- `make check` and `make build` pass; a live Guests evening has a `signature_act` (Results).

## Results

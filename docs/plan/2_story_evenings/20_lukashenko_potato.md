---
id: S2-20
title: Lukashenko and his potatoes
status: done
needs: [S2-08]
touches: [body/items.py, mind/local_policy.py, social/thoughts.py, characters/guests/lukashenko/, characters/guests/relationships.json, frontend/src/icons.ts]
---

# S2-20 — Lukashenko and his potatoes

## Why

A new famous guest whose habit is a gift: Alexander Lukashenko walks in with a sack of potatoes and presses one
into every hand near him, whether it was wanted or not. Some guests take it gladly and some refuse, which is a
small scene by itself.

## Scope

- In: the guest (card, news, relations with the other thirteen guests and Kim Jong Un, 21 poses at 68 px).
- In: `potato`, an ordinary giftable item (`received="gifted"`, up to five carried) with a new `Item.eagerness`:
  how much more its carrier feels like handing one over than any other gift, added to the want to give.
- Out: a signature act for the potato. It has no verb: the existing `give` and the `Giving` / `Receiving` poses carry it.
- Out: a way to get more potatoes during the evening.

## Shape

```python
"potato": Item("potato", "a potato", "potatoes", held="a potato", hands=5, received="gifted", eagerness=0.4),
```

`local_policy._score_gifts` adds `ITEMS[kind].eagerness` to the score of a `give`. The refusal rule is the ordinary
one (`giving.hand_over`): someone who thinks too ill of the giver will not take it, and the giver is rebuffed.

The card carries `{"potato": 5}`. Saves are schema 22 (approved on 2026-11-07, with the flag of [S2-21](21_kim_flag.md)).

## Art

- `characters/guests/lukashenko/art/*`: 21 states, 8 views each, 68x68, PixelLab group `4ba5cbb1-fc1d-4543-a5a4-7d6d1ea4cdc9`.
  The record is in `characters/guests/lukashenko/source/prompts.md`.
- `frontend/static/items/potato.png`: PixelLab object `20a79f4c-9a46-40c3-b776-0cd73bf15110`.

## Done when

- `make check` and `make build` pass, output pasted in the PR.
- In an offline Guests evening with Lukashenko, he gives potatoes away.

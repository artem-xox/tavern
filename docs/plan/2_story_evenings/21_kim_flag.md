---
id: S2-21
title: Kim Jong Un's little flag
status: done
needs: [S2-08]
touches: [body/items.py, body/activities.py, social/signature_acts.py, social/thoughts.py, mind/signature_candidates.py, mind/local_policy.py, mind/options.py, characters/guests/kim_jong_un/, characters/guests/relationships.json, frontend/src/icons.ts]
---

# S2-21 — Kim Jong Un's little flag

## Why

Kim Jong Un does not argue, he announces. When someone he dislikes is in sight he pulls a small flag of his country
from his sleeve and holds it up like a warning. It is a threat, not a protest: it shakes one guest instead of
shaming him before the hall.

## Scope

- In: `flag` → `brandish_flag`, a signature act on the S2-08 mechanic (`Item.offers`, `signature_act`, poses from carried items).
- In: whom it names: the guest in sight the holder dislikes most, as `accused_of` picks them, but only when the holder's
  opinion of them is below `BRANDISH_BELOW` (-15): a threat needs a real grudge, and an argument gets there.
- Out: a scene-aware trigger (a quarrel in the holder's own conversation); the opinion stands in for it, since insults lower it.

## Shape

Item: `flag`, `giftable=False`, `offers=("brandish_flag",)`.

Verb `brandish_flag`: no target, `duration=6.0`, `leaves_seat=True`, `fun=0.4`, `on_arrival=brandish_flag`, `pose="Brandishing"`,
`status="threatening"`, `family="company"`, `stopped_at_last_call` set. Not repeated inside `BRANDISHES_AGAIN_AFTER` (120 s),
read from the holder's memory like the protest sign's cool-down (`_acted_lately`).

Effect on arrival: the threatened guest gets `threatened` (`ThoughtKind(-4.0, -15.0, 240.0, 2, "threatened them with a little
flag", acquaints=True)`) about Kim, a short `THREAT` sound (loudness 0.4, reach 12) turns nearby heads, and one `signature_act`
is logged ("Kim Jong Un brandishes a little flag at Trump and threatens them").

Local utility rises with the holder's temper and the grudge. The option sentence names the guest who would be threatened.

## Art

- `characters/guests/kim_jong_un/art/*`: 22 states, 8 views each, 68x68, PixelLab group `4c2abd01-ed2d-46f2-858d-79cc65cd9af8`,
  among them `Brandishing` (`29eca895-0da5-4257-a877-c1ac6ee15233`). The record is in `characters/guests/kim_jong_un/source/prompts.md`.
- `frontend/static/items/flag.png`: PixelLab object `61e09d67-b792-4117-927f-638b4f8752e3`.

## Done when

- `make check` and `make build` pass, output pasted in the PR.
- In an offline Guests evening with Kim Jong Un and a guest he dislikes, he brandishes the flag at them.

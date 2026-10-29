---
id: S2-08
title: Signature items — the mechanic and Kim's phone
status: done
needs: [S2-03, S2-05]
touches: [body/items.py, body/activities.py, mind/agents.py, mind/local_policy.py, mind/options.py, mind/characters.py, adapters/characters.py, evening/story_score.py, characters/guests/kardashian/, frontend/src/icons.ts, frontend/src/inspector.ts]
---

# S2-08 — Signature items: the mechanic and Kim's phone

## Why

Each famous guest arrives with something only they would bring, and using it changes the room. Today
`carries` on every guest card is empty and no item offers a verb. After this task Kim Kardashian walks in with
a phone, holds it up when something scandalous happens, and the room knows it is being filmed.

This is the first of three items the user picked (2026-10-28). The other two reuse this mechanic:
[S2-18](18_protest_sign.md) (Greta's protest sign) and [S2-19](19_interview.md) (Sobchak's microphone).
The old backlog (golden pen, folding table, card deck) is dropped: the user did not like it.

## Scope

- In: `Item.offers: tuple[str, ...]`, the verbs an item gives whoever carries it. The candidate rule offers
  such a verb only to a carrier.
- In: signature items stay with their owner (`giftable=False`), like the cudgel.
- In: a character's poses are its role's poses plus the `pose` of every verb its carried items offer, so
  only Kim needs the `Filming` art and the catalog still checks it is complete.
- In: one `signature_act` event per use, weighted in the story score.
- In: `phone` → `livestream` for Kim, end to end, with its inventory icon.
- Out: the protest sign (S2-18), the microphone (S2-19), any item for other guests.

## Shape

Item, in `body/items.py`:

```python
"phone": Item("phone", "a phone", "phones", held="a phone held up to film", hands=1, received="gifted",
              giftable=False, offers=("livestream",)),
```

Verb, in `body/activities.py` (wording is a proposal, tune it in review):

- `livestream`: no target (like `wait`), `duration=8.0`, `leaves_seat=True`, `fun=0.6`, `pose="Filming"`,
  `status="filming"`, `doing="filming the room on her phone"`, `family="company"`,
  `sound=` a medium sound (look at `Sound` in `body/hearing.py` and how `give_speech` sounds),
  `stopped_at_last_call` set.
- Effect on completion: pick the **subject**, the loudest thing in her sight: a fight, else a quarrel, else a
  speech, else nobody (a selfie). Each subject participant gets a new thought `filmed`
  (`ThoughtKind(-2.0, -6.0, 240.0, 2, "filmed them on her phone", acquaints=True)`); a selfie gives none.
- Event: `{"type": "signature_act", "verb": "livestream", "item": "phone", "subject": [ids], ...}` with a
  message such as "Kim films Trump and Greta's quarrel for her followers" or "Kim films herself".

Candidate rule (`mind/agents.py`): offer an item verb when the actor's inventory holds an item whose
`offers` lists it. Local utility (`mind/local_policy.py`): low by default, high while a fight or quarrel is
in sight. Option sentence (`mind/options.py`): "Film the room for your followers".

Catalog (`mind/characters.py`, `adapters/characters.py`): `poses_of(character)` =
`ROLE_POSES[role]` + `ACTIVITIES[verb].pose` for each `verb` in each carried item's `offers`, without
duplicates. `_check_art` (adapters) and the public catalog (`mind/characters.py`, where `ROLE_POSES` is read today) use it, so the client's `visuals.poses` lists `Filming` for Kim
only. No snapshot field is new.

Story score (`evening/story_score.py`): `WEIGHTS["signature_act"] = 2.0` (a set piece, below a fight) and
`_BY_TYPE["signature_act"] = "signature_act"`.

Saves: no new saved field. The inventory gains a kind; check whether `empty_inventory` makes old saves fail
to load. If it does, ask the user before bumping `schema_version`.

Client: `frontend/static/items/phone.png` (32×32, ready). In `icons.ts`, keep the pixel maps and add a map
from item kind to picture URL. `inspector.ts` draws an `<img>` with `image-rendering: pixelated` for such a
kind. `scene.ts` already draws an unknown pose as Idle. Check that `Filming` shows while `livestream` runs.

## Art (ready, do not regenerate)

- `characters/guests/kardashian/art/Filming/rotations/*.png`: 8 views, 68×68, PixelLab state
  `90d34cd6-b2db-4140-934a-03539ff7214c` in group `ca6079e8-d5ff-40be-ac17-a966d65791f1`. The source is
  recorded in `characters/guests/kardashian/source/prompts.md`.
- `frontend/static/items/phone.png`: PixelLab object `b6b01b17-ae3f-444a-a27d-5515a767dd45`.

## Steps

1. Item offers a verb to its carrier only: a guest with a phone gets `livestream` as a candidate, a
   guest without one never does. Check: a parametrized test in `tests/test_agents.py` (empty inventory,
   phone, beer only).
2. The phone cannot be given away. Check: `give` refuses it (`tests/test_giving.py`-style case).
3. Poses follow carried items: Kim's catalog entry lists `Filming`, Greta's does not; a card that carries a
   phone but lacks `Filming` art fails to load. Check: `tests/test_character_catalog_files.py`.
4. `livestream` subject choice: fight > quarrel > speech > selfie, thoughts only for the subject. Check: a
   parametrized test through `world.step_world` with a small room helper.
5. `signature_act` in the story score. Check: `tests/test_story_score.py` case.
6. Kim's card: `"carries": {"phone": 1}`. Check: catalog loads, `make test`.
7. Client icon and pose. Check: `npm --prefix frontend test`, `make build`, run the app, pick Kim, and
   force `livestream` from the inspector.
8. Offline evening (`scripts/evening.py --seed 5 --mode local --writer scripted`) with Kim in the lineup:
   at least one `signature_act`.

## Done when

- `make check` and `make build` pass, output pasted in the PR.
- An offline Guests evening with Kim logs a `signature_act`, and the inspector shows the phone icon.

## Results

All three signature tickets (S2-08, S2-18, S2-19) were built together in one branch at the user's request.

- Mechanic: `Item.offers`; `mind/signature_candidates.py` offers a carried item's verbs (`livestream` always, `raise_sign`
  once a rival is in sight and 180 s after the last one, `interview_guest` toward each guest a walk over is offered to).
  `actions.action_error` now checks `requires_item` for every kind of verb (it used to be skipped by the person verbs), so
  the world refuses a signature act to anyone without the item. All three items are `giftable=False`.
- Poses: `characters.poses_of(character)` = role poses + the pose of each verb a carried item offers; the adapter's art check
  and the public catalog use it. Kim lists `Filming`, Greta `Protesting`, Sobchak `Interviewing`; nobody else does.
- Score: `signature_act` weighs 2.0 (below a fight at 4.0) and one event is one moment.
- Saves: the inventory gained three kinds, so an old save no longer loads. **`schema_version` is 21** (approved by the user);
  the tests that pinned 20, and the four kinds of an inventory, changed with it.
- `livestream` subject: a running fight with someone in sight, else a scene whose insult run is at least 2 (`FILMABLE_HEAT`),
  else a speaker on the stage, else a selfie. The thought `filmed` is worded "filmed them on a phone" (no pronoun).
- Client: signature items draw `static/items/*.png` through `icons.itemPicture`; the inventory wraps to a second row. No
  snapshot field changed.
- Offline check (`--scenario` with Kim added to `guests.json`, seeds 5–7, scripted lines): every seed logs several
  `signature_act`s: films of a guest, selfies, Greta's sign at Trump (or at Sobchak once), Sobchak's interviews.
- Not done: the live-model check of how the interview lines read (needs a key), and a look at the poses in the running app.

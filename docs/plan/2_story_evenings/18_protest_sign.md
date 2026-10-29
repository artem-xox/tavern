---
id: S2-18
title: Greta's protest sign
status: done
needs: [S2-08]
touches: [body/items.py, body/activities.py, social/thoughts.py, mind/agents.py, mind/local_policy.py, mind/options.py, characters/guests/greta/, frontend/src/icons.ts]
---

# S2-18 — Greta's protest sign

## Why

Greta scolds with words, and her quarrels run in circles. With a sign she can make the whole room watch: she
stands up, raises a cardboard sign at the guest she blames most, and shouts. The accused is shamed, and
whoever already dislikes the accused enjoys it. It is a loud set piece, as a speech is, but aimed at one person.

## Scope

- In: `protest_sign` → `raise_sign` for Greta, on the S2-08 mechanic (`Item.offers`, `signature_act`,
  poses from carried items).
- In: the accused is chosen by the world, not by a target field: the present guest Greta thinks worst of.
- Out: a sign other guests can grab or tear (`giftable=False`, as for every signature item); a sign written by
  the model (the event message is enough for now).

## Shape

Item:

```python
"protest_sign": Item("protest_sign", "a protest sign", "protest signs", held="a cardboard protest sign",
                     hands=1, received="gifted", giftable=False, offers=("raise_sign",)),
```

Verb `raise_sign`: no target, `duration=10.0`, `leaves_seat=True`, `fun=0.7`, `pose="Protesting"`,
`status="protesting"`, `doing="raising a protest sign and shouting"`, `family="company"`, a **loud** sound
the whole hall hears (as `give_speech`; reuse `hearing.emit` / `heard_loudness`), `stopped_at_last_call` set.
Greta should not raise it again for a while: reuse the `speeches.SPEAKS_AGAIN_AFTER` idea with a local
constant in the new effect, not a new world field.

Effect on completion:

- Accused = the guest present whom `opinion_of(greta, ...)` rates lowest. Tie: the lower actor id, so tests
  are deterministic (write that as a why-comment). With nobody else present, the act does not run: the
  candidate rule does not offer it.
- The accused gets `shamed`: `ThoughtKind(-5.0, -20.0, 300.0, 2, "shamed them with a protest sign", acquaints=True)`.
- Each other guest who heard it (loudness ≥ `speeches.HEARD_FROM`) and whose opinion of the accused is
  below 0 gets `protest_cheered`: `ThoughtKind(2.0, 6.0, 240.0, 1, "stood up to someone they dislike", acquaints=True)`.
  They think it about Greta.
- Event `signature_act` with `verb="raise_sign"`, `item="protest_sign"` and `subject=[accused]`, and the
  message "Greta raises her protest sign at Trump and shouts".

Local utility: higher with more listeners and a lower opinion of the accused. Option sentence: "Raise your
protest sign at {the accused's name}". The option names the accused, so the model knows who it is.

Greta's card: `"carries": {"protest_sign": 1}`.

## Art (ready, do not regenerate)

- `characters/guests/greta/art/Protesting/rotations/*.png`: 8 views, 68×68, PixelLab state
  `88817313-ac78-4b47-8d80-2787f331178f` ("Protesting v2") in group `4361869a-254b-4d51-a1ba-2d4fb341cc43`. She holds the
  sign at her chest. The first try, `f34470db-f9cc-4583-8452-504dd7ca8a9e`, raised it overhead and cut it off at the top.
- `frontend/static/items/protest_sign.png`: PixelLab object `ee290220-4ba8-496c-96b4-e3c5c72f58fd`.

## Steps

1. Accused choice: the lowest opinion, a tie broken by id, nobody else present → not offered. Check: a
   parametrized test (Greta alone, one other guest, two guests with a tie, three guests with distinct opinions).
2. Thoughts: the accused is shamed; a listener who dislikes the accused cheers; a listener out of earshot or
   friendly with the accused gets nothing. Check: a parametrized test through `world.step_world`.
3. `signature_act` logged once per use. Check: an event-log assertion and `story_score` counts 1.
4. Cool-down: a second `raise_sign` is not offered inside the window. Check: a candidate test.
5. Card, icon and pose. Check: `make check`, `make build`; in the app Greta's inspector shows the sign, and
   `raise_sign` forced from the inspector shows `Protesting`.
6. Offline evening with Greta and Trump: at least one `raise_sign`, aimed at Trump given their bad blood.

## Done when

- `make check` and `make build` pass, output pasted in the PR.
- An offline Guests evening with Greta and Trump logs Greta raising her sign at Trump.

## Results

Built with S2-08 (see its Results).

- `raise_sign` acts when Greta arrives at the spot, not when the ten seconds are up: the shout, the shaming and the
  cheers happen as she raises the sign, and the pose then holds for `duration`. The loud sound is emitted by hand
  (`signature_acts.PROTEST`, loudness 0.6, reach 30, turning heads like a speech), not by `Activity.sound`, so that the
  listeners can be told from the stimulus it makes.
- The accused is chosen among the guests in sight (`signature_acts.in_sight`, staff left out); the option sentence names
  the same one (`signature_candidates.accused_in_sight`). The cool-down is read from Greta's memory of her last
  `signature_act` with `verb == "raise_sign"` (`RAISES_AGAIN_AFTER` 180 s), so there is no new world field.
- The event reads "Greta raises a protest sign at Trump and shouts" (no pronoun).
- Offline: seeds 5 and 6 of the Guests evening log Greta raising her sign at Trump (at most once in 180 s); with Kim added, seeds 6
  and 7 do too, and seed 5 has her raise it at Sobchak.

---
id: S2-04
title: First guests
status: todo
needs: [S2-01, S2-03]
touches: [characters/guests/, data/scenarios/guests.json]
---

# S2-04 — First guests

## Why

We need real famous guests to experiment with live evenings. Start with a small cast and grow it once
evenings with them work.

## Scope

- In: three guests from the concept art, through the `add-npc` skill, with every pose in eight directions:
  - a Putin parody: wants to keep his distance; carries a folding table.
  - a Zelensky parody: wants a seat at the table; carries a deck of cards.
  - a Trump parody: wants others to pay; carries a golden pen.
  - a Greta Thunberg parody, `characters/guests/greta/` (art and card done, 21 poses x 8 views): a stern young
    campaigner in a hot-pink blouse with one long braid; wants every guest to admit what they have done
    wrong and one of them to promise to change; carries nothing yet. She scolds with "how dare you" and a
    pointing finger, and secretly fears nobody is listening. Natural foil for the Trump parody.
- In: their starting relationships (rivalries, grudges) and a `guests.json` scenario with all three plus
  two locals as bystanders.
- Out: what their items do (S2-08); further guests. The next candidates are a Bush parody (hunting for
  oil with Trump), a witcher, a mute GTA III hero, a pop star and a film star.

## Shape

Cards follow S2-03. Items are listed in `carries` as new item kinds with no activity yet: `folding_table`,
`card_deck`, `golden_pen`. They are visible in the inspector.

## Steps

1. Ask the user: the shown names (real or parody) and the exact obsessions.
2. Write the three cards. Check: catalog validation passes.
3. Ask the user before spending PixelLab credits. Generate art by
   [CHARACTER_ART_PIPELINE.md](../../CHARACTER_ART_PIPELINE.md) and review every pose at game scale.
4. `guests.json` and one live evening: `make evening CAST=guests SEED=5`. Read the lines: is each one
   recognisable without their name?

## Done when

- `make check` and `make build` pass; a Guests evening runs live to closing.
- Every guest is recognisable from three of their lines alone (judged by the user).

## Results

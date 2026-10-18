---
id: S2-04
title: First guests
status: doing
needs: [S2-01, S2-03]
touches: [characters/guests/, data/scenarios/guests.json]
---

# S2-04 — First guests

## Why

We need real famous guests to experiment with live evenings. Start with a small cast and grow it once
evenings with them work.

## Scope

- In: three guests from the concept art, through the `add-npc` skill, with every pose in eight directions:
  - a Putin parody, `characters/guests/putin/` (art and card done, 21 poses x 8 views): a compact, cold,
    controlled man in a dark suit and burgundy tie who wants to keep his distance, sits facing the door with an
    empty chair on each side, and learns what everyone wants before saying a word; carries nothing yet (the
    folding table is a later item). Quietly lonely at the end of every long table.
  - a Zelensky parody, `characters/guests/zelensky/` (art and card done, 21 poses x 8 views): a stubbled,
    quick-witted man in an olive field shirt who pulls up a spare stool uninvited and wants a seat at the table
    of the most powerful guests and one promise from them; carries nothing yet (the deck of cards is a later
    item). Jokes until the joke turns into a plea.
  - a Trump parody: wants others to pay; carries a golden pen.
  - a Greta Thunberg parody, `characters/guests/greta/` (art and card done, 21 poses x 8 views): a stern young
    campaigner in a hot-pink blouse with one long braid; wants every guest to admit what they have done
    wrong and one of them to promise to change; carries nothing yet. She scolds with "how dare you" and a
    pointing finger, and secretly fears nobody is listening. Natural foil for the Trump parody.
  - an Elon Musk parody, `characters/guests/musk/` (art and card done, 21 poses x 8 views): a pale founder in
    a black t-shirt and jeans who pitches a faster way to do everything and sketches machines on beer mats;
    wants one backer for his big idea and to outshine whoever talks loudest; carries nothing yet. Secretly
    never finishes a pint. Rival for the Trump parody's stage.
  - a Mike Tyson parody, `characters/guests/tyson/` (art and card done, 21 poses x 8 views): a huge, gentle,
    soft-spoken retired champion with a face tattoo and a cage of racing pigeons; wants a quiet pint and to
    stop any bully picking on the weak; carries nothing yet (the pigeons are a later item). Never starts a
    fight but finishes every one: the room's natural peacemaker and enforcer.
  - a Marilyn Monroe parody, `characters/guests/monroe/` (art and card done, 21 poses x 8 views): a
    platinum-curled film star in a white halter dress who is tired of being looked at but cannot sit in a room
    where nobody does; wants to be the centre of the room without asking and one person who talks to her, not
    at her; carries nothing yet. Secretly keeps a book of poems in her sleeve. Natural magnet for the Trump
    and Musk parodies.
  - a Margaret Thatcher parody, `characters/guests/thatcher/` (art and card done, 21 poses x 8 views): a
    formidable stateswoman in a powder-blue suit and pearls who audits the inn and its guests and never pays
    for a round she did not order; carries nothing yet (the handbag is a later item). Opens with "let me be
    absolutely clear" and corrects grammar. Natural foil for the Trump parody and the one guest who can
    out-argue Greta.
  - a Queen Elizabeth II parody, `characters/guests/queen/` (art and card done, 21 poses x 8 views): a small
    upright old queen in a turquoise coat, matching hat and pearls, quietly taking tea and noting every breach of
    manners; wants the room's manners to hold and to deliver one dry verdict on whoever behaves worst; carries
    nothing yet (the corgi is a later item). "One is not amused." Calm judge for the loud guests, foil for the
    Trump parody's manners and for Thatcher.
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

Four guests (Musk, Tyson, Trump, Greta) with persona cards; ties: Trump–Greta bad blood, Trump–Musk rivals.
`guests.json`: Musk 0 s, Tyson 20 s, Trump 50 s, Greta 100 s. Live Haiku evenings, 700 s limit, about $0.06 each:

| seed | story score | fights | note |
|------|-------------|--------|------|
| 1 (first cards) | 10 | 0 | Musk and Tyson loop on pigeons and "quiet pipe" for 25 turns |
| 2 | 68 | 1 | Trump shoves Greta after ten rounds of "fever" and "you shoved me" |
| 3 | 33 | 0 | Greta vs Musk's "honest road"; Trump insults Musk's napkins six times |
| 4 | 32 | 1 | Greta puts Trump's towers "on trial"; Trump attacks her |

Voices are recognisable from three lines (Trump "tremendous, believe me"; Musk "obviously, by next spring" and napkins;
Greta "what have you actually done"; Tyson "sir, a quiet pint"). Open problems: `share_place` makes every
guest recite "darts and the WC"; quarrels loop on one charge; Tyson never steps in; Trump's "others pay" has no
act; the retelling call fails (`thinking: disabled` is refused by `claude-sonnet-5-5`, S2-10).


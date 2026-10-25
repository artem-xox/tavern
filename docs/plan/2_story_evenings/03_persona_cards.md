---
id: S2-03
title: Persona cards
status: doing
needs: [S2-01]
touches: [adapters/characters.py, mind/cards.py, mind/turn_prompt.py, mind/intentions.py, social/turns.py, .agents/skills/add-npc]
---

# S2-03 — Persona cards

## Why

A famous guest is funny because the player recognises them: the way they talk, what they always want,
the thing they cannot stop doing. The Stage 1 card (occupation, background, temperament, speech, quirks,
secret, goal) was written for unknown border folk and has no place for that. Some famous characters
also never speak (Claude from GTA III).

## Scope

- In: new card fields for every character, optional for locals.
- In: the line writer and the intention prompt read them; a mute character gets no line requests and acts
  through emotes and actions only.
- Out: obsessions becoming goals (S2-06), signature items (S2-08), relationships between guests (S2-09).

## Shape

`character.json` gains (names to freeze here before code):

- `inspired_by`: the real or fictional person parodied, for models only (never sent to the browser,
  like `secret`). `name` stays what the game shows, so a parody rename is one field.
- `origin`: `real` | `fictional`.
- `persona`: two or three sentences on the public image to play up.
- `catchphrases`: up to five short lines the writer may echo or twist, never repeat word for word twice.
- `obsessions`: one to three wishes for tonight ("find out who has oil", "keep everyone at a distance",
  "get someone else to pay").
- `mute`: `true` for a character who never speaks. Default `false`. **Deferred**: no guest needs it yet (the
  GTA III hero is the first); it lands with that guest.

## Steps

1. Test first: the catalog parses the new fields, rejects too many catchphrases or obsessions, and keeps
   `inspired_by` out of browser data.
2. The card text for the models includes them; the shared prefix explains how to play a persona.
3. Test first: a mute character is never asked for a line and never chosen as a scene's next speaker; others
   can still talk to them.
4. Update `add-npc` with the new fields.

## Done when

- `make check` passes; the Locals evening replays unchanged.

## Results

Built: `inspired_by`, `origin`, `persona`, `catchphrases` (1–5), `obsessions` (1–3), all optional, so saves and
Locals cards are unchanged. They reach the line writer (cached card block) and the intention prompt through
`cards.persona_words`; the shared prefix rule 4 says how to play them. Not sent to the browser. `mute` deferred.

Later: cards also carry `news` (10–15 items of the last two years, common knowledge; a dead guest's stop before
their death), and the regard matrix and catalog ties carry an optional `history` (three or four true sentences per
pair) that reaches each guest's portrait. The lineup seats up to 8 guests.

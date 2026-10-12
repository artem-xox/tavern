---
name: add-npc
description: Add a playable Last Inn NPC to the authoritative characters catalog, including a complete profile, relationships, 68px directional PixelLab art, validation, and scenario references. Use when adding or changing a tavern guest or bartender.
---

# Add an NPC

`characters/<id>/` is the source of truth for a person. Do not add a character to
`data/`, a frontend registry, or a scenario as a copy of their profile.

## 1. Write the profile

Create these files before using the character in a scenario:

```
characters/<id>/
  character.json
  relationships.json
  visuals.json
  art/<Pose>/rotations/<direction>.png
  source/pixellab.json
```

`character.json` needs `id`, `role`, `name`, `color`, `looks`, `occupation`,
`background`, `temperament`, `speech`, `quirks`, `secret`, `goal`, `sex`, `params`,
and `carries`. Use a Python identifier for `id`; use role `guest` or `bartender`.
Write the prose in English, in concrete playable terms. Reuse the existing parameter
names and item kinds. Keep `secret` in this file: it is supplied to the model but never
to the browser API or UI.

`relationships.json` is a list of `{ "with", "kind", "note" }`. Write each pair
once, under either participant. The runtime makes the relation symmetric. Start with
`[]` when there is none. `visuals.json` is `{ "size": 68, "lift": -16 }` unless the
art layout changes deliberately.

## 2. Generate and retain art

Read `docs/CHARACTER_ART_PIPELINE.md` before spending credits. Use PixelLab MCP:

1. Call `get_pro_flash_capabilities`, then `get_balance`; ask the user before any
   paid generation or retry.
2. Call `create_character_pro_flash` for the canonical person, with the repository
   style reference and an English prompt that fixes identity, clothing, palette and
   silhouette. Wait for the job and inspect it with `get_character`.
3. Call `create_character_state` for every required pose, preserving that same
   identity and outfit. Use `save_to_asset` only for a targeted correction.
4. Export the native 68×68 transparent PNGs. Record the PixelLab IDs and prompts in
   `source/pixellab.json`; do not keep temporary image URLs.

Every guest needs all common poses plus `Fighting`, `KnockedOut`, `Hurt`,
`HurtSeated`, `Shoving`, and `HelpingUp`. A bartender needs all common poses plus
`PouringBeer`. Each pose needs all eight directions: `north`, `north-east`, `east`,
`south-east`, `south`, `south-west`, `west`, `north-west`. An incomplete set is an
error, not a fallback.

## 3. Put the NPC in an evening

Reference defaults only:

```json
{ "character": "new_id", "arrives_at": 0 }
```

For a bartender use `{ "character": "new_id", "post": "bar" }`. Scenario entries
may later override defaults, but do not duplicate profile fields to make a default
scenario work. No frontend registration is needed: the app fetches the public catalog
and generates its sprite registry from it.

## 4. Verify

Run `make check` and `make build`. Start the app and confirm the new person appears
with their sprite. The loader rejects missing poses or directions, non-68px art,
opaque art, malformed profiles, unknown carried items, and bad relationship targets.

# Character catalog and NPC authoring plan

Agreed 2026-10-11 and implemented in the character-catalog migration. This
document records the agreed architecture and acceptance checks.

**Changes planned for Stage 2.** Characters move into casts: `characters/guests/`
(famous characters), `characters/locals/` (the six characters below) and
`characters/staff/` (Hob) in [S2-01](plan/2_story_evenings/01_casts.md). Cards gain
persona fields (`inspired_by`, `origin`, `persona`, `catchphrases`, `obsessions`,
`mute`) in [S2-03](plan/2_story_evenings/03_persona_cards.md), and signature items in
[S2-08](plan/2_story_evenings/08_signature_items.md). The layout below is the one
in use until those tasks land; each task updates this document.

## Goal

Keep everything authored for an NPC under the repository-root
`characters/<id>/`: their description, background, relationships, traits,
default starting inventory, role, and all existing game images. The backend,
browser, and headless runner consume this single source. Adding a complete NPC
must not require editing a character list in Python or TypeScript.

The catalog describes a character before an evening starts. The world and its
saves describe that character during a particular evening. Drinking, gifts,
injuries, and changing opinions never write back into the catalog.

## Agreed scope

- Include Edda, Rurik, Toren, Brida, Calder, Saye, and Hob in the same catalog.
  Give every character an explicit `role`: `guest` or `bartender`. Hob's role
  preserves his existing bar duties; occupation remains descriptive text.
- Move the current images from `frontend/static/characters/`. No new portraits,
  replacement art, animation system, or paid generation is part of the migration.
- Preserve the existing symmetric relationship mechanics and numeric traits.
- Store goal, inventory, and relationships as character defaults. A later task
  may override them for one scenario without editing the character's source.
  Do not implement an override mechanism in this work.
- Every required pose must have all eight compass views: `north`, `north-east`,
  `east`, `south-east`, `south`, `south-west`, `west`, and `north-west`.
  These are eight directions for each pose, not a total of eight poses.
- A character needs the full image set for their role before the application
  can register them. Incomplete art is an actionable validation error, not a
  playable character with placeholder or fallback images.
- Keep `secret` in `characters/<id>/character.json` and in model-facing cards.
  Do not show it in the interface or send it in public character data or world
  snapshots. This adds no secret-revelation mechanic or dialogue policy.
- Guest selection, evening-setup UI, custom-card UI, and choosing news are
  outside this work. Do not design those flows here; E26 remains separate.

## Current sources to migrate

- `data/characters/*.json`: six guests' words, traits, appearance, and sex.
- `data/staff/hob.json`: the bartender's card, currently loaded separately.
- `data/scenarios/first_evening.json`: repeated identity and appearance fields,
  default carried items, and the three starting relationships.
- `frontend/static/characters/<sprite>/`: images and PixelLab metadata.
- `frontend/src/sprites.ts`: the manual character registry, display sizes,
  foot offsets, and supported poses.
- `backend/tavern/server/api.py`, `backend/tavern/app.py`, and
  `scripts/evening.py`: separate card-loading and scenario wiring.

Actor IDs already match the intended directory names. Existing sprite aliases
are `brida` -> `cook`, `calder` -> `courier`, `saye` -> `visitor`, and
`hob` -> `bartender`; Edda, Rurik, and Toren already match. Saved worlds contain
these old sprite names and embedded cards, so moving files alone is insufficient.

## Proposed layout

```text
characters/
  edda/
    character.json
    relationships.json
    visuals.json
    art/
      Idle/
        rotations/
          north.png
          north-east.png
          east.png
          south-east.png
          south.png
          south-west.png
          west.png
          north-west.png
      ...other required poses...
    source/
      pixellab.json
      prompts.md
  rurik/
  toren/
  brida/
  calder/
  saye/
  hob/
```

`character.json` owns `id`, `role`, `name`, `color`, `looks`, `occupation`,
`background`, `temperament`, `speech`, `quirks`, `secret`, `goal`, `sex`,
`params`, and `carries`. Retain the existing nine 0-1 parameters: patience,
temper, sociability, courage, strength, brawling, tolerance, comfort, curiosity.
Use the existing item kinds and limits; an empty starting inventory is `{}`.
There is no second manually maintained biography or trait list.

`relationships.json` owns default symmetric ties. Proposed records are
`{with, kind, note}`: `with` is another catalog ID, `kind` is one of the current
`old friends`, `rivals`, or `bad blood`, and `note` explains their shared past.
Store each pair once, in the directory whose ID sorts first, and derive both
participants' views. For example, the Edda-Brida tie lives under Brida. Reading
Edda's resolved profile still returns all her ties, including that one. Reject
duplicate pairs and conflicting records rather than choosing one silently.

`visuals.json` owns the actual canvas size, display size, foot offset, and
available pose paths relative to the character directory. Identity comes from
the character ID, not a separately editable sprite alias. Common required pose
sets belong in one shared contract per role, not in every character's manifest.

`source/pixellab.json` keeps existing export metadata and stable base, group,
and state IDs. `source/prompts.md` records known prompts, references, and review
notes. Preserve available provenance without inventing missing historical
prompts. Neither file is browser content.

The filenames and relationship ownership above are proposed implementation
choices. Freeze their exact validated shapes in the first task before migration.

## Implementation tasks

### CATALOG-1 — Define and validate a complete character

- [ ] Define typed records and pure parsers beside the existing character-card
  concept, retaining `mind/cards.py` as the model-facing card contract.
- [ ] Validate directory-safe IDs matching the folder name, roles, text bounds,
  exact trait names and ranges, colors, and default item counts. Reuse current
  card, inventory, and relationship validation where it applies.
- [ ] Validate all relationship targets against the complete catalog, including
  people absent from the current evening. Reject self-ties and duplicate pairs.
- [ ] Define the role's required pose set once. The current guest set has 21
  poses; the bartender has 16, including `PouringBeer`. All require eight views.
  Derive manifests, consumers, and validation from the same role contract.
- [ ] Validate that every required PNG exists, decodes, has transparency, and
  matches its declared native canvas. Validate relative paths stay inside the
  character directory. The current migrated stills are native 68 x 68.
- [ ] Define an explicit public projection excluding `secret` and source
  metadata, while retaining the full model-facing card on the server.

**Check:** write failing behavior tests first for one valid character, an empty
catalog, empty inventory and ties, duplicate IDs and pairs, malformed records,
unknown roles/items/targets, invalid counts/traits, unsafe paths, and missing or
invalid PNGs. A missing diagonal in any required pose must prevent registration.
Use a single-character catalog with empty ties and a multi-character catalog
with a symmetric tie. Diagnostics name the file, character, and bad field or
missing pose/direction. Run the narrow tests after each behavior change.

### CATALOG-2 — Migrate content and share backend loading

- [ ] Add filesystem loading in an adapter, with the root path supplied by the
  shell. Core receives validated records and performs no filesystem I/O.
- [ ] Move all seven profiles, defaults, and current image files into the new
  layout. Preserve words, traits, item quantities, PNG bytes, and source IDs.
- [ ] Resolve each participant's name, color, card, traits, and visuals from
  the catalog. Keep arrival times, working posts, news, needs, seed, and closing
  configuration in the scenario. Its participants reference characters by ID.
- [ ] Resolve defaults into the same runtime structures used today. Keep the
  current guest/staff distinction and reject casting a bartender as a guest.
- [ ] Include a default tie in an evening only when both characters participate;
  retain the existing symmetric opinions, familiarity, and model wording.
- [ ] Use the same loader in the server and headless runner, replacing the
  separate guest/staff directories and duplicated filesystem reads.
- [ ] Preserve actor IDs and the saved-world format. Saved sessions retain their
  embedded state, inventories, and cards; later catalog edits must not rewrite
  a resumed evening. Map the four legacy sprite aliases explicitly for rendering.

**Check:** compare the migrated first evening's resolved identities, traits,
goals, carried items, and three ties to the existing behavior. Verify the server
and headless runner use the same content. Test save/load with old sprite aliases,
and resuming after a catalog edit. Never change the save version merely to move
source files; any unavoidable format change requires separate agreement.

### CATALOG-3 — Publish browser data and assets from the catalog

- [ ] Serve a typed public catalog projection and rendering manifest derived
  from validated profiles. Do not maintain a second list of NPCs in TypeScript.
- [ ] Replace `SPRITES`' manual identity entries with catalog data. Keep general
  pose-selection logic separate from Phaser, and preserve facing and foot pivots.
- [ ] Publish only game PNGs and approved public metadata in development and
  production builds. Generated output may be copied from the catalog but is
  reproducible and never edited manually. Do not expose the entire root folder.
- [ ] Remove `secret` from browser snapshots as well as catalog responses. The
  current runtime deep-copies the whole world; review actors, expected arrivals,
  and departed actors so their embedded cards do not bypass the public projection.
  Keep full cards in persistence and model inputs. Update `types.ts` with the
  public snapshot contract instead of weakening the saved-card parser.
- [ ] Remove obsolete authoring sources after all consumers switch. Keep only
  explicit compatibility aliases needed by saved sessions. Existing pose
  fallback logic must not let an incomplete new character pass catalog validation.

**Check:** a complete temporary NPC is discovered without editing application
registries; an incomplete one fails with a useful error. Check all seven migrated
characters and every required pose/view in a production build. Test that catalog
responses, HTTP state, WebSocket snapshots, and published files omit `secret`,
while saved cards and model inputs keep it. Check the live app's eight directions,
seated actions, handovers, combat, and bartender pouring. Update path-based asset
tests because source paths change, retaining their coverage and assertions.

### CATALOG-4 — Write and exercise the project `add-npc` skill

- [ ] Add `.agents/skills/add-npc/SKILL.md` with a validated profile template,
  authoring checklist, art workflow, and completion criteria. Link to the shared
  schema and [character art pipeline](CHARACTER_ART_PIPELINE.md), rather than
  maintaining a second independent list of fields or required poses.
- [ ] Explain how to write English game content: a concrete occupation and past,
  observable habits, recognizable speech, a motive for visiting, and an achievable
  goal. Keep `secret` in the full profile; do not put it in public display text.
  Traits, relationships, inventory, and appearance must support the description.
- [ ] Explain every existing trait and item constraint. The existing card compiler
  can propose traits; its output needs validation and author review. Its labeled
  offline defaults are not model-derived traits. Adding an NPC must not require
  inventing a new game mechanic, item kind, or role.
- [ ] Describe PixelLab MCP calls by name and purpose:
  1. Read the art pipeline and inspect a current character's style reference.
  2. Use `get_pro_flash_capabilities` and `get_balance` to check native 68 x 68,
     eight-direction support and the available budget. Obtain user authorization
     before spending credits, including a retry or an additional pose batch.
  3. Use `create_character_pro_flash` for a new individual, matching the current
     camera, scale, outline, and palette. Do not use `create_character_state` to
     create a different person. Reuse an approved first frame when available.
  4. Wait through `wait_for_jobs` and `get_character`; inspect actual PNG dimensions
     and all eight base views before ordering the remaining poses. A nominal
     68 px request is insufficient: the older standard route returned 96 px.
  5. Use `create_character_state` on the base ID for each required pose, with an
     explicit `state_name`, the same identity/outfit/proportions, palette reuse,
     and no canvas override unless separately justified. Resume from recorded IDs
     after interruption instead of ordering completed work again.
  6. Review every pose and view at native game scale. Use `save_to_asset` only
     for an intended existing state/direction correction, never to overwrite Idle
     with a new action. Check weapons, mugs, and furniture against game overlays.
  7. Export all eight directions into the NPC's folder. Record stable IDs,
     actual sizes, references, and prompts; expiring download URLs are insufficient.
- [ ] Require the full role-specific set before integration. Do not generate an
  extra portrait, register a draft, or substitute another NPC's art to finish.
- [ ] Document validation and a temporary scenario smoke check without changing
  the shipped evening's cast or building guest-selection UI. Exercise authoring
  with an existing complete local export; live paid generation is not required
  to validate the skill. Finish with `make check`, `make build`, and in-app review,
  reporting the actual output and any missing prerequisites.

**Check:** follow the skill using a local fixture to produce a complete valid
character directory without manual registry edits. A reader can identify each
required field, MCP call, budget boundary, source record, and verification step.
Keep all automated tests offline; no real Jev/Claude calls or PixelLab spending.

## Completion criteria

- [ ] Seven current NPCs live under `characters/<id>/`, including Hob's explicit role.
- [ ] There is one editable source for every profile, default, relationship pair,
  and image; backend, browser, and headless runner consume it.
- [ ] All 1,136 current PNGs survive migration: six guests x 21 poses x eight
  views, plus Hob x 16 poses x eight views. New profiles cannot register incomplete.
- [ ] The first evening behaves as before, and existing sessions resume correctly.
- [ ] `secret` remains in each full profile and model input, and is absent from
  public data, published files, and the interface.
- [ ] A complete NPC can be added by following the skill and adding their directory,
  without editing a manual application registry.
- [ ] `make check` and `make build` pass, with output recorded and in-app art reviewed.
- [ ] No guest-selection UI, scenario override mechanism, new portrait, new game
  system, save-format change, or paid art generation was bundled into the migration.

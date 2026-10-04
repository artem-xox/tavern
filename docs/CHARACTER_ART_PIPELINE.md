# PixelLab character pipeline: 68 px stills

Tested 2026-10-03 with a Tier 1 PixelLab account. Six 68 px character
groups now supply the tavern's visitors. This document records their source
IDs, the renderer mapping, and the generation limits found in practice.

**Rule for future generations: four cardinal directions only** (north, south,
east, west). The game has no need for diagonals. PixelLab Pro Flash currently
generates eight directions for an exact 68 px character; we export and ship
only four. Before making another character, look for a true 68 px four-view
route or agree on a nearby supported size. Do not order eight views simply
because the current tool defaults to them.

## What the game needs

`frontend/src/types.ts` defines eleven action verbs. `backend/tavern/world.py`
executes them, while `frontend/src/scene.ts` loads four cardinal views for each
of nine poses. Walking remains interpolated between cells with one still per
direction. The beer mug and chat bubble are separate Phaser overlays. The
pose set below covers every verb without
making a unique image for actions that look the same.

- `take_beer` → **TakeBeer**, reaching toward the tap. Hide the drawn mug if
  the state already includes a tankard.
- `drink` → **DrinkingSeated** when the actor has a seat; otherwise
  **Drinking**. Both include a tankard, so hide the separate mug overlay.
- A seated participant in a conversation → **TalkingSeated**, with a hand
  gesture that reads as speech at native size.
- `rest` and `sit` → **Seated**. The actor also stays Seated between actions
  while `seat_id` is set.
- `talk` → **TalkingSeated** when seated, with the existing speech bubble.
  Use **Talking** only when the speaker is standing.
- `play_darts` → **Darts**, arm raised toward the board.
- `use_toilet` → **Bathroom**, compact seated pose facing the privy. The room
  and screen provide context; the sprite should not contain furniture.
- `watch` → **Idle** turned toward the fireplace or window. A separate pose
  adds little visual information at 68 px.
- `inspect` and `leave` → **Walking** while moving; `inspect` at its target
  and `leave` before departure can use Idle. Walking is a single still until
  animation is deliberately added.
- `wait` → **Idle**. Idle also covers thinking and standing between actions.

The `seating` candidate in `backend/tavern/agents.py` chooses a seat; it is
not an additional action verb or pose. “Walking” is an actor status rather
than a verb, but needs its own visual mapping when approved.

## Size and creation method

The current cast uses a **native 68 × 68 transparent canvas**, not a 96 px
image scaled down by Phaser. A 68 px canvas is a custom Pro Flash size.
`get_pro_flash_capabilities(operation="character", width=68, height=68,
n_directions=8)` quoted **6 generations** for image plus rotations. Three
`create_character_pro_flash` jobs produced actual 68 × 68, eight-direction
Idle states. For future production, first approve a separate 68 px south sprite,
then pass it as `first_frame_url` or `source_image_id` to Pro Flash; that
reuse path is supported by the tool but was not tested here. Review
north/east/west as carefully as south. [PixelLab's character and state
API overview](https://www.pixellab.ai/pixellab-api).

The cheaper `create_character(mode="standard", size=68, n_directions=4)`
accepted the request but **returned 96 × 96** for all three trials, including
Toren's 2026-10-02 retry. Its immediate response claimed 68 × 68; only
`get_character` exposed the actual size. This mismatch was reported to
PixelLab. Pro Flash supports one or eight directions, not four; its
`create_character_state` generates every direction of the base. Do not rely
on the standard route for exact 68 px until a completed export verifies it.
For the next cast, test a lower nearby size with four views before buying
any action states. The older automatic
animation tool also has a 64 × 64 maximum, so it does not fit this target.
[PixelLab automatic animation limits](https://www.pixellab.ai/docs/tools/create-animations-automatic).

Use the same low top-down camera, 68 px canvas, muted medieval palette,
dark outline, and full-body centered composition for every character. Toren
used Edda's south sprite as Pro Flash `style_image` with palette, outline,
shading, and detail options; his south view stayed distinct and broadly
matched the cast. Four cardinal views should be the first constraint when
choosing the next creation method.

## Tested characters and states

These are PixelLab library assets, with four cardinal PNGs per state copied to
`frontend/static/characters/<slug>/`. Use the stable IDs below with
`get_character`; avoid saving expiring image URLs as source records.
Each state's `get_character` result includes the shared `group_id`, rotations,
and a group download. They are native named siblings, unlike the old
independent workbench stills; verify their appearance on the Character page.

**Edda, border healer** — base `70cb1b10-0d43-480d-93e7-6a0920d55778`,
group `b846223d-49fb-4387-ab84-3063bbfc30d3`.

- Idle: `70cb1b10-0d43-480d-93e7-6a0920d55778`
- Seated: `a76df051-a453-40e2-95ed-cdf1d0e0591d`
- Darts: `4b329c01-6c44-4def-96d3-5c009ca1fa6f`
- Bathroom: `6f890123-4ce2-469e-b3ea-e5bdd8adc8a3`
- Drinking: `ac2b947d-fc05-4586-9a0a-8fc1b274735c`
- DrinkingSeated: `301f42fc-f5a1-40dd-80c8-53051267644c`
- TalkingSeated: `08463c9c-edca-4cef-9567-2afe3b33c267`
- TakeBeer: `adbc5b62-8af1-49e5-8e87-780ab38f057f`
- Walking: `955940d7-7e34-4eeb-9d10-a6d50557b70a`
- Talking: `4ec12ed2-c48b-4282-a42c-d2e6ef124878`

**Rurik, border guard** — base `72d81d2b-8274-46e4-b30d-607db83e6c2e`,
group `58958b80-af4b-46ac-a0b6-28e5bb25a722`. This leaner dark-haired
guard replaces the compact, round original Rurik group.

- Idle: `72d81d2b-8274-46e4-b30d-607db83e6c2e`
- Seated: `07db65b7-7059-4788-94e0-8cb5db9d169f`
- Darts: `5d01b034-a05a-4c4c-9a31-326f96fe5c6b`
- Bathroom: `344ab737-ca30-4fc5-90d4-3f9a61745be5`
- Drinking: `dc7044ae-d910-402a-9c88-25163031511c`
- DrinkingSeated: `1f31ede0-033b-4242-a6ea-93a309e3117c`
- TalkingSeated: `fae9587f-499b-4bd1-be5f-e15db1abbe82`
- TakeBeer: `7dcf0724-4c4f-48fd-aa29-4e909f62be87`
- Walking: `e70328c5-6101-4baf-91dd-c59437856941`
- Talking: `27cf2480-4f04-4e2f-8de8-9344743b4914`

**Toren, border trader** — base `ca874ea8-7b06-410b-9d4e-7ea585b9b93c`,
group `7cac920b-56f8-4f3d-9256-2f4fdf0565ad`.

- Idle: `ca874ea8-7b06-410b-9d4e-7ea585b9b93c`
- Seated: `2f65a5b1-0320-443e-af3a-793c8afd4666`
- Darts: `73ed2a18-7f8c-4780-beb2-282cd7545147`
- Bathroom: `b6d5d6d9-c583-4259-a29f-7583524120d8`
- Drinking: `957ae78b-e465-41ad-90da-82f2f04024e6`
- DrinkingSeated: `e689b767-01b7-477f-90ff-3528365a6f5f`
- TalkingSeated: `bf02d9a8-dcf0-47a3-832b-fd9a51df5790`
- TakeBeer: `e1e67432-381f-47b5-9474-a7d801e6f588`
- Walking: `feae7f97-da77-4045-85cc-178e3b4fed26`
- Talking: `4fb7de07-a422-406a-95d0-47f7bbe996c2`

**Brida, inn cook** — base `8727bfef-dd64-40c9-b344-a390bff7cb51`,
group `38504e4a-e0e8-40d9-b905-c3525abacefd`. Replaces the first evening's
old Idle-only veteran at 40 seconds, using the existing `cook` folder.

- Idle: `8727bfef-dd64-40c9-b344-a390bff7cb51`
- Seated: `7dd07b8a-5e93-4ecd-b759-bc103492443e`
- Darts: `e7cba64c-bdec-45f7-8b79-e366cd492d44`
- Bathroom: `ae1e63e8-0bb3-4815-b60e-21c23235c05b`
- Drinking: `8a86431e-3e7a-414c-b45d-ac982950c0ed`
- DrinkingSeated: `f5b22b85-d942-4488-8887-40b82df6c3da`
- TalkingSeated: `486a8430-8962-43d9-a4a4-50939a23493e`
- TakeBeer: `72841ad4-a481-4e58-b150-802908bcbfa8`
- Walking: `66c491ee-035c-44e9-85b0-c1fb8d78cdd0`
- Talking: `7642140b-b6a4-4ab1-9aad-7dfb69b462ab`

**Calder, road courier** — base `243262aa-8424-4bad-9100-433ddd43d8dc`,
group `bf431630-5232-41c8-96b7-6be67c003f4a`. Replaces the first evening's
old Idle-only traveler at 110 seconds, using the `courier` folder.

- Idle: `243262aa-8424-4bad-9100-433ddd43d8dc`
- Seated: `faa9208e-0691-4d02-a540-20cc93353330`
- Darts: `081c01f9-28ee-4ba3-b63f-4c1f6caa0388`
- Bathroom: `9979469e-25e6-416e-8888-0f33f668238e`
- Drinking: `522cabf3-93e2-410c-8ed1-7befc0f4d0ef`
- DrinkingSeated: `7b1ca7ff-acd4-46f8-9182-bce1918b509d`
- TalkingSeated: `86482795-ba2c-48cb-a38d-ddd1c3548058`
- TakeBeer: `58b5978c-b055-4f37-91a7-7a1e21ddd4fe`
- Walking: `d6766c3c-4a1d-467c-bc4e-a855632f8c28`
- Talking: `dcab5a35-bac4-410c-856d-0e128ed9f02b`

**Saye, traveling storyteller** — base `1e854b26-bd3f-4425-945c-baa541f8a0e5`,
group `6c8f78b2-3ea2-4174-8a1e-8f1cd6be218c`. Replaces the first evening's
old Idle-only merchant at 190 seconds, using the generic `visitor` folder.

- Idle: `1e854b26-bd3f-4425-945c-baa541f8a0e5`
- Seated: `fdf264fb-1849-490e-b216-220f721eee41`
- Darts: `d944b799-4656-49d4-a35d-9097545503b2`
- Bathroom: `324dc530-ac0e-4a8a-bde5-9b9fcbbb2c6e`
- Drinking: `036e6e97-aaa3-4f33-9669-323ce052b8b1`
- DrinkingSeated: `3822a9e3-68da-46d8-96b6-04e667fa6c74`
- TalkingSeated: `7040497a-9622-408b-831d-1baa71e64b4b`
- TakeBeer: `434836a1-0968-43c1-acc6-b4f02e7b43b0`
- Walking: `16ef800f-fa48-4726-8fac-a4a9c1e9ded2`
- Talking: `cb3a5e4f-8bcc-4079-835d-e130705f0766`

All 60 native assets (six Idle plus 54 action states) completed at 68 × 68.
Their PixelLab groups have eight rotations each, but only the four cardinal
rotations are in the browser build. `get_character` confirmed every state is
in its intended ten-state group. The two discarded
standard-mode trials, Edda
`5cc40ea8-affe-4283-a534-81f608009bec` and Rurik
`7b49907f-3d51-40de-9ee0-2589afd1ceef`, and Toren's trial
`78a4dfa2-c103-462a-93f2-63bfd645cf9b` are 96 × 96.

South-view inspection found these issues:

- Edda's Seated, Talking, Drinking, and Darts are visibly different from Idle.
  Bathroom is close to Seated, which is acceptable only if the privy screen
  supplies clear context. Walking looks too close to Idle at normal size.
- Rurik's replacement group has a slimmer full-body silhouette that matches
  Toren and the newer cast. Its south previews make Darts, Drinking,
  TakeBeer, Walking, Talking, and DrinkingSeated visibly distinct. The
  original compact group is no longer shipped.
- Edda is more compact and rounder than the old 92 px cast. A running tavern
  preview showed the 68 px sprites readable at native size.
- Toren's south views show readable Seated, Darts, Drinking, TakeBeer, and
  Talking actions. His Walking pose is subtle. The four shipped directions
  and foot pivots should be checked in the running tavern as art review.

The connected account reported 2,000 Tier 1 generations for this cycle.
The first three characters used 441 generations. Brida, Calder, and Saye each
used one Pro Flash base and seven named states. The balance after the six-character
run was 1,041/2,000. Six DrinkingSeated states used 120 generations, leaving
921/2,000. Rurik's replacement group used 166 generations, leaving 755/2,000.
Six TalkingSeated states used 120 generations, leaving 635/2,000.
PixelLab quotes 20–40
generations for `create_character_state`; check `get_balance` before
batching or retrying.
The native character states cost much more than a
single independent image because they preserve the individual across every
direction. [PixelLab API cost estimates](https://www.pixellab.ai/pixellab-api).

## Add a future pose to an existing character

1. Check the code's action/status mapping first. Reuse Idle, Seated, or a
   directional pose when that tells the player enough; only add a state for
   a new readable silhouette.
2. Call `create_character_state` with the **base character ID**, a short
   `state_name`, and an edit that says “same face, outfit, colors and scale;
   change only pose.” Set `use_color_palette_from_reference=true`; leave
   `override_width` and `override_height` unset to keep 68 × 68. This creates
   a new named sibling in the character group, unlike `save_to_asset`.
3. Wait for completion with `wait_for_jobs` and `get_character(new_state_id)`.
   Check `size`, `state_name`, all direction URLs, and `group_id`. Preview
   south, north, east, and west at 1×. The game does not use diagonals.
4. If a direction is weak or reversed, correct that **state's** rotation
   with PixelLab's image editor/workbench, then `save_to_asset(image=...,
   target="character:<state_id>:<direction>")`. This replaces one existing
   rotation and offers an undo call; it does **not** create a new state. Do
   not save a new action over Idle.
5. Download the group from the `download` URL in `get_character`; copy only
   the four cardinal PNGs per state into the game. Keep its `metadata.json`
   and the source IDs in this document. A state result's download bundles
   every sibling state. The PixelLab library retains the full originals.

For example, after reviewing Edda, a new “Reading” pose would use
`create_character_state(character_id="70cb1b10-0d43-480d-93e7-6a0920d55778",
state_name="Reading", edit_description="Same Edda ... change only pose ...",
use_color_palette_from_reference=true)`. Give the new state a unique name;
using another character creation call would make a new individual instead.

## Game integration

The first evening now has six 68 px guests: Edda, Rurik, and Toren arrive at
opening; Brida, Calder, and Saye replace the old Idle-only later arrivals.
The original guest IDs remain stable so saved sessions and force-action commands
stay compatible. Each guest's `sprite` in the scenario
(`data/scenarios/first_evening.json`) names their folder, and
`frontend/src/sprites.ts` lists every shipped folder with its display size and
the poses it has in all four directions. `frontend/src/scene.ts` loads those
PNGs with nearest-neighbor filtering, drawing this cast at its native 68 px
size. A pose a sprite lacks is drawn as Idle. Walking status selects
Walking. Drinking while seated selects DrinkingSeated; seated conversation
participants select TalkingSeated; other active actions select their named pose;
an occupied seat otherwise selects Seated. Idle
covers watch, inspect, wait, and arrival/departure when not moving. The actor
faces its seat or action target when stationary. The separate mug overlay is
hidden during Drinking, DrinkingSeated, and TakeBeer, whose art already
includes a tankard. Only these six 68 px character folders ship in the game.

The existing [tavern pixel art plan](PIXEL_ART_REDESIGN.md) remains the room
counterpart to this character workflow.

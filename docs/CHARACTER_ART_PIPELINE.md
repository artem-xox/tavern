# PixelLab character pipeline: 68 px stills

Tested 2026-10-02 with a Tier 1 PixelLab account. Three 68 px character
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
of eight poses. Walking remains interpolated between cells with one still per
direction. The beer mug and chat bubble are separate Phaser overlays. The
pose set below covers every verb without
making a unique image for actions that look the same.

- `take_beer` → **TakeBeer**, reaching toward the tap. Hide the drawn mug if
  the state already includes a tankard.
- `drink` → **Drinking**, tankard at mouth. Hide the separate mug overlay.
- `rest` and `sit` → **Seated**. The actor also stays Seated between actions
  while `seat_id` is set.
- `talk` → **Talking** when seated, with the existing speech bubble. A Seated
  fallback is acceptable if a Talking pose fails review.
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
- TakeBeer: `adbc5b62-8af1-49e5-8e87-780ab38f057f`
- Walking: `955940d7-7e34-4eeb-9d10-a6d50557b70a`
- Talking: `4ec12ed2-c48b-4282-a42c-d2e6ef124878`

**Rurik, border guard** — base `206359ae-58b9-4175-988e-4325b536abeb`,
group `d0e1751d-6fc5-409c-ae81-9680ed03834b`.

- Idle: `206359ae-58b9-4175-988e-4325b536abeb`
- Seated: `0d4e08a3-c4ba-43e5-bfc5-e1d92a5cf3dd`
- Darts: `e1b97886-2ac2-4cf4-b759-cc2df6f9d143`
- Bathroom: `d8f5a9e3-40bc-4549-8dea-b494cad7e7e7`
- Drinking: `119b8d75-98a5-43ca-a8f1-768deeec926c`
- TakeBeer: `4716426a-7249-4cba-88b8-1934a37628a3`
- Walking: `f16d07e9-57d3-464c-a55a-1b7464c2e185`
- Talking: `926b9960-a169-4050-84af-dd99a8ed9fb1`

**Toren, border trader** — base `ca874ea8-7b06-410b-9d4e-7ea585b9b93c`,
group `7cac920b-56f8-4f3d-9256-2f4fdf0565ad`.

- Idle: `ca874ea8-7b06-410b-9d4e-7ea585b9b93c`
- Seated: `2f65a5b1-0320-443e-af3a-793c8afd4666`
- Darts: `73ed2a18-7f8c-4780-beb2-282cd7545147`
- Bathroom: `b6d5d6d9-c583-4259-a29f-7583524120d8`
- Drinking: `957ae78b-e465-41ad-90da-82f2f04024e6`
- TakeBeer: `e1e67432-381f-47b5-9474-a7d801e6f588`
- Walking: `feae7f97-da77-4045-85cc-178e3b4fed26`
- Talking: `4fb7de07-a422-406a-95d0-47f7bbe996c2`

All 24 native assets (three Idle plus 21 action states) completed at 68 × 68.
Their PixelLab groups have eight rotations each, but only the four cardinal
rotations are in the browser build. `get_character` confirmed every state is
in its intended eight-state group. The two discarded
standard-mode trials, Edda
`5cc40ea8-affe-4283-a534-81f608009bec` and Rurik
`7b49907f-3d51-40de-9ee0-2589afd1ceef`, and Toren's trial
`78a4dfa2-c103-462a-93f2-63bfd645cf9b` are 96 × 96.

South-view inspection found these issues:

- Edda's Seated, Talking, Drinking, and Darts are visibly different from Idle.
  Bathroom is close to Seated, which is acceptable only if the privy screen
  supplies clear context. Walking looks too close to Idle at normal size.
- Rurik's Seated and Talking are legible. Darts has a weak arm gesture;
  Walking also looks too close to Idle. Drinking reads more like a held mug
  than an obvious sip. His TakeBeer south image appears back-facing, so that
  view needs art correction if a future layout puts the tap south of him.
- Edda and Rurik are more compact and rounder than the old 92 px cast. A
  running tavern preview showed all three new sprites readable at native size.
- Toren's south views show readable Seated, Darts, Drinking, TakeBeer, and
  Talking actions. His Walking pose is subtle. The four shipped directions
  and foot pivots should be checked in the running tavern as art review.

The connected account reported 2,000 Tier 1 generations for this cycle.
The first two characters used 294 generations. Toren added 147: one discarded
standard base × 1, one Pro Flash base × 6, and seven named states × 20.
The balance after completion was 1,559/2,000. PixelLab quotes 20–40
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
5. Download the group from the `download` URL in `get_character`; keep only
   the four cardinal PNGs per state in source control. Retain `metadata.json`
   with source IDs and `source_directions=8`, while `exported_directions` and
   file paths list the four shipped views. A state result's download bundles
   every sibling state. The PixelLab library retains the full originals.

For example, after reviewing Edda, a new “Reading” pose would use
`create_character_state(character_id="70cb1b10-0d43-480d-93e7-6a0920d55778",
state_name="Reading", edit_description="Same Edda ... change only pose ...",
use_color_palette_from_reference=true)`. Give the new state a unique name;
using another character creation call would make a new individual instead.

## Game integration

The default visitor IDs remain `mara`, `ivo`, and `nell` so saved sessions and
force-action commands stay compatible; new evenings display Edda, Rurik, and
Toren respectively. Each guest's `sprite` in the scenario
(`data/scenarios/first_evening.json`) names their folder, and
`frontend/src/sprites.ts` lists every shipped folder with its display size and
the poses it has in all four directions. `frontend/src/scene.ts` loads those
PNGs with nearest-neighbor filtering, drawing this cast at its native 68 px
size. A pose a sprite lacks is drawn as Idle. Walking status selects
Walking. Active actions select their named pose; an occupied seat otherwise
selects Seated. Idle covers watch, inspect, wait, and arrival/departure when
not moving. The actor faces its seat or action target when stationary.
The separate mug overlay is hidden during Drinking and TakeBeer, whose art
already includes a tankard. The generic visitor fallback remains 92 px.

The older 92 px traveler, veteran, and merchant stills dress the first
evening's later guests (Wenna, Brannoc, and Osric). They ship Idle in four
directions only (their single-direction Seated, Darts, and Bathroom stills are
not used), so these guests stay in Idle, drawn at 92 px like the visitor.

The existing [tavern pixel art plan](PIXEL_ART_REDESIGN.md) remains the room
counterpart to this character workflow.

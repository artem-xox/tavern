# PixelLab character pipeline: 68 px stills

Tested 2026-10-02 with a Tier 1 PixelLab account. This is a generation and
integration plan, plus the results of two character experiments. No new sprite
was added to the game in this pass.

## What the game needs

`frontend/src/types.ts` defines eleven action verbs. `backend/tavern/world.py`
executes them, while `frontend/src/scene.ts` currently loads four directional
Idle images and switches only to Seated, Darts, or Bathroom stills. Walking is
an interpolated position using an Idle direction. The beer mug and chat bubble
are separate Phaser overlays. The pose set below covers every verb without
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

Target a **native 68 × 68 transparent canvas**, not a 96 px image scaled down
by Phaser. A 68 px canvas is a custom Pro Flash size (multiple of four, beta).
`get_pro_flash_capabilities(operation="character", width=68, height=68,
n_directions=8)` quoted **6 generations** for image plus rotations. Two
`create_character_pro_flash` jobs produced actual 68 × 68, eight-direction
Idle states. For production, first approve a separate 68 px south sprite,
then pass it as `first_frame_url` or `source_image_id` to Pro Flash; that
reuse path is supported by the tool but was not tested here. Review
north/east/west as carefully as south. [PixelLab's character and state
API overview](https://www.pixellab.ai/pixellab-api).

The cheaper `create_character(mode="standard", size=68, n_directions=4)`
accepted the request but **returned 96 × 96** for both trial characters. Do
not rely on that route for an exact 68 px export. The older automatic
animation tool also has a 64 × 64 maximum, so it does not fit this target.
[PixelLab automatic animation limits](https://www.pixellab.ai/docs/tools/create-animations-automatic).

Use the same low top-down camera, 68 px canvas, muted medieval palette,
dark outline, and full-body centered composition for every character. For
later new individuals, try a reviewed 68 px sprite as Pro Flash's
`style_image` with palette/outline/detail options; this style-reference step
is supported by the tool but was **not tested** in this experiment. Establish
one accepted example in the running tavern before batch creation.

## Tested characters and states

These are PixelLab library assets, not files in this repo. Use the stable IDs
below with `get_character`; avoid saving expiring image URLs as source records.
Each state's `get_character` result includes the shared `group_id`, rotations,
and a group download. They are native named siblings, unlike the independent
workbench stills used for the current cast; verify their appearance on the
Character page as part of acceptance.

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

All 16 native assets (two Idle plus fourteen action states) completed at
68 × 68 with eight rotations each. A final `get_character` audit confirmed
every state is in its intended eight-state group. The two discarded
standard-mode trials, Edda
`5cc40ea8-affe-4283-a534-81f608009bec` and Rurik
`7b49907f-3d51-40de-9ee0-2589afd1ceef`, are 96 × 96.

South-view inspection found these issues:

- Edda's Seated, Talking, Drinking, and Darts are visibly different from Idle.
  Bathroom is close to Seated, which is acceptable only if the privy screen
  supplies clear context. Walking looks too close to Idle at normal size.
- Rurik's Seated and Talking are legible. Darts has a weak arm gesture;
  Walking also looks too close to Idle. Drinking reads more like a held mug
  than an obvious sip. The TakeBeer south image appears back-facing and must
  be corrected before use.
- Both bases are more compact and rounder than the existing 92 px cast. A
  side-by-side test in the tavern is still needed before adopting this style.
- All eight directions and ground pivots still need frame-by-frame review;
  a good south preview alone is not an acceptance check. No app integration
  or in-game readability claim is made here.

The connected account reported 2,000 Tier 1 generations for this cycle.
The run used 294 generations: 2 discarded standard bases × 1, 2 Pro Flash
bases × 6, and 14 named states × 20. The balance after completion was
1,706/2,000. PixelLab quotes 20–40 generations for
`create_character_state`; check `get_balance` before batching or retrying.
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
   south, north, east, and west at 1×; check the diagonals before export.
4. If a direction is weak or reversed, correct that **state's** rotation
   with PixelLab's image editor/workbench, then `save_to_asset(image=...,
   target="character:<state_id>:<direction>")`. This replaces one existing
   rotation and offers an undo call; it does **not** create a new state. Do
   not save a new action over Idle.
5. Download the group from the `download` URL in `get_character`; preserve
   its `metadata.json`, state folders, native PNGs, prompt, tool, and IDs in
   source control when the art is accepted. A state result's download bundles
   every sibling state. Keep a reviewed local export even though the PixelLab
   library retains the originals.

For example, after reviewing Edda, a new “Reading” pose would use
`create_character_state(character_id="70cb1b10-0d43-480d-93e7-6a0920d55778",
state_name="Reading", edit_description="Same Edda ... change only pose ...",
use_color_palette_from_reference=true)`. Give the new state a unique name;
using another character creation call would make a new individual instead.

## Integration and acceptance plan

1. Select one of the two pilots only after reviewing a contact sheet of all
   eight directions per state and compositing it beside the current cast on
   the 32 px tavern grid. Correct identity drift, reversed facings, clipped
   limbs, duplicate mugs, and foot-position jumps before export.
2. Add reviewed `68 × 68` state PNGs and export metadata under one
   `frontend/static/characters/<slug>/` folder. Keep the native size; use
   nearest-neighbor filtering and a stable foot anchor in Phaser. Adjust
   name, status, speech, shadow, mug, and seated offsets that currently
   assume a 92 px image in `frontend/src/scene.ts`.
3. Make pose selection explicit: a walking status chooses Walking only if
   that pose passed review; active action chooses its mapped state; an
   occupied chair otherwise chooses Seated; all else chooses directional
   Idle. Keep a fallback to Idle if an action state is missing. Point the
   character toward its action target or seat facing where available.
4. Use the force-action controls to verify every verb in the running app,
   including a seated drink and talk, darts, WC, beer tap, watch at a
   window and fireplace, wait, inspect, and leave. Check that every sprite
   aligns with its cell, does not hide selection, and stays crisp at the
   canvas's displayed scale. Add animation only after these stills work.

The existing [tavern pixel art plan](PIXEL_ART_REDESIGN.md) remains the room
counterpart to this character workflow.

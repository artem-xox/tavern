# Tavern room art plan

## Target and constraints

Use [the supplied room reference](references/tavern-room.png) as the visual target:
dark slate block perimeter, long warm-brown floorboards, amber pools of light,
the hearth centered on the north wall, a crowded bar in the northwest, a pale
stone privy in the northeast, five small colored table rugs, and restrained
plants, banners, barrels and wall lights. The reference is art direction, not
an image to place behind the game or a source of gameplay rules. It has no
written instructions. Match its composition, contrast and material language;
keep the existing cast and the current activity locations.

The game canvas is **20 × 14 cells at 32 px = 640 × 448**. The supplied image is
1489 × 1056, so its pixels cannot be treated as a 1:1 game tileset. Use native
32 px art and review it beside the shipped 68 px characters. Do not enlarge a
small image and call it a native 32 px tile. Preserve `data/tavern.json`'s
object IDs, coordinates, blocked cells, seats, interaction spots and routes.
The current map already has the reference's five table groups: four ordinary
tables and a central dice table. It also already places the hearth at (9, 0),
bar at (3, 2), privy at (17, 2), darts at (1, 8), three west windows and south
door at (10, 13). No world or save-format change is needed for the art pass.

The first milestone is a believable room at normal game zoom with the current
evening playing through it. Do not add new interactive furniture, character
poses or an animation pipeline until that is working.

The [Codex style pilot](references/tavern-style-pilot-codex.png) is a mood and
composition sample made from the reference on 2026-10-04. It is 1374 × 1145,
not a tile atlas or a seamless 32 px game asset. Do not place it in the game.

## Who makes what

| Work | Best route | Reason |
| --- | --- | --- |
| Composition, palette, native-size mockup, tile cleanup, color variants, Phaser layering and light | Codex in this repo | Exact dimensions, seams, anchors and interactions need deterministic edits and a running-game check. PixelLab's `pixelart_workbench` can help with exact pixel cleanup without a new AI generation. |
| Seamless floor and connected slate walls | PixelLab `create_building_kit`, after a cheap sample | Its building mode makes floor, wall joins and doorways as one vocabulary. Generate at 32 px, square top-down, one-tile walls; inspect every connection. If its plank direction or walls fail, draw/repair these few pieces directly. |
| Large focal props: hearth, bar, privy, dartboard, table, chair | PixelLab `create_map_object` or transparent `create_image_pixflux`, directed by Codex | These have distinctive silhouettes and benefit from generation. Export individual transparent PNGs and correct outlines/anchors by hand. For a coherent style, give `create_map_object` a crop of the approved room when its 192 px inpaint limit fits. |
| Tiny repeated details: dice, mugs, candle flame, bottle shapes, rug recolors, glow and vignette | Codex pixel editing and Phaser | A generator adds needless variation and cost to 5–12 px marks or effects. Keep tabletop details on separate layers when game state may change. |
| Full-room concept image | Already supplied | A second concept image would not produce the exact separable assets the game needs. PixelLab's Tier 1 map limit is below 640 × 448, and a flattened room would break editable walls and actor depth. |

I can run the connected PixelLab tools, inspect the returned native dimensions,
export the approved art and integrate it; there is no need to switch manually
between this chat and PixelLab unless visual selection in its editor is easier.
**Do not spend PixelLab generations during planning.** On 2026-10-04 the account
had 409 of 2,000 generations left, resetting 2026-11-02. Check the live balance
and the quoted cost immediately before a generation batch. The building kit is
currently documented at about 20–25 generations. Approve the cheap composition
pilot first.

### Generation budget

The estimate assumes **one 32 px building kit** at 20–25 generations and
**17–20 individual transparent image attempts** for the reusable focal props
and decorations. Floor/rug variants, tiny marks and lighting are made with
pixel edits or code. The Codex style pilot above used no PixelLab generations.

- **Everything usable on the first try:** about **37–45 PixelLab generations**.
- **Every asset needs five attempts total:** about **185–225 generations**.
- **Every asset needs ten attempts total:** about **370–450 generations**;
  this can exceed the 409 remaining on 2026-10-04. These are scenario
  estimates, not a quote: `create_map_object` and other modes may have a
  different charge. Verify each tool's quoted cost and balance before use.

The building kit dominates retry risk: five attempts alone cost 100–125,
ten cost 200–250. Stop after two failed kits and repair the tile pieces
directly instead of automatically rerolling the whole kit.

## Asset inventory, in production order

Native sizes below are targets for the exported canvas, not guarantees from a
generator. Trim transparent edges where appropriate and record each placement
anchor. `frontend/static/tavern/` will hold approved `tiles/`, `props/` and
`decor/` PNGs. One reusable sprite may be placed or recolored many times.

### 1. Room shell — required

- **Oak floor:** one 32 × 32 seamless plank tile plus two quiet variants.
  Floorboards run left to right as in the reference; vary seams and scuffs
  without checkerboarding. Use code/manual cleanup if a generated sample does
  not tile cleanly.
- **Slate perimeter:** one matched 32 px building kit for horizontal and
  vertical runs, inside/outside corners and doorway ends. Dark charcoal/slate
  with warm edge light. The north wall needs openings for the hearth and bar
  shelf; the privy partition uses the same wall language.
- **Privy floor:** one or two 32 × 32 pale grey stone tiles, restricted to the
  existing 3 × 3 northeast area. Its brighter value makes the WC readable.
- **Windows and entry:** one 32 × 32 amber-lit west window reused three times;
  one 32 × 32 south plank door. Build wall joins around both, not over them.

### 2. Interactive anchors — required

- **Hearth:** one 96 × 32 or 96 × 64 north-facing stone fireplace with a dark
  firebox and separate static flame/log layer, centered on `fireplace` at
  (9, 0), width 3. Let its facade overlap the adjacent floor visually without
  changing blocked cells. Keep the existing procedural flickering glow.
- **Bar:** one 128 × 32 south-facing oak counter for `bar` at (3, 2), width 4,
  plus a 32 × 32 tap/cask on the north wall at (6, 1). Add a narrow back shelf
  as a separate non-interactive layer. Hob's 68 px sprite stays behind the bar;
  check that his feet and hands are visible.
- **Tables and seating:** one 32 × 32 wood table, one 32 × 32 chair with an
  east/west mirrored placement, and one same-size dice-table top or a separate
  pair of dice. Reuse for four ordinary tables, eight chairs, the central dice
  table and two dice chairs. Keep the seat front and back in separable layers
  so seated actors are legible.
- **Privy and darts:** one 32 × 32 pale stone/ceramic basin with dark opening
  and a wooden pail in the existing WC cell; one 32 × 32 wall-mounted dartboard
  at (1, 8). The board's throw line is a small floor mark drawn locally.

### 3. Distinctive dressing — after the room reads well

- **Five rugs:** one 96 × 64 border/fringe design, adapted to the table groups
  in muted red, teal, green, blue and ochre. Use palette variants rather than
  five unrelated generations. Check each edge against walking cells.
- **Wall and corner details:** one torch/sconce reused at four to six positions;
  one hanging banner reused in two colors; one framed painting; one planter
  sprite reused and flipped; one barrel and one crate. Use the reference's
  density but keep the central travel lanes open and avoid decorating directly
  over a click or interaction spot.
- **Table and bar details:** mugs, bottles, a small candle and plant. Make these
  separate overlays so they can be hidden, moved or toned down if they obscure
  hands, speech bubbles or the dice game.

The same artwork may serve multiple locations. This is roughly **one building
kit, 10–12 distinct focal props, and a handful of deterministic variations**, not
one generation for every visible copy. Do not generate a new bartender: Hob and
the six guests already ship with four cardinal 68 px views. If a character is
revisited, follow `CHARACTER_ART_PIPELINE.md` and ship only N/S/E/W.

## PixelLab brief

Use the reference as a style guide after reducing it to the actual pixel grid
or a small palette/crop, rather than passing its 1489 px upscale blindly as a
native sprite. Base prompt: “border inn interior, low top-down pixel art, native
32 px tile scale, dark slate blocks, long worn oak planks, deep umber shadows,
warm amber candle/fire light, muted wine red, teal and moss green textiles,
readable hand-placed pixel clusters, selective dark outline, simple shading,
no lettering, no UI.” Add exactly one object, its view and its target canvas
size to each prop request. Keep the 68 px cast beside every review.

Record the tool, prompt, seed/job ID, actual exported dimensions, palette,
transparent bounds and bottom-center/edge anchor for each accepted result.
Check PNG dimensions after the job finishes; the earlier standard character
route accepted 68 px in the request but returned 96 px in its export.

## Codex floor and wall trial (2026-10-04)

The first in-game material trial uses Codex ImageGen, with the supplied room
reference as a style guide. `frontend/static/tavern/tiles/oak-floor.png` and
`slate-wall.png` are both 1254 × 1254 source images. The renderer scales the
floor across the 20 × 14 room and places one copy of the stone image in each
blocked cell. This keeps the server map and obstacle editing intact, but these
are visual prototypes rather than native, seamless 32 px tile exports.

The next pass reduced the floor boards to roughly two-thirds their original
size and added matching `slate-window.png` and `slate-door.png` wall art.
The current `slate-door.png` is a three-cell-wide, two-leaf entrance centered
across from the fireplace. Its map footprint spans cells (9–11, 13), and the
three existing interaction spots remain in front of it.

The next in-game pass added pale stone
floor and a wooden bucket in the privy, and replaced the procedural hearth,
bar, tap, tables and chairs with separate transparent PNGs. A barrel, plant and
candle PNG are reused as small overlays; the table rugs have muted colors drawn
in Phaser. `room-art.ts` owns these static layers and rebuilds them from the
server map when obstacles change. No PixelLab credits were used.

The window tile was later corrected to exactly one cell, matching every other
slate wall cell. Its amber glass and wooden frame are larger *within* the tile.
The oak floor source was lightened to honey brown, and the bar source and its
display height were increased so the counter has a deeper top and taller front.

ImageGen supplied the new sources in `tiles/privy-stone.png`, `props/` and
`decor/`. All props have alpha; the stone floor is opaque. The transparent
sources are 1254 px square except the wide fireplace and bar (about 2160 ×
725 px). They are scaled down in Phaser with nearest-neighbor filtering, so
they remain prototype art rather than final native-resolution sprites.
The image prompts used the existing oak and slate materials as style context:
top-down chunky pixel art, warm brown timber, charcoal stone, amber light,
muted colors, transparent background for each isolated object, no text or
characters. Each output named exactly one object: privy stone, wooden privy
bucket, fireplace, bar, table, chair, ale cask, barrel, plant, or candle.

## Delivery slices and checks

1. **Style pilot:** make a 32 px floor sample, a wall/corner sample, a table
   and one rug in a 6 × 5-cell mockup with Edda and Hob at native size.
   Compare side by side with the supplied image: plank direction, darkest
   values, pixel density, warm light and actor contrast. Only this pilot may
   authorize the building kit and prop batch.
2. **Shell in game:** replace the floor, perimeter, privy floor, windows, door
   and north hearth. At 640 × 448 inspect every wall seam and entrance.
   Verify dynamic obstacle editing still redraws the wall and the existing
   fireplace, window and entrance interactions are reachable.
3. **Furniture in game:** integrate bar, one full table/seat/rug group and the
   dice table; verify Hob behind the bar, seated poses, depth, clicks, hover,
   and dice visibility. Then reuse approved assets for the other groups,
   darts and privy.
4. **Dressing and play:** add the small decor and final lighting only after
   the working room is clear. Run an evening and manually inspect walking to
   every activity, sitting, the WC, darts, dice, actor selection, speech bubbles,
   obstacle editing and desktop/narrow browser widths. Run `make check` and
   `make build` for the frontend change.

Do not flatten the room into one picture. `TavernScene.preload()` can load the
approved PNGs; keep floor/rugs below actors, wall features and furniture at
appropriate bottom-edge depths, and speech/UI above them. `world.map.objects`
remains authoritative for interactive placement. Preserve nearest-neighbor
filtering and integer alignment, and inspect Phaser's fractional `Scale.FIT`
sizes for blur. Split `scene.ts` before growing it past the project's ~400-line
limit. The current Graphics art remains a fallback until its replacement slice
has passed the play check.

## Sources for tool choice

- [PixelLab Create tiles (Pro)](https://www.pixellab.ai/docs/tools/create-tiles-pro):
  building kit contents, 32 px recommendation, subscription and cost.
- [PixelLab Create map](https://www.pixellab.ai/docs/tools/create-map): Tier 1
  canvas limit, one reason not to generate the whole playable room.
- [PixelLab API](https://www.pixellab.ai/pixellab-api): map objects and
  transparent image generation.

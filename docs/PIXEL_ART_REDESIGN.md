# Tavern pixel art redesign plan

## Goal and boundaries

Make the existing room read as a lived-in medieval border inn: worn oak, dark timber,
limewashed plaster, rough stone, amber firelight, and a few muted red and green textiles.
Use the same low top-down perspective and pixel density as the PixelLab characters.
The first pass uses still images. Keep the 20 × 14 map, 32 px cells, object IDs,
interaction spots, collision, and NPC behavior in `data/tavern.json`.

Success is a readable 640 × 448 room where the characters look like they belong,
each activity has an obvious place, wall/floor tiles join cleanly, and players can still
see and select NPCs and navigate between all four tables, the bar, darts, and privy.

## What is there now

`frontend/src/scene.ts` paints the floor, rugs, walls, windows, entrance, fireplace,
counter, ale tap, tables, chairs, dartboard, and toilet with Phaser Graphics. The
character stills are already pixel art. The current room has four repeated table/seat
groups, a north counter, a northeast WC enclosure, an east hearth, a west dartboard,
three west windows, and a south entrance.

```text
    north
    ####################
    #.....A........#...#   A ale tap, B bar, P privy
    #..BBBB........#.P.#   F fireplace, D darts, E entrance
    #..................#   T table, c chair, w window
    w..............#####   # blocked wall, . floor
    #..................F
    w..cTc........cTc..F
    #..................#
    #..................#
    #.D................#
    #..................#
    w..cTc........cTc..#
    #..................#
    ##########E#########
```

The south door at (10, 13) and west windows at (0, 4), (0, 6), and (0, 11) sit
in wall cells. The fireplace spans (19, 5–6). The privy is at (17, 2), reached
through the opening at (15, 3). Art can extend into an adjacent cell visually,
but its collision and interaction point stay at the current coordinates.

## Art direction and generation order

1. **Approve one room corner first.** Generate a 32 px oak floor sample, a matching
   wall sample, and one 32 px table or chair. Composite them with the existing
   veteran sprite at actual game scale. Reject a set if its camera angle, outline,
   contrast, or implied pixel size makes the character look pasted on. This is the
   cheap style check before generating the full set.
2. **Build the room shell.** Preferred PixelLab tool: `create_building_kit` with
   `square_topdown`, 32 px tiles, one-tile walls, floor described as scuffed oak
   planks and walls as lime plaster with dark oak beams and a stone foot. Use the
   same palette and camera language as the approved corner. Map its floor,
   straight wall, corner, end, and doorway tiles onto the existing blocked-cell
   layout. The privy floor can use a small stone variation; it does not need an
   entire second architectural kit.
3. **Generate transparent props against that shell.** Use PixelLab
   `create_map_object` for each distinct prop, or `create_image_pixflux` with
   `no_background` for a small pilot. Keep one consistent `low top-down`,
   `basic shading`, selective/dark outline recipe. Supply an approved sample as
   style context where a tool supports it; otherwise use the same written palette
   and correct mismatches manually. Export individual PNGs with transparent
   margins trimmed and a documented placement anchor.
4. **Add restrained set dressing.** Make one small floor rug pattern, a barrel or
   crate stack behind the bar, and table-top mugs/candle details. Reuse and flip
   these sparingly. Do this only after the architecture and interactive props
   look coherent. Keep walking lanes visually open.

### Prompt recipe

Use this shared clause in each prompt: “medieval border inn interior, low top-down
game view, 32 px tile scale, hand-placed pixel clusters, warm worn oak and dark
umber outlines, amber highlights, muted moss green and oxblood accents, basic
shading, readable silhouette, no letters, no UI, no modern fixtures.” Then name
**one** object and its orientation. For example: “a square scarred oak tavern table,
seen from low top-down, plain tabletop with two tankards; transparent background.”
For the privy: “a timber enclosed medieval privy seat with a dark round opening,”
not a porcelain toilet. Review every output at 1× and inside the running room;
regenerate or touch up any blurry edges or perspective mismatch.

## Asset list and placement

Save approved source PNGs under `frontend/static/tavern/`, with architecture
tiles in `tiles/`, props in `props/`, and textiles in `decor/`. Keep a short
manifest recording the PixelLab tool, prompt, seed/job ID, native dimensions,
and game anchor for each accepted image. Dimensions below are native pixel
targets, not a request to scale a smaller image up.

- **Shell:** 32 × 32 repeating oak floor plus a few quiet variants; 32 × 32
  connectable timber/plaster wall pieces and doorway; 32 × 32 stone privy floor.
  Replaces `drawFloor`, `drawWall`, and `drawRoomDetails`.
- **Counter:** 128 × 32 four-cell oak bar at (3, 2), with its front facing south;
  32 × 32 cask/ale tap at (6, 1). Replaces `drawBar` and `drawTap`.
- **Seating:** one 32 × 32 table used four times; east- and west-facing
  32 × 32 stools or chairs used eight times; two 128 × 64 subdued rug variants
  beneath the groups. Replaces `drawTable`, `drawChair`, and `drawRugs`.
  Seat sprites must leave the seated character's body visible.
- **Wall features:** 32 × 32 leaded timber window used three times; 32 × 32
  heavy plank entrance door; 32 × 64 stone hearth with dark firebox and logs.
  Replaces `drawWindow`, `drawDoor`, and the static part of `drawFireplace`.
- **Activities:** 32 × 32 timber-backed dartboard at (2, 9), with a small floor
  throw mark at (3, 9); 32 × 32 privy seat at (17, 2), with a timber screen or
  latch cue at the enclosure entry. Replaces `drawDarts` and `drawToilet`.
  These two props should be easy to recognize at normal zoom.
- **Small dressing:** optional barrel/crate and tabletop detail sprites, reused
  rather than unique art for every table. They must not obscure destinations,
  path lines, or characters.

Do not generate a single flattened 640 × 448 image. A whole-map image would be
hard to reconcile with movable obstacles, selection, actor depth, and the exact
collision layout. PixelLab's map tool also limits free-tier canvas area below
this room's size.

## How to replace the renderer

1. Load the approved PNGs in `TavernScene.preload`. Place floor tiles first, rugs
   next, wall tiles and wall features next, then furniture, NPCs, labels, and route
   overlays. Keep the current firelight as a separate overlay for now.
2. Use `world.map.blocked` and the fixed wall-feature cells to choose wall
   joins/corners. `world.map.objects` remains the source for prop position,
   facing, and interaction. If obstacle editing changes blocked cells, rebuild
   affected wall visuals from the new map snapshot.
3. Give furnishings explicit pixel anchors and depth by their bottom edge. The
   counter, table fronts, and chairs can overlap feet, while a seated sprite must
   appear in front of its seat back. Do not flatten props into the floor.
4. Turn on nearest-neighbor texture filtering and integer pixel alignment for
   the room art. Check how Phaser's `Scale.FIT` behaves at browser sizes that
   produce a fractional scale; the final canvas should stay crisp.
5. Keep interaction feedback, but show appeal and stock labels on hover or
   selection instead of permanently covering the new art. Retain an accessible
   indication of the same information in the dashboard.

## Gates for implementation

1. **Style gate:** one floor/wall/table composite beside Edda, Rurik, and Toren at
   native scale. Verify perspective, palette, seams, and readability before
   generating the rest.
2. **Shell gate:** new floor and walls in the live scene, including south door,
   west windows, privy doorway, and east hearth; compare a 640 × 448 screenshot
   with the current map to check every cell and opening.
3. **Prop gate:** replace one table group and the bar, verify actor overlap and
   seating, then reuse the accepted sprites for the other groups and add the
   darts/privy/hearth pieces.
4. **Play gate:** in a restarted evening, verify walking to each interaction,
   sitting, playing darts, using the privy, object hover/click targets, obstacle
   editing, route visibility, and the scene at desktop and narrow widths.

## PixelLab access and generation budget

PixelLab's [Create tiles (Pro)](https://www.pixellab.ai/docs/tools/create-tiles-pro)
documentation lists the building kit at 20–25 generations and requires Tier 1.
Its [standard tileset](https://www.pixellab.ai/docs/tools/create-tileset) is
cheaper (usually 3–4 generations) but is designed for **terrain transitions**,
not the room's wall/door construction. On 2026-10-02, the connected account
was upgraded to Tier 1 and `get_balance` reported 2,000 generations for the
current cycle. The building kit is therefore available to test, although the
one-corner style pilot should still precede its 20–25-generation run. Check
the live balance and preserve room for props and retries. Do not spend credits
on a terrain tileset as a substitute for interior architecture. No room art
was generated in this planning pass.

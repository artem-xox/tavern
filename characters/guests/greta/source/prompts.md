# Greta: PixelLab record

- Base (Idle, 2026-10-17): `34d66c0e-931d-4c6d-b71b-4ebe95f80a4c`, group `4361869a-254b-4d51-a1ba-2d4fb341cc43`.
  Pro Flash 68x68, eight directions, style reference Edda's south view (`style_options`: detail, outline, shading;
  palette off). Prompt is in `pixellab.json`. A first version (yellow hooded cloak, `4bca785b-c86b-4f12-8a09-52b310f45aeb`)
  was replaced to match the user's reference photo: one long braid over the shoulder, hot-pink pleated blouse.
- Poses: `create_character_state` on the base, `use_color_palette_from_reference=true`, no size override, edit text
  "<pose>. Same face, outfit, colors and scale; change only pose."
- Hurt needed two retries (heavy-load failures `f61afdcb-...`, `96792534-...`); the shipped one is `5488904b-621f-46f7-af69-3de6f1fd283d`.
- 2026-10-18: TakeBeer regenerated without a tap or counter (new state `0576b146-6711-4aca-a81c-c935b0581168`), matching Edda, Toren and Trump.
- 2026-10-18: SleepingSeated regenerated without the drawn table plank (new state `e6227751-46d6-4551-a733-2c2a809f8e76`), curled forward like the rest of the cast.

## Signature item pose (2026-10-28, S2-18)

- `Protesting` = PixelLab state `88817313-ac78-4b47-8d80-2787f331178f` ("Protesting v2"), for `raise_sign` with the protest sign.
  `create_character_state` on the base, `use_color_palette_from_reference=true`, no size override, all eight views at 68×68. Edit:
  "Same Greta, … change only the pose. Standing firmly, she holds a SMALL hand-made rectangular light-brown cardboard protest sign
  with both hands in front of her chest, the sign's top edge level with her chin and well below the top of the canvas … a few thick
  black scrawled marks (not readable letters); fierce scowl, mouth open as if shouting. The figure is slightly smaller in the canvas."
- The first try, `f34470db-f9cc-4583-8452-504dd7ca8a9e`, held the sign overhead. The canvas cut off its top, so the user rejected it.
  It is still in the PixelLab group, unused.

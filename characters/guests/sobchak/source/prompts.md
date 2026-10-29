# Ksenia Sobchak — accepted character

- User accepted the Idle south appearance on 2026-10-25.
- Canonical Characters base: `58534577-892c-4c22-9fe5-445aacb712ef`.
- Characters group: `1663b56e-633d-451c-adeb-9d96bf0ff27a`.
- The initial Pro Flash south image used Putin's 68px south Idle
  (`048912b2-baa1-43a9-9883-d53a4afe6817`) for camera, proportions, outline and shading.
  It was reused by `create_character_pro_flash`; the accepted south pixels did not change.
- All twenty subsequent poses use `create_character_state` on this base,
  explicit state names, palette reuse and no canvas overrides. Exact prompts,
  state IDs and frame paths are retained in `pixellab.json`.
- Verified all 21 poses in eight directions: 168 native transparent 68x68 PNGs.
  Reviewed all views; `poses-south.png` is a 2x nearest-neighbour review sheet.
- Hurt south-east originally faced away. PixelLab workbench mirrored the correct
  south-west view and `save_to_asset` saved it into the existing Hurt state's
  south-east rotation. The correction was free and is recorded in `pixellab.json`.
- At the user's request, Seated was refined from TalkingSeated to keep the lower
  knee and foot positions, with a closed mouth and hands resting on the lap.
  The temporary `SeatedRefined` (`6902e2d3-7f73-4aa0-9fce-f4907eae4af1`) was removed
  after its eight rotations were saved into the original Seated state
  `0c7472e6-4395-4ba9-9866-35dea848c2b2` and a fresh export proved them identical.
  Both the Characters library and the game contain the same 21 working poses.
- GivingSeated, ReceivingSeated, HurtSeated and SleepingSeated also had raised
  lower legs. PixelLab `edit_image` corrected all eight views of each; `save_to_asset`
  replaced the rotations in their original Characters states, without new states.
  Exact edit prompts, image job IDs, targets and charges are in `pixellab.json`.
  All 56 seated frames were compared pixel for pixel with a fresh Characters export.
  `poses-seated.png` records the visual review of all seven poses and eight directions.
- Pose generation and corrections used 250 subscription generations. The accepted image and
  its initial rotations used 6 more.

## Persona sources and interpretation

The card is political satire. The user requested a cutting interviewer who
becomes obsequious toward Putin while claiming independence. Private motives,
the courtier interpretation and all catchphrases are authored fiction, not real
quotations or claims about a private arrangement. Dislike of Trump is a game
premise: public remarks include admiration for him.

- [Republic interview excerpt](https://republicmag.io/posts/117465): public interview persona and remarks about freedom; only the public excerpt was accessed.
- [Meduza, 28 April 2026](https://meduza.io/feature/2026/04/28/blagodarya-vladimiru-vladimirovichu-putinu-ya-mogu-rabotat-a-ne-sidet-v-tyurme): reported gratitude to Putin and the ability to do small good deeds, used as the card's satirical contradiction.
- [E1, 20 October 2026](https://www.e1.ru/text/world/2026/10/20/76713047/): discussion of the godfather rumour. The card does not repeat that rumour as fact.
- [Vucic interview report, 20 October 2026](https://novayagazeta.eu/amp/articles/2026/10/20/eshche-dolgo-putin-budet-u-vlasti-v-rossii-poetomu-ne-dumaite-poka-ob-etom): their recent public interview supplies mutual recognition and topics to probe.
- [Lady Mail report](https://lady.mail.ru/article/578188-moj-krash-kseniya-sobchak-voshitilas-donaldom-trampom/): positive remarks about Trump, distinguished from the user's fictional rivalry.

Relationships describe the tavern parodies' own views. Her adoration of Putin
is deliberately unreciprocated. Existing conversations, public challenges,
toasts, invitations and quarrels provide the interactions; no new verb is added.

## Signature item pose (2026-10-28, S2-19)

- `Interviewing` (state `30edab67-3bb7-4bae-8b8f-416f8124df72`), for `interview_guest` with the microphone. `create_character_state` on
  the base, `use_color_palette_from_reference=true`, no size override, all eight views at 68×68. Edit: "Same Ksenia Sobchak, same face,
  large dark angular glasses, honey-blonde bob, beige trouser suit, colors and scale; change only the pose. Standing and leaning
  slightly forward, her right arm extends a black handheld microphone with a silver mesh head forward toward someone in front of
  her, as if asking a sharp question." The card in her left hand did not come out; the microphone reads in every view.

# Stage 2 — Story evenings (current)

**Goal:** famous people, real and fictional, walk into the tavern, and their evening turns into chaos worth
retelling. Every evening ends with a retold story the player wants to screenshot.

The test of the stage: do evenings with famous guests produce many more interesting events than the
Stage 1 locals, and does the retelling at closing make an observer laugh or say "wait, what"?

## Decisions

- **Name and setting.** The game is *The Story Tavern*: a tavern between worlds where anyone may walk in
  (presidents, pop stars, film heroes, a witcher). The hall, the engine and the barkeep stay.
- **Two casts.** *Guests* are the famous characters, the main content. *Locals* are the Stage 1 people
  (Edda, Rurik, Toren, Brida, Calder, Saye), kept for internal tests and experiments. Hob tends the bar for
  both. A lineup screen picks the cast before an evening.
- **Chaos is the feature.** Shouting, insults, drinking, brawls and petty schemes are the content, not
  incidents to keep rare. A persona's public image is played up for satire. Limits that still apply are
  in [DESIGN.md](../../DESIGN.md#tone).
- **Real names are provisional.** Guests may be renamed into parody names (for example "Hutin",
  "Tromb") before anything is published. A card keeps the real person it parodies apart from the name
  the game shows, so a rename is one field.
- **Staff:** the barkeep only. No economy, agreements or memory between evenings.
- **Player:** still an observer who picks the cast and watches. Stage 3 puts the player in the room.
- **Language:** English for prompts, lines and the retelling.
- **Models:** Jev for choice and Claude Haiku 5.5 for lines and intentions, as in Stage 1. The retelling
  uses a stronger model, chosen in S2-10.
- **Saves:** a schema bump needs the user's approval before the first one in this stage
  ([plan rules](../README.md#working-on-a-task)).

## Done when

- A Guests evening scores at least twice the story score of a Locals evening on the same seed
  ([S2-05](05_story_score.md)), averaged over five live evenings.
- Every live Guests evening has at least one fight or shouting match, one use of a signature item, and one
  game played together.
- The closing screen shows a retelling whose every claim maps to a logged event, and an observer can
  retell one story from it.

Tasks and their order are in the [plan index](../README.md#stage-2-tasks).

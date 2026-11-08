---
id: S3-06
title: The player on the stage
status: todo
needs: [S3-04, S3-05]
touches: [backend/tavern/social/player_lines.py, backend/tavern/social/speeches.py, backend/tavern/social/stage_lines.py, backend/tavern/hall/lifecycle.py, backend/tavern/mind/haiku_reading.py, backend/tavern/evening/mind_loop.py, backend/tavern/evening/player_commands.py, frontend/src/types.ts]
---

# S3-06 — The player on the stage

## Why

The stage is how a guest addresses the whole hall: a toast, a roast, a pitch or a confession (S2-14). Haiku
writes a guest's number. After S3-02 a steered performer stands up there and says nothing until `give_speech`
runs out, which takes 14 s, too short to type in. This task lets the player give their own number in their own
words, answer a heckle, and stay up there for as long as they are typing.

## Scope

- In: `say` on the stage as a number or a comeback; the `ReadNumber` port; a performer who keeps the stage while
  typing; stepping down in silence.
- Out: heckling from the floor (a steered guest is never picked as a heckler: S3-02); shouting to the hall from
  outside a scene; the chat panel's stage mode (S3-09).

## Shape

- `player_commands.say` routes by where the played guest is:
  1. A heckle at them is still owed a comeback (within `stage_lines.HECKLE_WITHIN`): the text is the comeback,
     `heckles.answer_heckle(world, performer, heckler, text)`, with no reading.
  2. They are on the stage with no number given yet (`speeches.on_stage_for` is not None): the text is their
     number, after a reading.
  3. They are in a scene: S3-04.
  4. Otherwise: `ValueError` ("Nobody is listening: join a conversation or climb the stage").
  `to` is ignored on the stage.
- `ReadNumber = Callable[[Mapping view, str text], Coroutine[Any, Any, Mapping[str, Any]]]`, beside `ReadLine`.
  A reading is `{"number": <one of numbers.NUMBERS>, "target": <a guest in the hall> | None}`. The view is the one
  `stage_claims` builds for a performer, made by a function that both callers share. `deliver_number` calls
  `speeches.perform(world, speaker, kind, target, [text])`. A reading that fails or names a kind that needs a
  target without one becomes a `pitch` with no target (a speech to the hall), and a `misread` event records why.
- Haiku: `haiku_reading.number_question(view, text)` uses the same system blocks as the line reading, plus the
  number kinds and their meanings from `numbers.NUMBERS`. The offline reader is always `pitch`, None.
- `MindLoop.read_number` and `_deliver_numbers` work like the line reading; `EveningPorts.read_number` is wired in
  the shared wiring.
- The stage time: for a steered performer, `give_speech` does not run out while no number has been given and
  `max(climbed_at, typing_at) + silence × speed` has not passed. After the number, it lasts the number's reading
  time, as for a guest. When silence passes with no number, they step down, and a `stage_silent` event is
  recorded ("Marilyn Monroe stood on the stage and said nothing").
- `types.ts`: `WorldEvent` types gain `stage_silent` if the client lists event types.

## Steps

1. `say` routing. Red first: one block on where a `say` goes (`owed-a-comeback`, `on-stage-no-number`,
   `in-a-scene`, `on-stage-number-given-and-in-no-scene` → error, `nowhere` → error). Check:
   `pytest tests/test_player_commands.py -x`.
2. `deliver_number`. Red first, one block of readings and the number performed: `toast-to-trump`,
   `roast-of-putin`, `pitch-to-the-hall`, `unknown-kind-is-pitch`, `target-not-in-hall-is-pitch`,
   `reader-failed-is-pitch`. The performed lines are always `[text]`. Check: `pytest tests/test_stage_lines.py -x`.
3. The stage time. Red first: a steered performer stays up while typing (`typing_at` moves on) past the 14 s
   timer; steps down `silence × speed` after the last keystroke with no number, with `stage_silent`; after a
   number, steps down after its reading time. Check: `pytest tests/test_speeches.py -x`.
4. Haiku's question: the text and the kinds are used, and the schema's enums match the view (pattern:
   `tests/test_haiku_stage.py`).
5. Wiring and `types.ts`, then `make build`.

## Done when

- `make check` and `make build` pass, output pasted in Results.
- A lockstep test: the played guest climbs the stage (`act give_speech`) and says a roast of a guest present;
  the roasted guest gets the roast's thought, and a heckle, if one comes, can be answered with a second `say`.

## Results

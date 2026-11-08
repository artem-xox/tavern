---
id: S3-06
title: The player on the stage
status: done
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

Done on `claude/s3-06-stage-8cc700`.

- **`say` routing** (`player_commands._say_on_stage`): a heckle owed a comeback (`stage_lines.comeback_owed_to`, within
  `HECKLE_WITHIN`) takes the text as `answer_heckle`, with no reading; a performer with no number given
  (`speeches.on_stage_for`) has it read by `MindLoop.read_number`; in a scene it is S3-04's path; otherwise
  `ValueError` "Nobody is listening: join a conversation or climb the stage to say anything" ("to say anything" keeps
  `say` in the message for the existing refusal test). `to` is ignored on the stage; one number is read at a time.
- **`ReadNumber`** (`player_lines`, beside `ReadLine`; offline `read_as_pitch`). `stage_lines.number_view` is the view
  both the guest's writer and the reader get; `deliver_number` performs `[text]` as the reading says, and a failed or
  impossible reading (unknown kind, target not in the hall, aimed kind without a target) becomes a pitch with a
  `misread` event. The stage view's `room` entries now carry the guest's `id`, so the reading names a target by the name
  the model sees and the parse maps it back.
- **Haiku** (`haiku_reading.number_question`, `parse_number`, `claude_number_reader`): the same first system block as the
  line reading, then number rules; the schema enumerates `NUMBERS` and the hall's names.
- **Stage time** (`speeches.holds_stage`, called from `lifecycle._interact`): for a steered performer with no number the
  speech timer stands still until `rules.player.silence × speed` has passed since the later of the climb and
  `typing_at`; then `stage_silent` ("Marilyn Monroe stood on the stage and said nothing") and they step down. The climb
  time is kept as `climbed_at` on the action itself, so the next climb starts afresh. After the number
  (`perform` for a steered speaker) the timer is `give_speech − PERFORM_WAIT`, what a guest has left after the same
  wait.
- **Wiring**: `MindLoop`/`EveningPorts.read_number`; `number_reader` through `run_evening`, `TavernRuntime`,
  `TavernSessions`, `create_app`, `app.py` (Claude when keyed) and `scripts/evening.py` (`number_reading` calls, recorded
  and replayed). `types.ts` needed no change: `WorldEvent.type` is a plain string and the client lists no event types.
- **No schema bump.** `climbed_at` is an optional key of a saved action, which the loader does not restrict, and nothing
  else is saved; old saves load as before and no version pin changed.
- **Golden** (`make golden`, base taken before the first edit): four of five evenings are identical. The fifth, the
  scripted-player evening `monroe-5`, differs by design: Marilyn climbs the stage and types nothing, so she now steps
  down at the silence (`stage_silent`, t=525.4) instead of at the 14 s timer (t=519.5). Nothing else in its log moved.
  The baseline is refreshed to that.
- **Tests**: `tests/test_player_stage.py` (routing, refusals, and the lockstep evening: the played guest climbs by
  `act give_speech`, roasts Cid, Cid keeps the `roasted` thought, Cid's heckle is answered by a second `say`),
  `tests/test_stage_lines.py` (`deliver_number`), `tests/test_speeches.py` (stage time), `tests/test_haiku_number_reading.py`.
  No existing test was edited.
- **Not done live**: Haiku's reading of a real number was not run against the model (the question and parse are tested
  with a fake port).

```
make check:  4922 passed in 171.01s (backend); mypy: Success: no issues found in 144 source files;
             frontend node:test: tests 354, pass 354, fail 0; exit 0
make build:  ✓ built in 3.87s; exit 0
```

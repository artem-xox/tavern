---
id: S3-04
title: The player's voice
status: todo
needs: [S3-02]
touches: [backend/tavern/social/player_lines.py (new), backend/tavern/mind/haiku_reading.py (new), backend/tavern/social/turns.py, backend/tavern/mind/turn_view.py, backend/tavern/evening/mind_loop.py, backend/tavern/evening/player_commands.py, backend/tavern/server/runtime.py, backend/tavern/app.py, frontend/src/types.ts]
---

# S3-04 — The player's voice

## Why

This is the heart of the stage. The player types a line to the scene they are in. The guests hear those exact
words, and the world acts on a speech act, as it does for a guest's line: an insult stings and may start a
quarrel, an invitation waits for an answer, news spreads. Guests have Haiku pick the act while it writes the
line. For the player, a model reads the act from words that are already written, and the world validates it
with the same `check_turn`.

## Scope

- In: the `say` command in a scene; claiming the scene's next slot, cutting in on a guest whose line is in
  flight; the `ReadLine` port with a Haiku reader and an offline reader; the boundary that turns a reading into
  a turn; speaking the player's line; marking it in the log.
- Out: typing and the `ignored` thought (S3-05); `say` on the stage (S3-06); the chat panel (S3-09).

## Shape

- Command `say`: `{"type": "say", "text": str, "to": "auto" | "everyone" | <actor id>}`. The handler
  `player_commands.say` raises `ValueError` when: the evening has no player or the guest is on autopilot; the
  guest is in no scene; the text, once trimmed, is empty or longer than `scripted.MAX_LINE` (200); `to` names
  nobody else in the scene; or a line of theirs is already being read or waits to be spoken there (one at a
  time).
- The slot: `say` sets `scene["writing"] = {"turn": len(turns), "speaker": <player>, "since": now}` and
  clears a `written` line that is not spoken yet. Any claim of a guest is replaced. `turns.deliver_turn` drops an
  answer whose claim's speaker has changed since it was asked; today it checks only the turn index. The
  replaced guest is asked again later, with the player's line in their view.
- `turn_view(world, scene, speaker_id=None)`: when the speaker is given, it is used instead of `next_speaker`.
  This is the player's reading view.
- `social/player_lines.py`, "The player's typed lines: the reader port, and the boundary that makes a turn of a
  reading.":
  - `ReadLine = Callable[[Mapping view, str text, str to], Coroutine[Any, Any, Mapping[str, Any]]]`. A reading
    is `{"act", "addressee", "topic", "invitation"?, "fact_id"?}`.
  - `deliver_reading(world, scene_id, turn, text, to, outcome)` builds the turn. Its `line` is always the
    player's text, whatever the reader returned. An explicit `to` overrides the reading's addressee (`everyone`
    becomes None). The turn passes through `check_turn`. If the reading fails or the check refuses it, the turn
    becomes `{"act": "remark", "addressee": <to, or None for auto>, "topic": <the scene's topic>, "line": text}`
    and the reason goes into a `misread` event. Never a scripted line. An answer for a scene that ended, or whose
    claim has changed, is dropped, as in `deliver_turn`.
  - `read_as_remark`, the offline reader: a `remark` to the `to` given; for `auto`, to whoever spoke the last
    line addressed to the player, or None.
- `mind/haiku_reading.py`, "Haiku's reading of a player's line: the question and the parse.":
  `reading_question(view, text, to) -> Question` and `claude_reader(ask) -> ReadLine`. The system blocks are
  `turn_prompt.shared_prefix`, byte-identical, and then one cached block of reading rules (read, never rewrite;
  name the act the words perform; `remark` when unsure). The content holds the scene as the played guest knows
  it, its last lines, the acts offered now with their meanings, the invitation kinds open, the news the guest
  holds by `fact_id`, `to`, and the quoted text. The answer schema enumerates the offered acts and the
  participants. `MAX_TOKENS` is about 120. The answer is parsed at the boundary as `haiku_turns.parse_turn`
  does.
- `MindLoop.read_line(world, scene_id, text, to)` sends `read(view, text, to)` through the courier.
  `_deliver_readings` hands each answer that is back to `deliver_reading`. `EveningPorts.read` is wired in the
  one shared wiring (R13): `claude_reader` when a Claude key is set, otherwise `read_as_remark`. A request sent
  during a pause is delivered at the first tick after it.
- Speaking: in `speak_turns`, the speaker of a written line is the claim's `speaker`, not `next_speaker`. A
  player's line that fills their own waiting turn is due at once. The `turn` event of a steered speaker carries
  `player: true`.
- `types.ts`: `Command` gets `say`; `WorldEvent.player?: boolean`.

## Steps

1. `turn_view` with a speaker: a test that the view's `speaker` is the guest given, with the acts offered to that
   guest. A refactor with no behavior change for callers that give no speaker. Check: golden unchanged.
2. `deliver_reading`. Red first, one parametrized block of readings and the turn each becomes: `as-read`,
   `explicit-to-wins`, `everyone-to-none`, `unknown-act-is-remark`, `addressee-outside-is-remark`,
   `invite-without-kind-is-remark`, `reader-returns-its-own-line` (the text still wins), `reader-failed-is-remark`;
   one case each that the scene ended or the claim changed (dropped). Check: `pytest tests/test_player_lines.py -x`.
3. The slot and cutting in: a guest's claim is in flight, the player says something; the player's line is spoken
   first, the guest's late answer is dropped, and the guest is asked again with the player's line in view. Then
   the player's own turn: a guest addresses them, they answer, and the act's effect lands (an `insult` gives the
   target the `insulted` thought).
4. `say` refusals in one block (`no-player`, `autopilot`, `no-scene`, `empty`, `too-long`, `to-a-stranger`,
   `already-reading`).
5. Haiku's question: a test that the text, the offered acts and `to` are used in the question (not their
   wording), and that the schema's enums match the view; `parse_reading` error cases. Pattern:
   `tests/test_haiku_turns.py`.
6. Wiring and `types.ts`, then `make build`.
7. A reading check, local only (a throwaway script with the real key, not committed): 12 player lines across
   four scenes (a joke, an insult, a toast, an invitation to darts, news, a question, a compliment, a goodbye,
   an apology, a boast, agreement, nonsense). Paste the act each was read as, and whether a person would name
   the same act, in Results.

## Done when

- `make check` and `make build` pass, output pasted in Results; the golden diff is empty.
- In step 7, at least 10 of 12 lines are read as the act a person would name, and no line is spoken in words
  other than the player's own.

## Results

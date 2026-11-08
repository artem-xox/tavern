---
id: S3-05
title: Silence and typing
status: done
needs: [S3-04]
touches: [backend/tavern/hall/state.py, backend/tavern/hall/player.py, backend/tavern/social/turns.py, backend/tavern/social/conversation.py, backend/tavern/social/thoughts.py, backend/tavern/evening/player_commands.py, backend/tavern/adapters/persistence.py, backend/tavern/server/runtime.py, frontend/src/types.ts]
---

# S3-05 — Silence and typing

## Why

After S3-02, a scene waits a fixed `rules.player.silence` for the player, so a player typing a long reply can
lose the turn in the middle of a sentence. And when a turn passes in silence, nobody minds. The owner's
decision is that silence is a move too: a scene waits for as long as the player is typing, and a guest who
spoke to the player and got no answer feels ignored. That gives the story something to tell ("Monroe looked
straight through Putin").

## Scope

- In: the `typing` command; the wait counted from the last keystroke; the `ignored` thought and event.
- Out: the client's typing pings and countdown (S3-09); silence on the stage (S3-06); counting `ignored` in the
  story score, which S3-12 decides on evidence.

## Shape

- `Player.typing_at: float | None`: the game time of the last `typing` command, None before the first one.
- Command `typing`: `{"type": "typing"}`. `player_commands.typing` sets `typing_at = world["time"]`. It raises
  `ValueError` with no player or on autopilot. It is not logged (the client sends one at most every 2 s).
- The wait in `speak_turns`: a steered guest's due line waits until `max(due, typing_at) + silence × speed`,
  where `due` is when the line fell due. While a line of the player's is being read (their claim), the scene does
  not count silence at all. While the world is paused, game time stands still, so the wait does too.
- The `silence` act's effect also lets down whoever spoke the last line addressed to the silent guest: that
  guest thinks `ignored` about them, and an `ignored` event is recorded (`record_event`, "Putin was ignored by
  Marilyn Monroe"). If an invitation was waiting for the silent guest's answer, its inviter is the one ignored
  (the invitation is still declined, as in S3-02). A line to everyone lets nobody down.
- `THOUGHTS["ignored"]`: mood and opinion below zero, milder than `insulted`, lasting about four minutes, and
  `acquaints=False`, since being ignored does not make two people acquainted. The numbers are set in the table
  and are not pinned by a test.
- Saves: the next schema version (approved for Stage 3) carries `typing_at`.
- `types.ts`: `Player.typing_at: number | null`; `Command` gets `typing`.

## Steps

1. `typing_at` and the command: the type, the save check and version, and `player_commands.typing` with its
   refusals. Check: `pytest tests/test_player.py tests/test_player_commands.py tests/test_database.py -x`.
2. The wait. Red first, one parametrized block on when the turn passes: `no-typing` (at due + silence),
   `typed-after-due` (at that keystroke + silence), `typed-before-due` (at due + silence), `fast-world` (speed 4),
   `while-reading` (no silence until the reading lands). Check: `pytest tests/test_turns.py -x`.
3. Ignored. Red first: one block on who thinks `ignored` when a silence passes the turn: `addressed-by-putin`
   (Putin), `addressed-to-everyone` (nobody), `invited-by-trump` (Trump, and the invitation is declined),
   `no-line-before` (nobody). Test the thought's kind and its `about`, not its numbers.
4. `types.ts`, then `make build`.

## Done when

- `make check` and `make build` pass, output pasted in Results.
- A lockstep test: a guest speaks to the steered guest, who types for 40 s game time and never sends; the turn
  passes 20 s after the last keystroke, and that guest's inspector record shows `ignored`.

## Results

Done on `claude/s3-05-silence-bd69af`.

- **Typing.** `Player.typing_at` and the `typing` command (`player_commands.typing`, routed in `runtime.command` beside
  the player's hands, so it leaves no "Operator" event). It raises `ValueError` with no player or on autopilot.
- **The wait.** `speak_turns` (`_await_player`) passes a silent turn at `max(due, typing_at) + silence × speed`; no
  silence is counted while the player's own claim (a line being read) holds the slot. Paused game time stands still.
- **Ignored.** `THOUGHTS["ignored"]` (mood −2, opinion −6, 240 s, `acquaints=False`). The `silence` act's effect
  (`conversation._let_down_by_silence`) declines a waiting invitation as before, then the last speaker to the silent
  guest (the inviter if an invitation waited) thinks `ignored` about them and an `ignored` event is recorded
  ("Putin was ignored by Marilyn Monroe", field `ignored_by`). A line to everyone, or to someone else, lets nobody down.
- **Schema bump 25 → 26.** Approved for Stage 3. Only the two version pins changed
  (`tests/test_intention_saves.py`, `tests/test_database.py`). `typing_at` is *optional* in the saved record: a new
  evening's record stays `{actor_id, steering}` because `tests/test_lineup.py` pins it, and the key appears with the
  first keystroke; `check_player` accepts it absent, null or a non-negative number.
- **Tests.** `tests/test_player_typing.py` (command, save), the wait and ignored blocks in `tests/test_turns.py`, and the
  lockstep case in `tests/test_lockstep.py` (keystrokes to second 40, silence passes the turn at 60, not 59; the
  speaker's inspector record shows `ignored`).
- **Golden.** `make golden GOLDEN=runs/golden-base` before the first edit and `runs/golden-now` after:
  `diff -r runs/golden-base runs/golden-now` prints nothing.
- **Frontend.** `types.ts`: `Player.typing_at?: number | null` (optional, for the reason above) and `Command` gets `typing`.

```
make check  → 4848 passed in 195.55s; mypy: Success: no issues found in 142 source files; frontend node:test: tests 331, fail 0
make build  → ✓ built in 4.24s
make golden GOLDEN=runs/golden-now && diff -r runs/golden-base runs/golden-now  → (empty)
```

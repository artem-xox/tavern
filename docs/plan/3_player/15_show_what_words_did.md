---
id: S3-15
title: Show what the words did
status: done
needs: [S3-04, S3-09]
touches: [frontend/src/readings.ts (new), frontend/src/reactions.ts (new), frontend/src/chat.ts, frontend/src/chatpanel.ts, frontend/src/main.ts, frontend/src/style.css, frontend/tests/readings.test.ts (new), frontend/tests/reactions.test.ts (new), frontend/tests/chat.test.ts]
---

# S3-15 — Show what the words did

## Why

The owner's playtest found Stage 3 raw, and the biggest cause was that a typed line's effect could not be seen.
The world reads each line as a speech act (insult, invitation, news, or a remark when it refuses the reading), and
the people it reaches get thoughts, opinion and mood changes. The chat showed only the words. This is P1 of the
playtest analysis: make the consequences legible, without act buttons. The model still reads free text and the
world still validates.

## Scope

- In: a chip under each of the player's own chat lines saying how it was read; reactions over the people a player
  line or act touched (a thought over their head, toasts over the player for an opinion or mood change, a quarrel,
  an invitation accepted or declined).
- Out: anything the player did not cause; a backend field (the snapshot already carries everything); the centre
  chat popup (another task) and P5's auto-pause (another task).

## Shape

- `readings.ts` (pure):
  - `readingOf(turn, refused, nameOf) -> {text, refused} | null`: `insult → Trump`, `invitation: darts → Monroe`,
    `news → everyone`; an unknown act in plain words; a bare `remark` when refused; null for a silence or no act.
  - `refusedTurns(turns, events, playerId) -> Set<index>`: a refusal is the `misread` event with `speaker_id`; the
    refused line is the player's first turn at or after it, spoken as a `remark`.
- `chat.ts`: `ChatLine.reading`, filled only for the player's own lines (one additive field).
- `reactions.ts` (pure):
  - `reactions(previous, next) -> Reaction[]`: new thoughts other guests hold with `about` = the player, and
    `invitation_accepted`/`_declined` events with `inviter_id` = the player logged since the previous snapshot.
    Nothing on the first snapshot, so a reload replays nothing.
  - `stacked(reactions) -> [actor, text][]`: one message per figure, so reactions that land together do not overlap.
- Shell: `chatpanel.ts` draws the chip (gold as meant, dashed grey italic when refused); `main.ts` keeps the
  previous snapshot and floats each stacked message with the existing `scene.toast`.

## Done when

- Tests first in `frontend/tests/` cover a line read as meant, a refused line shown as a remark, a silence, a
  reaction caused by the player versus by someone else, an empty hall, and a malformed or unknown act.
- `make check` and `make build` pass, and the golden diff is empty.
- A played evening in the browser shows the chips and a reaction.

## Results

Done on 2026-11-08.

- No backend change. Refusal is read from the `misread` event (`speaker_id`), and who caused a reaction from the
  thought's `about` and the event's `inviter_id`. Nothing keys off wording. Limit: the world keeps its latest 200
  events, so a refusal older than that log shows as a remark read as meant. Within one scene this does not happen
  in practice.
- A thought shows over the guest who has it, for example `insulted by Marilyn Monroe −20`. In the browser run it
  sat half behind Monroe's toasts, so only the tests confirm its exact text. The toasts float over
  the played guest: `Vladimir Putin thinks worse of you −20`, `Vladimir Putin's mood −6`, `A quarrel with …`,
  `Trump accepted: darts`.
- Browser, `make run`-style pair with Jev, playing Monroe with Putin and Trump: the line "Vladimir, you are a cold
  little man with dead eyes, and your dice are loaded." showed the chip `insult → Vladimir Putin`. The second insult
  floated `Vladimir Putin thinks worse of you −20` / `Vladimir Putin's mood −6` / a Trump line (his
  `friend_insulted`) over Monroe as it landed.
- Known rough edge: the toasts share `floatToast`'s fixed height, so a toast and a speech bubble on neighbouring
  figures can overlap for their 3 s.
- `make check`: 4936 passed in 331.72s, mypy clean (144 files), `tsc --noEmit` clean, 396 frontend tests pass.
  `make build`: built in 4.26s.
- Golden: `git diff origin/main -- backend data scripts` is empty (0 lines), so the five offline evenings are
  unchanged by construction.

---
id: S2-19
title: Sobchak's microphone interview
status: done
needs: [S2-08]
touches: [body/items.py, body/activities.py, social/scenes.py, social/thoughts.py, mind/agents.py, mind/local_policy.py, mind/options.py, characters/guests/sobchak/, frontend/src/icons.ts]
---

# S2-19 — Sobchak's microphone interview

## Why

Sobchak is a celebrity interviewer who asks the question everyone is afraid to ask. Give her a microphone:
she walks up to a guest, holds it out and interviews them. Their talk becomes an interview: she asks sharp
questions and they dodge or boast. Whoever is near overhears it, as with any conversation. The satire is in
the words, so this verb reuses the conversation scenes Haiku already writes.

## Scope

- In: `microphone` → `interview_guest` for Sobchak, on the S2-08 mechanic.
- In: the interview is an ordinary conversation scene whose `topic` names it an interview, so the turn
  prompt plays it. No new scene field, so the saved format is unchanged.
- In: a thought for the interviewee, chosen by how they regard Sobchak.
- Out: a mic other guests take (`giftable=False`); a broadcast to the whole hall (that is the stage, S2-12);
  interview-specific prompt rules beyond the topic (only if the live check shows the topic is not enough).

## Shape

Item:

```python
"microphone": Item("microphone", "a microphone", "microphones", held="a reporter's microphone",
                   hands=1, received="gifted", giftable=False, offers=("interview_guest",)),
```

Verb `interview_guest`: `partner=True`, `approaches=True` (walks up as `approach` does, to a seated or a
standing guest), `duration=8.0` (nominal: the scene ends it), `fun=0.6`, `pose="Interviewing"`,
`status="interviewing"`, `doing="interviewing someone with a microphone"`, `family="company"`,
`stopped_at_last_call` set. `on_arrival` starts a scene with the partner, as `_approach_scene` does, then sets
the scene's `topic` to an interview wording such as `"Sobchak's interview of Trump: his towers"`.
Read `scenes.TOPICS` and how the turn prompt shows `topic` before choosing the wording.

Effect when the scene opens (or on completion, whichever the code makes simpler; say which in the PR):

- The interviewee gets `interviewed`: `ThoughtKind(2.0, 4.0, 240.0, 1, "interviewed them", acquaints=True)`
  when their opinion of Sobchak is at least 0. Otherwise they get `grilled`:
  `ThoughtKind(-3.0, -10.0, 240.0, 1, "grilled them with a microphone", acquaints=True)`.
- Event `signature_act` with `verb="interview_guest"`, `item="microphone"`, `subject=[partner]`, and the
  message "Sobchak sticks a microphone in Trump's face".

Pose: a conversation part normally draws `Talking`/`TalkingSeated` in `scene.ts`. Make the activity's
`Interviewing` pose win for Sobchak while she stands in this scene. Find where the client picks the
conversation pose, and test the rule in `frontend/tests/` if it is a pure function.

Candidate rule: offered to the carrier for each guest present who is not already in her scene. Local
utility: higher for famous guests she has ties with. Option sentence: "Interview {name} with your
microphone".

Sobchak's card: `"carries": {"microphone": 1}`.

## Art (ready, do not regenerate)

- `characters/guests/sobchak/art/Interviewing/rotations/*.png`: 8 views, 68×68, PixelLab state
  `30edab67-3bb7-4bae-8b8f-416f8124df72` in group `1663b56e-633d-451c-adeb-9d96bf0ff27a`.
- `frontend/static/items/microphone.png`: PixelLab object `92bcde61-f8f5-49e4-81e9-3ec3a9894dea`. It
  replaced an earlier attempt, `24e81912-bbaa-4c8d-8b36-0e836986203d`, which drew a red box.

## Steps

1. Candidates: a carrier gets one `interview_guest` per present guest, a non-carrier gets none, and a guest
   already in her scene is skipped. Check: a parametrized test in `tests/test_agents.py`.
2. Arrival opens a scene with the interview topic, for a seated and for a standing partner. Check: a
   parametrized test through `world.step_world` (reuse the helpers in `tests/test_approach.py`).
3. Thought by regard: `interviewed` for a regard of 0 or more, `grilled` below 0. Check: a parametrized test.
4. `signature_act` logged once per interview. Check: an event-log assertion.
5. Card, icon and pose. Check: `make check`, `make build`; in the app Sobchak shows `Interviewing` while
   the scene runs, then goes back to her normal pose.
6. Live check (with a `.env` key): `make evening CAST=guests SEED=5` with Sobchak, Trump and Putin. Read the
   interview lines: do they sound like an interview? If not, note it in Results. Do not grow the prompt here.

## Done when

- `make check` and `make build` pass, output pasted in the PR.
- An evening with Sobchak logs an interview, and its lines read as questions and answers.

## Results

Built with S2-08 (see its Results).

- `interview_guest` is offered toward every guest a walk over (`approach`) is offered to, so it follows the same rules
  about tables, reach and standing room; the action is `approaches` + `partner` and reuses `_approach_scene`.
- The opening of the scene does the rest (`signature_acts.open_interview`, on arrival, not on completion): the topic
  becomes "<name>'s microphone interview of <partner>" when she opened the scene (a scene she only joined keeps its
  topic), the partner gets `interviewed` (opinion of her 0 or more) or `grilled`, and one `signature_act` is logged.
- The `Interviewing` pose needs no client rule: while Sobchak's `interview_guest` action runs, `scene.ts` already draws the
  activity's pose and only falls back to `Talking` for an action with none.
- Offline: seeds 5–7 log several interviews each. Not done: the live check with a key, to read the lines.

# The Last Inn — Design

This document defines what we are building and why. The current prototype tests whether
model-driven guests make a tavern evening believable and produce stories worth retelling.

## Concept

A life simulation of a border inn: a hybrid of a light economic simulation and a story
generator. Stories come from believable characters whose choices are made by neural
models rather than scripts or fixed decision trees. RimWorld is the reference for
legible, systemic drama: simple visible rules, characters with moods and opinions,
and incidents that grow out of their interaction.

Guests come in to relax, drink, talk, and argue. They react to the room, share news,
make friends and enemies, get drunk, fall asleep, or start a fight. The player sees why.

## Player role

**Now:** an observer acting as the inn's administrator. Before an evening the player
chooses the guests (presets or characters they wrote), and the news of the day. During
the evening the player watches and inspects; there is no direct in-world intervention.
Debug controls (pause, speed, refill, block, forced actions) remain developer tools.

**Later:** tavern staff (barkeep, cook, bouncer) who take the player's commands, then
the inn's economy: prices, supplies, money, and rooms.

## Guests

Each guest has a character card: name, occupation, background, temperament, values,
speech style, quirks, an optional secret, and a goal for the evening (“came to forget”,
“looking for work”, “waiting for someone”). Cards come from presets or are written by
the player. A model extracts the numeric parameters the simulation needs (patience,
temper, sociability, strength, alcohol tolerance, money) from the text once; the game
validates them. The text goes to the dialogue model; the numbers drive the body and
choices, so an authored character behaves as written, not only speaks that way.

At runtime a guest has needs, drunkenness, mood made of RimWorld-style thoughts
(timed mood and opinion effects such as “insulted by Bren”), relationships, and
individual knowledge. Guests learn only by seeing, hearing, and talking.

## How a guest thinks

A guest thinks at three speeds:

```
world (10 Hz tick): positions, objects, queues, resources, drunkenness
   │ stimuli: sound, sight, events          ▲ only actions the game validated
   ▼                                        │
attention: salience × temperament × distance × current activity
   │
   ├─ every tick ─────────► body (code): queue, wait, step aside, turn to a sound
   ├─ event / task done ──► choice (Jev, ~1 s): score the legal next activities
   └─ asynchronously ─────► mind (Claude Haiku 4.5, 1–3 s): lines, intentions, reflection
```

- **Body** executes *how*: queuing, waiting, routing, facing a speaker or a noise.
  It never decides what to do.
- **Choice** decides *what next*: Jev scores the legal activities from the guest's
  own briefing, as in Stage 0. It is asked on events, not every tick.
- **Mind** decides *what to say and intend*: conversation turns with a speech act,
  a short intention after salient events, and the card compiler.

The body buys time for thought: when a fight starts, a guest stops and turns to it at
once, which reads as “looking and thinking” while the choice and the mind respond.

Models decide *what* and *why*; the game decides *whether* and *how*. Text alone never
changes the world: only validated actions and speech acts have effects.

Where this split falls short among guests who meet all evening, and the steps to change it,
are in [MIND.md](MIND.md).

## Actions

Activities are defined as data: roles (alone, pair, group), preconditions, steps and
duration, effects, interruptibility, the stimulus they emit, and their pose. Objects
and people offer activities; the choice layer scores the legal ones.

- **Needs:** drink, use the WC, sit, warm up by the fire, doze at a table.
- **Good:** introduce oneself, chat, join a table, buy someone a drink, toast, play darts
  together, play dice (the winner drawn from traits, drink and chance), help someone up,
  leave together.
- **Bad:** insult, cut in line, shove, start a fight.
- **Reactions:** glance, watch (a game of dice or a fight), cheer, intervene, back away, leave.

Joint activities start as invitations: one guest proposes, the other accepts or declines,
and the game validates. Later the same protocol carries persistent agreements.

## Reacting to the room

Shared resources (tap, WC, darts) have capacity and a queue. Joining a queue is body
work; giving up is a choice driven by patience and urgency; cutting in line is a source
of conflict. Events emit stimuli with loudness; walls dampen them. Attention decides
between a glance and an interrupt that pauses the current activity and asks for a new
choice with the cause in the briefing.

## Conversation and news

A conversation is a scene with participants, a topic, and turns; others can join it,
leave it, or overhear it. Each turn is a line plus a speech act (share news, ask, joke,
boast, complain, flirt, insult, invite, accept, decline, leave). Only acts have effects:
thoughts, opinions, names learned, knowledge passed on, invitations.

The evening has news from outside: tolls, robberies, border rumors. Guests know some of
it from their background and pass it on in their own words, so a story drifts as it
travels. Strangers are known by appearance until they introduce themselves.

## Conflict

Insults, grievances, drunkenness, and temper unlock hostile options; the choice layer
still has to pick them. A shove can stagger or knock someone down. A fight is resolved
in seeded exchanges from strength, brawling, drunkenness, and chance until someone
yields, is separated, or is knocked out. Bystanders watch, cheer, intervene, back away,
or help the fallen up. Everyone involved and every witness keeps thoughts about it.

## Looking alive

Guests face whoever speaks and turn to noises, show emotes (`!`, `?`, anger, heart,
`zzz`, music), speak in short bubbles with their actual lines, sway when drunk, stand in
visible queues, and form a ring around a fight. Idling over a mug is a valid activity.

## Stories

The event log is the source of truth. After closing, a model writes a short chronicle
of the evening that cites logged events, so the story can be checked against what
happened. Every decision keeps its trigger, scores, and intention for the inspector.

## Current prototype

One hall, one evening, four to six guests, an observer player. See
[Stage 1](stages/1_EVENING.md).

**Central test:** does an evening with four to six model-driven guests look believable
to an observer, and does it produce at least one story they can retell, with causes
visible in the event log?

## Later

Staff and commands; the inn's economy; agreements that outlive a conversation;
several evenings with regulars, memory, and reputation; a storyteller that paces
incidents; the yard and property improvements.

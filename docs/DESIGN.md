# The Story Tavern — Design

This document defines what we are building and why. The plan of how is in [plan/](plan/README.md).

## Concept

A tavern between worlds where famous people walk in for a drink: presidents, pop stars, film heroes,
characters from books and games. Nobody scripts them. Each one is played by language models from a
card of who they are, what they always want tonight, and what is in their backpack, and the evening
happens on its own. Putin's parody sets up his own table at the far end of the hall so no one gets close;
Trump's parody signs a decree that elves now pay a 145% toll; Zelensky's parody deals the cards; two
oil-hunters go from table to table asking who has any.

The game is a story generator first. Chaos is the feature: drinking, shouting matches, brawls, petty
schemes and absurd alliances. RimWorld is the reference for how: simple visible rules, characters with
moods and opinions, and incidents that grow out of their interaction, so the player can see *why* it
happened. At closing the evening is retold as a short story the player wants to share.

## Tone

- **Satire with no brakes.** Guests play up their public image. Rivals insult each other, fight and scheme.
  Political figures are here to be laughed at, all of them.
- **The world keeps the rules.** A model chooses what a guest wants and says; the game decides what
  happens. A brawl is resolved by the fight formula, not by a model.
- **Known limitation: real people.** Characters based on real people carry risks around likeness, names
  and platform rules. Cards keep the person parodied (`inspired_by`) apart from the name shown, so any
  guest can be renamed to a parody name (for example "Hutin", "Tromb") in one field. Decide the names
  before anything is published.

## Player role

**Now (Stage 2):** an observer. Before the evening the player picks who is drinking tonight: the
**Guests** (famous characters) or the **Locals** (the original border folk, kept for tests and experiments).
During the evening the player watches and inspects; debug controls stay in a debug panel.

**Next (Stage 3):** the player walks into the same room as a character and talks to the guests in typed
lines. The guests answer, remember it, and act on it.

## Characters

Every character lives in the catalog under `characters/` ([CHARACTER_CATALOG.md](CHARACTER_CATALOG.md)),
grouped into casts: `guests/`, `locals/`, and `staff/` (the barkeep, the only staff member).

A card has:

- **Who:** name, looks, occupation, background, temperament, speech, quirks, a secret.
- **Persona** (famous characters): the person or character parodied, whether real or fictional, the
  public image to play up, and a few catchphrases.
- **Obsessions:** one to three things they want tonight ("keep everyone at a distance", "get someone
  else to pay", "find out who has oil"). They become the guest's goals and intentions.
- **Backpack:** a signature item and the act it unlocks (a folding table, a deck of cards, a golden pen).
- **Numbers** the body and choices use: patience, temper, sociability, courage, strength, brawling,
  alcohol tolerance, comfort, curiosity. The text goes to the models; the numbers make a character
  behave as written, not only speak that way.
- **Relationships** with other characters: rivals, allies, grudges with a reason.
- **Mute** characters (the hero of GTA III) never speak; they act and emote.

At runtime a guest has needs (thirst, bladder, energy, company, boredom), drunkenness, mood made of
RimWorld-style thoughts ("insulted by X"), relationships, and their own knowledge. Guests learn only by
seeing, hearing, and talking.

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
   └─ asynchronously ─────► mind (Claude Haiku 5.5, 1–3 s): lines, intentions, goals
```

- **Body** executes *how*: queuing, waiting, routing, facing a speaker or a noise. It never decides.
- **Choice** decides *what next*: Jev scores the legal activities from the guest's own briefing.
- **Mind** decides *what to say and intend*: conversation turns with a speech act, and intentions that
  name an obsession and a typed goal the world can check.

Models decide *what* and *why*; the game decides *whether* and *how*. Text alone never changes the
world: only validated actions and speech acts have effects. Details are in [MIND.md](MIND.md).

## Actions

Activities are data (`body/activities.py`): targets, preconditions, timing, effects, wording, pose,
and how much fun they are. Objects, people and carried items offer activities; the choice layer scores
the legal ones.

- **Needs:** drink, use the WC, sit, warm up by the fire, doze at a table.
- **Together:** introduce oneself, chat, join a table, buy someone a drink, give something, toast,
  darts, dice, cards, leave together.
- **Hostile:** insult, shout, cut in line, sit at someone's table uninvited, shove, fight.
- **Reactions:** glance, watch, cheer, step in, help up, back away, leave.
- **Signature acts:** what a guest's item unlocks: set up a private table, deal cards, sign a decree.

Joint activities start as invitations: one guest proposes, the other accepts or declines, the game
validates.

## Fun and chaos

Guests do not only meet needs: they seek fun. Watching a fight, playing together, using their signature
item and serving an obsession are fun; nursing a mug alone is not. Rivals start the evening with grudges,
so a cause for a quarrel is in the room from the first minute. A quarrel can turn into a shouting match
the whole hall turns to, and a drunk one into a brawl.

## Looking alive

Guests face whoever speaks and turn to noises, show emotes, speak in short bubbles with their actual
lines, sway when drunk, stand in visible queues, and form a ring around a fight.

## Stories

The event log is the source of truth. A **story score** counts the moments worth retelling: someone got
drunk, a quarrel, a fight, a game played together, a signature act, a gift, a guest who stormed out. It
is the main metric of every change.

At closing a strong model **retells** the evening as a short story in a few chapters. Every sentence cites
the logged events behind it, so the story can be checked against what happened. The closing screen shows
it with the faces of who was involved.

## Scope now

One hall, one evening, three to six guests from one cast, one barkeep, an observer player. See
[Stage 2](plan/2_story_evenings/README.md).

**Central test:** do famous guests produce evenings with many more retellable moments than the locals,
and does the retelling make an observer want to share it?

## Later

The player in the room (Stage 3). More guests and signature items. Not planned: economy, more staff,
agreements and memory between evenings.

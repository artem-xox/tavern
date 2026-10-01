# The Last Inn — Design

This document defines what we are building and why. The first prototype tests whether
autonomous characters can create understandable, playable stories through agreements.

## Concept

A small indie sandbox with light economics and strategy. The player runs an inn near
a border crossing, moving through the inn and yard from a top-down perspective similar
to Stardew Valley. The appeal is living alongside characters whose choices change the
inn's economy, relationships, and daily events.

Player-facing mechanics stay approachable; depth comes from characters interacting
with each other and shared systems.

## Player loop

- Buy supplies, prepare and sell meals, and rent rooms.
- Explore the property, improve it, hire workers, and delegate tasks.
- Talk, negotiate deals, make promises, and build relationships through actions.
- Manage limited resources and respond to opportunities or conflicts caused by NPCs.

Property improvements and broader hiring are part of the full concept; the prototype
focuses on meals, lodging, trading, and agreements.

## Autonomous characters

Each NPC has personality traits, needs, goals, relationships, memories, and individual
knowledge. Characters learn through observation, conversations, and rumors; they do
not automatically know the complete world state.

NPCs can initiate conversations, trade, work, request help, make agreements, share
information, form partnerships, and create conflicts. They use a shared action library:
verb, target, object, and conditions. For example, a character can deliver ingredients
in exchange for lodging or prepare meals to repay a debt.

## Decisions and dialogue

Use TypeSafe AI's Jev to evaluate actions and a separate language model for dialogue.

1. Gather observations and relevant memories for the NPC.
2. Generate actions possible in the current situation.
3. Ask Jev to evaluate them against goals, personality, memories, and commitments.
4. Select an action with a controlled stochastic policy informed by those evaluations.
5. Execute it and record its consequences.

NPCs reconsider plans after completing a task or encountering a meaningful event.
Behavior should vary while remaining consistent with personality and commitments.

The game validates resources, permissions, prices, deadlines, and agreement terms.
A conversation can propose an agreement, but only validated, accepted terms become
active obligations. Actions produce actual transfers, completed work, relationship
changes, or new obligations; dialogue alone does not establish those effects.

## Emergent stories

Stories arise from interacting goals and consequences rather than fixed quest chains.
A delayed delivery might produce a credit agreement, a new supplier relationship,
or a community project. Movement, conversations, offers, and agreement records make
causes and consequences visible so the player can understand and influence them.

## First prototype

One inn and yard, one player character, and three autonomous NPCs with overlapping
interests: a cook, a courier, and a trader.

Include movement, basic inventory, ingredients and meals, lodging, money, a day cycle,
dialogue, persistent agreements, and saving of world and character state.
The engine, AI integration details, and presentation style remain to be chosen.

**Central test:** can a conversation create an agreement that changes NPC behavior,
affects another character, and produces a new playable situation?

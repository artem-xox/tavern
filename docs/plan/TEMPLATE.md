---
id: S<stage>-<nn>
title: <short imperative title>
status: todo        # todo | doing | done | dropped
needs: []           # task IDs that must be done first
touches: []         # main modules or files, so parallel work does not collide
---

# S<stage>-<nn> — <Title>

## Why

One paragraph: what is missing in an evening today and what the player will see after this task.

## Scope

- In: the behaviors this task adds.
- Out: what looks related but belongs to another task (name it).

## Shape

The exact new fields: card, save, snapshot, model view, model answer. Freeze them here before
writing code; update this section if the code disagrees.

## Steps

1. <behavior> — check: `<test or command>`
2. ...

## Done when

- `make check` passes (plus `make build` if `frontend/` changed), output pasted in the PR.
- <an observable result in an evening, a number in `metrics.json`, or a screen>

## Results

Filled in when the task is done: what was built, the numbers, one moment from a log.

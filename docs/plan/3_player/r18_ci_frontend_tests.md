---
id: S3-R18
title: CI runs the frontend tests, on the Node version they need
status: done
needs: []
touches: [.github/workflows/ci.yml]
---

# S3-R18 — Frontend tests in CI

## Why

`make check` runs `npm --prefix frontend test` (22 test files under `frontend/tests/`), but CI does not:
`.github/workflows/ci.yml` runs `mypy`, `pytest`, `npm run check` and `npm run build` only, on Node 20.
The frontend tests import `.ts` files directly, which needs Node's built-in TypeScript stripping (AGENTS.md:
"Node 24 runs `.ts` directly"; the owner's machine has v24.5.0). So a broken pure module can merge green.
The player work will add most of its client logic as pure modules; their tests must gate merges.

## Scope

- In: `node-version: 24` in `actions/setup-node`, and a step `- run: npm test --prefix frontend` after
  `npm run check --prefix frontend`.
- Out: `.do/` deploy config; anything else in the workflow.

## Approval

AGENTS.md: ".github/ ... deploy config: ask first". **Approved by the owner, 2026-11-07.**

## Steps

1. Edit the workflow. Check it locally: the YAML parses
   (`.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`; PyYAML is in the
   venv as a dependency of uvicorn), and `npm test --prefix frontend` passes on Node 24 (`node --version`).
   One commit.
2. CI proves it only once the series branch is pushed, which the owner decides. When it is, paste the run's
   link and the step's last lines into Results.

## Done when

- The workflow change is committed and the frontend tests pass locally on Node 24.
- After the series branch is pushed: CI is green with the frontend tests in it.

## Results

Done 2026-11-07. `.github/workflows/ci.yml`: `node-version: 24`, and `- run: npm test --prefix frontend` after
`npm run check --prefix frontend`.

Local checks: the YAML parses (`yaml.safe_load` OK, PyYAML from the main checkout's `.venv`). On Node v24.5.0,
`npm test --prefix frontend` ends with `tests 271 / pass 271 / fail 0`.

CI itself is not proven yet: it runs only after the owner pushes the series branch. Then paste the run link and
the step's last lines here.

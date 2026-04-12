# TremorGuard Agent Guide

## Purpose
- Use this repository to develop TremorGuard across three areas: product documentation, a React frontend prototype, and an ESP32 hardware utility.
- Prefer small, reviewable changes that keep docs, UI behavior, and hardware notes aligned.

## Repository Layout
- `tremor-guard-frontend/`: Vite + React + TypeScript frontend prototype.
- `tremor-guard-frontend/src/`: application source, components, styles, and bundled assets.
- `tremor-guard-frontend/public/`: static public assets.
- `docs/`: architecture and product reference documents.
- `I2C_Scanner/`: Arduino sketch for ESP32 I2C device bring-up.

## Working Style
- Read the relevant files before editing; do not assume the current prototype matches the architecture docs.
- Keep changes scoped to the user's request. Avoid opportunistic refactors unless they unblock the task.
- Treat `docs/`, `frontend`, and `hardware` as separate deliverables. If a change affects more than one area, update the connected artifacts together.
- Preserve user changes already in the worktree. Do not revert unrelated edits.

## Frontend Conventions
- Use TypeScript and React function components.
- Follow the existing 2-space indentation and keep component files in PascalCase.
- Keep helper names and variables in camelCase.
- Prefer relative imports within `src/`.
- Reuse existing styling patterns before introducing new structure or dependencies.
- Do not commit generated output from `tremor-guard-frontend/dist/`.

## Docs Conventions
- Keep documentation action-oriented and specific to TremorGuard.
- When editing architecture or workflow docs, preserve terminology across layers: hardware, cloud, AI, and application.
- Call out assumptions when docs describe planned behavior rather than implemented behavior.

## Hardware Conventions
- Treat `I2C_Scanner/I2C_Scanner.ino` as a bring-up utility, not production firmware.
- Preserve the expected serial baud rate of `115200` unless the task explicitly requires changing it.
- Note hardware assumptions clearly when updating scan logic or usage instructions.

## Commands
- Run frontend commands from `tremor-guard-frontend/`.
- Install dependencies: `npm install`
- Start dev server: `npm run dev`
- Build production bundle: `npm run build`
- Run lint: `npm run lint`
- Preview production build: `npm run preview`

## Validation
- For frontend changes, run `npm run lint` and `npm run build` unless the user asks not to or the environment blocks it.
- Manually smoke-test the changed UI path in `npm run dev` when behavior or layout changes.
- For docs-only changes, verify terminology, links, and referenced paths.
- For hardware-related edits, describe the expected manual validation steps in the final response if you cannot flash hardware here.

## Done Means
- The requested files are updated and internally consistent.
- Relevant checks have been run, or any blockers are explicitly reported.
- New instructions or behavior are reflected in the nearest relevant docs when needed.
- The final response summarizes what changed, how it was verified, and any remaining manual follow-up.

## Do Not
- Do not add secrets, credentials, patient data, or environment-specific values to the repo.
- Do not modify `node_modules/` or commit generated build artifacts.
- Do not invent backend, device, or medical capabilities that are not present in the repository or request.
- Do not present AI features as diagnostic or prescription functionality.

## Task Tips For Codex
- If the request is ambiguous and spans docs, frontend, and hardware, ask which area is in scope before making broad changes.
- If a task introduces a new workflow or convention, update this file or the nearest local doc so future runs do not need the same correction twice.

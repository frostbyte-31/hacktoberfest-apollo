# Welcome to your Lovable project

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Open your project in the [Lovable editor](https://lovable.dev) and keep building.

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: connect the project to GitHub and every change made in Lovable is committed straight to your repository.
- **Full ownership**: this code is yours. Push to your repository and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```

## Built with

- TanStack Start
- TypeScript
- React
- Tailwind CSS

## Visual demo: recorded AGC evidence replay

This is a small browser console that replays **recorded** evidence from Phases 7 and 8. It is not connected to a live emulator, and it does not show a landing.

- **Run locally:**
  1. Install: `bun install` (or `npm install`).
  2. Start: `bun run dev` (or `npm run dev`).
  3. Open the URL Vite prints; in this sandbox that is `http://localhost:8080`.
- **Lovable Preview:** the project now has a `dev` script in `package.json`, so the preview starts it automatically.
- **Data:** `tools/replay/extract_replay.py` reads `docs/phase7-evidence/runs/{closed,feedback_off}.jsonl` and `docs/phase8-evidence/runs/p63.jsonl` (read-only) and writes `src/data/replay.json`. Regenerate it with `python3 tools/replay/extract_replay.py`.
- **Labels on screen:**
  - **RECORDED:** values copied from the logs.
  - **MOCK VISUAL:** the illustration of the LM and surface; the LM's tilt follows the recorded pitch gimbal.
  - **NOT MODELLED:** altitude, velocities and fuel, which have no data in this project.
- **Rule:** the web app is only a viewer. It must read just `src/data/replay.json`, never run the emulator or write to `docs/`.

## Learning frontend (recorded replay only)
Run `bun install && bun run dev`, open http://localhost:8080. Pages: `/` Mission Control (Phase 9 P51→P63 replay and Phase 7 pitch runs), `/learn` (8 tutorials), `/evidence` (Phases 1–9 status, including missing Phase 1–6 logs), `/present` (full-screen talk; ← → keys).
Data is regenerated read-only from evidence with `python3 tools/replay/extract_replay.py` → `src/data/replay.json`. No live emulator connection exists; nothing is labelled LIVE. App tests: `bunx vitest run`.

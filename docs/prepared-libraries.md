# Prepared Skills & Libraries — Reference

Prepared for later use in the Sepang F1 Pit Wall project.
Current stack: **Vite 6 + Three.js 0.170 (vanilla JS, `type: module`)** — note React-first libraries below need a React layer or standalone build.

---

## 1. Remotion — programmatic video with React
- Repo: https://github.com/remotion-dev/remotion
- Docs: https://www.remotion.dev/docs/
- Use for: rendering videos programmatically from React components (highlight reels, telemetry overlays, social clips).
- Install (existing project): `npm i remotion @remotion/cli` and `@remotion/player` to embed a `<Player>`.
- Skills install: `npx -y skills@latest add remotion-dev/skills -g -y`
- Brownfield guide: https://www.remotion.dev/docs/brownfield
- Note: React-based. This project is vanilla JS/Three.js, so Remotion would run as a separate render pipeline (it already has Blender + ffmpeg stitch scripts as an alternative).

## 2. Motion (motion.dev) — animation library
- Site: https://motion.dev/  · Quick start: https://motion.dev/docs/quick-start
- LLM docs: https://motion.dev/llms.txt
- Hybrid engine: hardware-accelerated animations, layout transitions, touch/drag gestures, timeline orchestration.
- Vanilla JS install: `npm i motion` then `import { animate } from "motion"`.
- React install: https://motion.dev/docs/react-installation
- **Best fit for this project** — works with vanilla JS (`animate()`, `scroll()`, gestures) alongside the existing Vite setup and DOM UI overlays.

## 3. bklit UI — charts on shadcn/ui
- Repo: https://github.com/bklit/bklit-ui  · README: https://github.com/bklit/bklit-ui/blob/main/README.md
- It's a shadcn registry (thin wrapper over Recharts).
- Install: `npx shadcn@latest init` then `npx shadcn@latest add @bklit/line-chart`
- Note: React + shadcn/ui + Recharts. Requires a React setup.

## 4. lieflat-charts — data-viz Skill for AI agents
- Repo: https://github.com/larashero3-dotcom/lieflat-charts
- Turns data into polished, interactive standalone HTML charts (SVG / Chart.js / ECharts).
- Styles: Lupi Editorial, Lupi Basics, Glance, Interactive. Color presets: Mono, Porcelain (blue), Palm (green), Wire (red).
- Install (Claude): `npx skills add https://github.com/larashero3-dotcom/lieflat-charts --skill lieflat-charts`
  → clones to `~/.claude/skills/lieflat-charts` (Codex: `~/.codex/skills/lieflat-charts`).
- **Good fit** — produces self-contained HTML, framework-agnostic. Useful for race telemetry / strategy dashboards.

## 5. Kokonut UI — React/Tailwind/shadcn components
- Site: https://kokonutui.com/  · Docs: https://kokonutui.com/docs  · LLM docs: https://kokonutui.com/llms.txt
- 100+ animated, accessible components built on React, Tailwind CSS, shadcn/ui, and Motion.
- Install: `npx shadcn@latest add @kokonutui/<name>` (e.g. `@kokonutui/card-flip`).
- Note: React + Tailwind + shadcn. Requires a React setup.

## 6. Design DNA — reference-UI → JSON skill (ACTIVE)
- Extract quantified design tokens, qualitative style, and visual effects from reference images/URLs into JSON, then generate matching UI.
- 3 phases: Structure (schema) → Analyze (extract DNA) → Generate (apply to content).
- Already available and activated in this session.

---

## Stack compatibility summary
| Library | Framework | Works with current Vite+Three.js? |
|---|---|---|
| Motion | vanilla JS / React | ✅ directly |
| lieflat-charts | agent skill → HTML | ✅ standalone output |
| Design DNA | agent skill | ✅ |
| Remotion | React | ⚠️ separate render pipeline |
| bklit UI | React + shadcn | ⚠️ needs React layer |
| Kokonut UI | React + shadcn | ⚠️ needs React layer |

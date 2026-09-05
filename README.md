# Sepang Pit Wall 🏎️🌧️
> **Interactive Formula 1 Strategy, Telemetry & Monsoon Simulation for the Petronas Sepang International Circuit**

[![Vite](https://img.shields.io/badge/Vite-6.0-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![React](https://img.shields.io/badge/React-19.2-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Remotion](https://img.shields.io/badge/Remotion-4.0-0B84F3?logo=remotion&logoColor=white)](https://www.remotion.dev/)
[![Motion](https://img.shields.io/badge/Motion-13.2-black?logo=framer&logoColor=white)](https://motion.dev/)

---

## 🏁 Overview

**Sepang Pit Wall** is a high-fidelity F1 race engineering and strategy simulation console crafted for the legendary **Petronas Sepang International Circuit** (5.543 km, 15 turns). 

Sepang presents one of motorsport's most extreme engineering challenges: **54°C track temperatures** that aggressively degrade the right-front tyre carcass through sweeping high-G turns (Turns 5–6 and 11), coupled with **unpredictable tropical monsoon cloudbursts** that can saturate Sector 2 with standing water in under 90 seconds.

This application delivers real-time stint evaluation, tyre thermal dynamics, live telemetry HUD video compositing, and radar-based monsoon crossover calculations in a tactical, dark pit-wall interface.

---

## ✨ Key Features & Modules

### 1. 🎥 Cinema Stage & Telemetry HUD (`/cinema`)
- **Remotion Video Integration**: In-browser video compositor rendering frame-accurate telemetry gauges (speed, gear, throttle/brake telemetry, RPM, lateral Gs).
- **Synchronized Ambient Sound & Soundtrack**: Realistic F1 engine audio paired with selectable pit-wall commentary & race soundtrack.
- **Dynamic HUD Overlays**: Live corner indicators and DRS status tracking each onboard sector.

### 2. 📋 Race Brief & Track Conditions
- **Event Countdown**: Real-time countdown clock to race start with local Malaysia Time (UTC+8) synchronization.
- **Track Status Ribbon**: Live monitoring of ambient temperature (34°C), track temperature (54°C), humidity (82%), and barometric pressure.

### 3. 🗺️ Circuit Lab
- **Interactive Track Telemetry**: Vector SVG track map featuring Turn 1 through Turn 15 with speed profiles and braking points.
- **DRS Zones & Sector Breakdown**: Visualisation of Sector 1 (high-speed technical), Sector 2 (flowing high-G complexes), and Sector 3 (opposing 1 km straights).

### 4. 🧮 Strategy Lab (Stint Optimizer)
- **Combinatorial Stint Pricing**: Evaluates thousands of feasible 1-stop, 2-stop, and 3-stop strategies in real time.
- **Pit Delta & Loss Modeling**: Accurately prices the 22.4s pit lane loss versus on-track tyre degradation deltas.
- **Safety Car Sensitivity**: Dynamic risk assessment factoring in safety car windows and undercut advantage.

### 5. 🛞 Tyre Lab & Thermal Dynamics
- **Thermal Carcass Model**: Simulates core temperature versus surface blistering thresholds on Pirelli C1 (Hard), C2 (Medium), and C3 (Soft) compounds.
- **Compound Stint Degradation**: Non-linear degradation curves tracking lap-time falloff and degradation cliffs.

### 6. ⛈️ Monsoon Centre & Doppler Radar
- **Rapid Saturation Model**: Simulates convective tropical cloudbursts flooding the tarmac.
- **Tyre Crossover Calculator**: Automatic calculation of crossover lap windows:
  $$\text{Slick} \longrightarrow \text{Intermediate} \longrightarrow \text{Full Wet} \longrightarrow \text{Red Flag / Abandon}$$
- **Drainage & Drying Curves**: Sector-by-sector drainage modeling highlighting persistent rivers across Turn 9 downhill braking.

### 7. 🎬 Film Room & Academy
- **Curated Multi-Angle Footage**: Switch between onboard, aerial, and chase camera angles.
- **Interactive Learning Tracks**: Step-by-step guides breaking down race engineer communication, tyre management, and pit-stop decision trees.

### 8. 📊 Validation & Receipts
- Empirical validation comparing model predictions against historical Malaysian Grand Prix telemetry and race outcomes.

---

## 🛠️ Tech Stack

- **Core**: [React 19](https://react.dev/), [Vite 6](https://vitejs.dev/)
- **Video & Compositing**: [Remotion 4](https://www.remotion.dev/) (`@remotion/player`, `remotion`)
- **Motion & Micro-interactions**: [Motion 13](https://motion.dev/)
- **Styling**: Vanilla CSS3 design system with custom CSS variables, tactical grid system, and responsive typography (Chakra Petch, JetBrains Mono, Inter)
- **Testing & Tooling**: Puppeteer E2E validation

---

## 🚀 Getting Started

### Prerequisites
- [Node.js](https://nodejs.org/) (version 18.0.0 or higher recommended)
- [npm](https://www.npmjs.com/) or [pnpm](https://pnpm.io/)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/itzefyee/Sepang-Pit-Wall.git
   cd "Sepang Pit Wall"
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```
   Open [http://localhost:5173](http://localhost:5173) in your browser.

4. **Build for production:**
   ```bash
   npm run build
   ```

5. **Preview production build:**
   ```bash
   npm run preview
   ```

---

## 📁 Project Directory Structure

```text
├── index.html                   # Main entry point with custom branding & metadata
├── sepang_progress.html         # Progress dashboard entry
├── package.json                 # Project dependencies & build scripts
├── public/                      # Static assets
│   └── assets/
│       ├── audio/               # Engine audio & effects
│       ├── img/                 # Circuit logos, flags, photo decks
│       └── vid/                 # Compressed 1080p MP4 race clips
└── src/
    └── pitwall/
        ├── App.jsx              # Main application shell
        ├── main.jsx             # React DOM root render
        ├── theme.css            # Pit-wall tactical design tokens & UI styles
        ├── hooks.js             # Custom React hooks (scroll, countdown, motion)
        ├── cinema/              # Remotion video timeline, HUD, and grade filters
        │   ├── ClipStage.jsx
        │   ├── Hud.jsx
        │   └── SepangComposition.jsx
        ├── components/          # Application modules
        │   ├── Academy.jsx      # Strategy learning modules
        │   ├── CircuitLab.jsx   # Track geometry & telemetry
        │   ├── FilmRoom.jsx     # Video cinema player
        │   ├── Hero.jsx         # Hero stage & countdown banner
        │   ├── MonsoonCentre.jsx# Weather radar & wet crossover model
        │   ├── Nav.jsx          # Tactical header & navigation sheet
        │   ├── RaceBrief.jsx    # Weekend schedule & condition telemetry
        │   ├── StrategyLab.jsx  # Pit-stop combinatorics optimizer
        │   ├── TyreLab.jsx      # Tyre compound thermal physics
        │   └── Validation.jsx   # Empirical accuracy benchmarks
        └── data/                # Domain models, track coordinates & race constants
```

---

## 📜 License & Acknowledgements

- Built for the F1 Simulation & Strategy Hackathon.
- Track data & circuit telemetry calibrated to the Petronas Sepang International Circuit.

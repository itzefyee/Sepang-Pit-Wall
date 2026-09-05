import { Suspense, lazy } from "react";
import { Footer } from "./components/Footer.jsx";
import { Hero } from "./components/Hero.jsx";
import { Nav } from "./components/Nav.jsx";
import { RaceBrief } from "./components/RaceBrief.jsx";

const CircuitLab = lazy(() =>
  import("./components/CircuitLab.jsx").then((m) => ({ default: m.CircuitLab }))
);
const StrategyLab = lazy(() =>
  import("./components/StrategyLab.jsx").then((m) => ({ default: m.StrategyLab }))
);
const TyreLab = lazy(() =>
  import("./components/TyreLab.jsx").then((m) => ({ default: m.TyreLab }))
);
const FilmRoom = lazy(() =>
  import("./components/FilmRoom.jsx").then((m) => ({ default: m.FilmRoom }))
);
const MonsoonCentre = lazy(() =>
  import("./components/MonsoonCentre.jsx").then((m) => ({ default: m.MonsoonCentre }))
);
const Academy = lazy(() =>
  import("./components/Academy.jsx").then((m) => ({ default: m.Academy }))
);
const Validation = lazy(() =>
  import("./components/Validation.jsx").then((m) => ({ default: m.Validation }))
);

function SectionFallback() {
  return (
    <div
      style={{
        minHeight: "280px",
        display: "grid",
        placeContent: "center",
        color: "var(--fg-dim)",
        fontFamily: "var(--font-mono)",
        fontSize: "0.8rem",
        letterSpacing: "0.08em"
      }}
    >
      <span className="dot dot--live" style={{ marginRight: "8px" }} />
      STREAMING TELEMETRY MODULE…
    </div>
  );
}

export function App() {
  return (
    <div className="shell">
      <Nav />
      <main>
        <Hero />
        <RaceBrief />
        <Suspense fallback={<SectionFallback />}>
          <CircuitLab />
          <StrategyLab />
          <TyreLab />
          <FilmRoom />
          <MonsoonCentre />
          <Academy />
          <Validation />
        </Suspense>
      </main>
      <Footer />
    </div>
  );
}


import { Academy } from "./components/Academy.jsx";
import { CircuitLab } from "./components/CircuitLab.jsx";
import { FilmRoom } from "./components/FilmRoom.jsx";
import { Footer } from "./components/Footer.jsx";
import { Hero } from "./components/Hero.jsx";
import { MonsoonCentre } from "./components/MonsoonCentre.jsx";
import { Nav } from "./components/Nav.jsx";
import { RaceBrief } from "./components/RaceBrief.jsx";
import { StrategyLab } from "./components/StrategyLab.jsx";
import { TyreLab } from "./components/TyreLab.jsx";
import { Validation } from "./components/Validation.jsx";

export function App() {
  return (
    <div className="shell">
      <Nav />
      <main>
        <Hero />
        <RaceBrief />
        <CircuitLab />
        <StrategyLab />
        <TyreLab />
        <FilmRoom />
        <MonsoonCentre />
        <Academy />
        <Validation />
      </main>
      <Footer />
    </div>
  );
}

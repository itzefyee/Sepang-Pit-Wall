import { EVENT } from "../data/schedule.js";

export function Footer() {
  return (
    <footer className="footer">
      <div className="wrap footer__inner">
        <div className="footer__brand">
          <span className="nav__mark" aria-hidden="true" />
          <div>
            <strong>Sepang Pit Wall</strong>
            <p>Strategy, learning and simulation.</p>
          </div>
        </div>
        <div className="footer__links">
          <a href="#top">Top</a>
          <a href="#strategy">Strategy lab</a>
          <a href="#academy">Academy</a>
          <a href="#model">Model notes</a>
        </div>
        <p className="footer__legal">
          {EVENT.disclaimer} This independent educational simulation is not affiliated
          with Formula 1, Ferrari, FIA, Sepang International Circuit or their partners.
        </p>
      </div>
    </footer>
  );
}

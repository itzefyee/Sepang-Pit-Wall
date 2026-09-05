/**
 * Shared behaviour hooks.
 *
 * Everything here degrades under prefers-reduced-motion: reveals resolve
 * immediately, counters land on their final value, canvases stop looping.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/** Adds `.in` once the element crosses 85% of the viewport. Fires once. */
export function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.classList.add("in");
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add("in");
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -15% 0px", threshold: 0.01 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return ref;
}

/** True once the element has been seen. Used to defer expensive work. */
export function useInView(options) {
  const ref = useRef(null);
  const [seen, setSeen] = useState(false);
  const [visible, setVisible] = useState(false);
  const opts = useMemo(
    () => options ?? { threshold: 0.12, rootMargin: "120px" },
    [options]
  );
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => {
      setVisible(entry.isIntersecting);
      if (entry.isIntersecting) setSeen(true);
    }, opts);
    io.observe(el);
    return () => io.disconnect();
  }, [opts]);
  return [ref, seen, visible];
}

/**
 * Counts up to `value` when the element enters view.
 * Returns [ref, displayValue].
 */
export function useCountUp(value, { duration = 1100, decimals = 0 } = {}) {
  const [shown, setShown] = useState(0);
  const ref = useRef(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(value);
      return;
    }
    const io = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting || started.current) return;
      started.current = true;
      io.disconnect();
      const t0 = performance.now();
      const tick = (t) => {
        const p = Math.min(1, (t - t0) / duration);
        // ease-out expo, the same curve the CSS uses
        const eased = 1 - Math.pow(1 - p, 3);
        setShown(value * eased);
        if (p < 1) requestAnimationFrame(tick);
        else setShown(value);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.2 });
    io.observe(el);
    return () => io.disconnect();
  }, [value, duration]);

  return [ref, shown.toFixed(decimals)];
}

/** Sets --mx/--my/--lit on a panel so its spotlight follows the pointer. */
export function useSpotlight() {
  const ref = useRef(null);

  const onMove = useCallback((e) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${((e.clientX - r.left) / r.width) * 100}%`);
    el.style.setProperty("--my", `${((e.clientY - r.top) / r.height) * 100}%`);
  }, []);

  const onEnter = useCallback(() => {
    ref.current?.style.setProperty("--lit", "1");
  }, []);

  const onLeave = useCallback(() => {
    ref.current?.style.setProperty("--lit", "0");
  }, []);

  return {
    ref,
    handlers: {
      onPointerMove: onMove,
      onPointerEnter: onEnter,
      onPointerLeave: onLeave
    }
  };
}

/** Document scroll progress, 0..1, for the nav hairline. */
export function useScrollProgress() {
  const [p, setP] = useState(0);
  useEffect(() => {
    let raf = 0;
    const measure = () => {
      raf = 0;
      const h = document.documentElement.scrollHeight - window.innerHeight;
      setP(h > 0 ? Math.min(1, Math.max(0, window.scrollY / h)) : 0);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);
  return p;
}

/** Which section anchor is currently nearest the top of the viewport. */
export function useActiveSection(ids) {
  const [active, setActive] = useState(ids[0]);
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: 0 }
    );
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) io.observe(el);
    });
    return () => io.disconnect();
  }, [ids]);
  return active;
}

/** Live countdown to an ISO instant. */
export function useCountdown(iso) {
  const target = useMemo(() => new Date(iso).getTime(), [iso]);
  const compute = useCallback(() => {
    const ms = target - Date.now();
    const past = ms <= 0;
    const abs = Math.abs(ms);
    return {
      past,
      days: Math.floor(abs / 86400000),
      hours: Math.floor((abs % 86400000) / 3600000),
      minutes: Math.floor((abs % 3600000) / 60000),
      seconds: Math.floor((abs % 60000) / 1000)
    };
  }, [target]);

  const [t, setT] = useState(compute);

  useEffect(() => {
    setT(compute());
    const id = setInterval(() => setT(compute()), 1000);
    return () => clearInterval(id);
  }, [compute]);

  return t;
}

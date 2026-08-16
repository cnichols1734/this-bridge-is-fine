import { useEffect, useRef, useState } from "react";

const DETENTS = ["peek", "half", "full"];

function viewportH() {
  return window.visualViewport?.height || window.innerHeight;
}

export function detentHeight(detent) {
  const h = viewportH();
  const landscape = window.innerWidth > h && h <= 500;
  if (detent === "full") return Math.round(h * (landscape ? 0.88 : 0.92));
  if (detent === "half") return Math.round(h * (landscape ? 0.42 : 0.5));
  if (landscape) return Math.min(120, Math.round(h * 0.3));
  return Math.min(178, Math.round(h * 0.24));
}

function nearestDetent(height, dismissible) {
  const peek = detentHeight("peek");
  if (dismissible && height < peek * 0.62) return "dismiss";
  return DETENTS.reduce((best, name) => {
    const delta = Math.abs(detentHeight(name) - height);
    return delta < best.delta ? { name, delta } : best;
  }, { name: "peek", delta: Infinity }).name;
}

export default function Sheet({
  detent,
  onDetent,
  onDismiss,
  children,
}) {
  const [dragH, setDragH] = useState(null);
  const drag = useRef(null);
  const height = dragH ?? detentHeight(detent);

  useEffect(() => {
    document.documentElement.style.setProperty("--sheet-h", `${height}px`);
  }, [height]);

  useEffect(() => {
    const onResize = () => {
      if (!drag.current) setDragH(null);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const snap = (next) => {
    setDragH(null);
    if (next === "dismiss") {
      onDismiss?.();
      return;
    }
    onDetent(next);
  };

  const onPointerDown = (event) => {
    if (event.button && event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = {
      y: event.clientY,
      h: height,
      lastY: event.clientY,
      lastT: performance.now(),
      v: 0,
    };
    setDragH(height);
  };

  const onPointerMove = (event) => {
    const state = drag.current;
    if (!state) return;
    const now = performance.now();
    const dy = state.y - event.clientY;
    const max = detentHeight("full");
    const min = onDismiss ? 56 : detentHeight("peek");
    const next = Math.min(max, Math.max(min, state.h + dy));
    const dt = now - state.lastT;
    if (dt > 0) {
      state.v = (state.lastY - event.clientY) / dt;
    }
    state.lastY = event.clientY;
    state.lastT = now;
    setDragH(next);
  };

  const onPointerUp = () => {
    const state = drag.current;
    if (!state) return;
    drag.current = null;
    const current = dragH ?? height;
    let next = nearestDetent(current, Boolean(onDismiss));
    if (state.v > 0.55) {
      const i = DETENTS.indexOf(detent);
      next = DETENTS[Math.min(i + 1, DETENTS.length - 1)];
    } else if (state.v < -0.55) {
      const i = DETENTS.indexOf(detent);
      next = i <= 0 && onDismiss ? "dismiss" : DETENTS[Math.max(i - 1, 0)];
    }
    snap(next);
  };

  const startDrag = (event) => {
    if (event.button && event.button !== 0) return;
    if (event.target.closest(".sheet-close, a, input, .row")) return;
    if (!event.target.closest(".sheet-handle, .sheet-drag")) return;
    onPointerDown(event);
  };

  return (
    <section
      className={`sheet ${detent}${dragH != null ? " is-drag" : ""}`}
      style={{ height }}
      onPointerDown={startDrag}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <div className="sheet-handle">
        <div className="grab" aria-hidden="true" />
      </div>
      <div className="sheet-body">{children}</div>
    </section>
  );
}

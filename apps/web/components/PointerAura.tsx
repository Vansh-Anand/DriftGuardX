"use client";

import { useEffect, useRef } from "react";

export function PointerAura() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!window.matchMedia("(pointer: fine)").matches) return;
    const move = (event: PointerEvent) => {
      ref.current?.style.setProperty("--x", `${event.clientX}px`);
      ref.current?.style.setProperty("--y", `${event.clientY}px`);
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => window.removeEventListener("pointermove", move);
  }, []);
  return <div ref={ref} className="pointer-aura" aria-hidden="true" />;
}

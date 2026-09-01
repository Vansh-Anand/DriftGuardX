"use client";

import { useEffect, useRef } from "react";

export function PointerAura() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!window.matchMedia("(pointer: fine)").matches) return;
    const move = (event: PointerEvent) => {
      if (ref.current) {
         // Add a small offset so it's slightly below/right of the actual cursor
        ref.current.style.transform = `translate(${event.clientX + 10}px, ${event.clientY + 10}px)`;
      }
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => window.removeEventListener("pointermove", move);
  }, []);
  
  return (
    <div 
      ref={ref} 
      className="fixed top-0 left-0 w-2 h-2 bg-accent pointer-events-none z-[9999] transition-transform duration-75 ease-out" 
      aria-hidden="true" 
    />
  );
}

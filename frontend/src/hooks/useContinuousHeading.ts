import { useState } from "react";

// Keep equivalent angles continuous across the ±180° seam for CSS transitions.
export function useContinuousHeading(heading: number) {
  const [previous, setPrevious] = useState({ heading, rotation: heading });
  if (previous.heading !== heading) {
    const delta = ((heading - previous.heading + 180) % 360 + 360) % 360 - 180;
    const next = { heading, rotation: previous.rotation + delta };
    setPrevious(next);
    return next.rotation;
  }
  return previous.rotation;
}

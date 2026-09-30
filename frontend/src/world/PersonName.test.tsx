import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import type { Entity } from "../api/world";
import { PersonName } from "./PersonName";

describe("PersonName", () => {
  it("opens the referenced resident when clicked and leaves missing residents as text", async () => {
    const person: Entity = { id: "person:test", name: "Lea", kind: "person", position: { x: 0, y: 0 } };
    const onSelect = vi.fn();
    const container = document.createElement("div");
    const root = createRoot(container);
    try {
      await act(async () => root.render(<PersonName people={[person]} personId={person.id} onSelect={onSelect} />));
      expect(container.querySelector("button")?.textContent).toBe("Lea");
      await act(async () => container.querySelector("button")!.click());
      expect(onSelect).toHaveBeenCalledWith(person);
      await act(async () => root.render(<PersonName people={[person]} personId="missing" onSelect={onSelect} fallback="Unknown resident" />));
      expect(container.querySelector("button")).toBeNull();
      expect(container.textContent).toBe("Unknown resident");
    } finally {
      await act(async () => root.unmount());
    }
  });
});

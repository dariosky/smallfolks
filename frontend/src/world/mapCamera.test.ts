import { afterEach, describe, expect, it, vi } from "vitest";
import { MAP_CAMERA_STORAGE_KEY, readMapCamera, saveMapCamera } from "./mapCamera";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("saved map camera", () => {
  it("restores the saved position and zoom", () => {
    const camera = { zoom: 2.25, position: { x: -150, y: 320 } };
    saveMapCamera(camera);
    expect(readMapCamera()).toEqual(camera);
  });

  it("uses the default camera for malformed data", () => {
    for (const value of ["broken", '{"zoom":2}', '{"zoom":"2","position":{"x":0,"y":0}}']) {
      localStorage.setItem(MAP_CAMERA_STORAGE_KEY, value);
      expect(readMapCamera()).toEqual({ zoom: 1, position: { x: 0, y: 0 } });
    }
  });

  it("limits stored zoom to the supported range", () => {
    localStorage.setItem(
      MAP_CAMERA_STORAGE_KEY,
      JSON.stringify({ zoom: 99, position: { x: 0, y: 0 } }),
    );
    expect(readMapCamera().zoom).toBe(4);
  });

  it("keeps navigation usable when localStorage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("Blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("Blocked");
    });
    expect(readMapCamera().zoom).toBe(1);
    expect(() => saveMapCamera({ zoom: 2, position: { x: 0, y: 0 } })).not.toThrow();
  });
});

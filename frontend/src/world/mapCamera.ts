export type MapCamera = { zoom: number; position: { x: number; y: number } };

export const MAP_CAMERA_STORAGE_KEY = "smallfolks.map-camera";

export function readMapCamera(): MapCamera {
  const fallback = { zoom: 1, position: { x: 0, y: 0 } };
  try {
    const saved = JSON.parse(localStorage.getItem(MAP_CAMERA_STORAGE_KEY) ?? "null");
    if (
      !saved ||
      !Number.isFinite(saved.zoom) ||
      !Number.isFinite(saved.position?.x) ||
      !Number.isFinite(saved.position?.y)
    )
      return fallback;
    return {
      zoom: Math.max(1, Math.min(4, saved.zoom)),
      position: { x: saved.position.x, y: saved.position.y },
    };
  } catch {
    return fallback;
  }
}

export function saveMapCamera(camera: MapCamera) {
  try {
    localStorage.setItem(MAP_CAMERA_STORAGE_KEY, JSON.stringify(camera));
  } catch {
    // Map navigation still works when browser storage is unavailable.
  }
}

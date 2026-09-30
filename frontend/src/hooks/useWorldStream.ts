import { useEffect } from "react";
import { worldStreamUrl, type World } from "../api/world";
import { applyWorldPatch, type WorldPatch } from "../api/worldStream";
import { usePageVisible } from "./usePageVisible";

export function useWorldStream(
  worldId: string | null,
  onWorld: (world: World) => void,
  onError: () => void,
) {
  const visible = usePageVisible();
  useEffect(() => {
    if (!worldId || !visible) return;
    let cancelled = false;
    let socket: WebSocket;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let watchdog: ReturnType<typeof setTimeout> | undefined;
    let delay = 1000;
    function connect() {
      if (cancelled) return;
      let current: World | null = null;
      socket = new WebSocket(worldStreamUrl(worldId!));
      watchdog = setTimeout(() => socket.close(), 10000);
      socket.onmessage = (event) => {
        if (cancelled) return;
        try {
          const message = JSON.parse(event.data) as { type: "snapshot"; world: World } | WorldPatch;
          if (message.type === "snapshot" && message.world.id === worldId) {
            current = message.world;
          } else if (message.type === "patch" && current) {
            current = applyWorldPatch(current, message);
          } else throw new Error("Invalid world stream message");
          clearTimeout(watchdog);
          delay = 1000;
          onWorld(current);
        } catch {
          socket.close();
        }
      };
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        clearTimeout(watchdog);
        if (cancelled) return;
        onError();
        retry = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 10000);
      };
    }
    connect();
    return () => {
      cancelled = true;
      clearTimeout(retry);
      clearTimeout(watchdog);
      socket.close();
    };
  }, [worldId, visible, onWorld, onError]);
}

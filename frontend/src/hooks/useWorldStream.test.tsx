import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { World } from "../api/world";
import { useWorldStream } from "./useWorldStream";

class FakeSocket {
  static instances: FakeSocket[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }
  close() {
    this.closed = true;
    this.onclose?.();
  }
  message(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) } as MessageEvent);
  }
}
const onWorld = vi.fn();
const onError = vi.fn();
const world = { id: "world:test", revision: 1, people: [] } as unknown as World;
function Stream() {
  useWorldStream(world.id, onWorld, onError);
  return null;
}
describe("world stream", () => {
  let root: Root;
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    FakeSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeSocket);
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
    root = createRoot(document.createElement("div"));
  });
  afterEach(async () => {
    await act(() => root.unmount());
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });
  it("receives a snapshot and sparse updates without polling", async () => {
    await act(() => root.render(<Stream />));
    const socket = FakeSocket.instances[0];
    expect(socket.url).toMatch(/^ws:\/\/.*\/worlds\/world%3Atest\/stream$/);
    await act(() => socket.message({ type: "snapshot", world }));
    await act(() =>
      socket.message({
        type: "patch",
        base_revision: 1,
        revision: 2,
        operations: [{ path: ["revision"], value: 2 }],
      }),
    );
    expect(onWorld.mock.calls[1][0].revision).toBe(2);
    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(FakeSocket.instances).toHaveLength(1);
    expect(onWorld).toHaveBeenCalledTimes(2);
  });
  it("resynchronizes after a revision mismatch", async () => {
    await act(() => root.render(<Stream />));
    const socket = FakeSocket.instances[0];
    await act(() => socket.message({ type: "snapshot", world }));
    await act(() =>
      socket.message({ type: "patch", base_revision: 4, revision: 5, operations: [] }),
    );
    expect(socket.closed).toBe(true);
    expect(onWorld).toHaveBeenCalledTimes(1);
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(FakeSocket.instances).toHaveLength(2);
    await act(() =>
      FakeSocket.instances[1].message({ type: "snapshot", world: { ...world, revision: 5 } }),
    );
    expect(onWorld.mock.calls[1][0].revision).toBe(5);
  });
  it("disconnects while hidden, ignores old results and reconnects on return", async () => {
    await act(() => root.render(<Stream />));
    const socket = FakeSocket.instances[0];
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    await act(() => document.dispatchEvent(new Event("visibilitychange")));
    await act(() => socket.message({ type: "snapshot", world }));
    expect(socket.closed).toBe(true);
    expect(onWorld).not.toHaveBeenCalled();
    await act(() => vi.advanceTimersByTimeAsync(20000));
    expect(FakeSocket.instances).toHaveLength(1);
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
    await act(() => document.dispatchEvent(new Event("visibilitychange")));
    expect(FakeSocket.instances).toHaveLength(2);
  });
  it("backs off repeated connection failures", async () => {
    await act(() => root.render(<Stream />));
    await act(() => FakeSocket.instances[0].close());
    await act(() => vi.advanceTimersByTimeAsync(1000));
    await act(() => FakeSocket.instances[1].close());
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(FakeSocket.instances).toHaveLength(2);
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(FakeSocket.instances).toHaveLength(3);
  });
});

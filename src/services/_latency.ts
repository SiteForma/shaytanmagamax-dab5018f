/** Simulate latency to make UI feel real. */
export const latency = (ms = 280) => new Promise<void>((r) => setTimeout(r, ms));

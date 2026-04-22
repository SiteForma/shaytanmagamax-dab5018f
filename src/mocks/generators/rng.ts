/**
 * Tiny seeded RNG so mock data is deterministic across reloads.
 */
export function createRng(seed = 42) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

export function pick<T>(arr: readonly T[], rng: () => number): T {
  return arr[Math.floor(rng() * arr.length)];
}

export function rand(min: number, max: number, rng: () => number) {
  return min + Math.floor(rng() * (max - min + 1));
}

export function randFloat(min: number, max: number, rng: () => number, digits = 2) {
  const v = min + rng() * (max - min);
  const p = Math.pow(10, digits);
  return Math.round(v * p) / p;
}

export interface CoverPalette {
  background: string;
  color: string;
}

/** Deterministic pastel cover, so no external thumbnails are requested. */
export function coverPalette(seed: string): CoverPalette {
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = (hash * 31 + seed.charCodeAt(index)) % 360;
  }
  const hue = hash;
  return {
    background: `linear-gradient(145deg, hsl(${hue} 58% 90%), hsl(${(hue + 38) % 360} 48% 76%))`,
    color: `hsl(${hue} 38% 26%)`,
  };
}

export function initials(title: string): string {
  const words = title
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words[words.length - 1][0]}`.toUpperCase();
}

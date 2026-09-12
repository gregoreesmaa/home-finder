// Perceptual value scale for parameter heat: green = good, red = bad,
// interpolated in OKLCH (perceptually uniform) with strictly increasing
// lightness, so the value reads from brightness alone — legible for
// red-green colorblind readers and in greyscale. Goodness 0..100 is
// sequential data, so a sequential ramp (not a diverging one).

export interface LutEntry {
  r: number;
  g: number;
  b: number;
}

const LUT_SIZE = 256;
// Dark brick red -> amber middle -> leaf green, constant restrained chroma
// (map-like, prints well), lightness rising end to end.
const L0 = 0.44;
const L1 = 0.74;
const CHROMA = 0.11;
const HUE0 = 28;
const HUE1 = 142;

function cube(x: number): number {
  return x * x * x;
}

function linearToSrgb(u: number): number {
  const c = Math.min(1, Math.max(0, u));
  return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}

/** OKLCH (L 0..1) -> sRGB bytes, gamut-clipped. */
function oklchToRgb(L: number, C: number, hDeg: number): LutEntry {
  const h = (hDeg * Math.PI) / 180;
  const a = C * Math.cos(h);
  const b = C * Math.sin(h);
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.291485548 * b;
  const l = cube(l_);
  const m = cube(m_);
  const s = cube(s_);
  return {
    r: Math.round(linearToSrgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s) * 255),
    g: Math.round(linearToSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s) * 255),
    b: Math.round(linearToSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s) * 255),
  };
}

/** 256-entry ramp; index i carries value i/255*100. */
export function buildValueLut(size = LUT_SIZE): LutEntry[] {
  const out: LutEntry[] = [];
  for (let i = 0; i < size; i++) {
    const t = size === 1 ? 0 : i / (size - 1);
    out.push(oklchToRgb(L0 + (L1 - L0) * t, CHROMA, HUE0 + (HUE1 - HUE0) * t));
  }
  return out;
}

const DEFAULT_LUT = buildValueLut();

/** sRGB triplet for a 0..100 value (clamped). */
export function colorForValue(v: number, lut: LutEntry[] = DEFAULT_LUT): [number, number, number] {
  const t = Math.min(1, Math.max(0, v / 100));
  const e = lut[Math.round(t * (lut.length - 1))];
  return [e.r, e.g, e.b];
}

/** WCAG relative luminance, for the monotonic-lightness contract. */
export function relativeLuminance(e: LutEntry): number {
  const lin = (c: number) => {
    const u = c / 255;
    return u <= 0.03928 ? u / 12.92 : Math.pow((u + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(e.r) + 0.7152 * lin(e.g) + 0.0722 * lin(e.b);
}

/** Legend gradient sampled from the same LUT the map uses. */
export function lutCssGradient(lut: LutEntry[] = DEFAULT_LUT): string {
  const stops = [0, 25, 50, 75, 100].map((v) => {
    const [r, g, b] = colorForValue(v, lut);
    return `rgb(${r}, ${g}, ${b}) ${v}%`;
  });
  return `linear-gradient(to right, ${stops.join(", ")})`;
}

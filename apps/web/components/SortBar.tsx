"use client";

import type { SortMode } from "../lib/sort";

const OPTIONS: { value: SortMode; label: string }[] = [
  { value: "combined", label: "Parim match" },
  { value: "livability", label: "Elamiskvaliteet" },
  { value: "deal", label: "Soodne hind" },
];

export function SortBar({
  value,
  onChange,
  count,
  disabled,
}: {
  value: SortMode;
  onChange: (v: SortMode) => void;
  count: number;
  disabled?: boolean;
}) {
  return (
    <div aria-label="Järjesta kodud">
      <div role="group" aria-label="Sorteerimine">
        {OPTIONS.map((o) => (
          <button
            key={o.value}
            type="button"
            aria-pressed={value === o.value}
            disabled={disabled}
            onClick={() => onChange(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
      <p aria-live="polite">{count} kodu järjestatud</p>
    </div>
  );
}

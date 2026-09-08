"use client";

import type { Filters } from "../lib/filters";

export function FilterBar({
  value,
  counties,
  onChange,
  onReset,
}: {
  value: Filters;
  counties: string[];
  onChange: (v: Filters) => void;
  onReset: () => void;
}) {
  const set = (patch: Partial<Filters>) => onChange({ ...value, ...patch });
  const num = (raw: string): number | null =>
    raw.trim() === "" ? null : Number(raw);
  return (
    <form aria-label="Filtreeri kodusid" onSubmit={(e) => e.preventDefault()}>
      <fieldset>
        <legend>Filtrid</legend>
        <label>
          Maakond
          <select
            aria-label="Maakond"
            value={value.county}
            onChange={(e) => set({ county: e.target.value })}
          >
            <option value="">Kõik</option>
            {counties.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          Hind kuni €
          <input
            aria-label="Hind kuni"
            type="number"
            min={0}
            step={5000}
            placeholder="nt 200000"
            value={value.maxPrice ?? ""}
            onChange={(e) => set({ maxPrice: num(e.target.value) })}
          />
        </label>
        <label>
          Tube vähemalt
          <input
            aria-label="Tube vähemalt"
            type="number"
            min={0}
            max={10}
            value={value.minRooms ?? ""}
            onChange={(e) => set({ minRooms: num(e.target.value) })}
          />
        </label>
        <label>
          Kvaliteet vähemalt
          <input
            aria-label="Kvaliteet vähemalt"
            type="number"
            min={0}
            max={100}
            placeholder="0–100"
            value={value.minLiv ?? ""}
            onChange={(e) => set({ minLiv: num(e.target.value) })}
          />
        </label>
        <button type="button" onClick={onReset}>
          Lähtesta
        </button>
      </fieldset>
    </form>
  );
}

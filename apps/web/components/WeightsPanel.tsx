"use client";

import { DEFAULT_BALANCE, DIMS, type Multipliers } from "../lib/weights";

/**
 * Buyer-adjustable scoring (#74): the price-vs-quality balance plus one
 * slider per livability dimension (0–200%, 100 = registry default).
 * Everything recomputes client-side and stays URL-shared (?bal=, ?w=).
 */
export function WeightsPanel({
  balance,
  multipliers,
  onBalance,
  onMultipliers,
  onReset,
}: {
  balance: number;
  multipliers: Multipliers;
  onBalance: (v: number) => void;
  onMultipliers: (v: Multipliers) => void;
  onReset: () => void;
}) {
  const set = (key: string, v: number) =>
    onMultipliers({ ...multipliers, [key]: v });
  const customized =
    balance !== DEFAULT_BALANCE ||
    DIMS.some((d) => {
      const m = multipliers[d.key];
      return m !== undefined && m !== 100;
    });
  return (
    <form aria-label="Hinda ümber" onSubmit={(e) => e.preventDefault()}>
      <fieldset>
        <legend>Kaalud {customized ? "(kohandatud)" : "(vaikimisi)"}</legend>
        <label>
          Hind vs kvaliteet: {balance}% kvaliteet
          <input
            aria-label="Hinna ja kvaliteedi tasakaal"
            type="range"
            min={0}
            max={100}
            step={5}
            value={balance}
            onChange={(e) => onBalance(Number(e.target.value))}
          />
        </label>
        {DIMS.map((d) => (
          <label key={d.key}>
            {d.label}: {multipliers[d.key] ?? 100}%
            <input
              aria-label={`${d.label} kaal`}
              type="range"
              min={0}
              max={200}
              step={10}
              value={multipliers[d.key] ?? 100}
              onChange={(e) => set(d.key, Number(e.target.value))}
            />
          </label>
        ))}
        <button type="button" onClick={onReset} disabled={!customized}>
          Lähtesta kaalud
        </button>
      </fieldset>
    </form>
  );
}

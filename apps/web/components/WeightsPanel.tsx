"use client";

import { useState } from "react";
import {
  BALANCE_HINT,
  DEFAULT_BALANCE,
  DIMS,
  UNCONFIGURABLE_DIMS,
  type Multipliers,
} from "../lib/weights";

/**
 * Buyer-adjustable scoring (#74): the price-vs-quality balance plus one
 * slider per livability dimension (0–200%, 100 = registry default).
 * Everything recomputes client-side and stays URL-shared (?bal=, ?w=).
 *
 * Each slider carries an info tooltip (ⓘ): hover reveals it on desktop,
 * tap toggles it on touch, and the native button keeps it
 * keyboard-accessible. The copy lives in lib/weights.ts next to the
 * registry weights so it stays honest with livability.py.
 */
function InfoTip({ id, label, text }: { id: string; label: string; text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className={`wtip${open ? " wtip-open" : ""}`}>
      <button
        type="button"
        className="wtip-btn"
        aria-label={`${label}: selgitus`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span aria-hidden="true">ⓘ</span>
      </button>
      <span id={id} role="note" className="wtip-text">
        {text}
      </span>
    </span>
  );
}

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
        <div className="weight-row">
          <label>
            Hind vs kvaliteet: {balance}% kvaliteet
            <input
              aria-label="Hinna ja kvaliteedi tasakaal"
              aria-describedby="w-hint-balance"
              type="range"
              min={0}
              max={100}
              step={5}
              value={balance}
              onChange={(e) => onBalance(Number(e.target.value))}
            />
          </label>
          <InfoTip id="w-hint-balance" label="Hind vs kvaliteet" text={BALANCE_HINT} />
        </div>
        {DIMS.map((d) => (
          <div className="weight-row" key={d.key}>
            <label>
              {d.label}: {multipliers[d.key] ?? 100}%
              <input
                aria-label={`${d.label} kaal`}
                aria-describedby={`w-hint-${d.key}`}
                type="range"
                min={0}
                max={200}
                step={10}
                value={multipliers[d.key] ?? 100}
                onChange={(e) => set(d.key, Number(e.target.value))}
              />
            </label>
            <InfoTip id={`w-hint-${d.key}`} label={d.label} text={d.hint} />
          </div>
        ))}
        <p className="weights-legend">
          0% jätab mõõdiku arvestusest välja, 100% on vaikeväärtus, 200%
          kahekordistab selle osakaalu. Kui kuulutusel mõõdiku andmed
          puuduvad, jäetakse mõõdik vahele ja ülejäänud kaalud arvestatakse
          ümber — liugur sellist kuulutust ei mõjuta.
        </p>
        <details className="weights-fixed">
          <summary>Mida kaaludega muuta ei saa</summary>
          <ul>
            {UNCONFIGURABLE_DIMS.map((d) => (
              <li key={d.key}>
                <strong>{d.label}:</strong> {d.why}
              </li>
            ))}
          </ul>
        </details>
        <button type="button" onClick={onReset} disabled={!customized}>
          Lähtesta kaalud
        </button>
      </fieldset>
    </form>
  );
}

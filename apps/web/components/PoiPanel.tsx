"use client";

import { useState } from "react";
import type { Poi } from "../lib/poi";

/**
 * Buyer points of interest (#74): workplace, school, … Added by clicking
 * the map while armed, listed with remove buttons, URL-shared (?poi=).
 * Travel times render per listing; generic school scoring is untouched.
 */
export function PoiPanel({
  pois,
  armed,
  sortByPoi,
  onRemove,
  onArm,
  onSortByPoi,
}: {
  pois: Poi[];
  armed: boolean;
  sortByPoi: boolean;
  onRemove: (index: number) => void;
  onArm: (armed: boolean, label: string) => void;
  onSortByPoi: (v: boolean) => void;
}) {
  const [label, setLabel] = useState("Töö");
  return (
    <form aria-label="Huvipunktid" onSubmit={(e) => e.preventDefault()}>
      <fieldset>
        <legend>Minu punktid (töö, kool, …)</legend>
        {pois.length === 0 ? (
          <p>Punkte pole — lisa kaardilt, et näha sõiduaegu.</p>
        ) : (
          <ul>
            {pois.map((p, i) => (
              <li key={`${p.lat},${p.lon},${p.label}`}>
                {p.label} ({p.lat.toFixed(4)}, {p.lon.toFixed(4)})
                <button type="button" aria-label={`Eemalda ${p.label}`} onClick={() => onRemove(i)}>
                  Eemalda
                </button>
              </li>
            ))}
          </ul>
        )}
        <label>
          Nimi
          <input
            aria-label="Punkti nimi"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
        </label>
        <button
          type="button"
          aria-pressed={armed}
          onClick={() => onArm(!armed, label.trim() || "Punkt")}
        >
          {armed ? "Tühista (kliki kaardil punkti lisamiseks)" : "Lisa kaardilt"}
        </button>
        {pois.length > 0 && (
          <label>
            <input
              type="checkbox"
              checked={sortByPoi}
              onChange={(e) => onSortByPoi(e.target.checked)}
            />{" "}
            Järjesta lähima punkti järgi
          </label>
        )}
      </fieldset>
    </form>
  );
}

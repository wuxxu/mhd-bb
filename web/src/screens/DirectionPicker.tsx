import { useEffect, useState } from "react";
import Header from "../components/Header";
import { loadLine } from "../lib/data";
import type { Line } from "../types";

interface Props {
  line: string;
  onBack: () => void;
  onPick: (directionIndex: number) => void;
}

export default function DirectionPicker({ line, onBack, onPick }: Props) {
  const [data, setData] = useState<Line | null>(null);

  useEffect(() => {
    loadLine(line).then(setData);
  }, [line]);

  return (
    <div className="flex-1 flex flex-col bb-surface">
      <Header
        title={`Linka ${line}`}
        subtitle={data?.name ?? "Načítavam…"}
        onBack={onBack}
      />
      <main className="flex-1 overflow-y-auto safe-bottom p-4 space-y-3">
        {!data ? (
          <div className="text-stone-500 py-8 text-center pulse-soft">Načítavam…</div>
        ) : (
          data.directions.map((dir, i) => {
            const origin = dir.stops[0]?.name ?? "";
            return (
              <button
                key={i}
                onClick={() => onPick(i)}
                className="w-full bg-white rounded-2xl shadow-tile p-5 text-left active:shadow-tile-active active:scale-[0.99] transition-all border border-stone-200/70 group"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] uppercase tracking-wider font-semibold text-bb-red-600">
                      Smer {i + 1}
                    </div>
                    <div className="font-semibold text-bb-charcoal text-lg leading-tight mt-1">
                      {dir.headsign}
                    </div>
                    <div className="text-sm text-stone-500 mt-2 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-bb-red-600" />
                      <span className="truncate">z {origin}</span>
                    </div>
                  </div>
                  <div className="text-bb-red-600 transition-transform group-active:translate-x-0.5">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M9 18l6-6-6-6"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                </div>
                <div className="mt-3 pt-3 border-t border-stone-100 text-xs text-stone-500 tabular-nums">
                  {dir.stops.length} zastávok
                </div>
              </button>
            );
          })
        )}
      </main>
    </div>
  );
}

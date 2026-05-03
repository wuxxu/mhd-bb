import { useEffect, useState } from "react";
import Header from "../components/Header";
import { loadLine } from "../lib/data";
import type { Line } from "../types";

interface Props {
  line: string;
  directionIndex: number;
  onBack: () => void;
  onPick: (stopName: string) => void;
}

export default function StopPicker({ line, directionIndex, onBack, onPick }: Props) {
  const [data, setData] = useState<Line | null>(null);

  useEffect(() => {
    loadLine(line).then(setData);
  }, [line]);

  const direction = data?.directions[directionIndex];

  return (
    <div className="flex-1 flex flex-col bb-surface">
      <Header
        title={`Linka ${line}`}
        subtitle={direction ? `→ ${direction.headsign}` : "Načítavam…"}
        onBack={onBack}
      />
      <main className="flex-1 overflow-y-auto safe-bottom px-3 py-3">
        {!direction ? (
          <div className="text-stone-500 py-8 text-center pulse-soft">Načítavam…</div>
        ) : (
          <ul className="bg-white rounded-2xl shadow-tile border border-stone-200/70 overflow-hidden">
            {direction.stops.map((stop, i) => {
              const isLast = i === direction.stops.length - 1;
              const isFirst = i === 0;
              return (
                <li key={stop.name + i}>
                  <button
                    onClick={() => onPick(stop.name)}
                    className="w-full flex items-center gap-3 px-4 py-3.5 text-left active:bg-stone-50 transition-colors"
                  >
                    {/* Vertical route line with bus stop dot */}
                    <div className="relative flex flex-col items-center self-stretch w-3">
                      <div
                        className={`absolute inset-x-1/2 -translate-x-1/2 w-px ${
                          isFirst ? "top-1/2" : "top-0"
                        } ${isLast ? "bottom-1/2" : "bottom-0"} bg-stone-300`}
                      />
                      <div
                        className={`relative z-[1] w-3 h-3 rounded-full mt-[18px] ${
                          isFirst || isLast
                            ? "bg-bb-red-600 ring-4 ring-bb-red-100"
                            : "bg-white border-2 border-bb-red-600"
                        }`}
                      />
                    </div>
                    <span className="flex-1 text-bb-charcoal font-medium leading-tight py-0.5">
                      {stop.name}
                    </span>
                    {isFirst && (
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-bb-red-600 bg-bb-red-50 px-2 py-0.5 rounded-full">
                        Štart
                      </span>
                    )}
                    {isLast && (
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-bb-red-600 bg-bb-red-50 px-2 py-0.5 rounded-full">
                        Cieľ
                      </span>
                    )}
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      className="text-stone-400"
                    >
                      <path
                        d="M9 18l6-6-6-6"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                  {!isLast && <div className="h-px bg-stone-100 ml-10" />}
                </li>
              );
            })}
          </ul>
        )}
      </main>
    </div>
  );
}

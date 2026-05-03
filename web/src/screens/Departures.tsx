import { useEffect, useMemo, useRef, useState } from "react";
import Header from "../components/Header";
import { loadLine } from "../lib/data";
import { detectService, findUpcoming, formatCountdown, timeToMinutes } from "../lib/service";
import type { Line, Service } from "../types";

interface Props {
  line: string;
  directionIndex: number;
  stopName: string;
  onBack: () => void;
}

const TAB_LABEL: Record<Service, string> = {
  weekday: "Pracovný deň",
  weekend: "Víkend / sviatok"
};

export default function Departures({ line, directionIndex, stopName, onBack }: Props) {
  const [data, setData] = useState<Line | null>(null);
  const [now, setNow] = useState(new Date());
  // Default tab from current day; user can override
  const [tab, setTab] = useState<Service>(() => detectService());
  const lastDayRef = useRef<number>(now.getDay());

  useEffect(() => {
    loadLine(line).then(setData);
  }, [line]);

  useEffect(() => {
    const id = window.setInterval(() => {
      const next = new Date();
      // If the day rolled over, snap the tab to the new default service
      if (next.getDay() !== lastDayRef.current) {
        lastDayRef.current = next.getDay();
        setTab(detectService(next));
      }
      setNow(next);
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  const direction = data?.directions[directionIndex];
  const stop = direction?.stops.find((s) => s.name === stopName);
  const times = useMemo(() => stop?.times[tab] ?? [], [stop, tab]);

  const upcoming = useMemo(() => findUpcoming(times, now), [times, now]);

  const nowMins = now.getHours() * 60 + now.getMinutes();
  const nextMinutes = upcoming.next ? timeToMinutes(upcoming.next) - nowMins : null;
  const isImminent = nextMinutes !== null && nextMinutes >= 0 && nextMinutes <= 2;

  return (
    <div className="flex-1 flex flex-col bb-surface">
      <Header
        title={stopName}
        subtitle={`Linka ${line} → ${direction?.headsign ?? ""}`}
        onBack={onBack}
      />

      {/* Service tabs */}
      <div className="bg-white border-b border-stone-200 flex sticky top-0 z-[5] shadow-sm">
        {(["weekday", "weekend"] as Service[]).map((s) => (
          <button
            key={s}
            onClick={() => setTab(s)}
            className={`flex-1 py-3 text-sm font-semibold relative transition-colors ${
              tab === s ? "text-bb-red-600" : "text-stone-500"
            }`}
          >
            {TAB_LABEL[s]}
            {tab === s && (
              <span className="absolute inset-x-4 bottom-0 h-0.5 bg-bb-red-600 rounded-t" />
            )}
          </button>
        ))}
      </div>

      {!data || !stop ? (
        <div className="p-8 text-stone-500 text-center pulse-soft">Načítavam…</div>
      ) : times.length === 0 ? (
        <div className="p-6 text-stone-500 text-center">
          Pre tento deň nie sú k dispozícii žiadne odchody.
        </div>
      ) : (
        <main className="flex-1 overflow-y-auto safe-bottom">
          {/* Hero: next departure */}
          {upcoming.next ? (
            <section
              className={`text-white px-5 pt-5 pb-6 ${
                isImminent ? "bg-bb-red-700" : "bb-stripe"
              } relative overflow-hidden`}
            >
              <div className="absolute -right-12 -top-12 w-44 h-44 rounded-full bg-white/5" />
              <div className="absolute -right-4 top-12 w-24 h-24 rounded-full bg-white/5" />
              <div className="relative">
                <div className="text-[11px] uppercase tracking-wider text-white/75 font-semibold">
                  Najbližší odchod
                </div>
                <div className="flex items-baseline gap-3 mt-1">
                  <div className="text-5xl font-bold tabular-nums leading-none">
                    {upcoming.next}
                  </div>
                  <div
                    className={`text-2xl font-medium ${
                      isImminent ? "text-bb-gold-400 pulse-soft" : "text-white/85"
                    }`}
                  >
                    {nextMinutes !== null && formatCountdown(nextMinutes)}
                  </div>
                </div>
                <div className="text-xs text-white/70 mt-2 tabular-nums">
                  aktuálny čas{" "}
                  {now.toLocaleTimeString("sk-SK", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit"
                  })}
                </div>
              </div>
            </section>
          ) : (
            <section className="bg-stone-200/60 px-5 py-5 text-stone-700">
              <div className="text-[11px] uppercase tracking-wider font-semibold text-stone-500">
                Dnes už nejde žiadny spoj
              </div>
              <div className="text-base mt-1">Skontroluj zajtrajšie odchody alebo prepni záložku víkend.</div>
            </section>
          )}

          {/* Upcoming list — expanded by default */}
          {upcoming.rest.length > 0 && (
            <section className="px-3 pt-4">
              <h3 className="px-2 mb-2 text-[11px] font-semibold uppercase tracking-wider text-stone-500">
                Ďalšie odchody · {upcoming.rest.length}
              </h3>
              <ul className="bg-white rounded-2xl shadow-tile border border-stone-200/70 divide-y divide-stone-100 overflow-hidden">
                {upcoming.rest.map((t, i) => {
                  const minsAway = timeToMinutes(t) - nowMins;
                  return (
                    <li
                      key={t + i}
                      className="flex items-center justify-between px-4 py-3"
                    >
                      <span className="text-bb-charcoal font-semibold tabular-nums text-lg">
                        {t}
                      </span>
                      <span className="text-sm text-stone-500 tabular-nums">
                        {formatCountdown(minsAway)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {/* Past departures — collapsed */}
          {upcoming.pastCount > 0 && (
            <section className="px-3 pt-4 pb-6">
              <details className="bg-white rounded-2xl shadow-tile border border-stone-200/70 overflow-hidden group">
                <summary className="flex items-center justify-between px-4 py-3 text-sm text-stone-600 cursor-pointer list-none active:bg-stone-50">
                  <span>
                    Dnešné minulé odchody ·{" "}
                    <span className="tabular-nums">{upcoming.pastCount}</span>
                  </span>
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    className="text-stone-400 transition-transform group-open:rotate-180"
                  >
                    <path
                      d="M6 9l6 6 6-6"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </summary>
                <ul className="grid grid-cols-4 gap-2 px-3 pb-3 pt-1">
                  {times.slice(0, upcoming.pastCount).map((t, i) => (
                    <li
                      key={t + i}
                      className="bg-stone-50 rounded-md py-2 text-center text-stone-400 tabular-nums text-sm"
                    >
                      {t}
                    </li>
                  ))}
                </ul>
              </details>
            </section>
          )}

          {/* If no next bus, list everything for the day */}
          {!upcoming.next && (
            <section className="px-3 pt-4 pb-6">
              <h3 className="px-2 mb-2 text-[11px] font-semibold uppercase tracking-wider text-stone-500">
                Dnešné odchody
              </h3>
              <ul className="grid grid-cols-4 gap-2">
                {times.map((t, i) => (
                  <li
                    key={t + i}
                    className="bg-white rounded-md py-2 text-center text-stone-700 tabular-nums shadow-tile border border-stone-200/70"
                  >
                    {t}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </main>
      )}
    </div>
  );
}

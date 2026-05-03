import { useEffect, useState, type MouseEvent } from "react";
import Header from "../components/Header";
import { loadLineIndex } from "../lib/data";
import { getFavourites, toggleFavourite } from "../lib/storage";
import type { LineIndexEntry } from "../types";

interface Props {
  onPickLine: (line: string) => void;
}

function StarIcon({ filled }: { filled: boolean }) {
  if (filled) {
    return (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="#d4a017" aria-hidden="true">
        <path d="M12 2.6l2.95 6.74 7.34.62-5.58 4.84 1.7 7.18L12 18.3 5.59 22l1.7-7.18-5.58-4.84 7.34-.62z" />
      </svg>
    );
  }
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#a8a29e"
      strokeWidth="1.8"
      aria-hidden="true"
    >
      <path
        d="M12 2.6l2.95 6.74 7.34.62-5.58 4.84 1.7 7.18L12 18.3 5.59 22l1.7-7.18-5.58-4.84 7.34-.62z"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface RowProps {
  entry: LineIndexEntry;
  isFav: boolean;
  onPick: () => void;
  onToggleFav: () => void;
}

function LineRow({ entry, isFav, onPick, onToggleFav }: RowProps) {
  const handleStarClick = (e: MouseEvent) => {
    e.stopPropagation();
    onToggleFav();
  };
  return (
    <li>
      <div className="flex items-stretch active:bg-stone-50">
        <button
          onClick={onPick}
          className="flex-1 flex items-center gap-3 pl-4 pr-2 py-3 text-left"
          aria-label={`Linka ${entry.line}`}
        >
          <span className="text-bb-charcoal font-bold text-2xl tabular-nums tracking-tight w-14">
            {entry.line}
          </span>
          <span className="flex-1" />
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            className="text-stone-300"
            aria-hidden="true"
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
        <button
          onClick={handleStarClick}
          aria-label={isFav ? "Odstrániť z obľúbených" : "Pridať do obľúbených"}
          className="px-4 active:bg-stone-100"
        >
          <StarIcon filled={isFav} />
        </button>
      </div>
    </li>
  );
}

export default function LineList({ onPickLine }: Props) {
  const [lines, setLines] = useState<LineIndexEntry[] | null>(null);
  const [favs, setFavs] = useState<Set<string>>(() => getFavourites());

  useEffect(() => {
    loadLineIndex().then(setLines);
  }, []);

  return (
    <div className="flex-1 flex flex-col bb-surface">
      <Header
        title="MHD Banská Bystrica"
        subtitle="Vyber linku a zastávku"
        withBadge
      />
      <main className="flex-1 overflow-y-auto safe-bottom px-3 pt-3 pb-8">
        {!lines ? (
          <div className="text-stone-500 py-8 text-center pulse-soft">
            Načítavam linky…
          </div>
        ) : (
          (() => {
            const sorted = [...lines].sort(
              (a, b) => Number(a.line) - Number(b.line)
            );
            const favLines = sorted.filter((l) => favs.has(l.line));
            const otherLines = sorted.filter((l) => !favs.has(l.line));

            const renderList = (items: LineIndexEntry[]) => (
              <ul className="bg-white rounded-2xl shadow-tile border border-stone-200/70 divide-y divide-stone-100 overflow-hidden">
                {items.map((l) => (
                  <LineRow
                    key={l.line}
                    entry={l}
                    isFav={favs.has(l.line)}
                    onPick={() => onPickLine(l.line)}
                    onToggleFav={() => setFavs(toggleFavourite(l.line))}
                  />
                ))}
              </ul>
            );

            return (
              <>
                {favLines.length > 0 && (
                  <section className="mb-5">
                    <h2 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-bb-gold-500 mb-2 px-2">
                      <StarIcon filled />
                      Obľúbené
                    </h2>
                    {renderList(favLines)}
                  </section>
                )}
                <section>
                  {favLines.length > 0 && (
                    <h2 className="text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-2 px-2">
                      Všetky linky
                    </h2>
                  )}
                  {renderList(otherLines)}
                </section>
              </>
            );
          })()
        )}
      </main>
    </div>
  );
}

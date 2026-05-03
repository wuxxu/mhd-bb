import type { Line, LineIndexEntry } from "../types";

const indexCache = new Map<string, Promise<unknown>>();

function fetchJson<T>(url: string): Promise<T> {
  if (!indexCache.has(url)) {
    indexCache.set(url, fetch(url).then((r) => r.json()));
  }
  return indexCache.get(url) as Promise<T>;
}

export const loadLineIndex = () =>
  fetchJson<LineIndexEntry[]>(`${import.meta.env.BASE_URL}data/lines.json`);

export const loadLine = (lineNo: string) =>
  fetchJson<Line>(`${import.meta.env.BASE_URL}data/lines/${lineNo}.json`);

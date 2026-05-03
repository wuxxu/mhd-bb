const FAV_KEY = "mhdbb.favourites.v1";

export function getFavourites(): Set<string> {
  try {
    const raw = localStorage.getItem(FAV_KEY);
    if (!raw) return new Set();
    return new Set(JSON.parse(raw) as string[]);
  } catch {
    return new Set();
  }
}

export function toggleFavourite(line: string): Set<string> {
  const favs = getFavourites();
  if (favs.has(line)) favs.delete(line);
  else favs.add(line);
  localStorage.setItem(FAV_KEY, JSON.stringify([...favs]));
  return favs;
}

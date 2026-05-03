import type { Service } from "../types";

/** Detect default service tab based on day of week. Holidays are NOT detected. */
export function detectService(date = new Date()): Service {
  const day = date.getDay(); // 0 = Sunday, 6 = Saturday
  return day === 0 || day === 6 ? "weekend" : "weekday";
}

/** Convert a HH:MM string into minutes-since-midnight. */
export function timeToMinutes(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return h * 60 + m;
}

/** Find the next departure (and the one after) given current time + sorted times. */
export function findUpcoming(times: string[], now: Date): {
  next?: string;
  rest: string[];
  pastCount: number;
} {
  const nowMins = now.getHours() * 60 + now.getMinutes();
  // Determine the index of the first time >= now
  let idx = times.length;
  for (let i = 0; i < times.length; i++) {
    if (timeToMinutes(times[i]) >= nowMins) {
      idx = i;
      break;
    }
  }
  return {
    next: times[idx],
    rest: times.slice(idx + 1),
    pastCount: idx
  };
}

/** Format a duration in minutes as a localised "za X min" / "za 1 h 12 min" string. */
export function formatCountdown(minutes: number): string {
  if (minutes < 0) return "odišiel";
  if (minutes === 0) return "teraz";
  if (minutes < 60) return `o ${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (m === 0) return `o ${h} h`;
  return `o ${h} h ${m} min`;
}

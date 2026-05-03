export type Service = "weekday" | "weekend";

export interface DirectionSummary {
  headsign: string;
  stopCount: number;
}

export interface LineIndexEntry {
  line: string;
  name: string;
  fullName: string;
  operator: "DPMBB" | "SADZV";
  validFrom: string;
  directions: DirectionSummary[];
}

export interface Stop {
  name: string;
  times: Record<Service, string[]>;
}

export interface Direction {
  headsign: string;
  stops: Stop[];
}

export interface Line {
  line: string;
  name: string;
  operator: "DPMBB" | "SADZV";
  validFrom: string;
  directions: Direction[];
}

import { useState } from "react";
import LineList from "./screens/LineList";
import DirectionPicker from "./screens/DirectionPicker";
import StopPicker from "./screens/StopPicker";
import Departures from "./screens/Departures";

type View =
  | { kind: "lines" }
  | { kind: "directions"; line: string }
  | { kind: "stops"; line: string; directionIndex: number }
  | { kind: "departures"; line: string; directionIndex: number; stopName: string };

export default function App() {
  const [view, setView] = useState<View>({ kind: "lines" });

  return (
    <div className="min-h-full flex flex-col">
      {view.kind === "lines" && (
        <LineList onPickLine={(line) => setView({ kind: "directions", line })} />
      )}
      {view.kind === "directions" && (
        <DirectionPicker
          line={view.line}
          onBack={() => setView({ kind: "lines" })}
          onPick={(directionIndex) =>
            setView({ kind: "stops", line: view.line, directionIndex })
          }
        />
      )}
      {view.kind === "stops" && (
        <StopPicker
          line={view.line}
          directionIndex={view.directionIndex}
          onBack={() => setView({ kind: "directions", line: view.line })}
          onPick={(stopName) =>
            setView({
              kind: "departures",
              line: view.line,
              directionIndex: view.directionIndex,
              stopName
            })
          }
        />
      )}
      {view.kind === "departures" && (
        <Departures
          line={view.line}
          directionIndex={view.directionIndex}
          stopName={view.stopName}
          onBack={() =>
            setView({
              kind: "stops",
              line: view.line,
              directionIndex: view.directionIndex
            })
          }
        />
      )}
    </div>
  );
}

import type { ReactNode } from "react";

interface Props {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  right?: ReactNode;
  /** Render the small heraldic mark next to the title. */
  withBadge?: boolean;
}

/** Header badge that matches the PWA icon: cream square with a red "MHD" wordmark. */
function HeraldicMark({ size = 32 }: { size?: number }) {
  return (
    <div
      style={{ width: size, height: size }}
      className="rounded-md bg-white/95 flex items-center justify-center shadow-sm"
      aria-hidden="true"
    >
      <span className="text-bb-red-700 font-extrabold tracking-tight text-[11px] leading-none">
        MHD
      </span>
    </div>
  );
}

export default function Header({ title, subtitle, onBack, right, withBadge }: Props) {
  return (
    <header className="bb-stripe text-white shadow-md relative">
      <div className="safe-top">
        <div className="flex items-center gap-2 px-3 py-3">
          {onBack ? (
            <button
              onClick={onBack}
              aria-label="Späť"
              className="-ml-1 p-2 rounded-full active:bg-white/15"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <path
                  d="M15 18l-6-6 6-6"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          ) : withBadge ? (
            <div className="-ml-0.5 mr-1">
              <HeraldicMark size={32} />
            </div>
          ) : null}
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-semibold leading-tight truncate">{title}</h1>
            {subtitle && (
              <p className="text-xs text-white/75 truncate mt-0.5">{subtitle}</p>
            )}
          </div>
          {right && <div className="ml-auto">{right}</div>}
        </div>
      </div>
      {/* Hairline shadow at bottom for depth */}
      <div className="absolute inset-x-0 bottom-0 h-px bg-bb-red-800/40" />
    </header>
  );
}

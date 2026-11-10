import type { CSSProperties } from "react";

export function Icon({
  name,
  size = 20,
  ...props
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  const paths: Record<string, React.ReactNode> = {
    arena: (
      <>
        <rect x="3" y="6" width="18" height="13" rx="4" />
        <path d="M7 12h4m-2-2v4m6-2h.01m3 3h.01M8 6l1-3m7 3-1-3" />
      </>
    ),
    trophy: (
      <>
        <path d="M8 3h8v7a4 4 0 0 1-8 0V3Zm0 2H4v3a4 4 0 0 0 4 4m8-7h4v3a4 4 0 0 1-4 4m-4 2v6m-4 1h8" />
      </>
    ),
    robot: (
      <>
        <rect x="4" y="7" width="16" height="12" rx="4" />
        <path d="M12 3v4M1 11v4m22-4v4M8 12h.01M16 12h.01M9 16h6" />
      </>
    ),
    arrow: (
      <>
        <path d="M4 12h15m-6-6 6 6-6 6" />
      </>
    ),
    diagonal: (
      <>
        <path d="M6 18 18 6M6 6h12v12" />
      </>
    ),
    camera: (
      <>
        <rect x="3" y="6" width="13" height="12" rx="3" />
        <path d="m16 10 5-3v10l-5-3" />
      </>
    ),
    cameraOff: (
      <>
        <path d="m3 3 18 18M9 6h4a3 3 0 0 1 3 3v1l5-3v10l-5-3M5 6a3 3 0 0 0-2 3v6a3 3 0 0 0 3 3h7a3 3 0 0 0 3-2" />
      </>
    ),
    chevron: <path d="m8 10 4 4 4-4" />,
    sound: (
      <>
        <path d="m11 4-6 5H2v6h3l6 5V4Zm4 4a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14" />
      </>
    ),
    mute: (
      <>
        <path d="m11 4-6 5H2v6h3l6 5V4Zm5 5 6 6m0-6-6 6" />
      </>
    ),
    help: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M9.5 9a2.5 2.5 0 0 1 5 .5c0 2-2.5 2-2.5 4m0 3h.01" />
      </>
    ),
    close: <path d="m6 6 12 12M6 18 18 6" />,
    bolt: <path d="m13 2-9 12h7l-1 8 10-12h-8l1-8Z" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    flame: (
      <path d="M13 2c1 5-3 6-3 9-2-1-3-3-3-3-5 6-2 13 5 13 8 0 10-10 1-19Zm-1 12c4 4 1 7-1 6s-3-3 1-6Z" />
    ),
    check: <path d="m5 12 4 4L19 6" />,
    reset: (
      <>
        <path d="M3 10a9 9 0 1 1 1 8M3 4v6h6" />
      </>
    ),
    sun: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 3v2m0 14v2M4.2 4.2l1.4 1.4m12.8 12.8 1.4 1.4M3 12h2m14 0h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
      </>
    ),
    moon: <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {paths[name] || paths.arena}
    </svg>
  );
}

export type Move = "Rock" | "Paper" | "Scissors";
export function Hand({ move, size = 36 }: { move: Move; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {move === "Rock" ? (
        <>
          <path d="M15 35V24a5 5 0 0 1 10 0v-5a5 5 0 0 1 10 0v2a5 5 0 0 1 10 0v4a5 5 0 0 1 10 0v14c0 8-5 12-8 16H25c-3-5-12-10-13-16-1-5 4-8 8-5l10 7" />
          <path d="M25 24v10m10-13v12m10-8v9M25 55v5m22-5v5" />
        </>
      ) : move === "Paper" ? (
        <>
          <path d="M20 34V15a4 4 0 0 1 8 0v17-22a4 4 0 0 1 8 0v21-18a4 4 0 0 1 8 0v20-12a4 4 0 0 1 8 0v21c0 8-5 13-8 17H25c-3-6-10-10-13-17l-4-8c-2-5 4-8 7-4l7 9" />
          <path d="M25 59h19" />
        </>
      ) : (
        <>
          <path d="m23 35-7-22a4.5 4.5 0 0 1 8-3l9 22 6-24a4.5 4.5 0 0 1 9 2l-6 25c8-2 13 1 13 7 0 7-7 13-10 17H26c-3-6-12-10-14-16-2-5 2-9 6-6l10 7" />
          <path d="m35 38 10 3m-12 6 11 1M26 59h19" />
        </>
      )}
    </svg>
  );
}

export function Robot({
  mood = "idle",
  color = "#d7f75b",
  accessory = "antenna",
}: {
  mood?: string;
  color?: string;
  accessory?: string;
}) {
  return (
    <div className={`robot-art mood-${mood}`} style={{ "--robot-color": color } as CSSProperties}>
      <svg
        viewBox="0 0 340 300"
        fill="none"
        aria-label={`Rookie robot, ${mood} expression`}
        role="img"
      >
        <ellipse cx="170" cy="273" rx="87" ry="10" fill="#000" opacity=".22" />
        <g className="robot-body">
          {accessory === "antenna" && (
            <>
              <path d="M170 72V45" stroke="#888c7f" strokeWidth="5" />
              <circle cx="170" cy="40" r="8" fill="var(--robot-color)" />
              <circle cx="168" cy="37" r="2" fill="white" opacity=".8" />
            </>
          )}
          {accessory === "ears" && (
            <>
              <path
                d="m103 83-10-35 38 25m78 0 38-25-10 35"
                fill="var(--robot-color)"
                stroke="#92977c"
                strokeWidth="3"
              />
            </>
          )}
          <rect x="72" y="114" width="17" height="43" rx="7" fill="#64685e" />
          <rect x="251" y="114" width="17" height="43" rx="7" fill="#64685e" />
          <rect x="86" y="73" width="168" height="118" rx="38" fill="#d9ddd0" />
          <rect x="92" y="77" width="156" height="106" rx="33" fill="#eaecdf" />
          <path d="M118 84h102" stroke="white" strokeWidth="3" opacity=".8" strokeLinecap="round" />
          <rect x="102" y="91" width="136" height="81" rx="24" fill="#20251f" />
          <rect x="107" y="96" width="126" height="71" rx="21" fill="#151b16" />
          <g
            className="robot-eyes"
            stroke="var(--robot-color)"
            strokeWidth="9"
            strokeLinecap="round"
          >
            {mood === "happy" ? (
              <>
                <path d="M127 127q9-15 18 0m50 0q9-15 18 0" />
              </>
            ) : mood === "sad" ? (
              <>
                <path d="m128 119 17 8m50 0 17-8" />
              </>
            ) : mood === "thinking" ? (
              <>
                <path d="M128 124h17m50-6v12" />
              </>
            ) : (
              <>
                <path d="M136 117v15m68-15v15" />
              </>
            )}
          </g>
          <path
            d={mood === "sad" ? "M160 151q10-10 20 0" : "M160 147q10 9 20 0"}
            stroke="var(--robot-color)"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <path d="M150 192h40v13h-40z" fill="#72776a" />
          <rect x="118" y="201" width="104" height="56" rx="21" fill="#c6cbbd" />
          <rect x="124" y="201" width="92" height="49" rx="17" fill="#e1e4d5" />
          <rect x="147" y="214" width="46" height="24" rx="7" fill="#242b22" />
          <path
            d="m160 226 6 5 11-11"
            stroke="var(--robot-color)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <rect
            x="98"
            y="209"
            width="13"
            height="28"
            rx="6"
            fill="#909786"
            transform="rotate(15 98 209)"
          />
          <rect
            x="229"
            y="209"
            width="13"
            height="28"
            rx="6"
            fill="#909786"
            transform="rotate(-15 229 209)"
          />
          <path d="M138 257v8m63-8v8" stroke="#8d9580" strokeWidth="14" strokeLinecap="round" />
        </g>
      </svg>
    </div>
  );
}

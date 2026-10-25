const WIDTH = 1000;
const HEIGHT = 220;
const PAD = { l: 48, r: 8, t: 12, b: 32 };

export default function Columns({ bars, signed = false, tone, onPick, labelEvery = 1, unit = "" }) {
  if (!bars.length) return null;
  const values = bars.map((bar) => bar.value);
  const min = signed ? Math.min(0, ...values) : 0;
  const max = Math.max(signed ? 0 : 1, ...values);
  const span = max - min || 1;
  const innerW = WIDTH - PAD.l - PAD.r;
  const innerH = HEIGHT - PAD.t - PAD.b;
  const yAt = (value) => PAD.t + (1 - (value - min) / span) * innerH;
  const zero = yAt(0);
  const slot = innerW / bars.length;
  const barW = Math.max(2, slot * 0.68);

  return (
    <div className="plot-frame columns-frame">
      <svg className="plot" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={unit || "Chart"}>
        <line className="grid" x1={PAD.l} x2={WIDTH - PAD.r} y1={zero} y2={zero} />
        {unit && (
          <text className="axis" x={PAD.l - 8} y={PAD.t + 8} textAnchor="end">{unit}</text>
        )}
        {bars.map((bar, index) => {
          const x = PAD.l + index * slot + (slot - barW) / 2;
          const top = yAt(Math.max(bar.value, 0));
          const bottom = yAt(Math.min(bar.value, 0));
          const height = Math.max(1, bottom - top);
          const kind = tone ? tone(bar) : "ink";
          const label = index % labelEvery === 0 || index === bars.length - 1;
          const activate = onPick ? (event) => {
            if (event.type === "keydown" && event.key !== "Enter" && event.key !== " ") return;
            if (event.type === "keydown") event.preventDefault();
            onPick(bar);
          } : undefined;
          return (
            <g key={bar.key}>
              {onPick && (
                <rect
                  className="hit"
                  x={PAD.l + index * slot}
                  y={PAD.t}
                  width={slot}
                  height={innerH}
                  tabIndex={0}
                  role="link"
                  aria-label={bar.hint}
                  onClick={activate}
                  onKeyDown={activate}
                />
              )}
              <rect className={`col ${kind}`} x={x} y={top} width={barW} height={height}>
                <title>{bar.hint}</title>
              </rect>
              {label && (
                <text className="axis" x={x + barW / 2} y={HEIGHT - 10} textAnchor="middle">
                  {bar.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

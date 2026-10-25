import { mw } from "../format";

const WIDTH = 1000;
const HEIGHT = 460;
const PAD = { l: 78, r: 18, t: 16, b: 36 };

function tickStep(max) {
  if (max <= 8000) return 2000;
  if (max <= 20000) return 4000;
  if (max <= 40000) return 10000;
  return 20000;
}

function linePath(periods, key, xAt, yAt) {
  let path = "";
  let drawing = false;
  periods.forEach((period, index) => {
    const value = period[key];
    if (value == null) {
      drawing = false;
      return;
    }
    path += `${drawing ? "L" : "M"}${xAt(index).toFixed(1)},${yAt(value).toFixed(1)}`;
    drawing = true;
  });
  return path;
}

function bands(periods, xAt, yAt) {
  const shapes = [];
  for (let index = 0; index < periods.length - 1; index += 1) {
    const left = periods[index];
    const right = periods[index + 1];
    if ([left.forecast_mw, left.actual_mw, right.forecast_mw, right.actual_mw].some((value) => value == null)) {
      continue;
    }
    const x0 = xAt(index);
    const x1 = xAt(index + 1);
    const forecast0 = yAt(left.forecast_mw);
    const forecast1 = yAt(right.forecast_mw);
    const actual0 = yAt(left.actual_mw);
    const actual1 = yAt(right.actual_mw);
    const gap0 = left.forecast_mw - left.actual_mw;
    const gap1 = right.forecast_mw - right.actual_mw;
    const kind = (gap) => (gap >= 0 ? "short" : "long");
    if (gap0 === 0 || gap1 === 0 || gap0 * gap1 > 0) {
      shapes.push({
        kind: kind(gap0 || gap1),
        points: `${x0},${forecast0} ${x1},${forecast1} ${x1},${actual1} ${x0},${actual0}`,
      });
    } else {
      const mix = gap0 / (gap0 - gap1);
      const crossX = x0 + (x1 - x0) * mix;
      const crossY = forecast0 + (forecast1 - forecast0) * mix;
      shapes.push({
        kind: kind(gap0),
        points: `${x0},${forecast0} ${crossX},${crossY} ${x0},${actual0}`,
      });
      shapes.push({
        kind: kind(gap1),
        points: `${crossX},${crossY} ${x1},${forecast1} ${x1},${actual1}`,
      });
    }
  }
  return shapes;
}

export default function Chart({ periods, activeSp, onHover, showHaircut }) {
  const innerW = WIDTH - PAD.l - PAD.r;
  const innerH = HEIGHT - PAD.t - PAD.b;
  const values = periods.flatMap((period) => [period.forecast_mw, period.actual_mw, showHaircut ? period.adjusted_mw : null]);
  const finite = values.filter((value) => value != null);
  const max = Math.max(1, ...finite);
  const step = tickStep(max);
  const ceiling = Math.max(step, Math.ceil((max * 1.06) / step) * step);
  const xAt = (index) => PAD.l + ((index + 0.5) / periods.length) * innerW;
  const yAt = (value) => PAD.t + (1 - value / ceiling) * innerH;
  const ticks = [];
  for (let tick = 0; tick <= ceiling; tick += step) ticks.push(tick);
  const activeIndex = periods.findIndex((period) => period.sp === activeSp);
  const forecast = linePath(periods, "forecast_mw", xAt, yAt);
  const actual = linePath(periods, "actual_mw", xAt, yAt);
  const adjusted = showHaircut ? linePath(periods, "adjusted_mw", xAt, yAt) : "";

  return (
    <div className="plot-frame">
      <svg
        className="plot"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Wind forecast and outturn across the 48 settlement periods"
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="grid" x1={PAD.l} x2={WIDTH - PAD.r} y1={yAt(tick)} y2={yAt(tick)} />
            <text className="axis" x={PAD.l - 10} y={yAt(tick) + 4} textAnchor="end">
              {tick === ceiling ? `${tick.toLocaleString("en-GB")}` : tick === 0 ? "0" : tick.toLocaleString("en-GB")}
            </text>
          </g>
        ))}
        {bands(periods, xAt, yAt).map((shape, index) => (
          <polygon key={`${shape.kind}-${index}`} className={`band ${shape.kind}`} points={shape.points} />
        ))}
        <g className="chart-lines">
          <path className="trace forecast" d={forecast} />
          <path className="trace outturn" d={actual} />
          {adjusted && <path className="trace haircut" d={adjusted} />}
        </g>
        {[0, 6, 12, 18, 24].map((hour) => {
          const at = PAD.l + (hour / 24) * innerW;
          return (
            <text key={hour} className="axis" x={at} y={HEIGHT - 12} textAnchor={hour === 24 ? "end" : "start"}>
              {String(hour).padStart(2, "0")}
            </text>
          );
        })}
        {periods.map((period, index) => (
          <rect
            key={period.sp}
            className="hit"
            x={PAD.l + (index / periods.length) * innerW}
            y={PAD.t}
            width={innerW / periods.length}
            height={innerH}
            onMouseEnter={() => onHover(period.sp)}
            onMouseLeave={() => onHover(null)}
          >
            <title>
              {`SP ${period.sp} ${period.start_label}. Forecast ${mw(period.forecast_mw)}, outturn ${mw(period.actual_mw)}.`}
            </title>
          </rect>
        ))}
        {activeIndex >= 0 && (
          <g>
            <line
              className="cursor"
              x1={xAt(activeIndex)}
              x2={xAt(activeIndex)}
              y1={PAD.t}
              y2={HEIGHT - PAD.b}
            />
            {periods[activeIndex].forecast_mw != null && (
              <circle className="node forecast" cx={xAt(activeIndex)} cy={yAt(periods[activeIndex].forecast_mw)} r="4" />
            )}
            {periods[activeIndex].actual_mw != null && (
              <circle className="node outturn" cx={xAt(activeIndex)} cy={yAt(periods[activeIndex].actual_mw)} r="4" />
            )}
          </g>
        )}
      </svg>
    </div>
  );
}

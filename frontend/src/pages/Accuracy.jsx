import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Columns from "../components/Columns";
import { useControls } from "../components/Shell";
import { compact, gwh, mw, num, pct, plainMw, signedMw } from "../format";

export default function Accuracy() {
  const { auction, lead, params } = useControls();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [adjusted, setAdjusted] = useState(false);

  useEffect(() => {
    document.title = "January at the gate · Daymark";
    const query = new URLSearchParams({ auction, lead_minutes: String(lead) });
    const controller = new AbortController();
    setError(null);
    fetch(`/api/accuracy?${query}`, { signal: controller.signal })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || "The month could not be scored.");
        return body;
      })
      .then(setReport)
      .catch((reason) => {
        if (reason.name !== "AbortError") setError(reason.message);
      });
    return () => controller.abort();
  }, [auction, lead]);

  function openDay(decision) {
    const next = new URLSearchParams(params);
    next.set("date", decision);
    next.delete("issue");
    navigate({ pathname: "/", search: next.toString() });
  }

  if (error) return <p className="problem">{error}</p>;
  if (!report) return <p className="waiting">Scoring January.</p>;

  const summary = report.summary;
  const high = summary.bias_mw >= 0;
  const histogram = (adjusted ? report.histogram_adjusted : report.histogram).map((bin) => ({
    key: `${bin.lo}`,
    label: compact(bin.lo),
    value: bin.count,
    lo: bin.lo,
    hi: bin.hi,
    hint: `${compact(bin.lo)} to ${compact(bin.hi)} MW, ${bin.count} hours`,
  }));
  const usable = report.by_issue.filter((row) => row.usable);
  const late = report.by_issue.filter((row) => !row.usable);
  const first = usable[0];
  const used = report.by_issue.find((row) => row.slot === summary.usual_slot);
  const lastLate = late[late.length - 1];
  const gap = first && used ? Math.abs(first.mae_mw - used.mae_mw) : null;
  const calm = report.quintiles[0];
  const windy = report.quintiles[report.quintiles.length - 1];

  return (
    <article>
      <h1>January at the gate</h1>
      <p className="lede">
        Across {summary.days} delivery days, the {summary.usual_slot} issue you could bid was{" "}
        {high ? "high" : "low"} by <span className="num">{mw(Math.abs(summary.bias_mw))}</span> on average.
        It sat above outturn on {summary.hours_high} of {summary.hours} hours, and the day’s energy was short
        on {summary.days_high} of {summary.days} days. The issues counted on{" "}
        <span className="num">{gwh(summary.total_forecast_mwh)}</span> and outturn was{" "}
        <span className="num">{gwh(summary.total_actual_mwh)}</span>, a gap of{" "}
        <span className="num">{gwh(summary.total_error_mwh)}</span>.
      </p>
      <p className="lede">
        The shape still followed the day. Correlation was <span className="num">{num(summary.correlation, 2)}</span>.
        Yesterday’s outturn, used as a forecast, missed by <span className="num">{mw(summary.persistence_mae_mw)}</span> in
        a typical hour, against <span className="num">{mw(summary.mae_mw)}</span> for the issue you could bid.
      </p>

      <section className="block">
        <h2>Where the miss sits</h2>
        <div className="choices" role="group" aria-label="Error shown">
          <button type="button" className="choice" aria-pressed={!adjusted} onClick={() => setAdjusted(false)}>
            As published
          </button>
          <button type="button" className="choice" aria-pressed={adjusted} onClick={() => setAdjusted(true)}>
            After the haircut
          </button>
        </div>
        <p className="quiet">
          {adjusted
            ? "Each day is adjusted by a haircut fit on the other days, then the hours are pooled. Orange is still a high forecast."
            : "Hours of forecast minus outturn. The mass to the right of zero is wind you counted on and did not get."}
        </p>
        <Columns
          bars={histogram}
          unit="hours"
          labelEvery={2}
          tone={(bar) => ((bar.lo + bar.hi) / 2 >= 0 ? "short" : "long")}
        />
        {calm && windy && (
          <p>
            In the fifth of hours with the lowest forecast, the average miss was {mw(calm.bias_mw)}.
            In the fifth with the highest forecast, it was {mw(windy.bias_mw)}.
            A share of the forecast tracks that. Taking off a flat number of megawatts, the same leave-one-day test,
            leaves a typical miss of {mw(summary.constant_loo_mae_mw)}. The share leaves {mw(summary.loo_mae_mw)}.
            The full-month share is {pct(summary.k)}.
          </p>
        )}
      </section>

      <section className="block">
        <h2>Through the delivery day</h2>
        <p className="quiet">Average miss by hour, GMT. Positive means the issue was high.</p>
        <Columns
          bars={report.by_hour.map((hour) => ({
            key: hour.label,
            label: hour.label,
            value: hour.bias_mw,
            hint: `${hour.label}:00, average miss ${mw(hour.bias_mw)}, typical size ${mw(hour.mae_mw)}`,
          }))}
          signed
          unit="MW"
          labelEvery={6}
          tone={(bar) => (bar.value >= 0 ? "short" : "long")}
        />
      </section>

      <section className="block">
        <h2>The issues that morning</h2>
        {first && used && gap != null && Math.abs(summary.bias_mw) > gap * 5 && (
          <p>
            Moving from the {first.slot} issue to the {used.slot} issue changes the typical miss from {mw(first.mae_mw)} to {mw(used.mae_mw)}.
            {lastLate && ` The ${lastLate.slot} issue, which is after this gate, would have scored ${mw(lastLate.mae_mw)}.`}
            {" "}The gap between issues is small beside the level miss of {mw(Math.abs(summary.bias_mw))}.
          </p>
        )}
        <div className="scroll">
          <table className="data">
            <caption>Every issue published on the decision day, scored against the same delivery hours. Days used is how often it was the last one before the bid had to be in.</caption>
            <thead>
              <tr>
                <th className="left">Issue</th>
                <th className="left">At this gate</th>
                <th>Days seen</th>
                <th>Days used</th>
                <th>Bias</th>
                <th>MAE</th>
                <th>RMSE</th>
              </tr>
            </thead>
            <tbody>
              {report.by_issue.map((row) => (
                <tr key={row.slot} className={row.slot === summary.usual_slot ? "is-used" : undefined}>
                  <td className="left">{row.slot}</td>
                  <td className="left">{row.usable ? (row.days_used ? "Used" : "Usable") : "Too late"}</td>
                  <td>{row.days_seen}</td>
                  <td>{row.days_used}</td>
                  <td>{signedMw(row.bias_mw)}</td>
                  <td>{plainMw(row.mae_mw)}</td>
                  <td>{plainMw(row.rmse_mw)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="block">
        <h2>Cushions</h2>
        <p className="quiet">
          Count on the forecast, minus this many MW, and the outturn would still have covered you on that share of hours.
          Positive means take more off. Negative means the haircut had already gone past the outturn.
          This is a description of January, not a guarantee for the next month.
        </p>
        <table className="data cushion">
          <thead>
            <tr>
              <th className="left">Coverage</th>
              <th>Subtract from the issue</th>
              <th>Subtract after the haircut</th>
            </tr>
          </thead>
          <tbody>
            {report.buffers.map((row) => (
              <tr key={row.coverage}>
                <td className="left">{pct(row.coverage, 0)}</td>
                <td>{signedMw(row.raw_mw)} MW</td>
                <td>{signedMw(row.adjusted_mw)} MW</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="block">
        <h2>Day by day</h2>
        <p className="quiet">
          Delivery day, in GWh of forecast minus outturn. The last bar is 1 February, bid on 31 January.
          Choose a day to open its book.
        </p>
        <Columns
          bars={report.by_day.map((day) => ({
            key: day.decision_date,
            label: day.delivery_date.endsWith("-02-01") ? "1 Feb" : String(Number(day.delivery_date.slice(8))),
            value: day.error_mwh / 1000,
            hint: `${day.label}, ${day.error_mwh >= 0 ? "short" : "long"} ${gwh(day.error_mwh)}, from the ${day.slot} issue`,
            decision: day.decision_date,
          }))}
          signed
          unit="GWh"
          labelEvery={2}
          tone={(bar) => (bar.value >= 0 ? "short" : "long")}
          onPick={(bar) => openDay(bar.decision)}
        />
        <details>
          <summary>Every delivery day</summary>
          <table className="data">
            <thead>
              <tr>
                <th className="left">Delivery</th>
                <th>Issue</th>
                <th>Forecast</th>
                <th>Outturn</th>
                <th>Miss</th>
                <th>After haircut</th>
              </tr>
            </thead>
            <tbody>
              {report.by_day.map((day) => (
                <tr key={day.decision_date}>
                  <td className="left">
                    <button type="button" className="text-link" onClick={() => openDay(day.decision_date)}>
                      {day.label}
                    </button>
                  </td>
                  <td>{day.slot}</td>
                  <td>{gwh(day.forecast_mwh)}</td>
                  <td>{gwh(day.actual_mwh)}</td>
                  <td>{gwh(day.error_mwh)}</td>
                  <td>{gwh(day.adjusted_error_mwh)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </section>
    </article>
  );
}

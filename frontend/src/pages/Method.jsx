import { useEffect, useState } from "react";
import { useControls, useMeta } from "../components/Shell";
import { gwh, mw, num, pct } from "../format";

export default function Method() {
  const meta = useMeta();
  const { auction, lead } = useControls();
  const [report, setReport] = useState(null);

  useEffect(() => {
    document.title = "How a bid is scored · Daymark";
  }, []);

  useEffect(() => {
    const query = new URLSearchParams({ auction, lead_minutes: String(lead) });
    const controller = new AbortController();
    fetch(`/api/accuracy?${query}`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then(setReport)
      .catch(() => setReport(null));
    return () => controller.abort();
  }, [auction, lead]);

  const summary = report?.summary;
  const auctionName = meta.auctions.find((item) => item.id === auction)?.name;

  return (
    <article className="prose">
      <h1>How a bid is scored</h1>
      <p>
        Daymark is the wind number a GB desk could actually have used. For a delivery day, the bid
        goes in the day before, at the gate of the auction selected above. The forecast that counts
        is the last WINDFOR issue published at or before that gate, less the minutes the desk needs
        to get the bid in. One issue covers the whole delivery day.
      </p>
      <p>
        A later issue can be opened from the tape on the desk. It stays marked as too late, and it
        is not the bid. The point of the tape is to show what waiting would have changed, and what
        it would not have been allowed to change.
      </p>

      <h2>The gates</h2>
      <ul>
        {meta.auctions.map((item) => (
          <li key={item.id}>
            <strong>{item.name}, {item.gate_label}.</strong> {item.blurb}
          </li>
        ))}
      </ul>
      <p>
        These clocks are the published GMT gates. In January 2026, London is on GMT, so the civil
        clock and the auction clock are the same. The pilot does not include a summer day, when
        those two clocks can differ. Check the auction circular before reusing the clock then.
      </p>

      <h2>The two series</h2>
      <p>
        Forecasts come from Elexon{" "}
        <a href={meta.sources.forecast_docs}>WINDFOR</a>. Each row is an hourly megawatt value, with
        the time it was published and the hour it refers to. Outturn comes from{" "}
        <a href={meta.sources.actual_docs}>FUELHH</a>, fuel type WIND: the half-hour average megawatt
        value, with Elexon’s settlement date and settlement period. Nothing else was loaded.
      </p>
      <p>
        Decisions run from 1 January to 31 January 2026, so the delivery days run from 2 January to
        1 February. The 1 January outturn is loaded only so that yesterday can be used as a baseline
        for the 2 January delivery. {meta.forecast_rows.toLocaleString("en-GB")} forecast rows and{" "}
        {meta.actual_rows.toLocaleString("en-GB")} half-hour outturns are in the store.
      </p>
      {meta.notes.map((note) => <p key={note}>{note} Publish times are taken as Elexon sent them. A missing slot is not invented.</p>)}

      <h2>The join</h2>
      <p>
        WINDFOR does not have a half-hour shape. Each settlement period takes the forecast for the
        clock hour that contains it, so the two periods in an hour share one number. That is what
        the book shows, and why the forecast line is flat across the hour while the outturn steps.
      </p>
      <p>
        The scored error is on the hour: the forecast minus the mean of the two half-hour outturns.
        Scoring the half hours as well would count the same forecast twice. Energy in an hour is
        the megawatt value times one hour. Positive error means the forecast was above the outturn.
        A desk that subtracted the forecast from its demand was short of wind, and had to buy the
        difference somewhere else.
      </p>

      <h2>The score</h2>
      <table className="data define">
        <thead>
          <tr>
            <th className="left">Term</th>
            <th className="left">Meaning</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="left">Bias</td>
            <td className="left">Average error. The level the issue ran high or low.</td>
          </tr>
          <tr>
            <td className="left">MAE</td>
            <td className="left">Average absolute error. The typical size of the miss, in MW.</td>
          </tr>
          <tr>
            <td className="left">RMSE</td>
            <td className="left">Square root of the average squared error. Larger misses count for more.</td>
          </tr>
          <tr>
            <td className="left">Haircut</td>
            <td className="left">A share k of the forecast. k is total error divided by total forecast on the other delivery days. Count on forecast × (1 − k).</td>
          </tr>
          <tr>
            <td className="left">Cushion</td>
            <td className="left">A percentile of the error. Subtract it from what you count on, and that share of the hours in this month would still have been covered.</td>
          </tr>
          <tr>
            <td className="left">Persistence</td>
            <td className="left">Yesterday’s outturn for the same hour, used as if it were the forecast. A forecast you could have written with no model.</td>
          </tr>
          <tr>
            <td className="left">Within-month hour</td>
            <td className="left">The average outturn of that hour on the other delivery days. It uses the rest of January, including later days, so it is a description, not a bid.</td>
          </tr>
        </tbody>
      </table>
      {summary && (
        <p>
          For {auctionName} with the controls above, the issue you could bid has bias {mw(summary.bias_mw)},
          MAE {mw(summary.mae_mw)} and correlation {num(summary.correlation, 2)}. Persistence MAE is {mw(summary.persistence_mae_mw)}.
          The month’s energy gap is {gwh(summary.total_error_mwh)}. The leave-one-day haircut cuts MAE to {mw(summary.loo_mae_mw)}.
          The share fit on the whole month is {pct(summary.k)}.
        </p>
      )}

      <h2>Why the haircut is a share</h2>
      <p>
        On the day view, k is fit on the other delivery days only, using their biddable issue, and
        then applied to the day on screen. The day does not train its own correction. On the accuracy
        page the same leave-one-day rule is pooled, and a flat megawatt correction is shown beside it.
        The miss is wider in the hours the forecast itself called windy, which is why a share fits
        better than a fixed number of megawatts.
      </p>
      <p>
        It is still a description of this January. The same weather sits on both sides of the sum.
        A haircut estimated here will look kinder than one tested on a later month. It is not a
        model to ship into February without saying that.
      </p>

      <h2>What this will not tell you</h2>
      <ul>
        <li>No demand series was loaded. The demand box is your own flat megawatt figure.</li>
        <li>No prices were loaded, so the gap stays in megawatt hours and is not turned into pounds.</li>
        <li>No other fuel, and no embedded-wind adjustment. Both series are used as Elexon publishes them, joined on the interval.</li>
        <li>The cushions are percentiles of this month’s errors, not a calibrated probability for a new day.</li>
        <li>An issue has to cover at least 20 of the 24 delivery hours before it can displace an older complete issue. A fragment of a newer run does not win.</li>
      </ul>
      <p>
        The API is documented at <a href="/docs">/docs</a>. The numbers on the desk and on the accuracy
        page are computed in Python from the store. The page draws them.
      </p>
    </article>
  );
}

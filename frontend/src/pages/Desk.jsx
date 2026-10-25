import { useEffect, useState } from "react";
import Chart from "../components/Chart";
import { useControls, useMeta } from "../components/Shell";
import Tape from "../components/Tape";
import { plainMw, side } from "../format";
import { bidSentence, daySentence, demandSentence, haircutSentence, parseDemand, periodSentence } from "../speech";

export default function Desk() {
  const meta = useMeta();
  const { auction, lead, date, issue, demand, update } = useControls();
  const [desk, setDesk] = useState(null);
  const [error, setError] = useState(null);
  const [active, setActive] = useState(null);

  useEffect(() => {
    const query = new URLSearchParams({
      decision_date: date,
      auction,
      lead_minutes: String(lead),
    });
    if (issue) query.set("issue", issue);
    const controller = new AbortController();
    setError(null);
    fetch(`/api/desk?${query}`, { signal: controller.signal })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || "The book could not be loaded.");
        return body;
      })
      .then((body) => {
        setDesk(body);
        setActive(null);
        document.title = `${body.delivery_heading} · Daymark`;
      })
      .catch((reason) => {
        if (reason.name !== "AbortError") setError(reason.message);
      });
    return () => controller.abort();
  }, [auction, lead, date, issue]);

  useEffect(() => {
    function onKey(event) {
      const tag = event.target.tagName;
    if (tag !== "BODY" && tag !== "HTML") return;
      if (event.key === "ArrowLeft") shift(-1);
      if (event.key === "ArrowRight") shift(1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function shift(days) {
    const current = new Date(`${date}T00:00:00Z`);
    current.setUTCDate(current.getUTCDate() + days);
    const next = current.toISOString().slice(0, 10);
    if (next < meta.decision_start || next > meta.decision_end) return;
    update({ date: next, issue: "" });
  }

  const demandState = parseDemand(demand);
  const bookHref = (() => {
    const query = new URLSearchParams({
      decision_date: date,
      auction,
      lead_minutes: String(lead),
    });
    if (issue) query.set("issue", issue);
    return `/api/book.csv?${query}`;
  })();

  return (
    <article className="desk">
      <div className="day-nav">
        <button type="button" onClick={() => shift(-1)} disabled={date <= meta.decision_start}>
          Previous
        </button>
        <label className="date-field">
          Decision day
          <input
            type="date"
            min={meta.decision_start}
            max={meta.decision_end}
            value={date}
            onChange={(event) => update({ date: event.target.value, issue: "" })}
          />
        </label>
        <button type="button" onClick={() => shift(1)} disabled={date >= meta.decision_end}>
          Next
        </button>
      </div>

      {error && <p className="problem">{error}</p>}
      {!desk && !error && <p className="waiting">Loading the delivery day.</p>}

      {desk && !error && (
        <>
          <h1>{desk.delivery_heading}</h1>
          <p className={desk.vintage.biddable ? "lede" : "lede late"}>{bidSentence(desk)}</p>
          <ul className="legend">
            <li><i className="swatch forecast" /> Forecast</li>
            <li><i className="swatch outturn" /> Outturn</li>
            {desk.haircut.k != null && <li><i className="swatch haircut" /> After the haircut</li>}
            <li><i className="swatch short" /> Short</li>
            <li><i className="swatch long" /> Long</li>
            <li className="unit-note">MW</li>
          </ul>
          <Chart
            key={`${desk.vintage.publish_time}-${desk.delivery_date}`}
            periods={desk.periods}
            activeSp={active}
            onHover={setActive}
            showHaircut={desk.haircut.k != null}
          />
          <p className="reading">{daySentence(desk.summary)}</p>
          <p className="reading">{haircutSentence(desk)}</p>
          <p className="reading quiet">{periodSentence(desk.periods.find((period) => period.sp === active))}</p>
          <Tape
            vintages={desk.vintages}
            gateMinute={desk.gate_minute}
            cutoffMinute={desk.cutoff_minute}
            lead={desk.lead_minutes}
            onPick={(item) => update({ issue: item.publish_time })}
          />

          <div className="demand-row">
            <label htmlFor="demand">Flat demand</label>
            <input
              id="demand"
              inputMode="decimal"
              value={demand}
              placeholder="MW, optional"
              onChange={(event) => update({ demand: event.target.value })}
            />
            <span>Your figure, not from Elexon. Held flat across the delivery day.</span>
          </div>
          {demandState.error && <p className="problem">{demandState.error}</p>}
          {demandState.value != null && <p className="reading">{demandSentence(demandState.value, desk.summary)}</p>}

          <div className="block">
            <div className="block-head">
              <h2>Settlement book</h2>
              <a href={bookHref}>Download this book</a>
            </div>
            <p className="quiet">
              Miss is forecast minus outturn, in MW. A positive miss is short.
              The forecast is the hourly issue, held flat across the two settlement periods.
              The day’s energy is the sum of these half hours. The accuracy page scores each hour once.
            </p>
            <div className="scroll">
              <table className="book">
                <caption>Half-hour national wind for {desk.delivery_label}, from the {desk.vintage.slot} issue.</caption>
                <thead>
                  <tr>
                    <th>SP</th>
                    <th>GMT</th>
                    <th>Forecast</th>
                    <th>Outturn</th>
                    <th>Miss</th>
                    <th>After haircut</th>
                    {demandState.value != null && <th>Firm buy</th>}
                  </tr>
                </thead>
                <tbody>
                  {desk.periods.map((period) => {
                    const buy = demandState.value == null || period.adjusted_mw == null
                      ? null
                      : demandState.value - period.adjusted_mw;
                    return (
                      <tr
                        key={period.sp}
                        className={period.sp === active ? "is-active" : undefined}
                        onMouseEnter={() => setActive(period.sp)}
                        onFocus={() => setActive(period.sp)}
                        tabIndex={0}
                      >
                        <td>{period.sp}</td>
                        <td>{period.start_label}–{period.end_label}</td>
                        <td>{plainMw(period.forecast_mw)}</td>
                        <td>{plainMw(period.actual_mw)}</td>
                        <td className={tone(period.error_mw)}>{plainMw(period.error_mw)}</td>
                        <td>{plainMw(period.adjusted_mw)}</td>
                        {demandState.value != null && (
                          <td className={tone(buy)}>{plainMw(buy)}</td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </article>
  );
}

function tone(error) {
  const word = side(error);
  if (word === "short") return "short";
  if (word === "long") return "long";
  return undefined;
}

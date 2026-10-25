import { createContext, useContext } from "react";
import { NavLink, useSearchParams } from "react-router-dom";

export const MetaContext = createContext(null);

export function useMeta() {
  return useContext(MetaContext);
}

export function useControls() {
  const meta = useMeta();
  const [params, setParams] = useSearchParams();

  const auction = params.get("auction") || "n2ex";
  const lead = Number(params.get("lead") || "0");
  const date = params.get("date") || meta.default_decision_date;
  const issue = params.get("issue") || "";
  const demand = params.get("demand") ?? "";

  function update(next, replace = true) {
    setParams((current) => {
      const following = new URLSearchParams(current);
      Object.entries(next).forEach(([key, value]) => {
        if (value === "" || value == null) following.delete(key);
        else following.set(key, String(value));
      });
      return following;
    }, { replace });
  }

  return { auction, lead, date, issue, demand, update, params };
}

export default function Shell({ children }) {
  const meta = useMeta();
  const { auction, lead, update, params } = useControls();
  const search = params.toString();
  const current = meta.auctions.find((item) => item.id === auction) || meta.auctions[0];

  return (
    <>
      <a className="skip" href="#content">Skip to content</a>
      <header className="top">
        <div className="wrap top-row">
          <NavLink to={{ pathname: "/", search }} className="wordmark" end>
            Daymark
          </NavLink>
          <p className="product-line">National wind at gate closure</p>
        </div>
        <div className="wrap nav-row">
          <nav aria-label="Sections">
            <NavLink to={{ pathname: "/", search }} end>Desk</NavLink>
            <NavLink to={{ pathname: "/accuracy", search }}>Accuracy</NavLink>
            <NavLink to={{ pathname: "/method", search }}>Method</NavLink>
          </nav>
          <p className="month">January 2026</p>
        </div>
      </header>
      <div className="controls">
        <div className="wrap">
          <div className="control-row">
            <div className="choices" role="group" aria-label="Auction">
              {meta.auctions.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="choice"
                  aria-pressed={item.id === auction}
                  onClick={() => update({ auction: item.id, issue: "" })}
                >
                  {item.name}
                  <span className="choice-gate">{item.gate_clock}</span>
                </button>
              ))}
            </div>
            <div className="choices" role="group" aria-label="Time to get the bid in">
              {meta.leads.map((item) => (
                <button
                  key={item.minutes}
                  type="button"
                  className="choice"
                  aria-pressed={item.minutes === lead}
                  onClick={() => update({ lead: item.minutes === 0 ? "" : item.minutes, issue: "" })}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <p className="blurb">
            {current.blurb}
            {lead > 0 && ` An issue has to be out at least ${lead} minutes before that to be in the bid.`}
          </p>
        </div>
      </div>
      <main id="content" className="wrap">
        {children}
      </main>
      <footer className="foot">
        <div className="wrap">
          <p>
            Elexon WINDFOR and FUELHH wind. Decisions made 1–31 January 2026.
            Error is forecast minus outturn. Positive means the issue was high, and the desk was short of wind.
          </p>
        </div>
      </footer>
    </>
  );
}

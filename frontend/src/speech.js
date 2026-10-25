import { gwh, mw, pct, side, span, withoutYear } from "./format";

export function bidSentence(desk) {
  const issue = desk.vintage;
  const gate = desk.auction.gate_label;
  const when = withoutYear(desk.decision_label);
  if (!issue.biddable) {
    if (issue.minutes_before_gate > 0) {
      return `The ${issue.slot} issue is on the chart. It was published ${span(issue.minutes_before_gate)} before the ${desk.auction.name} gate, but after the ${desk.lead_minutes} minutes needed to get the bid in.`;
    }
    return `The ${issue.slot} issue is on the chart. It was published ${span(issue.minutes_before_gate)} after the ${desk.auction.name} gate at ${gate}, so it could not have been in the bid.`;
  }
  if (Math.abs(issue.minutes_before_gate) < 0.5) {
    return `Bid placed ${when} at ${gate}, on the ${issue.slot} issue, published at the gate.`;
  }
  return `Bid placed ${when} at ${gate}, on the ${issue.slot} issue, ${span(issue.minutes_before_gate)} before the gate.`;
}

export function daySentence(summary) {
  const partial = summary.hours_scored === summary.hours_expected
    ? ""
    : ` ${summary.hours_scored} of ${summary.hours_expected} hours are in this total.`;
  const word = side(summary.error_mwh);
  if (word === "flat") {
    return `That issue counted on ${gwh(summary.forecast_mwh)}. Outturn was ${gwh(summary.actual_mwh)}. The day was about flat.${partial}`;
  }
  return `That issue counted on ${gwh(summary.forecast_mwh)}. Outturn was ${gwh(summary.actual_mwh)}, so the day was ${word} ${gwh(summary.error_mwh)} of wind.${partial}`;
}

export function haircutSentence(desk) {
  const { k, reference_days: days } = desk.haircut;
  if (k == null) return "A haircut needs other delivery days, and this view does not have them.";
  const miss = desk.summary.adjusted_error_mwh;
  const word = side(miss);
  const outcome = word === "flat"
    ? "The day would then have been about flat."
    : `The day would then have been ${word} ${gwh(miss)}.`;
  const noun = days === 1 ? "day" : "days";
  return `A ${pct(k)} haircut, taken from the other ${days} delivery ${noun}, would have counted on ${gwh(desk.summary.adjusted_mwh)}. ${outcome}`;
}

export function periodSentence(period) {
  if (!period) return "Point at a settlement period to read it.";
  const clock = `SP ${period.sp}, ${period.start_label}–${period.end_label}.`;
  if (period.forecast_mw == null) {
    return `${clock} No forecast was published for this half hour. Outturn ${mw(period.actual_mw)}.`;
  }
  const word = side(period.error_mw);
  const miss = word === "flat" ? "flat on this half hour" : `${word} ${mw(Math.abs(period.error_mw))}`;
  return `${clock} Forecast ${mw(period.forecast_mw)}, outturn ${mw(period.actual_mw)}, ${miss}.`;
}

export function demandSentence(demandMw, summary) {
  if (demandMw == null) return null;
  const need = demandMw * 24;
  const firm = (gap) => {
    if (gap == null) return null;
    if (Math.abs(gap) < 0.5) return "firm energy would be about flat";
    if (gap > 0) return `you would buy ${gwh(gap)} of firm power`;
    return `wind would cover it with ${gwh(gap)} to spare`;
  };
  const demand = Math.round(demandMw).toLocaleString("en-GB");
  let text = `At a flat demand of ${demand} MW, the day needs ${gwh(need)}. Trusting the issue, ${firm(need - summary.forecast_mwh)}.`;
  if (summary.adjusted_mwh != null) {
    text += ` After the haircut, ${firm(need - summary.adjusted_mwh)}.`;
  }
  return text;
}

export function parseDemand(text) {
  if (text.trim() === "") return { value: null, error: null };
  const value = Number(text);
  if (!Number.isFinite(value) || value < 0 || value > 100000) {
    return { value: null, error: "Enter a demand between 0 and 100,000 MW, or leave this blank." };
  }
  return { value, error: null };
}

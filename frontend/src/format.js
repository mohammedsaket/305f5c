export function mw(value) {
  if (value == null || Number.isNaN(Number(value))) return "–";
  return `${Math.round(value).toLocaleString("en-GB")} MW`;
}

export function plainMw(value) {
  if (value == null || Number.isNaN(Number(value))) return "–";
  return Math.round(value).toLocaleString("en-GB");
}

export function signedMw(value) {
  if (value == null || Number.isNaN(Number(value))) return "–";
  const rounded = Math.round(value);
  const body = Math.abs(rounded).toLocaleString("en-GB");
  if (rounded > 0) return `+${body}`;
  if (rounded < 0) return `−${body}`;
  return "0";
}

export function gwh(mwh) {
  if (mwh == null || Number.isNaN(Number(mwh))) return "–";
  return `${(Math.abs(mwh) / 1000).toLocaleString("en-GB", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} GWh`;
}

export function pct(fraction, digits = 1) {
  if (fraction == null || Number.isNaN(Number(fraction))) return "–";
  return `${(fraction * 100).toLocaleString("en-GB", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}%`;
}

export function num(value, digits = 0) {
  if (value == null || Number.isNaN(Number(value))) return "–";
  return Number(value).toLocaleString("en-GB", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function compact(value) {
  if (value == null || Number.isNaN(Number(value))) return "";
  const rounded = Math.round(value);
  const sign = rounded < 0 ? "−" : "";
  const abs = Math.abs(rounded);
  if (abs >= 1000) {
    return `${sign}${(abs / 1000).toLocaleString("en-GB", { maximumFractionDigits: 1 })}k`;
  }
  return `${sign}${abs}`;
}

export function span(minutes) {
  const whole = Math.abs(Math.round(minutes));
  if (whole < 60) return whole === 1 ? "1 minute" : `${whole} minutes`;
  const hours = Math.floor(whole / 60);
  const rest = whole % 60;
  const hourLabel = hours === 1 ? "1 hour" : `${hours} hours`;
  if (!rest) return hourLabel;
  const minuteLabel = rest === 1 ? "1 minute" : `${rest} minutes`;
  return `${hourLabel} ${minuteLabel}`;
}

export function side(error) {
  if (error > 0.5) return "short";
  if (error < -0.5) return "long";
  return "flat";
}

export function withoutYear(label) {
  return label.replace(/ \d{4}$/, "");
}

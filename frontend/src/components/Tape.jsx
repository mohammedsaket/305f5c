export default function Tape({ vintages, gateMinute, cutoffMinute, lead, onPick }) {
  if (!vintages.length) return null;
  const minutes = vintages.map((item) => item.minute);
  const low = Math.min(...minutes, gateMinute, cutoffMinute) - 20;
  const high = Math.max(...minutes, gateMinute, cutoffMinute) + 20;
  const place = (minute) => 8 + ((minute - low) / (high - low)) * 84;

  return (
    <div className="tape" role="listbox" aria-label="Forecast issues on the decision day">
      <div className="tape-line" />
      {lead > 0 && (
        <div className="tape-mark" style={{ left: `${place(cutoffMinute)}%` }}>
          <span>Bid in</span>
        </div>
      )}
      <div className="tape-mark gate" style={{ left: `${place(gateMinute)}%` }}>
        <span>Gate</span>
      </div>
      {vintages.map((item) => (
        <button
          key={item.publish_time}
          type="button"
          role="option"
          aria-selected={item.selected}
          className={`${item.selected ? "is-selected" : ""} ${item.biddable ? "is-open" : "is-late"}`}
          style={{ left: `${place(item.minute)}%` }}
          onClick={() => onPick(item)}
        >
          <span className="dot" />
          <span className="tape-time">{item.slot}</span>
          <span className="tape-state">
            {item.selected && item.biddable && "In the bid"}
            {item.selected && !item.biddable && "Too late"}
            {!item.selected && item.biddable && "Usable"}
            {!item.selected && !item.biddable && (item.minutes_before_gate > 0 ? "Too late" : "After gate")}
          </span>
        </button>
      ))}
    </div>
  );
}

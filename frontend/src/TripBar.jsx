import SearchBox from "./SearchBox.jsx";
import { COPY } from "./format.js";

export default function TripBar({
  start,
  end,
  near,
  dropping,
  busy,
  onPickStart,
  onPickEnd,
  onDrop,
  onClear,
}) {
  return (
    <div className="trip-bar">
      <div className="trip-fields">
        <label className="trip-field">
          <span>{COPY.driveStart}</span>
          <SearchBox
            placeholder={COPY.driveHere}
            label={COPY.driveStart}
            value={start?.label || ""}
            near={near}
            onPick={(hit) =>
              onPickStart({ lng: hit.lng, lat: hit.lat, label: hit.label })
            }
          />
        </label>
        <label className="trip-field">
          <span>{COPY.driveEnd}</span>
          <SearchBox
            placeholder="City or address"
            label={COPY.driveEnd}
            value={end?.label || ""}
            near={near}
            onPick={(hit) =>
              onPickEnd({ lng: hit.lng, lat: hit.lat, label: hit.label })
            }
          />
        </label>
      </div>
      <div className="trip-actions">
        <button
          type="button"
          className={`trip-drop${dropping ? " is-on" : ""}`}
          aria-pressed={dropping}
          onClick={onDrop}
        >
          {COPY.driveDrop}
        </button>
        <button type="button" className="trip-clear" onClick={onClear}>
          {COPY.driveClear}
        </button>
      </div>
      {dropping ? <p className="trip-hint">{COPY.driveDropHint}</p> : null}
      {busy ? <p className="trip-hint">{COPY.driveLooking}</p> : null}
    </div>
  );
}

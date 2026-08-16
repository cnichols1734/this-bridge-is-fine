import SearchBox from "./SearchBox.jsx";
import { COPY } from "./format.js";

export default function TripBar({
  start,
  end,
  near,
  dropping,
  busy,
  error,
  onPickStart,
  onPickEnd,
  onFocusStart,
  onFocusEnd,
  onOpenChange,
  onDrop,
  onBack,
  onClear,
}) {
  return (
    <div className="trip-bar">
      <div className="trip-head">
        <button type="button" className="trip-back" onClick={onBack}>
          {COPY.driveBack}
        </button>
        <button type="button" className="trip-clear" onClick={onClear}>
          {COPY.driveClear}
        </button>
      </div>
      <div className="trip-fields">
        <label className="trip-field">
          <span>{COPY.driveStart}</span>
          <SearchBox
            placeholder={COPY.driveHere}
            label={COPY.driveStart}
            value={start?.label || ""}
            near={near}
            onFocus={onFocusStart}
            onOpenChange={onOpenChange}
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
            onFocus={onFocusEnd}
            onOpenChange={onOpenChange}
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
      </div>
      {error ? <p className="trip-error">{error}</p> : null}
      {dropping && !error ? <p className="trip-hint">{COPY.driveDropHint}</p> : null}
      {busy && !error ? <p className="trip-hint">{COPY.driveLooking}</p> : null}
    </div>
  );
}

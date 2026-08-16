import { COPY, conditionClass, formatAdt, formatDriveDistance, officialCondition } from "./format.js";

export function DriveButton({ onClick, className = "" }) {
  return (
    <button
      className={`drive-btn${className ? ` ${className}` : ""}`}
      type="button"
      onClick={onClick}
    >
      {COPY.driveAction}
    </button>
  );
}

export function NavBanner({ banner, note }) {
  if (!banner && !note) return null;
  return (
    <div className="nav-banner" role="status">
      {banner ? (
        <>
          <div className="nav-turn">{banner.text}</div>
          <div className="nav-dist">{formatDriveDistance(banner.distance_m)}</div>
        </>
      ) : null}
      {note ? <p className="nav-note">{note}</p> : null}
    </div>
  );
}

export function ApproachCard({ bridge, onOpen, onDismiss }) {
  if (!bridge) return null;
  const cond = officialCondition(bridge.condition);
  const label = bridge.condition_label || (cond === "P" ? "Poor" : cond === "F" ? "Fair" : cond === "G" ? "Good" : "Unknown");
  return (
    <div className="approach-card">
      <button
        type="button"
        className="approach-open"
        onClick={() => onOpen(bridge.id)}
      >
        <span className={conditionClass(bridge)} />
        <span className="approach-body">
          <span className="approach-title">
            {bridge.facility_carried || "Unnamed structure"}
          </span>
          <span className="approach-meta">
            <span className={`cond cond-${cond}`}>{label}</span>
            {bridge.score != null ? ` · ${bridge.score}` : ""}
            {` · ${formatAdt(bridge.adt, bridge.adt_suspect)}`}
          </span>
        </span>
      </button>
      <button
        type="button"
        className="approach-dismiss"
        aria-label={COPY.approachDismiss}
        onClick={onDismiss}
      >
        <span aria-hidden="true">×</span>
      </button>
    </div>
  );
}

export function WorstOnDrive({ bridges, selectedId, onSelect }) {
  if (!bridges?.length) return null;
  return (
    <div className="trip-worst">
      <div className="trip-worst-label">{COPY.driveWorst}</div>
      {bridges.map((bridge) => {
        const cond = officialCondition(bridge.condition);
        const label =
          bridge.condition_label ||
          (cond === "P" ? "Poor" : cond === "F" ? "Fair" : cond === "G" ? "Good" : "Unknown");
        return (
          <button
            key={bridge.id}
            type="button"
            className={`trip-worst-row${selectedId === bridge.id ? " is-on" : ""}${cond === "P" ? " is-poor" : ""}`}
            onClick={(event) => {
              event.stopPropagation();
              onSelect(bridge.id);
            }}
          >
            <span className={conditionClass(bridge)} />
            <span className="trip-worst-body">
              <span className="trip-worst-title">
                {bridge.facility_carried || "Unnamed structure"}
              </span>
              <span className="trip-worst-meta">
                <span className={`cond cond-${cond}`}>{label}</span>
                {bridge.score != null ? ` · ${bridge.score}` : ""}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

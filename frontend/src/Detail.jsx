import {
  COPY,
  RANK_NOTE,
  RATING_NOTE,
  formatAdt,
  formatInspect,
  officialCondition,
  ratingClass,
  ratingWord,
} from "./format.js";

const ORDER = ["deck", "superstructure", "substructure", "culvert"];
const NAMES = {
  deck: "Road surface",
  superstructure: "Support",
  substructure: "Foundation",
  culvert: "Culvert",
};

export function RankNote() {
  return <p className="rank-note">{RANK_NOTE}</p>;
}

export default function Detail({ bridge, onClose }) {
  if (!bridge) return null;
  const ratings = bridge.ratings || {};
  const title = bridge.facility_carried || "Unnamed structure";
  const score = bridge.score;
  const cond = officialCondition(bridge.condition);
  const condLabel = bridge.condition_label || "Unknown";
  const full = Boolean(bridge.ratings);
  const parts = ORDER.map((key) => {
    const item = ratings[key];
    if (!item || item.value == null) return null;
    return (
      <div className={ratingClass(item.value)} key={key}>
        <div className="rating-name">{NAMES[key]}</div>
        <div className="rating-track">
          <div
            className="rating-fill"
            style={{ width: `${(item.value / 9) * 100}%` }}
          />
        </div>
        <div className="rating-n">
          <span className="rating-word">{ratingWord(item.value, item.word)}</span>
          <span>{item.value}/9</span>
        </div>
      </div>
    );
  }).filter(Boolean);

  return (
    <article className="detail">
      <header className="place-head sheet-drag">
        <div>
          <h2 className="place-title">{title}</h2>
          <p className="place-meta">
            <span className={`cond cond-${cond}`}>{condLabel}</span>
            {[
              formatAdt(bridge.adt, bridge.adt_suspect),
              bridge.year_built,
            ]
              .filter(Boolean)
              .map((bit, i) => (
                <span key={i}>
                  {" · "}
                  {bit}
                </span>
              ))}
          </p>
        </div>
        {onClose ? (
          <button
            type="button"
            className="sheet-close"
            aria-label="Close"
            onClick={onClose}
          >
            <span aria-hidden="true">×</span>
          </button>
        ) : null}
      </header>

      {score != null ? (
        <div
          className="concern"
          aria-label={`${COPY.scoreHeading} ${score} out of 100, where higher is better. ${RANK_NOTE}`}
        >
          <div className="concern-kicker">{COPY.scoreHeading}</div>
          <div className="concern-word">{score}</div>
          <div className="concern-meta">
            <span className="concern-of">{COPY.scoreMeta}</span>
          </div>
          <div className="concern-bar" aria-hidden="true">
            <div className="concern-fill" style={{ width: `${score}%` }} />
          </div>
          <RankNote />
        </div>
      ) : null}

      {bridge.headline ? <p className="detail-title">{bridge.headline}</p> : null}
      <p className="detail-sub">
        {[bridge.feature_crossed && `Over ${bridge.feature_crossed}`, bridge.location]
          .filter(Boolean)
          .join(" · ")}
      </p>

      {full ? (
        <dl className="facts">
          <div className="fact">
            <dt>Built</dt>
            <dd>{bridge.year_built || "—"}</dd>
          </div>
          <div className="fact">
            <dt>Rebuilt</dt>
            <dd>{bridge.year_reconstructed || "—"}</dd>
          </div>
          <div className="fact">
            <dt>Status</dt>
            <dd>{bridge.status_label || "—"}</dd>
          </div>
          <div className="fact">
            <dt>Traffic</dt>
            <dd>{formatAdt(bridge.adt, bridge.adt_suspect)}</dd>
          </div>
          <div className="fact fact-wide">
            <dt>Inspected</dt>
            <dd>
              {formatInspect(bridge.inspect_date)}
              {bridge.inspect_overdue ? " · overdue" : ""}
            </dd>
          </div>
        </dl>
      ) : null}

      {parts.length ? (
        <div className="ratings">
          {parts}
          <p className="ratings-note">{RATING_NOTE}</p>
        </div>
      ) : null}

      {bridge.why ? <p className="why">{bridge.why}</p> : null}

      <p className="file-id">
        {bridge.state} {bridge.structure_number}
        {bridge.nbi_year ? ` · FHWA NBI ${bridge.nbi_year}` : " · FHWA NBI"}
      </p>
    </article>
  );
}

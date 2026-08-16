import {
  COPY,
  RANK_NOTE,
  RATING_NOTE,
  formatAdt,
  formatBuilt,
  formatInspect,
  officialCondition,
  ratingClass,
  ratingWord,
  scoreBand,
} from "./format.js";

const ORDER = ["deck", "superstructure", "substructure", "culvert"];
const NAMES = {
  deck: "Road surface",
  superstructure: "Support structure",
  substructure: "Foundation",
  culvert: "Culvert",
};

const DEDUCTIONS = [
  { key: "status_deduction", label: "Operating status" },
  { key: "scour_deduction", label: "Scour vulnerability" },
  { key: "redundancy_deduction", label: "Limited structural redundancy" },
  { key: "inspection_deduction", label: "Reported inspection timing" },
  { key: "traffic_deduction", label: "Traffic exposure" },
];

export function RankNote() {
  return <p className="rank-note">{RANK_NOTE}</p>;
}

function minus(n) {
  return `\u2212${n}`;
}

function InspectFact({ bridge }) {
  const date = formatInspect(bridge.inspect_date);
  const freq = bridge.inspect_freq_months;
  const due = formatInspect(bridge.inspect_due_on);
  const past = bridge.inspect_months_past_due;
  const bits = [date];
  if (freq) bits.push(`${freq}-month interval`);
  let extra = "";
  if (bridge.inspect_overdue && due && due !== "Unknown") {
    extra =
      past != null
        ? `Next implied ${due} · about ${past} ${past === 1 ? "month" : "months"} past due`
        : `Next implied ${due}`;
  } else if (due && due !== "Unknown") {
    extra = `Next implied ${due}`;
  }
  return (
    <>
      {bits.join(" · ")}
      {extra ? (
        <>
          <br />
          {extra}
        </>
      ) : null}
    </>
  );
}

export default function Detail({ bridge, onClose, snapshot }) {
  if (!bridge) return null;
  const ratings = bridge.ratings || {};
  const title = bridge.facility_carried || "Unnamed structure";
  const score = bridge.score;
  const band = bridge.score_band || scoreBand(score);
  const cond = officialCondition(bridge.condition);
  const condLabel = bridge.condition_label || "Unknown";
  const full = Boolean(bridge.ratings);
  const paragraphs = bridge.summary_paragraphs?.length
    ? bridge.summary_paragraphs
    : bridge.summary
      ? [bridge.summary]
      : [];
  const drivers = Array.isArray(bridge.explanations) ? bridge.explanations : [];
  const breakdown = bridge.score_breakdown || {};
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
        {item.plain ? <p className="rating-plain">{item.plain}</p> : null}
      </div>
    );
  }).filter(Boolean);
  const built = formatBuilt(bridge.year_built, bridge.age_years);
  const nbiYear = bridge.nbi_year || snapshot;

  return (
    <article className="detail">
      <header className="place-head sheet-drag">
        <div>
          <h2 className="place-title">{title}</h2>
          <p className="place-meta">
            <span className={`cond cond-${cond}`}>{condLabel}</span>
            {[formatAdt(bridge.adt, bridge.adt_suspect), bridge.year_built]
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

      {paragraphs.length ? (
        <section className="meaning">
          <div className="file-kicker">{COPY.meaning}</div>
          {paragraphs.map((para) => (
            <p key={para.slice(0, 48)}>{para}</p>
          ))}
        </section>
      ) : null}

      {score != null ? (
        <div
          className="concern"
          aria-label={`${COPY.scoreHeading} ${score} out of 100, where higher is better. ${COPY.scoreNote}`}
        >
          <div className="concern-kicker">{COPY.scoreHeading}</div>
          <div className="concern-word">
            {score}
            <span className="concern-of"> / 100</span>
          </div>
          {band ? <div className="concern-band">{band}</div> : null}
          <div className="concern-meta">{COPY.scoreHigher}</div>
          <div className="concern-bar" aria-hidden="true">
            <div className="concern-fill" style={{ width: `${score}%` }} />
          </div>
          <p className="rank-note">{COPY.scoreExplainer}</p>
          {breakdown.condition_base != null ? (
            <details className="score-why">
              <summary>{`Why ${score}?`}</summary>
              <ul>
                <li>
                  <span>Official component condition</span>
                  <span>{breakdown.condition_base}</span>
                </li>
                {DEDUCTIONS.map((row) => {
                  const n = Number(breakdown[row.key] || 0);
                  if (!n) return null;
                  return (
                    <li key={row.key}>
                      <span>{row.label}</span>
                      <span>{minus(n)}</span>
                    </li>
                  );
                })}
              </ul>
            </details>
          ) : null}
        </div>
      ) : null}

      {drivers.length ? (
        <section className="standout">
          <div className="file-kicker">{COPY.standout}</div>
          {drivers.map((row) => (
            <div className="standout-row" key={row.key}>
              <div className="standout-title">
                {row.title}
                {row.status ? ` · ${row.status}` : ""}
                {row.value && row.key !== "status" && row.key !== "redundancy"
                  ? ` · ${row.value}`
                  : ""}
              </div>
              {row.plain ? <p className="standout-plain">{row.plain}</p> : null}
              {row.technical ? (
                <p className="standout-tech">{row.technical}</p>
              ) : null}
            </div>
          ))}
        </section>
      ) : null}

      {parts.length ? (
        <div className="ratings">
          <div className="file-kicker">Official component ratings</div>
          {parts}
          <p className="ratings-note">{RATING_NOTE}</p>
        </div>
      ) : null}

      <p className="detail-sub">
        {[bridge.feature_crossed && `Over ${bridge.feature_crossed}`, bridge.location]
          .filter(Boolean)
          .join(" · ")}
      </p>

      {full ? (
        <dl className="facts">
          <div className="fact">
            <dt>Built</dt>
            <dd>{built || "—"}</dd>
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
              <InspectFact bridge={bridge} />
            </dd>
          </div>
        </dl>
      ) : null}

      <section className="source-block">
        <div className="file-kicker">{COPY.source}</div>
        <p>
          {COPY.sourceLine}
          {nbiYear ? ` · NBI ${nbiYear}` : ""}
        </p>
        <p className="file-id">
          {bridge.state} {bridge.structure_number}
        </p>
        <details className="method">
          <summary>{COPY.methodology}</summary>
          <p>{bridge.methodology || COPY.methodologyBody}</p>
        </details>
      </section>
    </article>
  );
}

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

function dash(value) {
  if (value == null || value === "") return "—";
  return value;
}

function Pair({ label, value }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd>{dash(value)}</dd>
    </div>
  );
}

function FileJump() {
  const go = (id) => (event) => {
    event.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  return (
    <nav className="file-jump" aria-label="Bridge file sections">
      <a href="#file-overview" onClick={go("file-overview")}>
        {COPY.overview}
      </a>
      <a href="#file-ratings" onClick={go("file-ratings")}>
        {COPY.ratingsJump}
      </a>
      <a href="#file-record" onClick={go("file-record")}>
        {COPY.fileJump}
      </a>
    </nav>
  );
}

export function TrendChart({ points }) {
  if (!points?.length || points.length < 2) return null;
  const width = 320;
  const height = 168;
  const pad = { l: 28, r: 10, t: 18, b: 28 };
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const years = points.map((p) => p.year);
  const minX = Math.min(...years);
  const maxX = Math.max(...years);
  const spanX = Math.max(1, maxX - minX);
  const yFor = (rating) => pad.t + ((9 - rating) / 9) * innerH;
  const xFor = (year) => pad.l + ((year - minX) / spanX) * innerW;
  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xFor(p.year).toFixed(1)} ${yFor(p.rating).toFixed(1)}`)
    .join(" ");
  const ticks = [0, 3, 5, 7, 9];
  return (
    <svg
      className="trend-svg"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Condition ratings by year, 0 to 9"
    >
      {ticks.map((n) => (
        <g key={n}>
          <line
            className="trend-grid"
            x1={pad.l}
            x2={width - pad.r}
            y1={yFor(n)}
            y2={yFor(n)}
          />
          <text className="trend-tick" x={pad.l - 6} y={yFor(n) + 3} textAnchor="end">
            {n}
          </text>
        </g>
      ))}
      <line className="trend-ref trend-good" x1={pad.l} x2={width - pad.r} y1={yFor(7)} y2={yFor(7)} />
      <text className="trend-ref-label is-good" x={(pad.l + width - pad.r) / 2} y={yFor(7) - 4}>
        Good
      </text>
      <line className="trend-ref trend-fair" x1={pad.l} x2={width - pad.r} y1={yFor(5)} y2={yFor(5)} />
      <text className="trend-ref-label is-fair" x={(pad.l + width - pad.r) / 2} y={yFor(5) - 4}>
        Fair
      </text>
      <path className="trend-line" d={path} fill="none" />
      {points.map((p) => (
        <circle
          key={p.year}
          className="trend-dot"
          cx={xFor(p.year)}
          cy={yFor(p.rating)}
          r="3.5"
        />
      ))}
      {points.map((p) => (
        <text
          key={`y-${p.year}`}
          className="trend-year"
          x={xFor(p.year)}
          y={height - 8}
          textAnchor="middle"
        >
          {p.year}
        </text>
      ))}
    </svg>
  );
}

export default function Detail({ bridge, onClose, snapshot, jump = false }) {
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
  const structure = bridge.structure || {};
  const dimensions = bridge.dimensions || {};
  const classification = bridge.classification || {};
  const inventory = bridge.inventory_status || {};
  const loads = bridge.load_ratings;
  const trend = bridge.condition_trend;
  const glanceLength = bridge.glance_length || dimensions.length_label;
  const showDetails = Boolean(
    structure.year_built ||
      structure.material ||
      dimensions.length_label ||
      classification.route_type ||
      inventory.toll ||
      full
  );

  return (
    <article className="detail">
      <header className="place-head sheet-drag" id="file-overview">
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

      {jump ? <FileJump /> : null}

      <p className="detail-sub">
        {[bridge.feature_crossed && `Over ${bridge.feature_crossed}`, bridge.location]
          .filter(Boolean)
          .join(" · ")}
      </p>

      <dl className="glance">
        <div className="glance-item">
          <dt>Condition</dt>
          <dd>
            <span className={`cond cond-${cond}`}>{condLabel}</span>
          </dd>
        </div>
        <div className="glance-item">
          <dt>Built</dt>
          <dd>{bridge.year_built || "—"}</dd>
        </div>
        <div className="glance-item">
          <dt>Traffic</dt>
          <dd>{formatAdt(bridge.adt, bridge.adt_suspect)}</dd>
        </div>
        <div className="glance-item">
          <dt>Length</dt>
          <dd>{glanceLength || "—"}</dd>
        </div>
      </dl>

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
          id="file-ratings"
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

      {trend?.points?.length >= 2 ? (
        <section className="file-block trend-block">
          <div className="file-kicker">{COPY.trend}</div>
          {trend.insight ? <p className="file-lead">{trend.insight}</p> : null}
          <TrendChart points={trend.points} />
          <p className="file-source">
            Data: {trend.points[0].year}–{trend.points[trend.points.length - 1].year} FHWA
            National Bridge Inventory
          </p>
        </section>
      ) : null}

      {loads ? (
        <section className="file-block loads-block" id="file-record">
          <div className="file-kicker">{COPY.loads}</div>
          <p className="file-lead">{COPY.loadIntro}</p>
          <div className="load-grid">
            <div>
              <div className="file-kicker">Operating rating</div>
              <div className="load-n">{loads.operating_label || "—"}</div>
              <p className="file-caption">{loads.operating_caption}</p>
            </div>
            <div>
              <div className="file-kicker">Inventory rating</div>
              <div className="load-n">{loads.inventory_label || "—"}</div>
              <p className="file-caption">{loads.inventory_caption}</p>
            </div>
          </div>
          {loads.paragraph ? <p className="file-lead">{loads.paragraph}</p> : null}
        </section>
      ) : (
        <div id="file-record" />
      )}

      {showDetails ? (
        <section className="file-block details-block">
          <div className="file-kicker">{COPY.details}</div>
          {structure.intro ? <p className="file-lead">{structure.intro}</p> : null}
          <div className="details-grid">
            <div>
              <div className="file-kicker">{COPY.construction}</div>
              <dl className="facts stacked">
                <Pair label="Year built" value={structure.year_built || bridge.year_built} />
                <Pair label="Year reconstructed" value={structure.year_reconstructed || bridge.year_reconstructed} />
                <Pair label="Material" value={structure.material} />
                <Pair label="Design type" value={structure.design} />
                <Pair label="Owner" value={structure.owner} />
              </dl>
            </div>
            {dimensions.length_label || dimensions.max_span_label ? (
              <div>
                <div className="file-kicker">{COPY.dimensions}</div>
                <dl className="facts stacked">
                  <Pair label="Total length" value={dimensions.length_label} />
                  <Pair label="Max span" value={dimensions.max_span_label} />
                  <Pair label="Deck width" value={dimensions.deck_width_label} />
                  <Pair label="Deck area" value={dimensions.deck_area_label} />
                </dl>
                {dimensions.note ? <p className="file-caption">{dimensions.note}</p> : null}
              </div>
            ) : null}
            {classification.route_type || classification.lanes_on != null ? (
              <div>
                <div className="file-kicker">{COPY.classification}</div>
                <dl className="facts stacked">
                  <Pair label="Route type" value={classification.route_type} />
                  <Pair label="Route number" value={classification.route_number} />
                  <Pair label="Lanes on bridge" value={classification.lanes_on} />
                  <Pair
                    label="Lanes under bridge"
                    value={classification.lanes_under == null ? "—" : classification.lanes_under}
                  />
                </dl>
              </div>
            ) : null}
            <div>
              <div className="file-kicker">{COPY.inventoryStatus}</div>
              <dl className="facts stacked">
                <Pair label="Toll bridge" value={inventory.toll} />
                <Pair label="Historical significance" value={inventory.historic} />
                <Pair label="Scour critical" value={inventory.scour || bridge.scour_label} />
                <Pair label="Detour length" value={inventory.detour_label} />
                <Pair label="Status" value={bridge.status_label} />
                {full ? (
                  <div className="fact fact-wide">
                    <dt>Inspected</dt>
                    <dd>
                      <InspectFact bridge={bridge} />
                    </dd>
                  </div>
                ) : null}
              </dl>
            </div>
          </div>
        </section>
      ) : full ? (
        <dl className="facts">
          <div className="fact">
            <dt>Built</dt>
            <dd>{built || "—"}</dd>
          </div>
          <div className="fact">
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

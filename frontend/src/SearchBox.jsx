import { useEffect, useRef, useState } from "react";
import { searchPlaces } from "./api.js";

export default function SearchBox({
  onPick,
  near,
  placeholder = "City or ZIP",
  label = "Search city or ZIP",
  value,
}) {
  const [q, setQ] = useState(value || "");

  useEffect(() => {
    if (value != null) setQ(value);
  }, [value]);
  const [hits, setHits] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [busy, setBusy] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    const query = q.trim();
    if (query.length < 2) {
      setHits([]);
      setOpen(false);
      return undefined;
    }
    const timer = setTimeout(() => {
      setBusy(true);
      searchPlaces(query, near)
        .then((results) => {
          setHits(results);
          setActive(0);
          setOpen(results.length > 0);
        })
        .catch(() => {
          setHits([]);
          setOpen(false);
        })
        .finally(() => setBusy(false));
    }, 320);
    return () => clearTimeout(timer);
  }, [q, near]);

  useEffect(() => {
    const onDoc = (event) => {
      if (box.current && !box.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onDoc);
    return () => document.removeEventListener("pointerdown", onDoc);
  }, []);

  const choose = (hit) => {
    if (!hit) return;
    setQ(hit.label);
    setOpen(false);
    onPick(hit);
  };

  return (
    <div className="search" ref={box}>
      <input
        type="search"
        enterKeyHint="search"
        autoComplete="off"
        spellCheck={false}
        placeholder={placeholder}
        aria-label={label}
        value={q}
        onChange={(event) => setQ(event.target.value)}
        onFocus={() => hits.length && setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setActive((i) => Math.min(i + 1, hits.length - 1));
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (event.key === "Enter") {
            event.preventDefault();
            choose(hits[active]);
          } else if (event.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {q ? (
        <button
          type="button"
          className="search-clear"
          aria-label="Clear search"
          onClick={() => {
            setQ("");
            setHits([]);
            setOpen(false);
          }}
        >
          <span aria-hidden="true">×</span>
        </button>
      ) : null}
      {busy ? <span className="search-status">Searching</span> : null}
      {open ? (
        <ul className="search-hits" role="listbox">
          {hits.map((hit, index) => (
            <li key={`${hit.label}-${hit.lat}`}>
              <button
                type="button"
                className={index === active ? "is-on" : ""}
                role="option"
                aria-selected={index === active}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(hit)}
              >
                <span className="search-name">{hit.label}</span>
                <span className="search-kind">{hit.kind}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

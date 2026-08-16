import { useEffect, useRef, useState } from "react";
import { searchPlaces } from "./api.js";
import { shouldFetchHits } from "./searchQuery.js";

export default function SearchBox({
  onPick,
  near,
  placeholder = "City or ZIP",
  label = "Search city or ZIP",
  value,
  onFocus,
  onOpenChange,
}) {
  const [q, setQ] = useState(value || "");

  useEffect(() => {
    if (value != null) setQ(value);
  }, [value]);
  const [hits, setHits] = useState([]);
  const [open, setOpen] = useState(false);
  const openRef = useRef(false);
  const pickedQuery = useRef(null);
  const fetchGen = useRef(0);

  const setHitsOpen = (next) => {
    if (openRef.current === next) return;
    openRef.current = next;
    setOpen(next);
    onOpenChange?.(next);
  };
  const [active, setActive] = useState(0);
  const [busy, setBusy] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    const query = q.trim();
    if (!shouldFetchHits(query, pickedQuery.current)) {
      if (query.length < 2) {
        pickedQuery.current = null;
        setHits([]);
        setHitsOpen(false);
      }
      return undefined;
    }
    const gen = fetchGen.current;
    const timer = setTimeout(() => {
      if (!shouldFetchHits(query, pickedQuery.current) || gen !== fetchGen.current) {
        return;
      }
      setBusy(true);
      searchPlaces(query, near)
        .then((results) => {
          if (gen !== fetchGen.current || !shouldFetchHits(query, pickedQuery.current)) {
            return;
          }
          setHits(results);
          setActive(0);
          setHitsOpen(results.length > 0);
        })
        .catch(() => {
          if (gen !== fetchGen.current) return;
          setHits([]);
          setHitsOpen(false);
        })
        .finally(() => {
          if (gen === fetchGen.current) setBusy(false);
        });
    }, 320);
    return () => clearTimeout(timer);
  }, [q, near]);

  useEffect(() => {
    return () => {
      if (openRef.current) onOpenChange?.(false);
    };
  }, []);

  useEffect(() => {
    const onDoc = (event) => {
      if (box.current && !box.current.contains(event.target)) {
        setHitsOpen(false);
      }
    };
    document.addEventListener("pointerdown", onDoc);
    return () => document.removeEventListener("pointerdown", onDoc);
  }, []);

  const choose = (hit) => {
    if (!hit) return;
    fetchGen.current += 1;
    pickedQuery.current = hit.label.trim();
    setQ(hit.label);
    setHits([]);
    setHitsOpen(false);
    setBusy(false);
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
        onChange={(event) => {
          const next = event.target.value;
          if (next.trim() !== pickedQuery.current) pickedQuery.current = null;
          setQ(next);
        }}
        onFocus={() => {
          onFocus?.();
          if (hits.length && shouldFetchHits(q, pickedQuery.current)) setHitsOpen(true);
        }}
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
            if (open) {
              event.preventDefault();
              event.stopPropagation();
              setHitsOpen(false);
            }
          }
        }}
      />
      {q ? (
        <button
          type="button"
          className="search-clear"
          aria-label="Clear search"
          onClick={() => {
            fetchGen.current += 1;
            pickedQuery.current = null;
            setQ("");
            setHits([]);
            setHitsOpen(false);
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

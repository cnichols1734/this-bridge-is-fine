export function shouldFetchHits(query, pickedLabel) {
  const q = String(query || "").trim();
  if (q.length < 2) return false;
  if (pickedLabel && q === String(pickedLabel).trim()) return false;
  return true;
}

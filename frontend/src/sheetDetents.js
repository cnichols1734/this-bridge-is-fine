/** iPhone X-class home indicator. The sheet pads this inside its height. */
export const IPHONE_X_SAFE_AREA = 34;

/**
 * Portrait Drive peek content: handle, time, ETA / distance / count / Poor,
 * Use this drive, worst label, and three two-line rows. Safe-area is extra.
 */
export const DRIVE_PEEK_PORTRAIT_CONTENT = 390;

export function isLandscape(width, height) {
  return width > height && height <= 500;
}

export function detentHeightFor(detent, { width, height, roomy = false } = {}) {
  const h = height;
  const landscape = isLandscape(width, h);
  if (detent === "full") return Math.round(h * (landscape ? 0.94 : 0.92));
  if (detent === "half") return Math.round(h * (landscape ? 0.52 : 0.56));
  if (roomy) {
    if (landscape) return Math.min(340, Math.max(292, Math.round(h * 0.84)));
    const half = Math.round(h * 0.56);
    const need = DRIVE_PEEK_PORTRAIT_CONTENT + IPHONE_X_SAFE_AREA;
    return Math.min(need, Math.max(248, half - 12));
  }
  if (landscape) return Math.min(96, Math.round(h * 0.26));
  return Math.min(156, Math.round(h * 0.22));
}

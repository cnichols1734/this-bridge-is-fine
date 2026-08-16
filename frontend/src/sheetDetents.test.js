import assert from "node:assert/strict";
import test from "node:test";
import {
  DRIVE_PEEK_PORTRAIT_CONTENT,
  IPHONE_X_SAFE_AREA,
  detentHeightFor,
} from "./sheetDetents.js";

const IPHONE_X = { width: 375, height: 812 };
const IPHONE_X_LANDSCAPE = { width: 812, height: 375 };

test("375×812 roomy peek fits facts, Use this drive, and three worst rows", () => {
  const peek = detentHeightFor("peek", { ...IPHONE_X, roomy: true });
  const half = detentHeightFor("half", IPHONE_X);
  const need = DRIVE_PEEK_PORTRAIT_CONTENT + IPHONE_X_SAFE_AREA;
  assert.ok(peek >= need, `peek ${peek} < content+safe-area ${need}`);
  assert.ok(peek < half, `peek ${peek} must stay below half ${half}`);
});

test("landscape roomy peek is unchanged", () => {
  const peek = detentHeightFor("peek", { ...IPHONE_X_LANDSCAPE, roomy: true });
  assert.equal(peek, Math.min(340, Math.max(292, Math.round(375 * 0.84))));
});

test("compact portrait peek is unchanged", () => {
  assert.equal(
    detentHeightFor("peek", IPHONE_X),
    Math.min(156, Math.round(812 * 0.22)),
  );
});

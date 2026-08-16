import assert from "node:assert/strict";
import test from "node:test";
import { shouldFetchHits } from "./searchQuery.js";

test("a picked suggestion does not fetch the same query again", () => {
  assert.equal(shouldFetchHits("Sunrise Road", "Sunrise Road"), false);
  assert.equal(shouldFetchHits("  Sunrise Road  ", "Sunrise Road"), false);
  assert.equal(shouldFetchHits("Sun", null), true);
  assert.equal(shouldFetchHits("Sunrise Road", null), true);
  assert.equal(shouldFetchHits("Sunrise", "Sunrise Road"), true);
  assert.equal(shouldFetchHits("S", null), false);
});

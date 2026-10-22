import assert from "node:assert/strict";
import { it } from "node:test";

import { waitingMessage } from "./format.ts";

it("signale un worker sans doute éteint après 5 minutes d'attente", () => {
  const now = new Date("2026-10-22T12:00:00Z");
  assert.equal(waitingMessage("2026-10-22T11:58:00Z", now), "En attente du traitement…");
  assert.match(waitingMessage("2026-10-22T11:50:00Z", now), /éteint/);
});

// Best-effort AI-account-identity scraping. HONEST LIMITATION, documented per the plan: these
// selectors are NOT verified against live authenticated sessions on each platform (this
// environment has no way to load a real logged-in Claude/ChatGPT/Gemini account to check exact
// current DOM structure), and account-menu markup changes on every UI redesign. Implemented as
// one generic heuristic — look for email-shaped text inside likely account/profile UI regions —
// rather than fabricated per-site selectors presented as verified. Report this as a known
// fragility, not a solved problem, when writing up this module.
import type { ExtensionMessage } from "../../shared/messages";

const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;
const ACCOUNT_REGION_SELECTOR =
  '[aria-label*="account" i], [aria-label*="profile" i], [aria-label*="user" i], ' +
  'button[data-testid*="account" i], button[data-testid*="profile" i], ' +
  '[class*="account-menu" i], [class*="user-menu" i], [class*="profile-menu" i]';

function scanGeneric(): string | null {
  const regions = document.querySelectorAll(ACCOUNT_REGION_SELECTOR);
  for (const region of regions) {
    const text = [
      region.textContent ?? "",
      region.getAttribute("aria-label") ?? "",
      region.getAttribute("title") ?? "",
    ].join(" ");
    const match = text.match(EMAIL_RE);
    if (match) return match[0];
  }
  return null;
}

let lastSighting: string | null = null;
let lastSentAt = 0;
const RESCAN_INTERVAL_MS = 30_000;

function tick() {
  const now = Date.now();
  if (now - lastSentAt < RESCAN_INTERVAL_MS) return;
  const identity = scanGeneric();
  if (!identity || identity === lastSighting) return;
  lastSighting = identity;
  lastSentAt = now;
  const message: ExtensionMessage = {
    type: "account_sighting",
    payload: { platform: location.hostname, account_identity: identity },
  };
  chrome.runtime.sendMessage(message);
}

setInterval(tick, RESCAN_INTERVAL_MS);
window.addEventListener("DOMContentLoaded", tick);

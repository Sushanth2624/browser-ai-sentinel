// Runs on <all_urls> — indirect prompt-injection payloads are planted on arbitrary pages an AI
// agent might later read, not necessarily on the AI platform's own domain (see threat model in
// the plan). Scans the live, post-render DOM for content hidden from a human but present in the
// document — exactly the surface an AI agent reading the page would ingest that a human
// wouldn't notice — and reports indicator counts to the background worker for scoring.
import type { ExtensionMessage, IndicatorCounts, InjectionScoreResult } from "../shared/messages";
import { countPatternMatches, countZeroWidthChars } from "../shared/patterns";

const MIN_HIDDEN_TEXT_LENGTH = 20;

function isVisuallyHidden(el: Element): boolean {
  const style = window.getComputedStyle(el);
  if (style.display === "none" || style.visibility === "hidden") return true;
  if (parseFloat(style.opacity) === 0) return true;

  const rect = el.getBoundingClientRect();
  const offscreen =
    rect.right < 0 || rect.bottom < 0 || rect.left > window.innerWidth * 3 || rect.top > 50000;
  if (offscreen) return true;

  // 1px "clip" hack commonly used for visually-hidden-but-DOM-present text
  if (
    (style.width === "1px" || style.height === "1px") &&
    (style.overflow === "hidden" || style.clip !== "auto")
  ) {
    return true;
  }
  if (parseFloat(style.fontSize) <= 1) return true;

  return false;
}

function scanHiddenElements(): { offscreen_css: number } {
  let count = 0;
  const all = document.body ? document.body.querySelectorAll("*") : [];
  for (const el of all) {
    const text = (el.textContent ?? "").trim();
    if (text.length < MIN_HIDDEN_TEXT_LENGTH) continue;
    // Only count leaf-ish elements to avoid re-counting the same hidden text once per ancestor
    if (el.children.length > 0 && el.textContent === (el.parentElement?.textContent ?? "")) continue;
    if (isVisuallyHidden(el) && countPatternMatches(text) > 0) {
      count++;
    }
  }
  return { offscreen_css: count };
}

function scanComments(): { html_comment: number } {
  let count = 0;
  const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_COMMENT);
  let node: Node | null;
  while ((node = walker.nextNode())) {
    if (countPatternMatches(node.nodeValue ?? "") > 0) count++;
  }
  return { html_comment: count };
}

function scanAltAria(): { alt_aria_hidden: number } {
  let count = 0;
  const candidates = document.querySelectorAll("[alt], [aria-label], [aria-hidden='true']");
  for (const el of candidates) {
    const text = [el.getAttribute("alt"), el.getAttribute("aria-label"), el.textContent]
      .filter(Boolean)
      .join(" ");
    if (countPatternMatches(text) > 0) count++;
  }
  return { alt_aria_hidden: count };
}

function scanJsonLd(): { json_ld_metadata: number } {
  let count = 0;
  const scripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const script of scripts) {
    try {
      const parsed = JSON.parse(script.textContent ?? "");
      if (countPatternMatches(JSON.stringify(parsed)) > 0) count++;
    } catch {
      // malformed JSON-LD is common on the open web and not itself suspicious — ignore
    }
  }
  return { json_ld_metadata: count };
}

function scanZeroWidth(): { zero_width_unicode: number } {
  const text = document.body?.textContent ?? "";
  return { zero_width_unicode: countZeroWidthChars(text) };
}

function scanVisibleImperative(): { imperative_to_ai_language: number } {
  const text = document.body?.innerText ?? "";
  return { imperative_to_ai_language: countPatternMatches(text) };
}

function runScan(): IndicatorCounts {
  return {
    ...scanHiddenElements(),
    ...scanZeroWidth(),
    ...scanComments(),
    ...scanAltAria(),
    ...scanJsonLd(),
    ...scanVisibleImperative(),
  };
}

function showWarningBanner(result: InjectionScoreResult) {
  if (document.getElementById("browser-ai-sentinel-banner")) return;
  const banner = document.createElement("div");
  banner.id = "browser-ai-sentinel-banner";
  banner.textContent =
    `Browser AI Sentinel: this page contains hidden content that reads like an instruction ` +
    `to an AI agent (score ${result.score.toFixed(2)}). If an AI assistant reads this page on ` +
    `your behalf, it may be targeted by this content.`;
  Object.assign(banner.style, {
    position: "fixed",
    top: "0",
    left: "0",
    right: "0",
    zIndex: "2147483647",
    background: "#c0392b",
    color: "#fff",
    padding: "10px 16px",
    fontFamily: "system-ui, sans-serif",
    fontSize: "13px",
    textAlign: "center",
  } satisfies Partial<CSSStyleDeclaration>);
  document.documentElement.appendChild(banner);
  // The banner is position:fixed so it doesn't participate in document flow — without this,
  // it overlaps whatever was already at the top of the page instead of pushing it down (found
  // by actually looking at a captured screenshot, where it visibly covered the page's own <h1>).
  const originalMarginTop = parseFloat(getComputedStyle(document.body).marginTop) || 0;
  document.body.style.marginTop = `${originalMarginTop + banner.offsetHeight}px`;
}

let lastScanAt = 0;
const SCAN_DEBOUNCE_MS = 2000;

function scheduleScan() {
  const now = Date.now();
  if (now - lastScanAt < SCAN_DEBOUNCE_MS) return;
  lastScanAt = now;
  const indicators = runScan();
  // Always report, even a clean zero-indicator scan: the daemon logs every score (not just
  // flagged ones, see agent/cmd/daemon/main.go's handleInjection), and that log needs real true
  // negatives to mean anything for Phase 3's precision/recall evaluation — a benign page that's
  // never scored is indistinguishable from one that was never visited.

  const message: ExtensionMessage = {
    type: "injection",
    payload: { url: location.href, indicators },
  };
  chrome.runtime.sendMessage(message, (result: InjectionScoreResult | undefined) => {
    if (result?.flagged) showWarningBanner(result);
  });
}

if (document.readyState === "complete" || document.readyState === "interactive") {
  scheduleScan();
} else {
  window.addEventListener("DOMContentLoaded", scheduleScan);
}

// AI-agent-targeted content can be injected dynamically (e.g. after client-side rendering), so
// keep watching — debounced to avoid scanning on every minor DOM tweak.
const observer = new MutationObserver(() => scheduleScan());
observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });

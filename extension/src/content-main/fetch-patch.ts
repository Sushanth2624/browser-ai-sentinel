// Runs in the MAIN world (page's own JS context) on known-AI-domain pages, at document_start —
// must patch fetch/XHR before the page's own scripts grab a reference to the originals. Cannot
// call chrome.* APIs directly (MV3 MAIN-world restriction), so classification requests go via
// window.postMessage to content-isolated/relay.ts, which bridges to the background worker.
//
// Only requests carrying a body are inspected — GETs for static assets/analytics aren't where
// a user's own typed/pasted/uploaded content leaves the machine.

const MAIN_TO_ISOLATED = "bas-main";
const ISOLATED_TO_MAIN = "bas-isolated";
const MAX_INSPECTED_TEXT_BYTES = 200_000; // cap: large binary uploads aren't text-scannable anyway

let requestSeq = 0;
const pending = new Map<string, (approved: boolean) => void>();

window.addEventListener("message", (event: MessageEvent) => {
  if (event.source !== window) return;
  const data = event.data as { source?: string; requestId?: string; approved?: boolean } | undefined;
  if (!data || data.source !== ISOLATED_TO_MAIN || !data.requestId) return;
  const resolve = pending.get(data.requestId);
  if (!resolve) return;
  pending.delete(data.requestId);
  resolve(Boolean(data.approved));
});

function requestApproval(text: string): Promise<boolean> {
  if (!text.trim()) return Promise.resolve(true);
  return new Promise((resolve) => {
    const requestId = `${Date.now()}-${++requestSeq}`;
    pending.set(requestId, resolve);
    window.postMessage(
      { source: MAIN_TO_ISOLATED, requestId, platform: location.hostname, text: text.slice(0, MAX_INSPECTED_TEXT_BYTES) },
      location.origin
    );
    // fail-open on a relay/background outage after a short wait — Phase 1 dev-friendliness;
    // background's own approval flow has its own longer fail-CLOSED timeout for the case where
    // the relay is reachable but the user just doesn't respond (see service-worker.ts).
    setTimeout(() => {
      if (pending.has(requestId)) {
        pending.delete(requestId);
        resolve(true);
      }
    }, 5000);
  });
}

async function extractBodyText(body: BodyInit | null | undefined): Promise<string> {
  if (!body) return "";
  if (typeof body === "string") return body;
  if (body instanceof URLSearchParams) return body.toString();
  if (body instanceof FormData) {
    const parts: string[] = [];
    for (const [key, value] of body.entries()) {
      if (typeof value === "string") {
        parts.push(`${key}=${value}`);
      } else {
        parts.push(`${key}=<file:${value.name}>`);
        if (value.size > 0 && value.size < MAX_INSPECTED_TEXT_BYTES && looksTextLike(value.type)) {
          try {
            parts.push(await value.text());
          } catch {
            // unreadable file content — filename alone still went through the entity scan above
          }
        }
      }
    }
    return parts.join("\n");
  }
  if (body instanceof Blob) {
    if (body.size < MAX_INSPECTED_TEXT_BYTES && looksTextLike(body.type)) {
      try {
        return await body.text();
      } catch {
        return "";
      }
    }
    return `<blob:${body.size} bytes>`;
  }
  return ""; // ArrayBuffer/ReadableStream bodies: out of scope for Phase 1 text scanning
}

function looksTextLike(mimeType: string): boolean {
  return (
    mimeType === "" ||
    mimeType.startsWith("text/") ||
    mimeType.includes("json") ||
    mimeType.includes("csv") ||
    mimeType.includes("xml")
  );
}

const originalFetch = window.fetch.bind(window);
window.fetch = async function patchedFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const bodyText = await extractBodyText(init?.body ?? null);
  if (!bodyText.trim()) return originalFetch(input, init);

  const approved = await requestApproval(bodyText);
  if (!approved) {
    throw new DOMException("Blocked by Browser AI Sentinel: sensitive content not approved for send", "AbortError");
  }
  return originalFetch(input, init);
};

const OriginalXHR = window.XMLHttpRequest;
class PatchedXMLHttpRequest extends OriginalXHR {
  send(body?: Document | XMLHttpRequestBodyInit | null): void {
    const bodyText = typeof body === "string" ? body : "";
    if (!bodyText.trim()) {
      super.send(body);
      return;
    }
    requestApproval(bodyText).then((approved) => {
      if (approved) {
        super.send(body);
      } else {
        this.dispatchEvent(new ProgressEvent("error"));
      }
    });
  }
}
window.XMLHttpRequest = PatchedXMLHttpRequest;

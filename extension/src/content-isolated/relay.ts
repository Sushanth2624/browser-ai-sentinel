// Runs in the ISOLATED world on known-AI-domain pages. MAIN-world scripts (content-main) can't
// call chrome.* APIs directly, so this relay bridges window.postMessage <-> chrome.runtime
// messaging. Also fires the Phase-1 platform_check on load (see plan: real platform ID moves to
// Zeek/Suricata in Phase 2, this is the domain-stub).
import type { ExtensionMessage } from "../shared/messages";

const MAIN_TO_ISOLATED = "bas-main";
const ISOLATED_TO_MAIN = "bas-isolated";

interface BridgeRequest {
  source: typeof MAIN_TO_ISOLATED;
  requestId: string;
  platform: string;
  text: string;
}

window.addEventListener("message", (event: MessageEvent) => {
  if (event.source !== window) return;
  const data = event.data as Partial<BridgeRequest> | undefined;
  if (!data || data.source !== MAIN_TO_ISOLATED || !data.requestId) return;

  const message: ExtensionMessage = {
    type: "dlp_check",
    payload: { platform: data.platform ?? location.hostname, text: data.text ?? "" },
  };

  chrome.runtime.sendMessage(message, (response: { approved: boolean; verdict: string } | undefined) => {
    window.postMessage(
      {
        source: ISOLATED_TO_MAIN,
        requestId: data.requestId,
        approved: response?.approved ?? false,
        verdict: response?.verdict ?? "error",
      },
      location.origin
    );
  });
});

// Phase 1 platform-ID stub: fire once per page load, on the known-AI-domain content script.
chrome.runtime.sendMessage({
  type: "platform_check",
  payload: { domain: location.hostname },
} satisfies ExtensionMessage);

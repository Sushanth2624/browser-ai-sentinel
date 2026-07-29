// Background service worker — the only place that talks to the native host. Content scripts
// never call chrome.runtime.connectNative directly; they send an ExtensionMessage via
// chrome.runtime.sendMessage and this worker relays it 1:1 to the Go daemon (through nmhost)
// and applies any side effects (approval-gate prompt, badge counts) before responding.
import type {
  DLPCheckResult,
  ExtensionMessage,
  IndicatorCounts,
  InjectionScoreResult,
  NMResponse,
} from "../shared/messages";

const NATIVE_HOST_NAME = "com.browseraisentinel.nmhost";

let nativePort: chrome.runtime.Port | null = null;
let requestSeq = 0;
const pendingRequests = new Map<
  number,
  { resolve: (r: NMResponse) => void; reject: (e: Error) => void }
>();

function getNativePort(): chrome.runtime.Port {
  if (nativePort) return nativePort;
  const port = chrome.runtime.connectNative(NATIVE_HOST_NAME);
  port.onMessage.addListener((msg: NMResponse & { __reqId?: number }) => {
    // nmhost/daemon don't know about request correlation — this worker matches responses to
    // requests strictly by arrival order per port, which is safe because native messaging
    // preserves message ordering on a single port and every request here awaits its response
    // before sending the next one (see callNative's queueing below).
    const next = pendingRequests.values().next();
    if (!next.done) {
      pendingRequests.delete([...pendingRequests.keys()][0]);
      next.value.resolve(msg);
    }
  });
  port.onDisconnect.addListener(() => {
    nativePort = null;
    const err = chrome.runtime.lastError;
    for (const { reject } of pendingRequests.values()) {
      reject(new Error(err?.message ?? "native host disconnected"));
    }
    pendingRequests.clear();
  });
  nativePort = port;
  return port;
}

// Native messaging ports are strictly ordered but this worker may receive several
// chrome.runtime.sendMessage calls concurrently from content scripts across tabs, so calls are
// serialized through a single in-flight queue rather than risking response mis-matching.
let callChain: Promise<unknown> = Promise.resolve();

function callNative(message: ExtensionMessage): Promise<NMResponse> {
  const run = () =>
    new Promise<NMResponse>((resolve, reject) => {
      const id = ++requestSeq;
      pendingRequests.set(id, { resolve, reject });
      try {
        getNativePort().postMessage(message);
      } catch (err) {
        pendingRequests.delete(id);
        reject(err instanceof Error ? err : new Error(String(err)));
      }
    });
  const result = callChain.then(run, run);
  callChain = result.catch(() => undefined);
  return result as Promise<NMResponse>;
}

// --- Approval gate for flagged DLP events -----------------------------------------------

const pendingApprovals = new Map<string, (approved: boolean) => void>();

function requestApproval(dlpEventId: number, platform: string, entityTypes: string[]): Promise<boolean> {
  return new Promise((resolve) => {
    const notificationId = `dlp-${dlpEventId}`;
    pendingApprovals.set(notificationId, resolve);
    chrome.notifications.create(notificationId, {
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "Browser AI Sentinel — sensitive data detected",
      message: `Content bound for ${platform} contains: ${entityTypes.join(", ")}. Allow send?`,
      buttons: [{ title: "Allow" }, { title: "Block" }],
      requireInteraction: true,
      priority: 2,
    });
  });
}

chrome.notifications.onButtonClicked.addListener((notificationId, buttonIndex) => {
  const resolve = pendingApprovals.get(notificationId);
  if (!resolve) return;
  pendingApprovals.delete(notificationId);
  chrome.notifications.clear(notificationId);
  resolve(buttonIndex === 0); // 0 = Allow, 1 = Block
});

// Auto-deny (fail closed) if the user never interacts — matches an IDS/DLP posture where an
// unacknowledged sensitive-data send should not silently go through.
const APPROVAL_TIMEOUT_MS = 30_000;

async function handleDLPCheck(payload: { platform: string; text: string }): Promise<{
  approved: boolean;
  verdict: string;
}> {
  const resp = await callNative({ type: "dlp_check", payload });
  if (!resp.ok || !resp.result) {
    return { approved: false, verdict: "error" };
  }
  const result = resp.result as DLPCheckResult;
  if (result.verdict !== "flagged") {
    return { approved: true, verdict: result.verdict };
  }

  const entityTypes = result.matched_entities.map((e) => e.type);
  const approvalPromise = requestApproval(result.dlp_event_id, payload.platform, entityTypes);
  const timeoutPromise = new Promise<boolean>((resolve) =>
    setTimeout(() => resolve(false), APPROVAL_TIMEOUT_MS)
  );
  const approved = await Promise.race([approvalPromise, timeoutPromise]);

  await callNative({
    type: "dlp_decision",
    payload: { dlp_event_id: result.dlp_event_id, approved },
  });

  return { approved, verdict: result.verdict };
}

// --- Injection alert badge ---------------------------------------------------------------

let injectionAlertCount = 0;

async function handleInjection(payload: { url: string; indicators: IndicatorCounts }) {
  const resp = await callNative({ type: "injection", payload });
  if (resp.ok && resp.result) {
    const result = resp.result as InjectionScoreResult;
    if (result.flagged) {
      injectionAlertCount++;
      chrome.action.setBadgeText({ text: String(injectionAlertCount) });
      chrome.action.setBadgeBackgroundColor({ color: "#c0392b" });
    }
    return result;
  }
  return { score: 0, flagged: false, contributing_indicators: {} };
}

// --- Message router --------------------------------------------------------------------

chrome.runtime.onMessage.addListener((message: ExtensionMessage, _sender, sendResponse) => {
  (async () => {
    switch (message.type) {
      case "dlp_check":
        sendResponse(await handleDLPCheck(message.payload));
        return;
      case "injection":
        sendResponse(await handleInjection(message.payload));
        return;
      case "platform_check":
      case "account_sighting":
      case "dlp_decision":
        sendResponse(await callNative(message));
        return;
    }
  })();
  return true; // keep the message channel open for the async response above
});

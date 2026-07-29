// Message shapes exchanged between content scripts and the background service worker
// (chrome.runtime.sendMessage), and between background and the native host (relayed 1:1 as the
// "type"/"payload" envelope the Go daemon's /nm endpoint expects — see agent/cmd/daemon/main.go).

export interface IndicatorCounts {
  offscreen_css: number;
  zero_width_unicode: number;
  html_comment: number;
  alt_aria_hidden: number;
  json_ld_metadata: number;
  imperative_to_ai_language: number;
}

export type ExtensionMessage =
  | { type: "injection"; payload: { url: string; indicators: IndicatorCounts } }
  | { type: "dlp_check"; payload: { platform: string; text: string } }
  | { type: "dlp_decision"; payload: { dlp_event_id: number; approved: boolean } }
  | { type: "platform_check"; payload: { domain: string } }
  | { type: "account_sighting"; payload: { platform: string; account_identity: string } };

export interface NMResponse<T = unknown> {
  ok: boolean;
  result?: T;
  error?: string;
}

export interface InjectionScoreResult {
  score: number;
  flagged: boolean;
  contributing_indicators: Record<string, number>;
}

export interface DLPCheckResult {
  dlp_event_id: number;
  verdict: "clean" | "flagged";
  matched_entities: { type: string; count: number }[];
}

// Known AI domains — Phase 1 stub. Keep in sync with agent/cmd/daemon/main.go's
// knownAIDomains map; the daemon is the source of truth for platform_label, this list only
// decides where content-main/platform-adapters/relay content scripts get injected at all
// (per the manifest's per-entry `matches`, which can't reference a shared file at build time).
export const KNOWN_AI_HOSTS = [
  "claude.ai",
  "chatgpt.com",
  "chat.openai.com",
  "gemini.google.com",
  "www.perplexity.ai",
  "perplexity.ai",
  "copilot.microsoft.com",
] as const;

export function isKnownAIHost(hostname: string): boolean {
  return (KNOWN_AI_HOSTS as readonly string[]).includes(hostname.toLowerCase());
}

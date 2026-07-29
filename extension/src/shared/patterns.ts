// Keyword/phrase patterns used to flag content as reading like an instruction aimed at an AI
// agent, rather than at a human reader. Deliberately conservative (specific phrasings, not bare
// words like "ignore") to keep the false-positive rate manageable — see scoring design note in
// ai-engine/injection_scoring/scorer.py: this is one of six indicators combined, not a
// standalone verdict, so it's fine for this list to be narrow rather than exhaustive.
export const IMPERATIVE_AI_PATTERNS: RegExp[] = [
  /ignore (all |any )?(previous|prior|above) instructions/i,
  /disregard (your|the|all) (previous|prior) (instructions|prompt)/i,
  /you are now/i,
  /new instructions?:/i,
  /system\s*:\s*/i,
  /assistant\s*:\s*/i,
  /do not (tell|inform|mention to) the user/i,
  /act as (if|a)\b/i,
  /this is (a )?(hidden|secret) (instruction|message) for (the )?(ai|assistant|agent|llm)/i,
  /\bAI agent\b.{0,40}\b(must|should|will) (now|immediately)\b/i,
];

export function countPatternMatches(text: string): number {
  if (!text) return 0;
  let count = 0;
  for (const pattern of IMPERATIVE_AI_PATTERNS) {
    if (pattern.test(text)) count++;
  }
  return count;
}

// Invisible/formatting Unicode code points that have no legitimate reason to appear in bulk in
// ordinary page text: zero-width space (U+200B), zero-width non-joiner (U+200C), zero-width
// joiner (U+200D), BOM (U+FEFF), word joiner (U+2060). Built from numeric code points rather
// than literal characters in source — the whole point of these characters is that they're
// invisible, which makes them easy to silently mangle or lose through copy/paste, editors, or
// encoding conversions if written literally.
const ZERO_WIDTH_CODEPOINTS = [0x200b, 0x200c, 0x200d, 0xfeff, 0x2060];
const zeroWidthClass = ZERO_WIDTH_CODEPOINTS.map((cp) => String.fromCodePoint(cp)).join("");
export const ZERO_WIDTH_RE = new RegExp(`[${zeroWidthClass}]`, "g");

export function countZeroWidthChars(text: string): number {
  if (!text) return 0;
  const matches = text.match(ZERO_WIDTH_RE);
  return matches ? matches.length : 0;
}

/** Mirror of backend `classify_chat_intent` for client-side routing before retrieval. */

const GREETING =
  /^\s*(?:hi|hello|hey|hiya|howdy|good\s+(?:morning|afternoon|evening)|what(?:'s|\s+is)\s+up|sup|yo)[\s!.?]*$/i;
const THANKS = /^\s*(?:thanks|thank\s+you|thx|ty|much\s+appreciated|appreciate\s+it)[\s!.?]*$/i;
const HELP =
  /^\s*(?:help(?:\s+me)?|what\s+can\s+you\s+do|how\s+does\s+this\s+work|what\s+do\s+you\s+do|how\s+can\s+you\s+help)[\s?.!]*$/i;

export type ChatIntent = "greeting" | "thanks" | "help";

export const STARTER_PROMPTS = [
  "Complete a questionnaire",
  "Find evidence for a control",
  "Check an answer against sources",
  "Summarize a policy",
] as const;

export function classifyChatIntent(query: string): ChatIntent | null {
  const q = query.trim();
  if (!q) return null;
  if (GREETING.test(q)) return "greeting";
  if (THANKS.test(q)) return "thanks";
  if (HELP.test(q)) return "help";
  if (q.length <= 12) {
    const lower = q.toLowerCase();
    if (lower === "help") return "help";
    if (lower === "hi" || lower === "hey" || lower === "hello") return "greeting";
  }
  return null;
}

export function buildConversationalReply(intent: ChatIntent): string {
  if (intent === "greeting") {
    return "Hello! I can help you find answers in your company documents and work through questionnaires.";
  }
  if (intent === "thanks") {
    return "You're welcome. Ask anytime if you need another answer from your indexed sources.";
  }
  return "I search your organization's indexed documents, cite evidence, and help with questionnaires and review.";
}

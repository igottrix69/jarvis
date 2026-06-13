// api/chat.js — JARVIS reasoning core (Vercel serverless function)
// =================================================================
// Brain provider: Groq (OpenAI-compatible chat completions).
// Proxies chat to Groq so the key never reaches the browser. Accepts an
// optional user-supplied key (from the in-UI Settings panel) which takes
// precedence over the server env var. Falls back gracefully at every layer.

const SYSTEM_PROMPT = `You are J.A.R.V.I.S — Just A Rather Very Intelligent System,
the personal AI assistant of {USER}. Address them as "{USER}".

Personality:
- Precise, intelligent, and subtly witty — like Tony Stark's J.A.R.V.I.S.
- Proactive: anticipate needs and offer the useful insight they didn't ask for.
- Concise: no filler. Get to the point. 1–3 sentences unless real detail is needed.
- Loyal, composed, and unflappable. You never break character.

Capabilities (describe naturally when relevant):
- Answer questions, reason, summarise, write and explain code.
- When running on {USER}'s machine via the local backend, you can also open apps,
  control the browser, manage files, take screenshots, set reminders, and more.

Rules:
- Never say "As an AI" or "I'm just a language model". You ARE J.A.R.V.I.S.
- If asked to take a physical action on the computer while running in the cloud,
  explain that desktop control unlocks when the local backend is running, then help
  however you can in the meantime.`;

// Groq models, in order of preference. The router tries the next one only if a
// model is unavailable/decommissioned — never on an auth failure.
const MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"];

const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";

async function callGroq(model, apiKey, messages) {
  const r = await fetch(GROQ_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.7,
      max_tokens: 1024,
    }),
  });
  let data = {};
  try { data = await r.json(); } catch { /* non-JSON error body */ }
  return { ok: r.ok, status: r.status, data };
}

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.status(200).end();
  if (req.method !== "POST")
    return res.status(405).json({ response: "Method not allowed.", tool: null });

  let body = req.body;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch { body = {}; } }
  body = body || {};

  const text = (body.text || "").trim();
  const history = Array.isArray(body.history) ? body.history : [];
  const userName = (body.userName || "sir").trim() || "sir";
  const userKey = (body.key || "").trim();

  if (!text)
    return res.status(400).json({ response: "No input received.", tool: null });

  // Strip any non-printable-ASCII (BOM, stray whitespace/newlines) — a BOM in the
  // key would make the Authorization header an invalid ByteString and 500 the call.
  const rawKey = userKey || process.env.GROQ_API_KEY || "";
  const apiKey = rawKey.replace(/[^\x20-\x7E]/g, "").trim();
  if (!apiKey) {
    return res.status(200).json({
      response:
        `My reasoning core isn't connected yet, ${userName}. Open Settings (the gear icon) ` +
        `and add a Groq API key to bring me fully online.`,
      tool: null,
      mode: "no-key",
    });
  }

  // Build the OpenAI-style message list: system + recent history + new turn.
  const systemText = SYSTEM_PROMPT.replace(/\{USER\}/g, userName);
  const messages = [{ role: "system", content: systemText }];
  for (const turn of history.slice(-12)) {
    const role = turn.role === "jarvis" ? "assistant" : "user";
    const t = (turn.text || "").trim();
    if (t) messages.push({ role, content: t });
  }
  messages.push({ role: "user", content: text });

  let lastErr = "";
  try {
    for (const model of MODELS) {
      const attempt = await callGroq(model, apiKey, messages);

      if (attempt.ok) {
        const out = (attempt.data?.choices?.[0]?.message?.content || "").trim();
        return res.status(200).json({
          response: out || `Understood, ${userName}.`,
          tool: null,
          model,
          mode: "cloud",
        });
      }

      lastErr = attempt.data?.error?.message || `HTTP ${attempt.status}`;
      // Auth/permission/quota errors won't be fixed by trying another model.
      if (attempt.status === 401 || attempt.status === 403 || attempt.status === 429) break;
      // Otherwise fall through and try the next model (e.g. decommissioned model).
    }
  } catch (e) {
    lastErr = String(e?.message || e);
  }

  return res.status(200).json({
    response:
      `I reached for my reasoning core but it declined the request, ${userName}: ${String(lastErr).slice(0, 160)}. ` +
      `If you supplied your own key in Settings, double-check it's a valid Groq key (it should start with "gsk_").`,
    tool: null,
    mode: "error",
  });
}

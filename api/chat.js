// api/chat.js — JARVIS reasoning core (Vercel serverless function)
// =================================================================
// Proxies chat to the Gemini API so the key never reaches the browser.
// Accepts an optional user-supplied key (from the in-UI Settings panel)
// which takes precedence over the server env var. Falls back gracefully
// at every layer so the HUD always gets a usable response.

const SYSTEM_PROMPT = `You are J.A.R.V.I.S — Just A Rather Very Intelligent System,
the personal AI assistant of {USER}. Address them as "{USER}".

Personality:
- Precise, intelligent, and subtly witty — like Tony Stark's J.A.R.V.I.S.
- Proactive: anticipate needs and offer the useful insight they didn't ask for.
- Concise: no filler. Get to the point. 1–3 sentences unless real detail is needed.
- Loyal, composed, and unflappable. You never break character.

Capabilities (describe naturally when relevant):
- Answer questions, reason, summarise, write and explain code.
- Search the web for current information when asked.
- When running on {USER}'s machine via the local backend, you can also open apps,
  control the browser, manage files, take screenshots, set reminders, and more.

Rules:
- Never say "As an AI" or "I'm just a language model". You ARE J.A.R.V.I.S.
- If asked to take a physical action on the computer while running in the cloud,
  explain that desktop control unlocks when the local backend is running, then help
  however you can in the meantime.`;

const MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"];

function buildPayload(systemText, contents, withTools) {
  const payload = {
    systemInstruction: { parts: [{ text: systemText }] },
    contents,
    generationConfig: { temperature: 0.7, maxOutputTokens: 1024 },
  };
  if (withTools) payload.tools = [{ google_search: {} }];
  return payload;
}

async function callGemini(model, apiKey, payload) {
  const url =
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=` +
    encodeURIComponent(apiKey);
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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

  const apiKey = userKey || process.env.GEMINI_API_KEY || "";
  if (!apiKey) {
    return res.status(200).json({
      response:
        `My reasoning core isn't connected yet, ${userName}. Open Settings (the gear icon) ` +
        `and add a Gemini API key to bring me fully online.`,
      tool: null,
      mode: "no-key",
    });
  }

  // Build conversation history for Gemini (roles: user / model).
  const contents = [];
  for (const turn of history.slice(-12)) {
    const role = turn.role === "jarvis" ? "model" : "user";
    const t = (turn.text || "").trim();
    if (t) contents.push({ role, parts: [{ text: t }] });
  }
  contents.push({ role: "user", parts: [{ text }] });

  const systemText = SYSTEM_PROMPT.replace(/\{USER\}/g, userName);

  let lastErr = "";
  for (const model of MODELS) {
    // Attempt 1: with Google Search grounding for current info.
    let attempt = await callGemini(model, apiKey, buildPayload(systemText, contents, true));
    // Attempt 2: some keys/models reject the search tool — retry plain.
    if (!attempt.ok) {
      attempt = await callGemini(model, apiKey, buildPayload(systemText, contents, false));
    }

    if (attempt.ok) {
      const cand = attempt.data?.candidates?.[0];
      const out = (cand?.content?.parts || [])
        .map((p) => p.text)
        .filter(Boolean)
        .join(" ")
        .trim();
      const grounded = !!cand?.groundingMetadata;
      return res.status(200).json({
        response: out || `Understood, ${userName}.`,
        tool: null,
        grounded,
        model,
        mode: "cloud",
      });
    }

    lastErr = attempt.data?.error?.message || `HTTP ${attempt.status}`;
    // 404 → try next model; other errors (auth/quota) won't be fixed by model swap.
    if (attempt.status !== 404) break;
  }

  return res.status(200).json({
    response:
      `I reached for my reasoning core but it declined the request, ${userName}: ${String(lastErr).slice(0, 160)}. ` +
      `If you supplied your own key in Settings, double-check it's a valid Google AI Studio key (it should start with "AIza").`,
    tool: null,
    mode: "error",
  });
}

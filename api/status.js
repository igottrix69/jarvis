// api/status.js — JARVIS health check (Vercel serverless function)
// Reports whether the reasoning core is configured, without leaking the key.

export default function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.status(200).json({
    status: "online",
    core: process.env.GEMINI_API_KEY ? "connected" : "no-key",
    runtime: "vercel-serverless",
    time: new Date().toISOString(),
  });
}

export async function onRequestPost({ request, env }) {
  try {
    // Accept JSON even if the header is missing/mis-set
    const body = await request.json().catch(() => null);
    if (!body) return json({ ok: false, error: "bad_json" }, 400);

    const email = String(body?.email || "").trim();
    const channels = body?.channels || {};
    const wantEmail = (channels.email === undefined) ? !!email : !!channels.email;

    if (!wantEmail) return json({ ok: false, error: "no_channel" }, 400);
    if (!looksLikeEmail(email)) return json({ ok: false, error: "bad_email" }, 400);

    if (!env?.NOTIFY_KV) return json({ ok: false, error: "kv_not_configured" }, 500);
    if (!env?.NOTIFY_KEY) return json({ ok: false, error: "key_not_configured" }, 500);

    const keyBytes = await normalizeKeyBytes(String(env.NOTIFY_KEY || ""));
    const aesKey = await crypto.subtle.importKey("raw", keyBytes, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);

    const now = Date.now();
    const payload = {
      email,
      channels: { email: true },
      created: now,
      v: 2
    };

    const enc = await aesGcmEncrypt(JSON.stringify(payload), aesKey);

    const subId = await hmacId(keyBytes, email.toLowerCase());
    const rec = {
      v: 2,
      created: now,
      channels: payload.channels,
      enc
    };

    await env.NOTIFY_KV.put(`sub:${subId}`, JSON.stringify(rec));

    return json({ ok: true, id: subId }, 200);
  } catch (e) {
    return json({ ok: false, error: "server_error" }, 500);
  }
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store"
    }
  });
}

function looksLikeEmail(v) {
  v = String(v || "").trim();
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v);
}

function tryBase64ToBytes(input) {
  try {
    const cleaned = String(input || "").replace(/[\s\r\n]+/g, "");
    const bin = atob(cleaned);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  } catch {
    return null;
  }
}

/**
 * Supports:
 * - base64 32 bytes (recommended)
 * - any other string (derives 32 bytes with SHA-256)
 */
async function normalizeKeyBytes(secret) {
  const b = tryBase64ToBytes(secret);
  if (b && b.byteLength === 32) return b;

  const src = (b && b.byteLength) ? b : new TextEncoder().encode(String(secret || ""));
  const hash = await crypto.subtle.digest("SHA-256", src);
  return new Uint8Array(hash);
}

function bytesToB64(bytes) {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

function base64UrlFromBytes(bytes) {
  return bytesToB64(bytes).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

async function hmacId(secretBytes, message) {
  const key = await crypto.subtle.importKey("raw", secretBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(String(message || "")));
  return base64UrlFromBytes(new Uint8Array(sig)).slice(0, 22);
}

async function aesGcmEncrypt(plainText, key) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const pt = new TextEncoder().encode(String(plainText || ""));
  const ctBuf = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, pt);
  return { iv: bytesToB64(iv), ct: bytesToB64(new Uint8Array(ctBuf)) };
}

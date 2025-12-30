export async function onRequestPost({ request, env }) {
  try {
    const ct = request.headers.get("content-type") || "";
    if (!ct.includes("application/json")) {
      return json({ ok: false, error: "bad_content_type" }, 400);
    }

    const body = await request.json();
    const email = String(body?.email || "").trim();
    const phone = String(body?.phone || "").trim();
    const channels = body?.channels || {};
    const wantEmail = !!channels.email;
    const wantSms = !!channels.sms;

    if (!wantEmail && !wantSms) return json({ ok: false, error: "no_channel" }, 400);

    if (wantEmail && !looksLikeEmail(email)) return json({ ok: false, error: "bad_email" }, 400);
    if (wantSms && !looksLikePhone(phone)) return json({ ok: false, error: "bad_phone" }, 400);

    if (!env?.NOTIFY_KV) return json({ ok: false, error: "kv_not_configured" }, 500);
    if (!env?.NOTIFY_KEY) return json({ ok: false, error: "key_not_configured" }, 500);

    const now = Date.now();
    const payload = {
      email: wantEmail ? email : "",
      phone: wantSms ? phone : "",
      channels: { email: wantEmail, sms: wantSms },
      created: now,
      v: 1,
    };

    const aesKey = await importAesKey(env.NOTIFY_KEY);
    const enc = await aesGcmEncrypt(JSON.stringify(payload), aesKey);

    const subId = await hmacId(env.NOTIFY_KEY, `${email.toLowerCase()}|${phone}`);
    const rec = {
      v: 1,
      created: now,
      channels: payload.channels,
      enc,
    };

    await env.NOTIFY_KV.put(`sub:${subId}`, JSON.stringify(rec));

    return json({ ok: true, id: subId }, 200);
  } catch (e) {
    return json({ ok: false, error: "server_error" }, 500);
  }
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function looksLikeEmail(s) {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(s || ""));
}
function looksLikePhone(s) {
  return /^\+?[0-9][0-9\s().-]{6,}$/.test(String(s || ""));
}

function b64ToBytes(b64) {
  const bin = atob(String(b64 || "").replace(/[\s\r\n]+/g, ""));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
function bytesToB64(bytes) {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

async function importAesKey(b64Key) {
  // expect 32 bytes base64 (AES-256)
  const raw = b64ToBytes(b64Key);
  if (raw.byteLength !== 32) throw new Error("bad_key_len");
  return crypto.subtle.importKey("raw", raw, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}

async function aesGcmEncrypt(plainText, key) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const pt = new TextEncoder().encode(String(plainText || ""));
  const ctBuf = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, pt);
  return { iv: bytesToB64(iv), ct: bytesToB64(new Uint8Array(ctBuf)) };
}

async function hmacId(secretB64, message) {
  // HMAC-SHA256(secret, message) => short id
  const secret = b64ToBytes(secretB64);
  const key = await crypto.subtle.importKey("raw", secret, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(String(message || "")));
  const b64 = bytesToB64(new Uint8Array(sig)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  return b64.slice(0, 22);
}

/* Portfolio Roblox — app.js
   - UGC (profil + groupe) + favoris + filtre types Roblox
   - Podium 3 derniers UGC (bordure glow uniquement)
   - Zoom image (UGC / Galerie / Commissions)
   - Copier: clic sur Nom / ID
*/

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const state = {
  items: [],
  filtered: [],
  gallery: [],
  commissions: null,
  commView: "models",
};

const TYPE_FR_BY_ID = {
  // Accessories
  8: "Chapeau",
  41: "Cheveux",
  42: "Visage",
  43: "Cou",
  44: "Épaule",
  45: "Avant",
  46: "Dos",
  47: "Taille",
  57: "Oreilles",
  58: "Yeux",
  76: "Sourcils",
  77: "Cils",

  // Clothing (classic)
  2: "T‑Shirt (classique)",
  11: "Haut (classique)",
  12: "Pantalon (classique)",

  // Layered clothing
  64: "T‑Shirt (layered)",
  65: "Haut (layered)",
  66: "Pantalon (layered)",
  67: "Veste",
  68: "Pull",
  69: "Short",
  70: "Chaussure (G)",
  71: "Chaussure (D)",
  72: "Robe / Jupe",

  // Body
  17: "Tête",
  18: "Face",
  27: "Torse",
  28: "Bras (D)",
  29: "Bras (G)",
  30: "Jambe (G)",
  31: "Jambe (D)",
  79: "Tête dynamique",

  // Animations
  24: "Animation",
  48: "Anim • Climb",
  49: "Anim • Death",
  50: "Anim • Fall",
  51: "Anim • Idle",
  52: "Anim • Jump",
  53: "Anim • Run",
  54: "Anim • Swim",
  55: "Anim • Walk",
  56: "Anim • Pose",
  61: "Anim • Emote",
  78: "Anim • Mood",
};

const CATEGORY_BY_TYPE_ID = new Map([
  // Accessories
  [8, "ACCESSORIES"], [41, "ACCESSORIES"], [42, "ACCESSORIES"], [43, "ACCESSORIES"], [44, "ACCESSORIES"],
  [45, "ACCESSORIES"], [46, "ACCESSORIES"], [47, "ACCESSORIES"], [57, "ACCESSORIES"], [58, "ACCESSORIES"],
  [76, "ACCESSORIES"], [77, "ACCESSORIES"],

  // Clothing
  [2, "CLOTHING"], [11, "CLOTHING"], [12, "CLOTHING"],
  [64, "CLOTHING"], [65, "CLOTHING"], [66, "CLOTHING"], [67, "CLOTHING"], [68, "CLOTHING"],
  [69, "CLOTHING"], [70, "CLOTHING"], [71, "CLOTHING"], [72, "CLOTHING"],

  // Body
  [17, "BODY"], [18, "BODY"], [27, "BODY"], [28, "BODY"], [29, "BODY"], [30, "BODY"], [31, "BODY"], [79, "BODY"],

  // Animations
  [24, "ANIMATIONS"], [48, "ANIMATIONS"], [49, "ANIMATIONS"], [50, "ANIMATIONS"], [51, "ANIMATIONS"],
  [52, "ANIMATIONS"], [53, "ANIMATIONS"], [54, "ANIMATIONS"], [55, "ANIMATIONS"], [56, "ANIMATIONS"],
  [61, "ANIMATIONS"], [78, "ANIMATIONS"],
]);

const TYPE_OPTIONS = {
  ALL: [{ key: "ALL", label: "Tous", ids: null }],

  ACCESSORIES: [
    { key: "ALL", label: "Tous", ids: null },
    { key: "HAT", label: "Chapeaux", ids: [8] },
    { key: "HAIR", label: "Cheveux", ids: [41] },
    { key: "FACE", label: "Visage", ids: [42] },
    { key: "NECK", label: "Cou", ids: [43] },
    { key: "SHOULDER", label: "Épaules", ids: [44] },
    { key: "FRONT", label: "Avant", ids: [45] },
    { key: "BACK", label: "Dos", ids: [46] },
    { key: "WAIST", label: "Taille", ids: [47] },
    { key: "EARS", label: "Oreilles", ids: [57] },
    { key: "EYES", label: "Yeux", ids: [58] },
    { key: "EYEBROW", label: "Sourcils", ids: [76] },
    { key: "EYELASH", label: "Cils", ids: [77] },
  ],

  CLOTHING: [
    { key: "ALL", label: "Tous", ids: null },
    { key: "TSHIRT_CLASSIC", label: "T‑Shirts classiques", ids: [2] },
    { key: "SHIRT_CLASSIC", label: "Hauts classiques", ids: [11] },
    { key: "PANTS_CLASSIC", label: "Pantalons classiques", ids: [12] },
    { key: "TSHIRT_LAYER", label: "T‑Shirts (layered)", ids: [64] },
    { key: "SHIRT_LAYER", label: "Hauts (layered)", ids: [65] },
    { key: "PANTS_LAYER", label: "Pantalons (layered)", ids: [66] },
    { key: "JACKET", label: "Vestes", ids: [67] },
    { key: "SWEATER", label: "Pulls", ids: [68] },
    { key: "SHORTS", label: "Shorts", ids: [69] },
    { key: "SHOES", label: "Chaussures", ids: [70, 71] },
    { key: "DRESS", label: "Robes / Jupes", ids: [72] },
  ],

  BODY: [
    { key: "ALL", label: "Tous", ids: null },
    { key: "HEAD", label: "Têtes", ids: [17] },
    { key: "FACE", label: "Faces", ids: [18] },
    { key: "TORSO", label: "Torses", ids: [27] },
    { key: "ARMS", label: "Bras", ids: [28, 29] },
    { key: "LEGS", label: "Jambes", ids: [30, 31] },
    { key: "DYNAMIC_HEAD", label: "Têtes dynamiques", ids: [79] },
  ],

  ANIMATIONS: [
    { key: "ALL", label: "Tous", ids: null },
    { key: "IDLE", label: "Idle", ids: [51] },
    { key: "WALK", label: "Walk", ids: [55] },
    { key: "RUN", label: "Run", ids: [53] },
    { key: "JUMP", label: "Jump", ids: [52] },
    { key: "FALL", label: "Fall", ids: [50] },
    { key: "CLIMB", label: "Climb", ids: [48] },
    { key: "SWIM", label: "Swim", ids: [54] },
    { key: "POSE", label: "Pose", ids: [56] },
    { key: "EMOTE", label: "Emotes", ids: [61] },
    { key: "MOOD", label: "Mood", ids: [78] },
    { key: "OTHER_ANIM", label: "Autres", ids: [24, 49] },
  ],
};

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (m) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  }[m]));
}

function fmtNumber(n) {
  if (!Number.isFinite(n)) return "0";
  return new Intl.NumberFormat("fr-FR").format(n);
}

function fmtDate(ts) {
  if (!Number.isFinite(ts) || ts <= 0) return "—";
  const d = new Date(ts);
  return d.toLocaleDateString("fr-FR", { year: "numeric", month: "short", day: "2-digit" });
}

function normalizeItem(it) {
  const assetId = Number(it.assetId ?? it.id ?? 0);
  const name = String(it.name ?? `Item ${assetId}`);
  const typeId = Number(it.assetTypeId ?? it.assetType ?? it.typeId ?? NaN);
  const typeName = String(it.assetTypeName ?? it.type ?? it.typeName ?? "Autre");
  const typeFr = String(it.typeFr ?? TYPE_FR_BY_ID[typeId] ?? typeName ?? "Autre");

  const favorites = Number(it.favorites ?? it.favoriteCount ?? it.favouriteCount ?? 0);
  const price = Number(it.price ?? it.priceInRobux ?? it.priceInRobux ?? NaN);

  const created = it.created ? String(it.created) : "";
  const createdTs = created ? Date.parse(created) : 0;

  const category = String(it.category ?? CATEGORY_BY_TYPE_ID.get(typeId) ?? "ALL");
  const thumb = String(it.thumb ?? it.thumbnail ?? "");

  return {
    assetId,
    name,
    typeId: Number.isFinite(typeId) ? typeId : null,
    typeName,
    typeFr,
    category,
    favorites: Number.isFinite(favorites) ? favorites : 0,
    price: Number.isFinite(price) ? price : null,
    created,
    createdTs: Number.isFinite(createdTs) ? createdTs : 0,
    thumb,
    creator: String(it.creator ?? ""),
  };
}

function showToast(text) {
  const toast = $("#toast");
  toast.textContent = text;
  toast.classList.add("show");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.remove("show"), 1200);
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    showToast("Copié ✅");
    return true;
  } catch {
    // fallback
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
      showToast("Copié ✅");
      return true;
    } catch {
      showToast("Copie impossible");
      return false;
    }
  }
}

/* Zoom */
function openZoom(src, caption = "") {
  const zoom = $("#zoom");
  const img = $("#zoomImg");
  const cap = $("#zoomCaption");

  img.src = src;
  img.alt = caption || "Image";
  cap.textContent = caption || "";

  zoom.setAttribute("aria-hidden", "false");
}
function closeZoom() {
  const zoom = $("#zoom");
  zoom.setAttribute("aria-hidden", "true");
  $("#zoomImg").src = "";
  $("#zoomCaption").textContent = "";
}

/* Tabs */
function setTab(key) {
  $$(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === key));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${key}`));
}

/* Render podium */
function podiumCard(it, rank) {
  const badge = it.typeFr || "Autre";
  const created = fmtDate(it.createdTs);
  const fav = fmtNumber(it.favorites);
  const price = it.price != null ? `${it.price} R$` : "—";

  const featured = rank === 1 ? " featured" : "";
  const href = `https://www.roblox.com/catalog/${it.assetId}/`;

  return `
    <div class="podium-card${featured}">
      <div class="thumb" data-zoom-src="${escapeHtml(it.thumb)}" data-zoom-caption="${escapeHtml(it.name)}">
        <img src="${escapeHtml(it.thumb)}" alt="${escapeHtml(it.name)}" loading="lazy" />
      </div>
      <div class="body">
        <div class="name" data-copy="${escapeHtml(it.name)}" title="Copier le nom">${escapeHtml(it.name)}</div>
        <div class="meta">
          <span class="meta-pill">${escapeHtml(badge)}</span>
          <span class="meta-pill copy" data-copy="${it.assetId}" title="Copier l'ID">ID: ${it.assetId}</span>
          <span class="meta-pill">❤️ ${fav}</span>
          <span class="meta-pill">${created}</span>
        </div>
        <div class="cta">
          <div class="price">${price}</div>
          <a class="btn small" href="${href}" target="_blank" rel="noopener">Ouvrir</a>
        </div>
      </div>
    </div>
  `;
}

function renderPodium() {
  const el = $("#podiumGrid");
  const items = state.items.slice(0, 3);

  if (!items.length) {
    el.innerHTML = `<div class="muted">Aucun item.</div>`;
    return;
  }

  const first = items[0];
  const second = items[1];
  const third = items[2];

  const html = [
    second ? podiumCard(second, 2) : "",
    first ? podiumCard(first, 1) : "",
    third ? podiumCard(third, 3) : "",
  ].filter(Boolean).join("");

  el.innerHTML = html;
}

/* Render UGC grid */
function itemCard(it) {
  const badge = it.typeFr || it.typeName || "Autre";
  const created = fmtDate(it.createdTs);
  const fav = fmtNumber(it.favorites);
  const price = it.price != null ? `${it.price} R$` : "—";
  const href = `https://www.roblox.com/catalog/${it.assetId}/`;

  return `
    <div class="item-card">
      <div class="item-thumb" data-zoom-src="${escapeHtml(it.thumb)}" data-zoom-caption="${escapeHtml(it.name)}">
        <img src="${escapeHtml(it.thumb)}" alt="${escapeHtml(it.name)}" loading="lazy" />
        <span class="badge">${escapeHtml(badge)}</span>
      </div>

      <div class="item-body">
        <div class="item-name" data-copy="${escapeHtml(it.name)}" title="Copier le nom">${escapeHtml(it.name)}</div>

        <div class="item-meta">
          <span class="meta-pill copy" data-copy="${it.assetId}" title="Copier l'ID">ID: ${it.assetId}</span>
          <span class="meta-pill">❤️ ${fav}</span>
          <span class="meta-pill">${created}</span>
        </div>

        <div class="item-footer">
          <div class="price">${price}</div>
          <a class="btn small" href="${href}" target="_blank" rel="noopener">Ouvrir</a>
        </div>
      </div>
    </div>
  `;
}

function renderUGC() {
  const grid = $("#ugcGrid");
  const list = state.filtered;

  $("#ugcCount").textContent = `${list.length} item(s)`;

  grid.innerHTML = list.map(itemCard).join("") || `<div class="muted">Aucun résultat.</div>`;
}

/* Render gallery */
function renderGallery() {
  const grid = $("#galleryGrid");
  if (!state.gallery.length) {
    grid.innerHTML = `<div class="muted">Aucune image.</div>`;
    return;
  }

  grid.innerHTML = state.gallery.map((g) => {
    const src = String(g.url || "");
    const caption = String(g.caption || "");
    return `
      <div class="item-card">
        <div class="item-thumb media-thumb" data-zoom-src="${escapeHtml(src)}" data-zoom-caption="${escapeHtml(caption)}">
          <img src="${escapeHtml(src)}" alt="${escapeHtml(caption || "Image")}" loading="lazy" />
        </div>
      </div>
    `;
  }).join("");
}

/* Render commissions */
function extractCommissionImages(commissionsJson, mode) {
  // mode: "models" or "textures"
  const out = [];

  const root = commissionsJson;
  const arr = Array.isArray(root) ? root : (root?.commissions || root?.items || []);
  if (!Array.isArray(arr)) return out;

  const key = mode === "textures" ? "texturing" : "model3d";

  for (const c of arr) {
    const title = c?.client || c?.name || c?.title || "";
    const images = c?.images?.[key] ?? c?.[key] ?? c?.images ?? [];
    if (typeof images === "string") out.push({ src: images, caption: title });
    else if (Array.isArray(images)) {
      images.forEach((src) => out.push({ src, caption: title }));
    }
  }
  return out.filter(x => typeof x.src === "string" && x.src.trim().length);
}

function renderCommissions() {
  const grid = $("#commissionsGrid");
  if (!state.commissions) {
    grid.innerHTML = `<div class="muted">commissions.json manquant.</div>`;
    return;
  }

  const imgs = extractCommissionImages(state.commissions, state.commView);
  if (!imgs.length) {
    grid.innerHTML = `<div class="muted">Aucune image.</div>`;
    return;
  }

  grid.innerHTML = imgs.map((m) => `
    <div class="item-card">
      <div class="item-thumb media-thumb" data-zoom-src="${escapeHtml(m.src)}" data-zoom-caption="${escapeHtml(m.caption)}">
        <img src="${escapeHtml(m.src)}" alt="${escapeHtml(m.caption || "Commission")}" loading="lazy" />
      </div>
    </div>
  `).join("");
}

/* Filtering */
function populateTypeSelect(category) {
  const select = $("#filterType");
  const opts = TYPE_OPTIONS[category] || TYPE_OPTIONS.ALL;

  select.innerHTML = opts.map(o => `<option value="${o.key}">${escapeHtml(o.label)}</option>`).join("");
}

function getTypeIdsForFilter(category, typeKey) {
  const opts = TYPE_OPTIONS[category] || TYPE_OPTIONS.ALL;
  const hit = opts.find(o => o.key === typeKey) || opts[0];
  if (!hit || !hit.ids) return null;
  return new Set(hit.ids);
}

function applyFilters() {
  const cat = $("#filterCategory").value;
  const typeKey = $("#filterType").value;
  const sort = $("#filterSort").value;
  const q = ($("#filterSearch").value || "").trim().toLowerCase();

  let list = state.items.slice();

  // Category
  if (cat !== "ALL") list = list.filter(it => it.category === cat);

  // Type
  const ids = getTypeIdsForFilter(cat, typeKey);
  if (ids) list = list.filter(it => it.typeId != null && ids.has(it.typeId));

  // Search
  if (q) {
    list = list.filter(it => {
      const idStr = String(it.assetId);
      const name = it.name.toLowerCase();
      return idStr.includes(q) || name.includes(q);
    });
  }

  // Sort
  if (sort === "FAV") {
    list.sort((a, b) => (b.favorites || 0) - (a.favorites || 0) || (b.createdTs || 0) - (a.createdTs || 0));
  } else if (sort === "PRICE_DESC") {
    list.sort((a, b) => (b.price || 0) - (a.price || 0) || (b.createdTs || 0) - (a.createdTs || 0));
  } else if (sort === "PRICE_ASC") {
    list.sort((a, b) => (a.price || 0) - (b.price || 0) || (b.createdTs || 0) - (a.createdTs || 0));
  } else {
    // NEW
    list.sort((a, b) => (b.createdTs || 0) - (a.createdTs || 0) || (b.assetId || 0) - (a.assetId || 0));
  }

  state.filtered = list;
  renderUGC();
}

function wireEvents() {
  // Tabs
  $$(".tab-btn").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));

  // Zoom close
  $$("[data-zoom-close]").forEach((el) => el.addEventListener("click", closeZoom));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeZoom();
  });

  // Delegation: zoom + copy
  document.addEventListener("click", async (e) => {
    const t = e.target;

    const zoomEl = t.closest?.("[data-zoom-src]");
    if (zoomEl) {
      const src = zoomEl.getAttribute("data-zoom-src");
      const cap = zoomEl.getAttribute("data-zoom-caption") || "";
      if (src) openZoom(src, cap);
      return;
    }

    const copyEl = t.closest?.("[data-copy]");
    if (copyEl) {
      const text = copyEl.getAttribute("data-copy") || "";
      if (text) await copyToClipboard(text);
      return;
    }
  });

  // Filters
  $("#filterCategory").addEventListener("change", () => {
    populateTypeSelect($("#filterCategory").value);
    $("#filterType").value = "ALL";
    applyFilters();
  });
  $("#filterType").addEventListener("change", applyFilters);
  $("#filterSort").addEventListener("change", applyFilters);
  $("#filterSearch").addEventListener("input", () => {
    clearTimeout(wireEvents._st);
    wireEvents._st = setTimeout(applyFilters, 90);
  });

  // Commission switch
  $$(".pill").forEach((p) => p.addEventListener("click", () => {
    $$(".pill").forEach(x => x.classList.remove("active"));
    p.classList.add("active");
    state.commView = p.dataset.commView || "models";
    renderCommissions();
  }));

  // Basic anti-copy (dissuasion, pas une sécurité)
  document.addEventListener("contextmenu", (e) => e.preventDefault());
  document.addEventListener("keydown", (e) => {
    const k = e.key?.toLowerCase?.() || "";
    const block =
      (e.ctrlKey && ["u", "s"].includes(k)) ||
      (e.ctrlKey && e.shiftKey && ["i", "j", "c"].includes(k)) ||
      (e.key === "F12");
    if (block) e.preventDefault();
  });
}

async function fetchJson(path) {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}

async function load() {
  // Types
  populateTypeSelect("ALL");

  // Data
  const [u, g] = await Promise.allSettled([fetchJson("./data_user.json"), fetchJson("./data_group.json")]);

  const userItems = u.status === "fulfilled" ? (u.value.items || []) : [];
  const groupItems = g.status === "fulfilled" ? (g.value.items || []) : [];

  const merged = [
    ...userItems.map(x => ({ ...x, creator: "Profil" })),
    ...groupItems.map(x => ({ ...x, creator: "Groupe" })),
  ].map(normalizeItem);

  // Sort newest first for base list
  merged.sort((a, b) => (b.createdTs || 0) - (a.createdTs || 0) || (b.assetId || 0) - (a.assetId || 0));

  state.items = merged;
  state.filtered = merged.slice();

  // Build info
  const uAt = (u.status === "fulfilled" && u.value.generatedAt) ? String(u.value.generatedAt) : "";
  const gAt = (g.status === "fulfilled" && g.value.generatedAt) ? String(g.value.generatedAt) : "";
  $("#buildInfo").textContent = `MAJ: ${uAt || "—"} ${gAt ? "• " + gAt : ""}`;

  // Render UGC
  renderPodium();
  applyFilters();

  // Gallery
  try {
    const gal = await fetchJson("./gallery.json");
    state.gallery = Array.isArray(gal) ? gal : [];
  } catch {
    state.gallery = [];
  }
  renderGallery();

  // Commissions
  try {
    state.commissions = await fetchJson("./commissions.json");
  } catch {
    state.commissions = null;
  }
  renderCommissions();
}

wireEvents();
load().catch(() => {
  $("#ugcCount").textContent = "Erreur de chargement.";
});

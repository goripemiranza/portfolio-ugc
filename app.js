/* app.js — Roblox Portfolio (notify: desktop + email, commissions auto by name) */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const on = (el, evt, fn, opts) => { if (el) el.addEventListener(evt, fn, opts); };

const FILES = {
  user: "data_user.json",
  group: "data_group.json",
  gallery: "gallery.json",
  commissions: "commissions.json",
};

const ROBLOX_ITEM_URL = (assetId) => `https://www.roblox.com/catalog/${assetId}`;
const ROBLOX_PROFILE_URL = (username) => `https://www.roblox.com/users/profile?username=${encodeURIComponent(username)}`;
const FALLBACK_THUMB = (assetId) =>
  `https://www.roblox.com/asset-thumbnail/image?assetId=${encodeURIComponent(assetId)}&width=420&height=420&format=png`;

const TYPE_LABEL_EN = {
  Hat: "Hat",
  HairAccessory: "Hair",
  FaceAccessory: "Face",
  NeckAccessory: "Neck",
  ShoulderAccessory: "Shoulder",
  FrontAccessory: "Front",
  BackAccessory: "Back",
  WaistAccessory: "Waist",
  EarAccessory: "Ear",
  EyeAccessory: "Eye",
  EyebrowAccessory: "Eyebrow",
  EyelashAccessory: "Eyelash",
  Head: "Head",
  Face: "Face (Classic)",
  DynamicHead: "Dynamic Head",
  TShirt: "T-Shirt",
  Shirt: "Shirt",
  Pants: "Pants",
  TShirtAccessory: "T-Shirt (LC)",
  ShirtAccessory: "Shirt (LC)",
  PantsAccessory: "Pants (LC)",
  JacketAccessory: "Jacket (LC)",
  SweaterAccessory: "Sweater (LC)",
  ShortsAccessory: "Shorts (LC)",
  LeftShoeAccessory: "Left Shoe (LC)",
  RightShoeAccessory: "Right Shoe (LC)",
  DressSkirtAccessory: "Dress/Skirt (LC)",
  Animation: "Animation",
  ClimbAnimation: "Climb",
  DeathAnimation: "Death",
  FallAnimation: "Fall",
  IdleAnimation: "Idle",
  JumpAnimation: "Jump",
  RunAnimation: "Run",
  SwimAnimation: "Swim",
  WalkAnimation: "Walk",
  PoseAnimation: "Pose",
  EmoteAnimation: "Emote",
  MoodAnimation: "Mood",
  Package: "Package",
};

function typeToLabel(type) {
  if (!type || typeof type !== "string") return "Other";
  return TYPE_LABEL_EN[type] || type;
}

function typeToCategory(type) {
  const t = String(type || "");
  if (t.endsWith("Animation") || t === "Animation" || t === "MoodAnimation") return "Animations";
  if (t === "Package") return "Packages";
  if (t.endsWith("Accessory") || t === "Hat") return "Accessories";
  if (t === "Head" || t === "DynamicHead") return "Heads";
  if (t === "Face") return "Faces";
  if (t === "TShirt" || t === "Shirt" || t === "Pants") return "Clothing";
  if (t.includes("Jacket") || t.includes("Sweater") || t.includes("Shorts") || t.includes("Shoe") || t.includes("Dress")) return "Clothing";
  if (t.includes("TShirt") || t.includes("Shirt") || t.includes("Pants")) return "Clothing";
  return "Other";
}

function safeDate(ts) {
  const d = ts ? new Date(ts) : null;
  if (!d || Number.isNaN(d.getTime())) return "—";
  try {
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  } catch {
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yy = d.getFullYear();
    return `${dd}/${mm}/${yy}`;
  }
}

function num(n) {
  return typeof n === "number" && Number.isFinite(n) ? n : null;
}
function fmtRobux(price) {
  const p = num(price);
  if (p == null) return "—";
  return `${p} R$`;
}
function plural(n, one, many) { return n === 1 ? one : many; }

async function fetchJson(path, { optional = false } = {}) {
  // Performance: allow HTTP caching + revalidation (fast 304), no cache-busting query.
  try {
    const r = await fetch(path, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${path} HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    if (optional) return null;
    throw e;
  }
}

const STATE = {
  all: [],
  filtered: [],
  gallery: [],
  commissions: { models: [], textures: [] },
  commMode: "models",

  // Site likes (anonymous per browser)
  likes: new Map(),        // assetId -> count
  liked: new Set(),        // assetId set liked by this browser
  likeUid: null,           // anonymous stable id for this browser
};

/* View transitions */
function setActiveView(name) {
  const next = $(`#view-${name}`);
  if (!next) return;

  $$(".tabBtn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));

  const current = $(".view.active");
  if (current === next) return;

  const showNext = () => {
    next.classList.add("active", "entering");
    setTimeout(() => next.classList.remove("entering"), 330);
  };

  if (current) {
    current.classList.add("leaving");
    setTimeout(() => {
      current.classList.remove("active", "leaving");
      showNext();
    }, 260);
  } else {
    showNext();
  }
}

function jumpToLegal() {
  const active = document.querySelector(".view.active");
  if (!active) return;

  const card = active.querySelector(".legalCard") || active.querySelector(".legalAccordion");
  const details = active.querySelector(".legalAccordion");
  if (details) details.open = true;

  if (card && card.scrollIntoView) {
    card.scrollIntoView({ behavior: "smooth", block: "end" });
    try {
      card.classList.add("legalFlash");
      setTimeout(() => card.classList.remove("legalFlash"), 900);
    } catch (e) { console.warn("[Silent error]", e); }
  }
}


/* Scroll reveal */
let REVEAL_OBS = null;
function ensureRevealObserver() {
  if (REVEAL_OBS) return REVEAL_OBS;
  REVEAL_OBS = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) {
        e.target.classList.add("revealed");
        REVEAL_OBS.unobserve(e.target);
      }
    }
  }, { threshold: 0.08, rootMargin: "120px 0px 120px 0px" });
  return REVEAL_OBS;
}
function reveal(el) {
  if (!el) return;
  el.classList.add("reveal");
  ensureRevealObserver().observe(el);
}

/* Podium */
function computePodium(items) {
  const list = items.slice().sort((a, b) => (b.createdTs || 0) - (a.createdTs || 0));
  return list.slice(0, 3);
}
function setPodiumSlotClass(card, slot) {
  if (!card || !slot) return;
  card.classList.add(`podium-${slot}`);
}
function createPodiumBadge(kind) {
  const b = document.createElement("div");
  b.className = `podiumBadge ${kind}`;
  if (kind === "new") b.textContent = "NEW";
  if (kind === "rank2") b.textContent = "2";
  if (kind === "rank3") b.textContent = "3";
  return b;
}

function createUgcCard(item, { featured = false, podiumSlot = null, podiumBadge = null } = {}) {
  const card = document.createElement("article");
  card.className = `ugcCard${featured ? " featured" : ""}`;
  card.dataset.assetId = String(item.assetId);

  setPodiumSlotClass(card, podiumSlot);

  const badge = document.createElement("div");
  badge.className = "badge";
  badge.textContent = typeToCategory(item.type);

  const pill = document.createElement("div");
  pill.className = "sourcePill";
  pill.textContent = item.source;

  const thumbBtn = document.createElement("button");
  thumbBtn.type = "button";
  thumbBtn.className = "thumbBtn";
  thumbBtn.dataset.action = "zoom";
  thumbBtn.dataset.src = item.thumb || FALLBACK_THUMB(item.assetId);
  thumbBtn.dataset.caption = `${item.name} • ${item.assetId}`;

  const img = document.createElement("img");
  img.className = "thumb";
  const isPodium = Boolean(podiumSlot);
  img.loading = isPodium ? "eager" : "lazy";
  img.decoding = "async";
  try { if (isPodium && "fetchPriority" in img) img.fetchPriority = "high"; } catch (_) {}

  img.alt = item.name || "UGC";
  img.src = item.thumb || FALLBACK_THUMB(item.assetId);
  img.draggable = false;
  thumbBtn.appendChild(img);

  const body = document.createElement("div");
  body.className = "body";

  const title = document.createElement("div");
  title.className = "title";

  const titleBtn = document.createElement("button");
  titleBtn.type = "button";
  titleBtn.className = "linkLike";
  titleBtn.dataset.action = "copy-name";
  titleBtn.dataset.copy = item.name || "";
  titleBtn.textContent = item.name || `Item ${item.assetId}`;
  title.appendChild(titleBtn);

  const meta = document.createElement("div");
  meta.className = "metaRow";

  const idBtn = document.createElement("button");
  idBtn.type = "button";
  idBtn.className = "kvBtn";
  idBtn.dataset.action = "copy-id";
  idBtn.dataset.copy = String(item.assetId);
  idBtn.textContent = `ID ${item.assetId}`;

  const dateTag = document.createElement("span");
  dateTag.className = "metaTag dateTag";
  dateTag.textContent = safeDate(item.created);

  const fav = document.createElement("span");
  fav.className = "metaTag favTag";
  const f = num(item.favorites);
  fav.textContent = `❤ ${f == null ? "—" : f}`;

  const typeTag = document.createElement("span");
  typeTag.className = "metaTag typeTag";
  typeTag.textContent = typeToLabel(item.type);

  meta.appendChild(idBtn);
  meta.appendChild(dateTag);
  meta.appendChild(fav);
  meta.appendChild(typeTag);

  const foot = document.createElement("div");
  foot.className = "foot";

  const price = document.createElement("div");
  price.className = "price";
  price.textContent = fmtRobux(item.price);

  const openBtn = document.createElement("button");
  openBtn.type = "button";
  openBtn.className = "btnOpen";
  openBtn.dataset.action = "open";
  openBtn.textContent = "Open";

  // Like button (site likes)
  const likeBtn = document.createElement("button");
  likeBtn.type = "button";
  likeBtn.className = "likeBtn";
  likeBtn.dataset.action = "like";
  likeBtn.dataset.assetId = String(item.assetId);
  likeBtn.setAttribute("aria-label", "Like");

  const likeInner = document.createElement("span");
  likeInner.className = "likeInner";

  const likeHeart = document.createElement("span");
  likeHeart.className = "likeHeart";
  likeHeart.textContent = "♥";

  const likeNum = document.createElement("span");
  likeNum.className = "likeNum";
  likeNum.textContent = String(getLikeCount(item.assetId));

  likeInner.appendChild(likeHeart);
  likeInner.appendChild(likeNum);
  likeBtn.appendChild(likeInner);

  likeBtn.classList.toggle("liked", isLiked(item.assetId));

  const actions = document.createElement("div");
  actions.className = "footActions";
  actions.appendChild(likeBtn);
  actions.appendChild(openBtn);

  foot.appendChild(price);
  foot.appendChild(actions);

  body.appendChild(title);
  body.appendChild(meta);
  body.appendChild(foot);

  card.appendChild(thumbBtn);
  card.appendChild(badge);
  card.appendChild(pill);
  if (podiumBadge) card.appendChild(createPodiumBadge(podiumBadge));
  card.appendChild(body);

  return card;
}

function renderPodium() {
  const row = $("#podiumRow");
  const empty = $("#podiumEmpty");
  if (!row || !empty) return;
  row.innerHTML = "";

  const podium = computePodium(STATE.all).filter((x) => num(x.price) != null && x.price > 0);
  if (!podium.length) {
    empty.hidden = false;
    $("#podiumHint").textContent = `0 ${plural(0, "item", "items")}`;
    return;
  }
  empty.hidden = true;

  const mid = podium[0] || null;
  const left = podium[1] || null;
  const right = podium[2] || null;

  const cards = [
    left ? createUgcCard(left, { featured: false, podiumSlot: "left", podiumBadge: "rank2" }) : null,
    mid ? createUgcCard(mid, { featured: true, podiumSlot: "mid", podiumBadge: "new" }) : null,
    right ? createUgcCard(right, { featured: false, podiumSlot: "right", podiumBadge: "rank3" }) : null,
  ].filter(Boolean);

  const frag = document.createDocumentFragment();
  for (const c of cards) {
    frag.appendChild(c);
    reveal(c);
  }
  row.appendChild(frag);

  $("#podiumHint").textContent = `${podium.length} ${plural(podium.length, "item", "items")}`;
}

/* Filters */
function fillSelect(selectEl, options, selectedValue) {
  selectEl.innerHTML = "";
  for (const opt of options) {
    const o = document.createElement("option");
    o.value = opt.value;
    o.textContent = opt.label;
    selectEl.appendChild(o);
  }
  if (selectedValue != null) selectEl.value = selectedValue;
}

function getFilters() {
  const cat = $("#fCategory")?.value || "all";
  const type = $("#fType")?.value || "all";
  const sort = $("#fSort")?.value || "new";
  const q = ($("#fSearch")?.value || "").trim().toLowerCase();
  return { cat, type, sort, q };
}

function updateFilterActiveUI() {
  const set = (el, active) => {
    const c = el?.closest(".control");
    if (c) c.classList.toggle("active", !!active);
  };
  const catEl = $("#fCategory");
  const typeEl = $("#fType");
  const qEl = $("#fSearch");
  set(catEl, catEl && catEl.value !== "all");
  set(typeEl, typeEl && typeEl.value !== "all");
  set(qEl, qEl && qEl.value.trim().length > 0);
}

function applyFilters() {
  const { cat, type, sort, q } = getFilters();

  let items = STATE.all.slice();
  items = items.filter((x) => num(x.price) != null && x.price > 0);

  if (cat !== "all") items = items.filter((x) => typeToCategory(x.type) === cat);
  if (type !== "all") items = items.filter((x) => String(x.type) === type);

  if (q) {
    items = items.filter((x) => {
      const name = String(x.name || "").toLowerCase();
      const id = String(x.assetId || "");
      return name.includes(q) || id.includes(q);
    });
  }

  if (sort === "new") items.sort((a, b) => (b.createdTs || 0) - (a.createdTs || 0));
  if (sort === "old") items.sort((a, b) => (a.createdTs || 0) - (b.createdTs || 0));
  if (sort === "fav") items.sort((a, b) => (num(b.favorites) || -1) - (num(a.favorites) || -1));
  if (sort === "price_desc") items.sort((a, b) => (num(b.price) || 0) - (num(a.price) || 0));
  if (sort === "price_asc") items.sort((a, b) => (num(a.price) || 0) - (num(b.price) || 0));

  STATE.filtered = items;
}

function renderUgcGrid() {
  const grid = $("#ugcGrid");
  const empty = $("#ugcEmpty");
  if (!grid || !empty) return;

  grid.replaceChildren();

  const items = STATE.filtered;
  $("#ugcCount").textContent = `${items.length} ${plural(items.length, "item", "items")}`;

  if (!items.length) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  const frag = document.createDocumentFragment();
  for (const it of items) {
    const c = createUgcCard(it);
    frag.appendChild(c);
    reveal(c);
  }
  grid.appendChild(frag);
}

function renderFiltersUI() {
  const catEl = $("#fCategory");
  const typeEl = $("#fType");
  if (!catEl || !typeEl) return;

  const cats = ["Accessories", "Clothing", "Animations", "Heads", "Faces", "Packages", "Other"];
  const presentCats = new Set(STATE.all.map((x) => typeToCategory(x.type)));
  const catOptions = [{ value: "all", label: "All" }].concat(
    cats.filter((c) => presentCats.has(c)).map((c) => ({ value: c, label: c }))
  );

  const types = Array.from(new Set(STATE.all.map((x) => String(x.type || "")))).filter(Boolean);
  types.sort((a, b) => typeToLabel(a).localeCompare(typeToLabel(b), "en"));
  const typeOptions = [{ value: "all", label: "All" }].concat(
    types.map((t) => ({ value: t, label: typeToLabel(t) }))
  );

  const prevCat = catEl.value || "all";
  const prevType = typeEl.value || "all";
  fillSelect(catEl, catOptions, prevCat);
  fillSelect(typeEl, typeOptions, prevType);

  updateFilterActiveUI();
}

/* Gallery */
function renderGallery() {
  const grid = $("#galleryGrid");
  const empty = $("#galleryEmpty");
  if (!grid || !empty) return;

  grid.replaceChildren();

  const items = STATE.gallery || [];
  $("#galleryCount").textContent = `${items.length} ${plural(items.length, "image", "images")}`;

  if (!items.length) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  const frag = document.createDocumentFragment();
  for (const g of items) {
    const card = document.createElement("div");
    card.className = "galCard";
    reveal(card);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "galBtn";
    btn.dataset.action = "zoom";
    btn.dataset.src = g.url;
    btn.dataset.caption = "";

    const img = document.createElement("img");
    img.className = "galImg";
    img.loading = "lazy";
    img.alt = "Gallery";
    img.src = g.url;
    img.draggable = false;

    btn.appendChild(img);
    card.appendChild(btn);
    frag.appendChild(card);
  }
  grid.appendChild(frag);
}

/* Commissions — auto split by filename (Texture* => textures, Modèle/Modele/Model* => models) */
function stripAccents(s) {
  try { return String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, ""); }
  catch { return String(s || ""); }
}
function filenameOnly(url) {
  try {
    const u = String(url || "");
    const p = u.split("?")[0].split("#")[0];
    const parts = p.split("/");
    return parts[parts.length - 1] || p;
  } catch { return String(url || ""); }
}
function isTextureName(name) {
  const n = stripAccents(name).toLowerCase();
  return n.startsWith("texture") || n.includes(" texture");
}
function isModelName(name) {
  const n = stripAccents(name).toLowerCase();
  return n.startsWith("modele") || n.includes(" modele") || n.startsWith("model") || n.includes(" model");
}
function normalizeCommissionJson(raw) {
  const models = [];
  const textures = [];

  if (!raw) return { models, textures };

  // New format: { models:[], textures:[] }
  if (Array.isArray(raw.models) || Array.isArray(raw.textures)) {
    (raw.models || []).forEach((x) => typeof x === "string" && models.push(x));
    (raw.textures || []).forEach((x) => typeof x === "string" && textures.push(x));
    return { models, textures };
  }

  // Flat arrays: ["commissions/Texture 1.png", ...]
  if (Array.isArray(raw) && raw.every((x) => typeof x === "string")) {
    for (const url of raw) {
      const fn = filenameOnly(url);
      if (isTextureName(fn)) textures.push(url);
      else models.push(url);
    }
    return { models, textures };
  }

  // Legacy format: commissions blocks with images
  const list = Array.isArray(raw) ? raw : (Array.isArray(raw.commissions) ? raw.commissions : []);
  for (const c of list) {
    if (!c || typeof c !== "object") continue;
    const imgs = c.images || c.media || c;
    const m = imgs.model3d || imgs.models || imgs.model || [];
    const t = imgs.texturing || imgs.textures || imgs.texture || [];
    const pushAll = (arr, target) => {
      if (!arr) return;
      if (Array.isArray(arr)) arr.forEach((x) => typeof x === "string" && target.push(x));
      else if (typeof arr === "string") target.push(arr);
    };
    pushAll(m, models);
    pushAll(t, textures);
  }

  // Extra: if raw.images is a list
  if (Array.isArray(raw.images)) {
    for (const url of raw.images) {
      const fn = filenameOnly(url);
      if (isTextureName(fn)) textures.push(url);
      else if (isModelName(fn)) models.push(url);
      else models.push(url);
    }
  }

  return { models, textures };
}

function renderCommissions() {
  const grid = $("#commissionGrid");
  const empty = $("#commissionEmpty");
  if (!grid || !empty) return;

  grid.replaceChildren();
  const list = STATE.commissions[STATE.commMode] || [];

  if (!list.length) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  const frag = document.createDocumentFragment();
  for (const url of list) {
    const card = document.createElement("div");
    card.className = "comCard";
    reveal(card);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "comBtn";
    btn.dataset.action = "zoom";
    btn.dataset.src = url;
    btn.dataset.caption = "";

    const img = document.createElement("img");
    img.className = "comImg";
    img.loading = "lazy";
    img.alt = "Commission";
    img.src = url;
    img.draggable = false;

    btn.appendChild(img);
    card.appendChild(btn);
    frag.appendChild(card);
  }
  grid.appendChild(frag);
}

/* Modal (zoom) */
let ZOOM = { scale: 1, x: 0, y: 0, dragging: false, px: 0, py: 0 };

function setModalTransform() {
  const img = $("#modalImg");
  if (!img) return;
  img.style.transform = `translate(${ZOOM.x}px, ${ZOOM.y}px) scale(${ZOOM.scale})`;
}
function modalReset() {
  ZOOM.scale = 1;
  ZOOM.x = 0;
  ZOOM.y = 0;
  setModalTransform();
  const z = $("#zoomReset");
  if (z) z.textContent = "1×";
}
function modalZoom(delta) {
  const next = Math.min(4, Math.max(1, ZOOM.scale + delta));
  ZOOM.scale = next;
  if (ZOOM.scale === 1) { ZOOM.x = 0; ZOOM.y = 0; }
  setModalTransform();
  const z = $("#zoomReset");
  if (z) z.textContent = `${ZOOM.scale.toFixed(1)}×`.replace(".0", "");
}
function openModal(src, caption = "") {
  const modal = $("#modal");
  const img = $("#modalImg");
  const cap = $("#modalCaption");
  if (!modal || !img) {
    window.open(src, "_blank", "noopener,noreferrer");
    return;
  }
  img.src = src;
  if (cap) cap.textContent = caption || "";
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  modalReset();
}
function closeModal() {
  const modal = $("#modal");
  const img = $("#modalImg");
  if (!modal) return;
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  if (img) img.src = "";
}

/* Toast */
let toastTimer = null;
function showToast(text) {
  const t = $("#toast");
  if (!t) return;
  t.textContent = text;
  t.classList.add("show");
  t.setAttribute("aria-hidden", "false");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    t.classList.remove("show");
    t.setAttribute("aria-hidden", "true");
  }, 1300);
}
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(String(text));
    showToast("Copied ✅");
  } catch {
    const ta = document.createElement("textarea");
    ta.value = String(text);
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); showToast("Copied ✅"); } catch (e) { console.warn("[execCommand deprecated]", e); showToast("Copy blocked"); }
    document.body.removeChild(ta);
  }
}

/* Delegated actions */
function onClickAction(e) {
  const target = e.target.closest("[data-action]");
  if (!target) return;

  const action = target.dataset.action;

  if (action === "zoom") {
    const src = target.dataset.src;
    const cap = target.dataset.caption || "";
    if (src) openModal(src, cap);
    return;
  }


  if (action === "like") {
    const btn = target;
    const assetId = btn.dataset.assetId || btn.closest("[data-asset-id]")?.dataset.assetId || "";
    if (!assetId) return;

    const wantLike = !isLiked(assetId);

    // Optimistic UI
    btn.classList.add("pop");
    setTimeout(() => btn.classList.remove("pop"), 320);

    // Send to backend
    setLike(assetId, wantLike).catch((err) => {
      console.warn("[Like error]", err);
      showToast("Like failed");
    });
    return;
  }

  if (action === "open") {
    const card = target.closest("[data-asset-id]");
    const assetId = card?.dataset.assetId;
    if (assetId) window.open(ROBLOX_ITEM_URL(assetId), "_blank", "noopener,noreferrer");
    return;
  }

  if (action === "copy-id" || action === "copy-name" || action === "copy-discord") {
    const text = target.dataset.copy || "";
    if (text) copyText(text);
    return;
  }

  if (action === "open-roblox-profile") {
    const username = target.dataset.username || "";
    if (username) window.open(ROBLOX_PROFILE_URL(username), "_blank", "noopener,noreferrer");
    return;
  }
}

/* Protection layer (deterrence) */
function hardenClient() {
  const isEditable = (t) => {
    if (!t) return false;
    const tag = t.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || t.isContentEditable === true;
  };

  document.addEventListener("contextmenu", (e) => {
    if (isEditable(e.target)) return;
    e.preventDefault();
    showToast("Protected");
  });

  const block = (e) => {
    if (isEditable(e.target)) return;
    e.preventDefault();
    showToast("Protected");
  };
  ["copy", "cut", "dragstart"].forEach((ev) => document.addEventListener(ev, block));

  document.addEventListener("keydown", (e) => {
    if (isEditable(e.target)) return;

    const k = String(e.key || "").toLowerCase();
    const ctrl = e.ctrlKey || e.metaKey;

    if (e.key === "F12" || (ctrl && (k === "u" || k === "s" || k === "p")) || (ctrl && e.shiftKey && (k === "i" || k === "j" || k === "c"))) {
      e.preventDefault();
      showToast("Protected");
    }
  });
}

/* Notifications */
const NOTIF = {
  desktop: false,
  email: false,
  subId: "",
  lastTs: 0,
  timer: null,
  intervalMs: 2 * 60 * 1000, // auto-check every 2 minutes
};

function loadNotifPrefs() {
  try {
    NOTIF.desktop = localStorage.getItem("notif_desktop") === "1";
    NOTIF.email = localStorage.getItem("notif_email") === "1";
    NOTIF.subId = localStorage.getItem("notif_sub_id") || "";
    NOTIF.lastTs = Number(localStorage.getItem("notif_last_ts") || "0") || 0;
  } catch (e) { console.warn("[Silent error]", e); }

}
// ===== Likes prefs (anonymous per browser) =====
const LS_LIKE_UID = "ugc_like_uid_v1";
const LS_LIKED_SET = "ugc_liked_set_v1";

function loadLikePrefs() {
  try {
    let uid = localStorage.getItem(LS_LIKE_UID);
    if (!uid) {
      const buf = new Uint8Array(16);
      crypto.getRandomValues(buf);
      uid = Array.from(buf).map((b) => b.toString(16).padStart(2, "0")).join("");
      localStorage.setItem(LS_LIKE_UID, uid);
    }
    STATE.likeUid = uid;

    const raw = localStorage.getItem(LS_LIKED_SET);
    const arr = raw ? JSON.parse(raw) : [];
    STATE.liked = new Set(Array.isArray(arr) ? arr.map(String) : []);
  } catch {
    STATE.likeUid = STATE.likeUid || "anon";
    STATE.liked = new Set();
  }
}

function saveLikePrefs() {
  try {
    localStorage.setItem(LS_LIKED_SET, JSON.stringify(Array.from(STATE.liked)));
  } catch (e) { console.warn("[Silent error]", e); }
}

function getLikeCount(assetId) {
  return num(STATE.likes.get(String(assetId))) || 0;
}

function isLiked(assetId) {
  return STATE.liked.has(String(assetId));
}

function updateLikeButtons(assetId) {
  const id = String(assetId);
  const count = getLikeCount(id);
  const liked = isLiked(id);

  const btns = document.querySelectorAll(`.likeBtn[data-asset-id="${CSS.escape ? CSS.escape(String(id)) : id}"]`);
  btns.forEach((b) => {
    b.classList.toggle("liked", liked);
    const n = b.querySelector(".likeNum");
    if (n) n.textContent = String(count);
  });
}

async function fetchLikeCounts(ids) {
  const unique = Array.from(new Set(ids.map(String))).filter(Boolean);
  if (!unique.length) return;

  // Keep URL small; split in chunks
  const chunkSize = 120;
    const uidEnc = encodeURIComponent(String(STATE.likeUid || ""));
for (let i = 0; i < unique.length; i += chunkSize) {
    const part = unique.slice(i, i + chunkSize);
    const url = `/api/likes?ids=${encodeURIComponent(part.join(","))}&uid=${uidEnc}&t=${Date.now()}`;
    const r = await fetch(url, { cache: "no-store" });
    const j = await r.json().catch(() => null);
    if (!r.ok || !j?.ok) continue;

    const counts = j.counts || {};
    for (const k of Object.keys(counts)) {
      STATE.likes.set(String(k), num(counts[k]) || 0);
    }
    const likedMap = j.liked || null;
    if (likedMap) {
      for (const k of Object.keys(likedMap)) {
        if (likedMap[k]) STATE.liked.add(String(k));
        else STATE.liked.delete(String(k));
      }
      saveLikePrefs();
    }
  }
}

async function setLike(assetId, like) {
  const id = String(assetId);
  const uid = String(STATE.likeUid || "");
  if (!uid) throw new Error("no_uid");

  const r = await fetch("/api/like", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ assetId: id, uid, like: !!like }),
  });
  const j = await r.json().catch(() => null);
  if (!r.ok || !j?.ok) throw new Error(j?.error || "like_failed");

  STATE.likes.set(id, num(j.count) || 0);

  if (j.liked) STATE.liked.add(id);
  else STATE.liked.delete(id);

  saveLikePrefs();
  updateLikeButtons(id);
  return j;
}


function saveNotifPrefs() {
  try {
    localStorage.setItem("notif_desktop", NOTIF.desktop ? "1" : "0");
    localStorage.setItem("notif_email", NOTIF.email ? "1" : "0");
    localStorage.setItem("notif_sub_id", NOTIF.subId || "");
    localStorage.setItem("notif_last_ts", String(NOTIF.lastTs || 0));
  } catch (e) { console.warn("[Silent error]", e); }
}

function setNotifyStatus(msg) {
  const s = $("#notifyStatus");
  if (s) s.textContent = msg || "";
}

function getLatestItem(items) {
  let best = null;
  for (const it of items) if (!best || (it.createdTs || 0) > (best.createdTs || 0)) best = it;
  return best;
}

function fireDesktopNotification(item) {
  if (!("Notification" in window)) return;
  if (Notification.permission !== "granted") return;

  try {
    const n = new Notification("New UGC on sale", {
      body: item?.name ? item.name : "A new item was published.",
      icon: item?.thumb || undefined,
      tag: "ugc-new",
      renotify: true,
    });
    n.onclick = () => {
      try { window.focus(); } catch (e) { console.warn("[Silent error]", e); }
      if (item?.assetId) window.open(ROBLOX_ITEM_URL(item.assetId), "_blank", "noopener,noreferrer");
      try { n.close(); } catch (e) { console.warn("[Silent error]", e); }
    };
  } catch (e) { console.warn("[Silent error]", e); }
}

async function subscribeRemoteEmail(email) {
  const payload = {
    email: String(email || "").trim(),
    channels: { email: true },
  };

  const r = await fetch("/api/subscribe", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });

  const j = await r.json().catch(() => ({}));
  if (!r.ok || j?.ok !== true) throw new Error(String(j?.error || `http_${r.status}`));
  return String(j.id || "");
}

/**
 * Checks if a newer on-sale item exists. If yes -> refresh UI (boot()) automatically.
 * Works with the JSON generated by fetch_ugc.py (data_user.json / data_group.json).
 */
async function checkForNewUgc({ notify = true } = {}) {
  const [userRaw, groupRaw] = await Promise.all([
    fetchJson(FILES.user, { optional: true }),
    fetchJson(FILES.group, { optional: true }),
  ]);

  const u = normalizeItems(userRaw, "Profile");
  const g = normalizeItems(groupRaw, "Group");

  const all = [...u.items, ...g.items].filter((x) => num(x.price) != null && x.price > 0);
  const latest = getLatestItem(all);
  if (!latest) return;

  if (!NOTIF.lastTs) {
    NOTIF.lastTs = latest.createdTs || 0;
    saveNotifPrefs();
    return;
  }

  if ((latest.createdTs || 0) > (NOTIF.lastTs || 0)) {
    NOTIF.lastTs = latest.createdTs || 0;
    saveNotifPrefs();

    if (notify) showToast("New item detected ✨");
    if (notify && NOTIF.desktop) fireDesktopNotification(latest);

    boot();
  }
}

/** Always runs in background (no user action). */
function scheduleAutoRefreshLoop() {
  clearTimeout(NOTIF.timer);
  NOTIF.timer = setTimeout(async () => {
    try { await checkForNewUgc({ notify: true }); } catch (e) { console.warn("[Auto-refresh error]", e); }
    scheduleAutoRefreshLoop();
  }, NOTIF.intervalMs);
}

/* Notify modal */
function openNotifyModal() {
  const modal = $("#notifyModal");
  if (!modal) return;

  $("#chkDesktop") && ($("#chkDesktop").checked = !!NOTIF.desktop);
  $("#chkEmail") && ($("#chkEmail").checked = !!NOTIF.email);

  // don't prefill email (privacy)
  $("#notifyEmail") && ($("#notifyEmail").value = "");

  updateNotifyFieldVisibility();

  setNotifyStatus(
    (NOTIF.desktop || NOTIF.email)
      ? "Enabled."
      : "Disabled."
  );

  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeNotifyModal() {
  const modal = $("#notifyModal");
  if (!modal) return;
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

function updateNotifyFieldVisibility() {
  const emailOn = !!$("#chkEmail")?.checked;
  const rowEmail = $("#rowEmail");
  if (rowEmail) rowEmail.style.display = emailOn ? "flex" : "none";
}

function looksLikeEmail(s) {
  const v = String(s || "").trim();
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v);
}

async function saveNotifySettings() {
  const wantDesktop = !!$("#chkDesktop")?.checked;
  const wantEmail = !!$("#chkEmail")?.checked;

  const email = String($("#notifyEmail")?.value || "").trim();

  // Validate
  if (wantEmail && !looksLikeEmail(email)) {
    showToast("Invalid email");
    return;
  }

  // Desktop permission
  if (wantDesktop) {
    if (!("Notification" in window)) {
      showToast("Not supported");
      return;
    }
    const perm = await Notification.requestPermission();
    if (perm !== "granted") {
      showToast("Permission denied");
      return;
    }
  }

  // Remote subscribe (email)
  let subId = NOTIF.subId || "";
  if (wantEmail) {
    try {
      subId = await subscribeRemoteEmail(email);
      showToast("Saved ✅");
      setNotifyStatus("Email saved (encrypted).");
    } catch (e) {
      const code = String(e?.message || "");
      if (code === "kv_not_configured" || code === "key_not_configured" || code === "server_not_configured") {
        showToast("Email backend not configured");
        setNotifyStatus("Email backend not configured (Cloudflare KV + NOTIFY_KEY).");
      } else if (code === "bad_email") {
        showToast("Invalid email");
        setNotifyStatus("Invalid email.");
      } else if (code === "bad_json" || code === "bad_content_type" || code === "no_channel") {
        showToast("Email backend error");
        setNotifyStatus(`Backend rejected request (${code}).`);
      } else if (code === "server_error") {
        showToast("Email backend error");
        setNotifyStatus("Email backend error. Check NOTIFY_KEY and redeploy.");
      } else {
        showToast("Email subscription failed");
        setNotifyStatus(`Email subscription failed (${code || "unknown"}).`);
      }
      // keep desktop if enabled, do not close modal
      return;
    }
  } else {
    subId = "";
  }

  NOTIF.desktop = wantDesktop;
  NOTIF.email = wantEmail;
  NOTIF.subId = subId;

  // baseline & loop
  try { await checkForNewUgc({ notify: false }); } catch (e) { console.warn("[Silent error]", e); }
  saveNotifPrefs();

  closeNotifyModal();
}


/* Wiring */
function wireUI() {
  // Tabs
  $$(".tabBtn").forEach((b) => {
    if (!b.dataset.view) return;
    on(b, "click", () => setActiveView(b.dataset.view));
  });

  // Legal jump
  on($("#btnLegal"), "click", () => jumpToLegal());

  // Refresh
  on($("#btnRefresh"), "click", () => boot());

  // Notify
  on($("#btnNotify"), "click", () => openNotifyModal());
  on($("#notifyClose"), "click", closeNotifyModal);
  on($("#notifyCancel"), "click", closeNotifyModal);
  on($("#notifySave"), "click", () => saveNotifySettings());
  on($("#notifyModal"), "click", (e) => { if (e.target && e.target.id === "notifyModal") closeNotifyModal(); });

  on($("#chkEmail"), "change", updateNotifyFieldVisibility);
  
  // Filters (debounced search)
  const runFilter = () => {
    applyFilters();
    updateFilterActiveUI();
    renderPodium();
    renderUgcGrid();

    // Re-apply counts/classes on newly rendered cards
    try {
      STATE.filtered.forEach((x) => updateLikeButtons(x.assetId));
    } catch (e) { console.warn("[Silent error]", e); }
  };

  ["fCategory", "fType", "fSort"].forEach((id) => on(document.getElementById(id), "change", runFilter));

  const search = document.getElementById("fSearch");
  let t = null;
  on(search, "input", () => {
    clearTimeout(t);
    t = setTimeout(runFilter, 90);
  });

  // Commissions segment
  $$(".segBtn").forEach((b) => {
    on(b, "click", () => {
      $$(".segBtn").forEach((x) => {
        x.classList.toggle("active", x === b);
        x.setAttribute("aria-selected", x === b ? "true" : "false");
      });
      STATE.commMode = b.dataset.comm;
      renderCommissions();
    });
  });

  // Click actions
  on($("#ugcGrid"), "click", onClickAction);
  on($("#podiumRow"), "click", onClickAction);
  on($("#galleryGrid"), "click", onClickAction);
  on($("#commissionGrid"), "click", onClickAction);
  on($("#contactGrid"), "click", onClickAction);

  // Modal close
  on($("#modalClose"), "click", closeModal);
  on($("#modal"), "click", (e) => { if (e.target && e.target.id === "modal") closeModal(); });
  on(document, "keydown", (e) => { if (e.key === "Escape") { closeModal(); closeNotifyModal(); } });

  // Modal tools
  on($("#zoomIn"), "click", () => modalZoom(+0.25));
  on($("#zoomOut"), "click", () => modalZoom(-0.25));
  on($("#zoomReset"), "click", modalReset);

  // Modal wheel zoom + drag
  const stage = $("#modalStage");
  if (!stage) return;

  on(stage, "wheel", (e) => {
    const modal = $("#modal");
    if (!modal || !modal.classList.contains("open")) return;
    e.preventDefault();
    modalZoom(e.deltaY < 0 ? +0.2 : -0.2);
  }, { passive: false });

  on(stage, "pointerdown", (e) => {
    const modal = $("#modal");
    if (!modal || !modal.classList.contains("open")) return;
    if (ZOOM.scale <= 1) return;
    ZOOM.dragging = true;
    ZOOM.px = e.clientX;
    ZOOM.py = e.clientY;
    try { stage.setPointerCapture(e.pointerId); } catch (e) { console.warn("[Silent error]", e); }
  });

  on(stage, "pointermove", (e) => {
    if (!ZOOM.dragging) return;
    const dx = e.clientX - ZOOM.px;
    const dy = e.clientY - ZOOM.py;
    ZOOM.px = e.clientX;
    ZOOM.py = e.clientY;
    ZOOM.x += dx;
    ZOOM.y += dy;
    setModalTransform();
  });

  on(stage, "pointerup", () => { ZOOM.dragging = false; });
  on(stage, "pointercancel", () => { ZOOM.dragging = false; });
}

function normalizeItems(raw, sourceLabel) {
  const items = Array.isArray(raw?.items) ? raw.items : [];
  const updated = raw?.updated || null;
  const out = [];

  for (const it of items) {
    if (!it || typeof it !== "object") continue;
    const assetId = it.assetId ?? it.id;
    const price = it.price ?? it.priceInRobux;
    const created = it.created ?? it.createdUtc ?? null;
    const fav = it.favorites ?? it.favoriteCount ?? it.favoritesCount ?? null;
    if (!assetId) continue;

    out.push({
      assetId,
      name: it.name || `Item ${assetId}`,
      type: it.type || it.assetType || "Other",
      price,
      created,
      createdTs: created ? Date.parse(created) : 0,
      thumb: it.thumb || it.thumbnail || FALLBACK_THUMB(assetId),
      favorites: fav,
      source: sourceLabel,
      updated,
    });
  }

  return { items: out, updated };
}

async function boot() {
  $("#ugcGrid")?.replaceChildren();
  $("#podiumRow")?.replaceChildren();
  $("#ugcEmpty") && ($("#ugcEmpty").hidden = true);
  $("#podiumEmpty") && ($("#podiumEmpty").hidden = true);
  $("#ugcCount") && ($("#ugcCount").textContent = "…");
  $("#podiumHint") && ($("#podiumHint").textContent = "…");
  $("#updateInfo") && ($("#updateInfo").textContent = "");

  let userRaw = null;
  let groupRaw = null;

  try {
    [userRaw, groupRaw] = await Promise.all([
      fetchJson(FILES.user, { optional: true }),
      fetchJson(FILES.group, { optional: true }),
    ]);
  } catch (e) { console.warn("[Silent error]", e); }

  const u = normalizeItems(userRaw, "Profile");
  const g = normalizeItems(groupRaw, "Group");
  STATE.all = [...u.items, ...g.items];

  // Update info
  const parts = [];
  if (u.updated) parts.push(`Updated Profile: ${u.updated}`);
  if (g.updated) parts.push(`Updated Group: ${g.updated}`);
  $("#updateInfo") && ($("#updateInfo").textContent = parts.join(" • "));

  if (!STATE.all.length) {
    $("#ugcCount") && ($("#ugcCount").textContent = `0 ${plural(0, "item", "items")}`);
    $("#podiumHint") && ($("#podiumHint").textContent = `0 ${plural(0, "item", "items")}`);
    $("#ugcEmpty") && ($("#ugcEmpty").hidden = false);
    $("#podiumEmpty") && ($("#podiumEmpty").hidden = false);
  }

  renderFiltersUI();
  applyFilters();
  updateFilterActiveUI();
  renderPodium();
  renderUgcGrid();
  // Likes: fetch counts for all items (async, idle)
  scheduleIdle(() => {
    fetchLikeCounts(STATE.all.map((x) => x.assetId))
    .then(() => {
      // Sync visible cards
      STATE.filtered.forEach((x) => updateLikeButtons(x.assetId));
      // Podium too
      computePodium(STATE.all).slice(0, 3).forEach((x) => updateLikeButtons(x.assetId));
    })
    .catch(() => {});
  });

  // Gallery + Commissions (defer for smoothness)
  scheduleIdle(async () => {
    const gal = await fetchJson(FILES.gallery, { optional: true });
    STATE.gallery = Array.isArray(gal) ? gal : (Array.isArray(gal?.images) ? gal.images : []);
    renderGallery();
  }, 1200);

  scheduleIdle(async () => {
    const comRaw = await fetchJson(FILES.commissions, { optional: true });
    STATE.commissions = normalizeCommissionJson(comRaw);
    renderCommissions();
  }, 1400);
}

function scheduleIdle(fn, timeout = 1200) {
  const ric = window.requestIdleCallback;
  if (typeof ric === "function") {
    ric(() => fn(), { timeout });
  } else {
    setTimeout(fn, 0);
  }
}


/* Ripple effects (lightweight) */
function initRipples() {
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) return;

  document.addEventListener("pointerdown", (e) => {
    const el = e.target.closest("button, a");
    if (!el) return;

    // Only for visible, clickable elements
    const rect = el.getBoundingClientRect();
    if (rect.width < 18 || rect.height < 18) return;

    // Ensure containment
    const cs = getComputedStyle(el);
    if (cs.position === "static") el.style.position = "relative";
    if (cs.overflow === "visible") el.style.overflow = "hidden";

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const r = document.createElement("span");
    r.className = "ripple";
    r.style.left = `${x}px`;
    r.style.top = `${y}px`;

    el.appendChild(r);

    // cleanup
    r.addEventListener("animationend", () => r.remove(), { once: true });
  }, { passive: true });
}

document.addEventListener("DOMContentLoaded", () => {
  loadNotifPrefs();
  loadLikePrefs();
  wireUI();
  hardenClient();
  initRipples();
  boot();

  // Baseline (no toast), then auto-refresh loop.
  setTimeout(() => { checkForNewUgc({ notify: false }).catch((e) => console.warn("[Boot refresh error]", e)); }, 600);
  scheduleAutoRefreshLoop();

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) checkForNewUgc({ notify: false }).catch((e) => console.warn("[Boot refresh error]", e));
  });
});

/* =====================================================================
   SIM — Scherer Investments Money · Frontend Application
   ===================================================================== */

let STATE = {
  portfolio: null,
  currentTab: "DASHBOARD",
  previousTab: "DASHBOARD",
  portfolioSubTab: "CHART", // 'CHART' | 'CATEGORIES'
  donutMode: "CATEGORY",    // 'CATEGORY' | 'ASSET'
  categoryListFilter: "ALL",
  marketClass: "ACAO_BR",
  marketSort: "em_alta",
  marketScope: "ALL",       // 'ALL' | 'FAVORITES' | 'MINE'
  onlyMine: false,
  marketSearch: "",
  portfolioSearch: "",
  listLayout: localStorage.getItem("sim.listLayout") || "GRID", // 'GRID' | 'STRIPS'
  favorites: new Set(JSON.parse(localStorage.getItem("sim.favorites") || "[]")),
  lastMarketAssets: [],
  privacyMode: false,
  theme: localStorage.getItem("sim.theme") || "dark",
  activeAssetTicker: null,
  activeAssetPeriod: "1M",
  activeAssetData: null,
  currentUser: null,
};

/* ---------- Paleta semântica ---------- */
const CLASS_COLORS = {
  FII: "#5b8def",
  ACAO_BR: "#3ecf8e",
  CAIXINHA: "#a78bfa",
  RENDA_FIXA: "#818cf8",
  TESOURO: "#2dd4bf",
  FUNDO_INV: "#e8b04b",
  ETF_BR: "#38bdf8",
  STOCK_US: "#f0883e",
  CRIPTO: "#f472b6",
};

const ASSET_PALETTE = [
  "#3ecf8e", "#5b8def", "#a78bfa", "#e8b04b", "#f472b6",
  "#38bdf8", "#818cf8", "#2dd4bf", "#f0883e", "#f2555a",
  "#84cc16", "#c084fc", "#60a5fa", "#fbbf24"
];

const CLASS_NAMES = {
  FII: "Fundos Imobiliários",
  ACAO_BR: "Ações B3",
  CAIXINHA: "Caixinhas & Liquidez Diária",
  RENDA_FIXA: "CDB, LCI, LCA & Renda Fixa",
  TESOURO: "Tesouro Direto",
  FUNDO_INV: "Fundos de Investimento",
  ETF_BR: "ETFs Listados na B3",
  STOCK_US: "Stocks & REITs (EUA)",
  CRIPTO: "Criptomoedas",
};

const CLASS_SUBTITLES = {
  FII: "Fundos imobiliários e Fiagros listados na B3 — renda mensal isenta de IR.",
  ACAO_BR: "Empresas brasileiras negociadas na B3 com cotações, múltiplos e dividendos.",
  ETF_BR: "Fundos de índice nacionais e internacionais negociados na B3.",
  STOCK_US: "Empresas e REITs listados nas bolsas americanas (NYSE / NASDAQ) em dólar.",
  CRIPTO: "Criptoativos globais com cotação em dólar em tempo real.",
};

/* ---------- Sistema de Ícones Vetoriais (Lucide-style) ---------- */
const ICONS = {
  wallet: `<rect x="2" y="5" width="20" height="15" rx="3"/><path d="M16 12.5h.01"/><path d="M2 9.5h20"/>`,
  piggy: `<path d="M19 5c-1.5 0-2.8 1.4-3 2-3.5-1.5-11-.3-11 5 0 1.8 0 3 2 4.5V20h4v-2h3v2h4v-4c1-.5 1.7-1 2-2h2v-4h-2c0-1-.5-1.5-1-2V5z"/><path d="M2 9v1c0 1.1.9 2 2 2h1"/><path d="M16 11h.01"/>`,
  coins: `<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/>`,
  "trending-up": `<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>`,
  "trending-down": `<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>`,
  building: `<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/>`,
  layers: `<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>`,
  globe: `<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>`,
  bitcoin: `<path d="M11.767 19.089c4.924.868 6.14-6.025 1.216-6.894m-1.216 6.894L5.86 18.047m5.908 1.042-.347 1.97m1.563-8.864c4.924.869 6.14-6.025 1.215-6.893m-1.215 6.893-3.94-.694m5.155-6.2L8.29 4.26m5.908 1.042.348-1.97M7.48 20.364l3.126-17.727"/>`,
  smartphone: `<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/>`,
  refresh: `<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/>`,
  eye: `<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>`,
  "eye-off": `<path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"/><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"/><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"/><path d="m2 2 20 20"/>`,
  moon: `<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>`,
  sun: `<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>`,
  plus: `<path d="M5 12h14"/><path d="M12 5v14"/>`,
  minus: `<path d="M5 12h14"/>`,
  pie: `<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>`,
  list: `<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>`,
  trash: `<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>`,
  target: `<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>`,
  "arrow-right": `<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>`,
  "arrow-left": `<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>`,
  "arrow-up-right": `<path d="M7 7h10v10"/><path d="M7 17 17 7"/>`,
  history: `<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>`,
  "chevron-down": `<path d="m6 9 6 6 6-6"/>`,
  flame: `<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>`,
  tag: `<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>`,
  calculator: `<rect width="16" height="20" x="4" y="2" rx="2"/><line x1="8" x2="16" y1="6" y2="6"/><line x1="16" x2="16" y1="14" y2="18"/><path d="M16 10h.01"/><path d="M12 10h.01"/><path d="M8 10h.01"/><path d="M12 14h.01"/><path d="M8 14h.01"/><path d="M12 18h.01"/><path d="M8 18h.01"/>`,
  sparkles: `<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/>`,
  newspaper: `<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/>`,
  compass: `<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>`,
  x: `<path d="M18 6 6 18"/><path d="m6 6 12 12"/>`,
  search: `<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>`,
  check: `<path d="M20 6 9 17l-5-5"/>`,
  "check-circle": `<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>`,
  alert: `<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>`,
  download: `<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>`,
  landmark: `<line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/><line x1="10" x2="10" y1="18" y2="11"/><line x1="14" x2="14" y1="18" y2="11"/><line x1="18" x2="18" y1="18" y2="11"/><polygon points="12 2 20 7 4 7"/>`,
  shield: `<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>`,
  star: `<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>`,
  "star-fill": `<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" fill="currentColor"/>`,
  grid: `<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/>`,
  rows: `<rect x="3" y="4" width="18" height="4" rx="1"/><rect x="3" y="10" width="18" height="4" rx="1"/><rect x="3" y="16" width="18" height="4" rx="1"/>`,
  gauge: `<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>`,
  "file-spreadsheet": `<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M8 13h2"/><path d="M14 13h2"/><path d="M8 17h2"/><path d="M14 17h2"/>`,
  "upload-cloud": `<path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m16 16-4-4-4 4"/>`,
  settings: `<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>`,
  "message-circle": `<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>`,
  send: `<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>`,
  user: `<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>`,
  "user-plus": `<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/>`,
  users: `<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>`,
  lock: `<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>`,
  key: `<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/><path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/>`,
  "shield-check": `<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>`,
};

function ic(name, size = 16) {
  const body = ICONS[name] || ICONS.coins;
  return `<svg class="ic" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach(el => {
    const name = el.getAttribute("data-icon");
    const size = parseInt(el.getAttribute("data-size") || "16", 10);
    el.classList.add("ic-wrap");
    el.innerHTML = ic(name, size);
  });
}

const CLASS_ICON_NAME = {
  FII: "building",
  ACAO_BR: "trending-up",
  CAIXINHA: "piggy",
  RENDA_FIXA: "shield",
  TESOURO: "landmark",
  FUNDO_INV: "layers",
  ETF_BR: "layers",
  STOCK_US: "globe",
  CRIPTO: "bitcoin",
};

function classAvatar(cls, label = "", sizeCls = "") {
  const c = CLASS_COLORS[cls] || "#3ecf8e";
  const content = label
    ? label.slice(0, 4).toUpperCase()
    : ic(CLASS_ICON_NAME[cls] || "coins", sizeCls === "lg" ? 22 : 16);
  return `<span class="avatar ${sizeCls}" style="--c:${c}">${content}</span>`;
}

/* ---------- Segurança & Sanitização (XSS Protection) ---------- */
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
const esc = escapeHtml;

function sanitizeUrl(url) {
  if (!url || typeof url !== "string") return "#";
  const trimmed = url.trim();
  if (/^(https?:|\/|data:image\/|blob:)/i.test(trimmed)) {
    return trimmed.replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
  return "#";
}

/* ---------- Wrapper de API com Autenticação Token/PIN & CSRF Safe ---------- */
const _nativeFetch = window.fetch;
window.fetch = async function (url, options = {}) {
  const isApi = typeof url === "string" && url.startsWith("/api/");
  if (isApi) {
    options = options || {};
    const headers = new Headers(options.headers || {});
    const token = localStorage.getItem("sim_auth_token");
    if (token && !headers.has("X-SIM-Token")) {
      headers.set("X-SIM-Token", token);
    }
    options.headers = headers;
  }
  const res = await _nativeFetch(url, options);
  if (isApi && res.status === 401 && !url.includes("/api/auth/status") && !url.includes("/api/auth/login") && !url.includes("/api/auth/setup")) {
    localStorage.removeItem("sim_auth_token");
    STATE.currentUser = null;
    openAuthModal("LOGIN");
  }
  return res;
};

/* ---------- Formatadores ---------- */
function fmtMoney(val, currency = "BRL") {
  if (STATE.privacyMode) return "••••••";
  const num = Number(val || 0);
  const sym = currency === "USD" ? "US$ " : "R$ ";
  return sym + num.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(val, showPlus = true) {
  const num = Number(val || 0);
  const prefix = showPlus && num > 0 ? "+" : "";
  return prefix + num.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%";
}

function fmtCompact(val) {
  const num = Number(val || 0);
  if (num >= 1e9) return "R$ " + (num / 1e9).toFixed(2).replace(".", ",") + " bi";
  if (num >= 1e6) return "R$ " + (num / 1e6).toFixed(1).replace(".", ",") + " mi";
  if (num >= 1e3) return "R$ " + (num / 1e3).toFixed(0) + " mil";
  return "R$ " + num.toFixed(0);
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function normalizeSearchText(str) {
  return String(str || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

/* ---------- Favoritos (Estrela) & Estilo de Lista (Grade vs Tiras) ---------- */
function isFavorite(ticker) {
  return STATE.favorites.has(String(ticker || "").toUpperCase());
}

function saveFavoritesLocal() {
  try {
    localStorage.setItem("sim.favorites", JSON.stringify([...STATE.favorites]));
  } catch (e) {}
}

async function syncFavoritesFromServer() {
  try {
    const res = await fetch("/api/favorites");
    if (res.ok) {
      const data = await res.json();
      const serverFavs = (data.favorites || []).map(t => String(t).toUpperCase());
      const localOnly = [...STATE.favorites].filter(t => !serverFavs.includes(t));
      serverFavs.forEach(t => STATE.favorites.add(t));
      saveFavoritesLocal();
      for (const t of localOnly) {
        fetch(`/api/favorites/${encodeURIComponent(t)}`, { method: "POST" }).catch(() => {});
      }
      updateFavoriteCounters();
    }
  } catch (e) {}
}

function favStarButton(ticker, sizeCls = "") {
  const t = String(ticker || "").toUpperCase();
  const fav = isFavorite(t);
  const iconSize = sizeCls === "lg" ? 18 : 15;
  return `<button type="button" class="fav-btn ${fav ? "is-fav" : ""} ${sizeCls}" data-fav-ticker="${t}" onclick="toggleFavorite('${t}', event)" title="${fav ? "Remover dos favoritos" : "Marcar como favorito"}">${ic(fav ? "star-fill" : "star", iconSize)}</button>`;
}

async function toggleFavorite(ticker, ev) {
  if (ev && ev.stopPropagation) ev.stopPropagation();
  const t = String(ticker || "").toUpperCase().trim();
  if (!t) return;

  const willBeFav = !STATE.favorites.has(t);
  if (willBeFav) STATE.favorites.add(t);
  else STATE.favorites.delete(t);
  saveFavoritesLocal();

  // Atualiza todos os botões de estrela desse ativo visíveis na tela
  document.querySelectorAll(`[data-fav-ticker="${t}"]`).forEach(btn => {
    btn.classList.toggle("is-fav", willBeFav);
    const isLg = btn.classList.contains("lg");
    btn.innerHTML = ic(willBeFav ? "star-fill" : "star", isLg ? 18 : 15);
    btn.title = willBeFav ? "Remover dos favoritos" : "Marcar como favorito";
  });

  updateFavoriteCounters();
  showToast(willBeFav ? `${t} marcado como favorito ★` : `${t} removido dos favoritos.`);

  // Sincroniza com o banco SQLite
  fetch(`/api/favorites/${encodeURIComponent(t)}`, { method: "POST" }).catch(() => {});

  // Se estiver filtrando apenas favoritos, re-renderiza a lista imediatamente
  if (STATE.currentTab === "DASHBOARD" && STATE.categoryListFilter === "FAVORITES" && STATE.portfolio) {
    renderCategorizedInvestments(STATE.portfolio);
  } else if (["ACAO_BR", "FII", "STOCK_US", "CRIPTO", "ETF_BR"].includes(STATE.currentTab) && STATE.marketScope === "FAVORITES") {
    renderMarketAssetsView();
  }
}

function updateFavoriteCounters() {
  // Contador de favoritos na aba de mercado atual
  const favScopeCount = document.getElementById("fav-scope-count");
  if (favScopeCount) {
    const classAssets = STATE.lastMarketAssets || [];
    const inClassCount = classAssets.filter(a => isFavorite(a.ticker)).length;
    favScopeCount.textContent = inClassCount;
  }

  // Contador de favoritos na carteira
  const portFavCount = document.getElementById("portfolio-fav-count");
  if (portFavCount && STATE.portfolio) {
    const pos = STATE.portfolio.positions || [];
    const count = pos.filter(p => isFavorite(p.ticker)).length;
    portFavCount.textContent = count > 0 ? `(${count})` : "";
  }
}

function setListLayout(mode) {
  STATE.listLayout = mode === "STRIPS" ? "STRIPS" : "GRID";
  localStorage.setItem("sim.listLayout", STATE.listLayout);
  syncLayoutButtons();
  if (STATE.portfolio) {
    renderCategorizedInvestments(STATE.portfolio);
  }
  if (["ACAO_BR", "FII", "STOCK_US", "CRIPTO", "ETF_BR"].includes(STATE.currentTab)) {
    renderMarketAssetsView();
  }
}

function syncLayoutButtons() {
  document.querySelectorAll(".layout-btn-GRID").forEach(b => b.classList.toggle("is-active", STATE.listLayout === "GRID"));
  document.querySelectorAll(".layout-btn-STRIPS").forEach(b => b.classList.toggle("is-active", STATE.listLayout === "STRIPS"));
}

/* ---------- Inicialização ---------- */
async function initApp() {
  hydrateIcons();
  syncThemeButton();
  syncLayoutButtons();
  syncFavoritesFromServer();

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }

  const today = new Date().toISOString().split("T")[0];
  const txDate = document.getElementById("tx-date");
  const fiStart = document.getElementById("fi-start");
  const divDate = document.getElementById("div-date");
  const fiMat = document.getElementById("fi-maturity");
  if (txDate) txDate.value = today;
  if (fiStart) fiStart.value = today;
  if (divDate) divDate.value = today;
  if (fiMat) fiMat.value = "2028-12-31";

  buildStaticLists();

  // Fechar modais com ESC ou clique no backdrop
  document.querySelectorAll(".modal").forEach(m => {
    m.addEventListener("click", (ev) => {
      if (ev.target === m) {
        if (m.id === "modal-auth" && !STATE.currentUser) return;
        closeModal(m.id);
      }
    });
  });
  window.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      document.querySelectorAll(".modal.is-open").forEach(m => {
        if (m.id === "modal-auth" && !STATE.currentUser) return;
        closeModal(m.id);
      });
    }
  });

  window.addEventListener("resize", () => {
    if (STATE.currentTab === "ASSET_DETAIL" && STATE.activeAssetData) {
      drawInteractiveAssetChart(STATE.activeAssetData);
    } else if (STATE.currentTab === "DASHBOARD" && STATE.portfolio) {
      drawDonutWithHover(_currentDonutSlices, _currentDonutTotal, null);
    }
  });

  const authOk = await checkAuthStatus();
  if (authOk) {
    await refreshAll();
  }
  setInterval(() => {
    if (STATE.currentUser) {
      refreshAll(true);
    }
  }, 30000);
}

function buildStaticLists() {
  // Tiles de estado vazio e do modal de novo lançamento
  const options = [
    { key: "FII", title: "Fundo Imobiliário", sub: "MXRF11, HGLG11, KNCR11…", color: CLASS_COLORS.FII, icon: "building" },
    { key: "ACAO_BR", title: "Ação Brasileira", sub: "PETR4, VALE3, BBAS3, WEGE3…", color: CLASS_COLORS.ACAO_BR, icon: "trending-up" },
    { key: "CAIXINHA", title: "Caixinha / Liquidez", sub: "Nubank, Inter, 100%–110% CDI", color: CLASS_COLORS.CAIXINHA, icon: "piggy" },
    { key: "RENDA_FIXA", title: "CDB, LCI ou LCA", sub: "Pós-fixado CDI, IPCA+ ou isento", color: CLASS_COLORS.RENDA_FIXA, icon: "shield" },
    { key: "TESOURO", title: "Tesouro Direto", sub: "Tesouro Selic, IPCA+ ou Prefixado", color: CLASS_COLORS.TESOURO, icon: "landmark" },
    { key: "STOCK_US", title: "Global / ETF / Cripto", sub: "Stocks EUA, ETFs e Bitcoin", color: CLASS_COLORS.STOCK_US, icon: "globe" },
  ];

  const emptyTiles = document.getElementById("empty-tiles");
  if (emptyTiles) {
    emptyTiles.innerHTML = `
      <button class="tile" style="--c:#3ecf8e" onclick="openB3SyncModal()">
        <span class="avatar sm" style="--c:#3ecf8e">${ic("file-spreadsheet", 16)}</span>
        <div>
          <div class="tile-title">Sincronizar Planilha B3</div>
          <div class="tile-sub">Importar Excel (.xlsx) do Portal B3</div>
        </div>
      </button>
    ` + options.slice(0, 3).map(o => `
      <button class="tile" style="--c:${o.color}" onclick="openAddInvestmentModal('${o.key}')">
        <span class="avatar sm" style="--c:${o.color}">${ic(o.icon, 16)}</span>
        <div>
          <div class="tile-title">${o.title}</div>
          <div class="tile-sub">${o.sub}</div>
        </div>
      </button>
    `).join("");
  }

  const pickerBody = document.getElementById("add-picker-body");
  if (pickerBody) {
    pickerBody.innerHTML = `
      <div class="callout" style="margin-bottom:4px;border-color:color-mix(in srgb, var(--accent) 35%, var(--border))">
        <div class="row gap-2">
          <span class="avatar sm" style="--c:#3ecf8e">${ic("file-spreadsheet", 16)}</span>
          <div>
            <div class="strong xs">Tem conta na B3 (Área do Investidor)?</div>
            <div class="xs faint">Sincronize Ações, FIIs, Tesouro, Renda Fixa e Proventos via Excel (.xlsx)</div>
          </div>
        </div>
        <button class="btn btn-sm btn-secondary" onclick="closeModal('modal-add-picker'); openB3SyncModal();">
          Sincronizar B3 ${ic("arrow-right", 13)}
        </button>
      </div>
      <div class="picker-section">Ou cadastre manualmente</div>
      <div class="picker">
        ${options.map(o => `
          <button class="tile" style="--c:${o.color}" onclick="closeModal('modal-add-picker'); openAddInvestmentModal('${o.key}')">
            <span class="avatar sm" style="--c:${o.color}">${ic(o.icon, 16)}</span>
            <div>
              <div class="tile-title">${o.title}</div>
              <div class="tile-sub">${o.sub}</div>
            </div>
          </button>
        `).join("")}
      </div>
      <div class="callout">
        <span>Recebeu dividendos ou rendimentos na conta?</span>
        <button class="link" onclick="closeModal('modal-add-picker'); openDividendModal();">
          Registrar provento ${ic("arrow-right", 14)}
        </button>
      </div>
    `;
  }

  // Chips de atalho no modal de transação
  const quickPicks = [
    ["MXRF11", "FII"], ["HGLG11", "FII"], ["XPML11", "FII"], ["KNCR11", "FII"], ["BTLG11", "FII"],
    ["PETR4", "ACAO_BR"], ["BBAS3", "ACAO_BR"], ["VALE3", "ACAO_BR"], ["WEGE3", "ACAO_BR"], ["ITUB4", "ACAO_BR"],
  ];
  const qpEl = document.getElementById("tx-quick-picks");
  if (qpEl) {
    qpEl.innerHTML = quickPicks.map(([t, cls]) => `
      <button type="button" class="chip" style="--c:${CLASS_COLORS[cls]}" onclick="quickPickTicker('${t}','${cls}')">
        <span class="dot"></span>${t}
      </button>
    `).join("");
  }
}

/* ---------- Tema & Privacidade ---------- */
function toggleTheme() {
  STATE.theme = STATE.theme === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", STATE.theme);
  localStorage.setItem("sim.theme", STATE.theme);
  syncThemeButton();
  if (STATE.portfolio) renderPortfolioDonutAndBars(STATE.portfolio);
  if (STATE.currentTab === "ASSET_DETAIL" && STATE.activeAssetData) {
    drawInteractiveAssetChart(STATE.activeAssetData);
  }
}

function syncThemeButton() {
  const btn = document.getElementById("btn-theme");
  if (!btn) return;
  btn.innerHTML = ic(STATE.theme === "dark" ? "sun" : "moon", 16);
  btn.title = STATE.theme === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro";
}

function togglePrivacy() {
  STATE.privacyMode = !STATE.privacyMode;
  const btn = document.getElementById("btn-privacy");
  if (btn) btn.innerHTML = ic(STATE.privacyMode ? "eye-off" : "eye", 16);
  if (STATE.portfolio) {
    renderDashboard(STATE.portfolio);
    renderFixedIncomeView(STATE.portfolio.fixed_income);
    renderDividendsView(STATE.portfolio.dividends);
  }
}

/* ---------- Atualização global ---------- */
async function refreshAll(silent = false) {
  const refreshBtn = document.getElementById("btn-refresh");
  if (!silent && refreshBtn) refreshBtn.classList.add("is-spinning");
  try {
    const res = await fetch("/api/portfolio");
    const data = await res.json();
    STATE.portfolio = data;
    renderMacroTicker(data.macro);
    renderDashboard(data);
    renderFixedIncomeView(data.fixed_income);
    renderDividendsView(data.dividends);
    await loadRebalance();

    if (["ACAO_BR", "FII", "STOCK_US", "CRIPTO", "ETF_BR"].includes(STATE.currentTab)) {
      await loadMarketClassAssets();
    } else if (STATE.currentTab === "ASSET_DETAIL" && STATE.activeAssetTicker) {
      await openAssetDetail(STATE.activeAssetTicker, STATE.activeAssetPeriod, true);
    }
  } catch (e) {
    console.error("Erro ao atualizar dados:", e);
  } finally {
    if (refreshBtn) setTimeout(() => refreshBtn.classList.remove("is-spinning"), 350);
  }
}

/* ---------- Macro Ticker Tape ---------- */
function renderMacroTicker(m) {
  if (!m) return;
  const items = [
    { label: "IBOV", val: Number(m.ibov).toLocaleString("pt-BR", { maximumFractionDigits: 0 }) + " pts", chg: m.ibov_change },
    { label: "USD/BRL", val: "R$ " + Number(m.usd_brl).toFixed(2).replace(".", ","), chg: m.usd_change },
    { label: "S&P 500", val: Number(m.sp500).toLocaleString("pt-BR", { maximumFractionDigits: 0 }), chg: m.sp500_change },
    { label: "BTC", val: "US$ " + Number(m.btc_usd).toLocaleString("pt-BR", { maximumFractionDigits: 0 }), chg: m.btc_change },
    { label: "SELIC", val: Number(m.selic).toFixed(2).replace(".", ",") + "% a.a.", chg: null },
    { label: "CDI", val: Number(m.cdi).toFixed(2).replace(".", ",") + "% a.a.", chg: null },
    { label: "IPCA 12M", val: Number(m.ipca_12m).toFixed(2).replace(".", ",") + "%", chg: null },
  ];

  const chunk = items.map(it => {
    let chgHtml = "";
    if (it.chg !== null && it.chg !== undefined) {
      const cls = it.chg >= 0 ? "pos" : "neg";
      chgHtml = `<span class="tk-chg ${cls}">${fmtPct(it.chg)}</span>`;
    }
    return `<span class="tk"><span class="tk-label">${it.label}</span><span class="tk-val">${it.val}</span>${chgHtml}</span>`;
  }).join("");

  const bar = document.getElementById("macro-ticker-bar");
  if (bar) bar.innerHTML = chunk + chunk; // duplicado para loop contínuo

  if (m.updated_at) {
    const badge = document.getElementById("last-sync-badge");
    if (badge) badge.textContent = "Sincronizado às " + m.updated_at;
  }
}

/* ---------- Sub-abas e Filtros da Carteira ---------- */
function switchPortfolioSubTab(subTab) {
  STATE.portfolioSubTab = subTab;
  const bChart = document.getElementById("subtab-CHART");
  const bCat = document.getElementById("subtab-CATEGORIES");
  const vChart = document.getElementById("portfolio-subview-CHART");
  const vCat = document.getElementById("portfolio-subview-CATEGORIES");

  if (subTab === "CHART") {
    bChart.classList.add("is-active");
    bCat.classList.remove("is-active");
    vChart.classList.remove("hidden");
    vCat.classList.add("hidden");
    if (STATE.portfolio) renderPortfolioDonutAndBars(STATE.portfolio);
  } else {
    bCat.classList.add("is-active");
    bChart.classList.remove("is-active");
    vCat.classList.remove("hidden");
    vChart.classList.add("hidden");
    if (STATE.portfolio) renderCategorizedInvestments(STATE.portfolio);
  }
}

function setDonutMode(mode) {
  STATE.donutMode = mode;
  document.getElementById("donut-mode-CATEGORY")?.classList.toggle("is-active", mode === "CATEGORY");
  document.getElementById("donut-mode-ASSET")?.classList.toggle("is-active", mode === "ASSET");
  if (STATE.portfolio) renderPortfolioDonutAndBars(STATE.portfolio);
}

function setCategoryListFilter(catKey) {
  STATE.categoryListFilter = catKey;
  document.querySelectorAll(".cat-filter-btn").forEach(b => b.classList.remove("is-active"));
  document.getElementById(`catfilter-${catKey}`)?.classList.add("is-active");
  if (STATE.portfolio) renderCategorizedInvestments(STATE.portfolio);
}

/* ---------- Dashboard: Hero + KPIs ---------- */
function renderDashboard(data) {
  const k = data.kpis;
  const kpiContainer = document.getElementById("kpi-cards-container");
  const profitPositive = k.total_profit_brl >= 0;
  const dayPositive = k.day_change_brl >= 0;

  const activeAlloc = (data.allocation || []).filter(a => a.current_brl > 0);
  const allocBarHtml = activeAlloc.length > 0
    ? activeAlloc.map(a => `<span style="flex-grow:${Math.max(1, a.current_pct)};background:${CLASS_COLORS[a.asset_class] || '#3ecf8e'}" title="${a.label}: ${a.current_pct.toFixed(1)}%"></span>`).join("")
    : `<span style="flex-grow:1;background:var(--surface-3)"></span>`;

  const allocLegendHtml = activeAlloc.length > 0
    ? activeAlloc.slice(0, 5).map(a => `<span><i style="background:${CLASS_COLORS[a.asset_class] || '#3ecf8e'}"></i>${a.label.split("(")[0].trim()} <b>${a.current_pct.toFixed(0)}%</b></span>`).join("")
    : `<span>Sem ativos cadastrados no momento</span>`;

  kpiContainer.innerHTML = `
    <div>
      <div class="eyebrow">Patrimônio líquido consolidado</div>
      <div class="hero-value">${fmtMoney(k.total_current_brl)}</div>
      <div class="hero-meta">
        <span class="badge ${dayPositive ? "badge-pos" : "badge-neg"}">${fmtPct(k.day_change_pct)} (${fmtMoney(k.day_change_brl)}) hoje</span>
        <span class="dot-sep"></span>
        <span class="muted">Equiv. <strong class="strong num">${fmtMoney(k.total_current_usd, "USD")}</strong></span>
        <span class="dot-sep"></span>
        <span class="faint">USD R$ ${Number(data.macro.usd_brl).toFixed(2).replace(".", ",")}</span>
      </div>
    </div>

    <div class="hero-stats">
      <div class="hero-stat">
        <div class="stat-label">Valor investido</div>
        <div class="stat-value">${fmtMoney(k.total_invested_brl)}</div>
        <div class="stat-foot">Custo de aquisição</div>
      </div>
      <div class="hero-stat">
        <div class="stat-label">Rentabilidade total</div>
        <div class="stat-value ${profitPositive ? "pos" : "neg"}">${fmtMoney(k.total_profit_brl)}</div>
        <div class="stat-foot ${profitPositive ? "pos" : "neg"}">${fmtPct(k.total_profit_pct)} sobre custo</div>
      </div>
      <div class="hero-stat">
        <div class="stat-label">Renda passiva est.</div>
        <div class="stat-value accent">${fmtMoney(k.estimated_monthly_divs_brl)}<span class="faint small"> /mês</span></div>
        <div class="stat-foot">Acumulado: ${fmtMoney(k.total_dividends_brl)}</div>
      </div>
      <div class="hero-stat">
        <div class="stat-label">Referência CDI</div>
        <div class="stat-value">${Number(data.macro.cdi).toFixed(2).replace(".", ",")}%<span class="faint small"> a.a.</span></div>
        <div class="stat-foot">IPCA 12m: ${Number(data.macro.ipca_12m).toFixed(2).replace(".", ",")}%</div>
      </div>
      <div class="hero-stat hero-alloc">
        <div class="alloc-bar">${allocBarHtml}</div>
        <div class="alloc-legend">${allocLegendHtml}</div>
      </div>
    </div>
  `;

  const totalHoldings = (data.positions ? data.positions.length : 0) + (data.fixed_income ? data.fixed_income.length : 0);
  const countBadge = document.getElementById("portfolio-count-badge");
  if (countBadge) countBadge.textContent = totalHoldings;
  const navCount = document.getElementById("nav-count-portfolio");
  if (navCount) navCount.textContent = totalHoldings > 0 ? totalHoldings : "";

  const emptyState = document.getElementById("portfolio-empty-state");
  const clearBtn = document.getElementById("btn-clear-portfolio");
  if (totalHoldings === 0) {
    emptyState.classList.remove("hidden");
    if (clearBtn) clearBtn.classList.add("hidden");
  } else {
    emptyState.classList.add("hidden");
    if (clearBtn) clearBtn.classList.remove("hidden");
  }

  renderPortfolioDonutAndBars(data);
  renderCategorizedInvestments(data);
}

/* ---------- Alocação: Donut + Legenda ---------- */
function renderPortfolioDonutAndBars(data) {
  const barsContainer = document.getElementById("allocation-bars-list");
  if (!barsContainer) return;

  let slices = [];
  if (STATE.donutMode === "ASSET") {
    const assets = data.allocation_by_asset || [];
    slices = assets.map((a, idx) => ({
      key: a.code,
      label: a.code,
      canvasLabel: a.code,
      sublabel: a.name !== a.code ? a.name : a.category_label,
      current_brl: a.current_brl,
      invested_brl: a.invested_brl,
      profit_brl: a.profit_brl,
      profit_pct: a.profit_pct,
      pct: a.weight_pct,
      color: ASSET_PALETTE[idx % ASSET_PALETTE.length],
      asset_class: a.asset_class,
      is_fixed_income: a.is_fixed_income,
      fi_id: a.fi_id,
    }));
  } else {
    const alloc = (data.allocation || []).filter(it => it.current_brl > 0 || it.target_pct > 0);
    slices = alloc.map(it => ({
      key: it.asset_class,
      label: it.label,
      canvasLabel: it.label.split("(")[0].trim(),
      sublabel: `${it.count || 0} ativo(s) · Meta ${it.target_pct}%`,
      current_brl: it.current_brl,
      invested_brl: it.invested_brl || 0,
      profit_brl: it.profit_brl || 0,
      profit_pct: it.profit_pct || 0,
      pct: it.current_pct,
      color: CLASS_COLORS[it.asset_class] || "#3ecf8e",
      asset_class: it.asset_class,
    }));
  }

  renderInteractiveDonutCanvas(slices, data.kpis.total_current_brl);
  renderQuickHoldingsGrid(data);

  const activeSlices = slices.filter(s => s.current_brl > 0);
  if (activeSlices.length === 0) {
    barsContainer.innerHTML = `
      <div class="empty-sm">
        Nenhum ativo na carteira ainda. Clique em <strong class="strong">Novo lançamento</strong> para começar.
      </div>
    `;
    return;
  }

  const isAssetMode = STATE.donutMode === "ASSET";
  barsContainer.innerHTML = activeSlices.map((item, idx) => {
    const profCls = item.profit_brl >= 0 ? "pos" : "neg";
    const clickAction = isAssetMode && !item.is_fixed_income
      ? `openAssetDetail('${item.key}')`
      : `openCategoryFromDonut('${item.asset_class}')`;

    const deleteBtn = isAssetMode
      ? (item.is_fixed_income && item.fi_id
          ? `<span class="row-actions"><button onclick="deleteFixedIncome(${item.fi_id}, event)" class="btn-icon sm danger" title="Remover">${ic("trash", 14)}</button></span>`
          : `<span class="row-actions"><button onclick="deleteVariablePosition('${item.key}', event)" class="btn-icon sm danger" title="Remover">${ic("trash", 14)}</button></span>`)
      : "";

    return `
      <div class="legend-row ${isAssetMode ? "has-actions" : ""}"
           onmouseenter="highlightDonutSlice(${idx})"
           onmouseleave="highlightDonutSlice(null)"
           onclick="${clickAction}">
        <span class="legend-dot" style="background:${item.color}"></span>
        <div style="min-width:0">
          <div class="legend-title">${item.label}</div>
          <div class="legend-sub">${item.sublabel}</div>
        </div>
        <div class="legend-val">
          <div class="strong">${fmtMoney(item.current_brl)}</div>
          <div class="xs ${profCls}">${fmtPct(item.profit_pct)}</div>
        </div>
        <div class="legend-pct">${item.pct.toFixed(1)}%</div>
        ${deleteBtn}
        <div class="legend-bar"><span style="width:${Math.min(100, Math.max(2, item.pct))}%;background:${item.color}"></span></div>
      </div>
    `;
  }).join("");
}

function renderQuickHoldingsGrid(data) {
  const panel = document.getElementById("quick-holdings-panel");
  const grid = document.getElementById("quick-holdings-grid");
  if (!panel || !grid) return;

  const positions = data.positions || [];
  const fixedIncome = data.fixed_income || [];
  if (positions.length === 0 && fixedIncome.length === 0) {
    panel.classList.add("hidden");
    grid.innerHTML = "";
    return;
  }

  panel.classList.remove("hidden");

  const posRows = positions.map(p => {
    const profCls = p.profit_brl >= 0 ? "pos" : "neg";
    return `
      <div class="hold-row">
        ${favStarButton(p.ticker)}
        ${classAvatar(p.asset_class, p.ticker, "sm")}
        <div class="hold-main" onclick="openAssetDetail('${p.ticker}')">
          <div class="hold-title">${p.ticker} <span class="faint xs">· ${p.quantity} cotas</span></div>
          <div class="hold-sub">${p.name}</div>
        </div>
        <div class="hold-val">
          <div class="strong">${fmtMoney(p.current_brl)}</div>
          <div class="xs ${profCls}">${fmtPct(p.profit_pct)}</div>
          ${p.pm_estimated ? `<div class="xs" style="color:var(--amber);cursor:pointer" onclick="openAdjustAvgPriceModal('${p.ticker}', ${p.avg_price}, event)" title="PM estimado pelo fechamento B3. Clique para ajustar.">⚠️ PM Estimado</div>` : ""}
        </div>
        <div class="row-actions">
          <button class="btn-icon sm" title="Lançar compra/venda" onclick="openTransactionModal('${p.ticker}','${p.asset_class}',${p.current_price},'${p.currency}')">${ic("plus", 14)}</button>
          <button class="btn-icon sm danger" title="Remover ${p.ticker}" onclick="deleteVariablePosition('${p.ticker}', event)">${ic("trash", 14)}</button>
        </div>
      </div>
    `;
  });

  const fiRows = fixedIncome.map(f => {
    return `
      <div class="hold-row">
        ${classAvatar(f.asset_class, "", "sm")}
        <div class="hold-main" onclick="switchMainTab('RENDA_FIXA')">
          <div class="hold-title">${f.title_name}</div>
          <div class="hold-sub">${f.issuer} · ${f.rate_label}</div>
        </div>
        <div class="hold-val">
          <div class="strong">${fmtMoney(f.net_amount)}</div>
          <div class="xs pos">${fmtPct(f.net_profit_pct)}</div>
        </div>
        <div class="row-actions">
          <button class="btn-icon sm danger" title="Remover título" onclick="deleteFixedIncome(${f.id}, event)">${ic("trash", 14)}</button>
        </div>
      </div>
    `;
  });

  grid.innerHTML = [...posRows, ...fiRows].join("");
}

function openCategoryFromDonut(assetClass) {
  switchPortfolioSubTab("CATEGORIES");
  const filterKey = ["ETF_BR", "FUNDO_INV", "STOCK_US", "CRIPTO"].includes(assetClass) ? "OUTROS" : assetClass;
  setCategoryListFilter(filterKey);
}

/* ---------- Donut Canvas (DPI-aware) ---------- */
let _currentDonutSlices = [];
let _currentDonutTotal = 0;

function highlightDonutSlice(hoverIdx) {
  drawDonutWithHover(_currentDonutSlices, _currentDonutTotal, hoverIdx);
}

function renderInteractiveDonutCanvas(slices, totalBrl) {
  _currentDonutSlices = slices.filter(s => s.current_brl > 0);
  _currentDonutTotal = totalBrl;
  drawDonutWithHover(_currentDonutSlices, _currentDonutTotal, null);

  const canvas = document.getElementById("allocation-canvas");
  if (!canvas) return;

  canvas.onmousemove = (e) => {
    if (_currentDonutSlices.length === 0) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    const dist = Math.sqrt(x * x + y * y);
    if (dist < 62 || dist > 112) {
      drawDonutWithHover(_currentDonutSlices, _currentDonutTotal, null);
      return;
    }
    let angle = Math.atan2(y, x) + Math.PI / 2;
    if (angle < 0) angle += Math.PI * 2;
    const total = _currentDonutSlices.reduce((acc, s) => acc + s.current_brl, 0);
    let accum = 0;
    let foundIdx = null;
    for (let i = 0; i < _currentDonutSlices.length; i++) {
      const sliceAngle = (_currentDonutSlices[i].current_brl / total) * (Math.PI * 2);
      if (angle >= accum && angle <= accum + sliceAngle) {
        foundIdx = i;
        break;
      }
      accum += sliceAngle;
    }
    drawDonutWithHover(_currentDonutSlices, _currentDonutTotal, foundIdx);
  };

  canvas.onmouseleave = () => {
    drawDonutWithHover(_currentDonutSlices, _currentDonutTotal, null);
  };
}

function drawDonutWithHover(activeSlices, totalBrl, hoverIdx = null) {
  const canvas = document.getElementById("allocation-canvas");
  if (!canvas) return;

  const size = 240;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = size * dpr;
  canvas.height = size * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, size, size);

  const cx = size / 2;
  const cy = size / 2;
  const radius = 88;
  const baseLineWidth = 22;

  const textMain = cssVar("--text") || "#edeef0";
  const textSub = cssVar("--text-3") || "#6b7079";
  const trackColor = cssVar("--chart-track") || "#1d2127";

  const total = activeSlices.reduce((acc, it) => acc + it.current_brl, 0);

  // Anel de fundo
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.strokeStyle = trackColor;
  ctx.lineWidth = baseLineWidth;
  ctx.stroke();

  if (total <= 0) {
    ctx.fillStyle = textSub;
    ctx.font = "500 11px Geist, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("SEM ATIVOS", cx, cy - 4);
    ctx.fillStyle = textMain;
    ctx.font = "400 20px 'Instrument Serif', Georgia, serif";
    ctx.fillText("R$ 0,00", cx, cy + 18);
    return;
  }

  let startAngle = -Math.PI / 2;
  activeSlices.forEach((item, idx) => {
    const sliceAngle = (item.current_brl / total) * (Math.PI * 2);
    const isHovered = hoverIdx === idx;
    const gap = activeSlices.length > 1 ? 0.028 : 0;
    ctx.beginPath();
    ctx.arc(cx, cy, isHovered ? radius + 2 : radius, startAngle, startAngle + Math.max(0.01, sliceAngle - gap));
    ctx.strokeStyle = item.color;
    ctx.lineWidth = isHovered ? baseLineWidth + 5 : baseLineWidth;
    ctx.stroke();
    startAngle += sliceAngle;
  });

  if (hoverIdx !== null && activeSlices[hoverIdx]) {
    const s = activeSlices[hoverIdx];
    const cleanTitle = (s.canvasLabel || s.label || "").slice(0, 18);
    ctx.fillStyle = textSub;
    ctx.font = "500 11px Geist, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(cleanTitle.toUpperCase(), cx, cy - 20);

    ctx.fillStyle = textMain;
    ctx.font = "400 30px 'Instrument Serif', Georgia, serif";
    ctx.fillText(`${s.pct.toFixed(1)}%`, cx, cy + 8);

    ctx.fillStyle = textSub;
    ctx.font = "500 11.5px 'Geist Mono', monospace";
    ctx.fillText(fmtMoney(s.current_brl), cx, cy + 26);
  } else {
    ctx.fillStyle = textSub;
    ctx.font = "500 10.5px Geist, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("PATRIMÔNIO", cx, cy - 18);

    ctx.fillStyle = textMain;
    ctx.font = "400 22px 'Instrument Serif', Georgia, serif";
    ctx.fillText(fmtMoney(totalBrl), cx, cy + 6);

    ctx.fillStyle = textSub;
    ctx.font = "500 11px Geist, sans-serif";
    ctx.fillText(`${activeSlices.length} ${STATE.donutMode === "ASSET" ? "ativo(s)" : "classe(s)"}`, cx, cy + 25);
  }
}

/* ---------- Posições por Categoria ---------- */
function onPortfolioSearchInput(val) {
  STATE.portfolioSearch = val || "";
  const clearBtn = document.getElementById("portfolio-search-clear");
  if (clearBtn) clearBtn.classList.toggle("hidden", !STATE.portfolioSearch.trim());
  if (STATE.portfolio) renderCategorizedInvestments(STATE.portfolio);
}

function clearPortfolioSearch() {
  STATE.portfolioSearch = "";
  const inp = document.getElementById("portfolio-search-input");
  if (inp) inp.value = "";
  const clearBtn = document.getElementById("portfolio-search-clear");
  if (clearBtn) clearBtn.classList.add("hidden");
  if (STATE.portfolio) renderCategorizedInvestments(STATE.portfolio);
}

function renderCategorizedInvestments(data) {
  const container = document.getElementById("categorized-investments-container");
  if (!container) return;

  updateFavoriteCounters();

  const qNorm = normalizeSearchText(STATE.portfolioSearch);
  const onlyFavs = STATE.categoryListFilter === "FAVORITES";

  const rawPositions = data.positions || [];
  const rawFixedIncome = data.fixed_income || [];

  const positions = rawPositions.filter(p => {
    if (onlyFavs && !isFavorite(p.ticker)) return false;
    if (qNorm) {
      const hay = normalizeSearchText(`${p.ticker} ${p.name} ${p.broker || ""}`);
      if (!hay.includes(qNorm)) return false;
    }
    return true;
  });

  const fixedIncome = rawFixedIncome.filter(f => {
    if (onlyFavs) return false;
    if (qNorm) {
      const hay = normalizeSearchText(`${f.title_name} ${f.issuer} ${f.rate_label || ""} ${f.broker || ""}`);
      if (!hay.includes(qNorm)) return false;
    }
    return true;
  });

  const totalPortfolioBrl = data.kpis.total_current_brl || 0;

  const categoryConfigs = [
    {
      key: "FII",
      filterGroup: "FII",
      title: "Fundos Imobiliários (FIIs & Fiagros)",
      subtitle: "Renda passiva mensal isenta de Imposto de Renda",
      addAction: "openAddInvestmentModal('FII')",
      addLabel: "Adicionar FII",
      isVariable: true,
      items: positions.filter(p => p.asset_class === "FII"),
    },
    {
      key: "ACAO_BR",
      filterGroup: "ACAO_BR",
      title: "Ações Brasileiras (B3)",
      subtitle: "Participação em empresas listadas na Bolsa",
      addAction: "openAddInvestmentModal('ACAO_BR')",
      addLabel: "Adicionar ação",
      isVariable: true,
      items: positions.filter(p => p.asset_class === "ACAO_BR"),
    },
    {
      key: "CAIXINHA",
      filterGroup: "CAIXINHA",
      title: "Caixinhas & Liquidez Diária",
      subtitle: "Reserva de emergência rendendo % do CDI todos os dias úteis",
      addAction: "openAddInvestmentModal('CAIXINHA')",
      addLabel: "Adicionar caixinha",
      isVariable: false,
      items: fixedIncome.filter(f => f.asset_class === "CAIXINHA"),
    },
    {
      key: "RENDA_FIXA",
      filterGroup: "RENDA_FIXA",
      title: "CDBs, LCIs, LCAs & Fundos DI",
      subtitle: "Títulos bancários pós-fixados (% CDI), híbridos (IPCA+) e isentos",
      addAction: "openAddInvestmentModal('RENDA_FIXA')",
      addLabel: "Adicionar título",
      isVariable: false,
      items: fixedIncome.filter(f => f.asset_class === "RENDA_FIXA" || f.asset_class === "FUNDO_INV"),
    },
    {
      key: "TESOURO",
      filterGroup: "TESOURO",
      title: "Tesouro Direto",
      subtitle: "Títulos públicos federais corrigidos por IPCA ou Taxa Selic",
      addAction: "openAddInvestmentModal('TESOURO')",
      addLabel: "Adicionar Tesouro",
      isVariable: false,
      items: fixedIncome.filter(f => f.asset_class === "TESOURO"),
    },
    {
      key: "OUTROS",
      filterGroup: "OUTROS",
      title: "ETFs, Stocks EUA & Criptomoedas",
      subtitle: "Diversificação global, fundos de índice e criptoativos",
      addAction: "openAddInvestmentModal('ETF_BR')",
      addLabel: "Adicionar ativo",
      isVariable: true,
      items: positions.filter(p => ["ETF_BR", "FUNDO_INV", "STOCK_US", "CRIPTO"].includes(p.asset_class)),
    },
  ];

  const hasAnyInPortfolio = rawPositions.length + rawFixedIncome.length > 0;
  const filteredCategories = categoryConfigs.filter(cat => {
    if (STATE.categoryListFilter === "FAVORITES") return cat.items.length > 0;
    if (STATE.categoryListFilter !== "ALL") return cat.filterGroup === STATE.categoryListFilter;
    if (qNorm) return cat.items.length > 0;
    return hasAnyInPortfolio ? cat.items.length > 0 : true;
  });

  if (filteredCategories.length === 0) {
    container.innerHTML = `
      <div class="card empty-sm">
        ${onlyFavs
          ? "Você ainda não marcou nenhum ativo da carteira com a estrela (★) de favorito."
          : "Nenhum ativo da sua carteira corresponde à pesquisa."}
      </div>
    `;
    renderIndividualTransactionsList(data.transactions || []);
    return;
  }

  container.innerHTML = filteredCategories.map(cat => {
    const catInvested = cat.items.reduce((acc, it) => acc + (cat.isVariable ? it.invested_brl : it.invested_amount), 0);
    const catCurrent = cat.items.reduce((acc, it) => acc + (cat.isVariable ? it.current_brl : it.net_amount), 0);
    const catProfit = catCurrent - catInvested;
    const catProfitPct = catInvested > 0 ? (catProfit / catInvested) * 100.0 : 0.0;
    const catWeightPct = totalPortfolioBrl > 0 ? (catCurrent / totalPortfolioBrl) * 100.0 : 0.0;
    const profCls = catProfit >= 0 ? "pos" : "neg";
    const avatarKey = cat.key === "OUTROS" ? "STOCK_US" : cat.key;

    let bodyHtml = "";
    if (cat.items.length === 0) {
      bodyHtml = `
        <div class="empty-sm row between" style="padding:14px 4px 2px">
          <span>Nenhum ativo cadastrado nesta categoria.</span>
          <button onclick="${cat.addAction}" class="btn btn-sm btn-secondary">${ic("plus", 14)}${cat.addLabel}</button>
        </div>
      `;
    } else if (cat.isVariable && STATE.listLayout === "STRIPS") {
      // Visualização em Lista Ordenada de Tiras Horizontais
      const stripsHtml = cat.items.map((p, idx) => {
        const rank = String(idx + 1).padStart(2, "0");
        const chgCls = p.change_pct >= 0 ? "badge-pos" : "badge-neg";
        const pProfCls = p.profit_brl >= 0 ? "pos" : "neg";
        const divTxt = p.last_dividend_per_share > 0 ? fmtMoney(p.last_dividend_per_share, p.currency) : "—";
        return `
          <div class="strip-row strip-row-portfolio" onclick="openAssetDetail('${p.ticker}')">
            <div class="strip-rank">
              <span class="rank-num">#${rank}</span>
              ${favStarButton(p.ticker)}
            </div>
            <div class="strip-asset">
              ${classAvatar(p.asset_class, p.ticker, "sm")}
              <div style="min-width:0">
                <div class="cell-title">${p.ticker}</div>
                <div class="cell-sub">${p.name} · ${p.broker || "Corretora"}</div>
              </div>
            </div>
            <div class="right hide-sm">
              <span class="strip-cell-label">Qtd</span>
              <span class="strong">${p.quantity}</span>
            </div>
            <div class="right hide-md">
              <span class="strip-cell-label">Preço médio</span>
              <div class="row gap-1 align-center" style="justify-content:flex-end" onclick="event.stopPropagation()">
                <span class="muted">${fmtMoney(p.avg_price, p.currency)}</span>
                <button class="btn-icon xs" title="Ajustar Preço Médio" onclick="openAdjustAvgPriceModal('${p.ticker}', ${p.avg_price}, event)">${ic("edit-3", 11)}</button>
              </div>
              ${p.pm_estimated ? `<div class="xs" style="color:var(--amber);cursor:pointer;margin-top:2px" onclick="event.stopPropagation();openAdjustAvgPriceModal('${p.ticker}', ${p.avg_price}, event)" title="Estimado pela cotação de fechamento da B3. Clique para definir o Preço Médio real.">⚠️ PM Estimado</div>` : ""}
            </div>
            <div class="right">
              <span class="strip-cell-label">Cotação</span>
              <div class="strong">${fmtMoney(p.current_price, p.currency)}${p.is_stale ? ` <span class="badge badge-outline xs" style="color:var(--amber);font-size:10px;padding:0 3px;border-color:rgba(234,179,8,0.4)" title="Cotação não sincronizada recentemente com o mercado">desatualizada</span>` : ""}</div>
              <span class="badge ${chgCls}" style="margin-top:2px">${fmtPct(p.change_pct)}</span>
            </div>
            <div class="right hide-md">
              <span class="strip-cell-label">Últ. div/cota</span>
              <span class="accent">${divTxt}</span>
            </div>
            <div class="right hide-sm">
              <span class="strip-cell-label">Saldo atual</span>
              <div class="strong">${fmtMoney(p.current_brl)}</div>
              <div class="xs faint">${p.weight_pct.toFixed(1)}% da carteira</div>
            </div>
            <div class="right hide-sm ${pProfCls}">
              <span class="strip-cell-label">Resultado</span>
              <div class="strong" style="color:inherit">${fmtMoney(p.profit_brl)}</div>
              <div class="xs">${fmtPct(p.profit_pct)}</div>
            </div>
            <div class="strip-actions" onclick="event.stopPropagation()">
              <button onclick="openTransactionModal('${p.ticker}','${p.asset_class}',${p.current_price},'${p.currency}')" class="btn-icon sm" title="Comprar / vender">${ic("plus", 14)}</button>
              <button onclick="deleteVariablePosition('${p.ticker}', event)" class="btn-icon sm danger" title="Remover">${ic("trash", 14)}</button>
            </div>
          </div>
        `;
      }).join("");

      bodyHtml = `
        <div class="strip-list">
          <div class="strip-head strip-head-portfolio">
            <span>#</span>
            <span>Ativo</span>
            <span class="right">Qtd</span>
            <span class="right">Preço médio</span>
            <span class="right">Cotação</span>
            <span class="right">Últ. div/cota</span>
            <span class="right">Saldo atual</span>
            <span class="right">Resultado</span>
            <span class="right">Ações</span>
          </div>
          ${stripsHtml}
        </div>
      `;
    } else if (cat.isVariable) {
      // Visualização em Grade de Cards (Gadgets da Carteira)
      const cardsHtml = cat.items.map(p => {
        const chgCls = p.change_pct >= 0 ? "badge-pos" : "badge-neg";
        const pProfCls = p.profit_brl >= 0 ? "pos" : "neg";
        const divTxt = p.last_dividend_per_share > 0 ? fmtMoney(p.last_dividend_per_share, p.currency) : "—";
        return `
          <div class="card asset-card" style="background:var(--surface-2)" onclick="openAssetDetail('${p.ticker}')">
            <div class="asset-head">
              ${classAvatar(p.asset_class, p.ticker)}
              <div class="asset-id">
                <div class="asset-ticker">
                  <span>${p.ticker}</span>
                  <span class="badge">${p.quantity} cotas</span>
                </div>
                <div class="asset-name">${p.name} · ${p.broker || "Corretora"}</div>
              </div>
              ${favStarButton(p.ticker)}
              <div class="asset-price">
                <div class="p">${fmtMoney(p.current_brl)}</div>
                <span class="badge ${p.profit_brl >= 0 ? "badge-pos" : "badge-neg"}" style="margin-top:4px">${fmtPct(p.profit_pct)}</span>
              </div>
            </div>

            <dl class="metrics">
              <div>
                <dt class="row gap-1 align-center" style="justify-content:space-between">
                  <span>Preço médio</span>
                  <button class="btn-icon xs" style="width:16px;height:16px;padding:0" title="Ajustar Preço Médio" onclick="event.stopPropagation();openAdjustAvgPriceModal('${p.ticker}', ${p.avg_price}, event)">${ic("edit-3", 10)}</button>
                </dt>
                <dd>${fmtMoney(p.avg_price, p.currency)}</dd>
                ${p.pm_estimated ? `<div class="xs" style="color:var(--amber);cursor:pointer;margin-top:2px" onclick="event.stopPropagation();openAdjustAvgPriceModal('${p.ticker}', ${p.avg_price}, event)" title="Estimado pelo fechamento B3. Clique para corrigir.">⚠️ Estimado B3</div>` : ""}
              </div>
              <div>
                <dt>Cotação hoje</dt>
                <dd>${fmtMoney(p.current_price, p.currency)} <span class="xs ${p.change_pct >= 0 ? "pos" : "neg"}">(${fmtPct(p.change_pct)})</span></dd>
              </div>
              <div>
                <dt>Últ. div/cota</dt>
                <dd class="accent">${divTxt}</dd>
              </div>
            </dl>

            <div class="asset-foot" onclick="event.stopPropagation()">
              <span>Resultado <strong class="${pProfCls} num">${fmtMoney(p.profit_brl)}</strong></span>
              <div class="row gap-1">
                <button onclick="openAssetDetail('${p.ticker}')" class="btn btn-sm btn-ghost">Raio-X ${ic("arrow-right", 13)}</button>
                <button onclick="openTransactionModal('${p.ticker}','${p.asset_class}',${p.current_price},'${p.currency}')" class="btn-icon sm" title="Comprar / vender">${ic("plus", 14)}</button>
                <button onclick="deleteVariablePosition('${p.ticker}', event)" class="btn-icon sm danger" title="Remover">${ic("trash", 14)}</button>
              </div>
            </div>
          </div>
        `;
      }).join("");

      bodyHtml = `<div class="grid grid-cards">${cardsHtml}</div>`;
    } else {
      const cardsHtml = cat.items.map(f => renderFixedIncomeCardHtml(f, false)).join("");
      bodyHtml = `<div class="grid grid-2">${cardsHtml}</div>`;
    }

    return `
      <div class="card cat-group">
        <div class="cat-head">
          <div class="cat-id">
            ${classAvatar(avatarKey)}
            <div>
              <div class="row gap-2">
                <h3 class="card-title">${cat.title}</h3>
                <span class="badge">${cat.items.length}</span>
              </div>
              <p class="card-sub">${cat.subtitle}</p>
            </div>
          </div>
          <div class="row gap-4">
            <div class="cat-total">
              <div class="xs faint">${catWeightPct.toFixed(1)}% da carteira</div>
              <div class="v">${fmtMoney(catCurrent)} <span class="xs ${profCls}">${fmtPct(catProfitPct)}</span></div>
            </div>
            <button onclick="${cat.addAction}" class="btn btn-sm btn-secondary">${ic("plus", 14)}<span class="label-hide">${cat.addLabel}</span></button>
          </div>
        </div>
        ${bodyHtml}
      </div>
    `;
  }).join("");

  renderIndividualTransactionsList(data.transactions || []);
}

function renderFixedIncomeCardHtml(f, standalone = false) {
  const fProfCls = f.net_profit >= 0 ? "pos" : "neg";
  return `
    <div class="fi-card ${standalone ? "card" : ""}">
      <div class="row between" style="align-items:flex-start">
        <div class="row gap-3">
          ${classAvatar(f.asset_class, "", "sm")}
          <div>
            <div class="strong">${esc(f.title_name)}</div>
            <div class="xs faint">${esc(f.issuer)} · Venc. ${f.maturity_date || "Liquidez diária"}</div>
          </div>
        </div>
        <div class="row gap-2">
          <span class="badge badge-accent">${f.rate_label}</span>
          <button onclick="openAdjustFixedIncomeModal(${f.id})" title="Editar Custo / Saldo Atualizado" class="btn-icon sm">${ic("edit", 14)}</button>
          <button onclick="deleteFixedIncome(${f.id}, event)" title="Remover" class="btn-icon sm danger">${ic("trash", 14)}</button>
        </div>
      </div>

      <div class="row between" style="align-items:baseline">
        <div>
          <div class="xs faint">Saldo líquido hoje</div>
          <div class="fi-hero">${fmtMoney(f.net_amount)}</div>
        </div>
        <div class="right">
          <span class="badge ${f.net_profit >= 0 ? "badge-pos" : "badge-neg"}">+${fmtMoney(f.net_profit)} (${fmtPct(f.net_profit_pct)})</span>
          <div class="xs faint" style="margin-top:4px">${f.tax_exempt ? "Isento de IR" : `IR ${f.ir_rate}% · ${f.days_elapsed} dias`}</div>
        </div>
      </div>

      <div class="fi-stats">
        <div class="kv">
          <dt class="row gap-1 align-center">
            <span>Valor aplicado</span>
            ${f.cost_estimated ? `<span class="badge badge-warning xs" style="cursor:pointer;padding:1px 6px;font-size:10px" onclick="openAdjustFixedIncomeModal(${f.id})" title="Custo aplicado estimado. Clique para informar seu valor real.">⚠️ Custo Estimado</span>` : ""}
          </dt>
          <dd class="row gap-1 align-center">
            <span>${fmtMoney(f.invested_amount)}</span>
            <button onclick="openAdjustFixedIncomeModal(${f.id})" title="Ajustar Custo" class="btn-icon sm xs-icon" style="padding:2px;opacity:0.6">${ic("edit", 12)}</button>
          </dd>
        </div>
        <div class="kv">
          <dt>Saldo bruto ${f.value_anchor_date ? `<span class="xs faint">(${f.value_anchor_date})</span>` : ""}</dt>
          <dd>${fmtMoney(f.gross_amount)}</dd>
        </div>
      </div>
    </div>
  `;
}

function renderIndividualTransactionsList(txList) {
  const panel = document.getElementById("individual-transactions-panel");
  const tbody = document.getElementById("individual-transactions-tbody");
  const badge = document.getElementById("tx-count-badge");
  if (!panel || !tbody) return;

  if (!txList || txList.length === 0) {
    panel.classList.add("hidden");
    tbody.innerHTML = "";
    return;
  }

  panel.classList.remove("hidden");
  if (badge) badge.textContent = txList.length;

  tbody.innerHTML = txList.map(tx => {
    const isBuy = tx.tx_type === "BUY";
    const typeBadge = isBuy
      ? `<span class="badge badge-pos">Compra</span>`
      : `<span class="badge badge-gold">Venda</span>`;
    const totalVal = (Number(tx.quantity) || 0) * (Number(tx.unit_price) || 0);
    return `
      <tr>
        <td class="mono muted">${esc(tx.tx_date)}</td>
        <td><span class="strong">${esc(tx.ticker)}</span> <span class="faint xs">· ${esc(tx.broker || "Corretora")}</span></td>
        <td>${typeBadge}</td>
        <td class="r">${Number(tx.quantity) || 0}</td>
        <td class="r muted">${fmtMoney(tx.unit_price, tx.currency || "BRL")}</td>
        <td class="r strong">${fmtMoney(totalVal, tx.currency || "BRL")}</td>
        <td class="r">
          <button onclick="deleteIndividualTransaction(${tx.id}, event)" class="btn-icon sm danger" title="Excluir lançamento">${ic("trash", 14)}</button>
        </td>
      </tr>
    `;
  }).join("");
}

/* ---------- Rebalanceamento ---------- */
async function loadRebalance() {
  const input = document.getElementById("input-rebalance-amount");
  const val = parseFloat(input ? input.value : "2000") || 2000;
  const res = await fetch(`/api/rebalance?contribution_brl=${val}`);
  const data = await res.json();
  const box = document.getElementById("rebalance-results");
  if (!box) return;

  box.innerHTML = data.suggestions.slice(0, 4).map(s => {
    const color = CLASS_COLORS[s.asset_class] || "#3ecf8e";
    const curW = Math.min(100, Math.max(0, s.current_pct));
    const tgtW = Math.min(100, Math.max(0, s.target_pct));
    return `
      <div class="rb-row">
        <div class="rb-top">
          <span class="rb-name"><span style="width:7px;height:7px;border-radius:2px;background:${color}"></span>${s.label.split("(")[0].trim()}</span>
          <span class="rb-amount">+ ${fmtMoney(s.suggested_contribution_brl)}</span>
        </div>
        <div class="rb-track">
          <span class="rb-fill" style="width:${curW}%;background:${color}"></span>
          <span class="rb-target" style="left:${tgtW}%" title="Meta ${s.target_pct}%"></span>
        </div>
        <div class="rb-meta">
          <span>Atual ${s.current_pct}%</span>
          <span>Meta ${s.target_pct}%</span>
        </div>
      </div>
    `;
  }).join("");
}

/* ---------- Navegação Principal ---------- */
const PAGE_META = {
  DASHBOARD: ["Patrimônio", "Minha carteira"],
  RENDA_FIXA: ["Patrimônio", "Renda fixa & caixinhas"],
  DIVIDENDS: ["Patrimônio", "Proventos recebidos"],
  AI_RADAR: ["Inteligência Artificial", "Radar IA & Oportunidades"],
  ACAO_BR: ["Mercado", "Ações B3"],
  FII: ["Mercado", "Fundos imobiliários"],
  ETF_BR: ["Mercado", "ETFs"],
  STOCK_US: ["Mercado", "Stocks EUA"],
  CRIPTO: ["Mercado", "Criptomoedas"],
  ASSET_DETAIL: ["Raio-X do ativo", "Análise completa"],
};

function switchMainTab(tabKey) {
  STATE.currentTab = tabKey;

  // Sidebar items
  document.querySelectorAll(".sidebar .nav-item[data-tab]").forEach(btn => {
    btn.classList.toggle("is-active", btn.getAttribute("data-tab") === tabKey);
  });

  // Mobile bottom nav
  const isMarketTab = ["ACAO_BR", "FII", "ETF_BR", "STOCK_US", "CRIPTO"].includes(tabKey);
  document.querySelectorAll(".bottom-nav .bn-item").forEach(btn => {
    const t = btn.getAttribute("data-tab");
    btn.classList.toggle("is-active", t === tabKey || (t === "MARKET" && isMarketTab));
  });

  // Mobile chips inside market explorer
  document.querySelectorAll("#market-class-chips .chip").forEach(c => {
    c.classList.toggle("is-active", c.getAttribute("data-tab") === tabKey);
  });

  // Topbar breadcrumb
  const [eyebrow, title] = PAGE_META[tabKey] || ["SIM", "Minha carteira"];
  document.getElementById("page-eyebrow").textContent = eyebrow;
  document.getElementById("page-title").textContent = title;

  // Toggle views
  ["DASHBOARD", "MARKET_CLASS", "ASSET_DETAIL", "RENDA_FIXA", "DIVIDENDS", "AI_RADAR"].forEach(v => {
    document.getElementById(`view-${v}`)?.classList.add("hidden");
  });

  if (tabKey === "DASHBOARD") {
    document.getElementById("view-DASHBOARD").classList.remove("hidden");
  } else if (tabKey === "RENDA_FIXA") {
    document.getElementById("view-RENDA_FIXA").classList.remove("hidden");
  } else if (tabKey === "DIVIDENDS") {
    document.getElementById("view-DIVIDENDS").classList.remove("hidden");
  } else if (tabKey === "AI_RADAR") {
    document.getElementById("view-AI_RADAR")?.classList.remove("hidden");
    loadAiRadarView(false);
  } else {
    STATE.marketClass = tabKey;
    document.getElementById("view-MARKET_CLASS").classList.remove("hidden");
    document.getElementById("market-class-title").textContent = CLASS_NAMES[tabKey] || "Explorador";
    document.getElementById("market-class-subtitle").textContent =
      CLASS_SUBTITLES[tabKey] || "Clique em qualquer ativo para abrir o gráfico interativo, fundamentos e relatórios IA.";
    renderMarketClassContextBanner(tabKey);
    loadMarketClassAssets();
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ---------- Contexto Institucional de cada Classe de Mercado ---------- */
const CLASS_SPECIALIST_CONFIG = {
  ACAO_BR: {
    color: "#3ecf8e",
    placeholder: "Pesquisar ação B3 por código, empresa ou setor (ex: PETR4, WEGE3, Bancos, Energia…)",
    sort4: "Maior dividendo (DY)",
    sort5: "Menor P/L · Descontadas",
    pillars: [
      { label: "Natureza do Ativo", val: "Participação Societária (B3)", sub: "Lucros, Dividendos, JCP e Valorização" },
      { label: "5 Pilares de Análise", val: "Valuation · Dívida · Eficiência", sub: "ROE, ROIC, Margem Líquida e CAGR 5A" },
      { label: "Tributação Proventos", val: "Dividendos Isentos · JCP 15%", sub: "Vendas até R$ 20 mil/mês isentas (Swing)" },
      { label: "Fonte Regulatória", val: "CVM RAD / Empresas.NET", sub: "ITR, DFP e Fatos Relevantes Oficiais" },
    ],
  },
  FII: {
    color: "#38bdf8",
    placeholder: "Pesquisar FII por código, nome ou segmento (ex: GARE11, MXRF11, Logística, Shopping, Papel…)",
    sort4: "Maior rendimento (DY)",
    sort5: "Mais descontados (P/VP)",
    pillars: [
      { label: "Foco Principal", val: "Renda Passiva Mensal Isenta", sub: "100% isento de IR para Pessoa Física" },
      { label: "Métrica Chave", val: "P/VP Patrimonial & Cap Rate", sub: "Abaixo de 1,00x indica desconto sobre o VP" },
      { label: "Qualidade da Carteira", val: "Vacância, LTV & Indexadores", sub: "Contratos corrigidos por IPCA+ e CDI+" },
      { label: "Fonte Regulatória", val: "B3 Fundos.NET (FNET)", sub: "Relatórios Gerenciais e Avisos de Rendimento" },
    ],
  },
  ETF_BR: {
    color: "#22d3ee",
    placeholder: "Pesquisar ETF por código, índice ou gestora (ex: IVVB11, BOVA11, WRLD11, S&P 500, Ouro…)",
    sort4: "Maior retorno (12M)",
    sort5: "Menor taxa de adm.",
    pillars: [
      { label: "Mecânica de Retorno", val: "Acumulação Total Return", sub: "Dividendos são reinvestidos na cota sem IR" },
      { label: "Eficiência Estrutural", val: "Taxa de Adm. & Tracking Error", sub: "Baixo custo anual e aderência ao índice" },
      { label: "Exposição & Moeda", val: "Índices B3, S&P 500, Global & Ouro", sub: "Diversificação automática em centenas de ativos" },
      { label: "Regra Tributária", val: "15% IR na Venda com Lucro", sub: "Sem come-cotas semestral" },
    ],
  },
  STOCK_US: {
    color: "#f43f5e",
    placeholder: "Pesquisar Stock EUA / REIT por ticker, nome ou setor (ex: NVDA, AAPL, MSFT, O, Semicondutores…)",
    sort4: "Maior ROE (Rentabilidade)",
    sort5: "Menor P/E (Valuation)",
    pillars: [
      { label: "Moeda & Jurisdição", val: "100% Dólar (NYSE & NASDAQ)", sub: "Proteção cambial e geração de caixa global" },
      { label: "Alocação de Capital", val: "Crescimento, P&D e Buybacks", sub: "Recompra de ações reduz oferta e eleva LPA" },
      { label: "Métricas Wall Street", val: "P/E Ratio, ROE, Margem & FCF", sub: "Foco em expansão composta de lucros (CAGR)" },
      { label: "Acesso Local (B3)", val: "Direto em USD ou via BDRs", sub: "Cotação convertida ao vivo pelo dólar PTAX" },
    ],
  },
  CRIPTO: {
    color: "#f97316",
    placeholder: "Pesquisar Criptoativo por símbolo, rede ou caso de uso (ex: BTC, ETH, SOL, Layer 1, DeFi…)",
    sort4: "Maior alta (12M)",
    sort5: "Maior dominância",
    pillars: [
      { label: "Arquitetura Monetária", val: "Escassez Digital & Rede P2P", sub: "Sem dividendos fiduciários ou banco emissor" },
      { label: "Tokenomics & Oferta", val: "Supply Máximo, Halving & Burn", sub: "Emissão programada e verificável on-chain" },
      { label: "Métricas de Mercado", val: "Market Cap, Dominância & ATH", sub: "Negociação global ininterrupta 24/7" },
      { label: "Conversão Instantânea", val: "Cotação em USD e Equivalente R$", sub: "Monitoramento em tempo real via Binance / BCB" },
    ],
  },
};

function renderMarketClassContextBanner(tabKey) {
  const cfg = CLASS_SPECIALIST_CONFIG[tabKey] || CLASS_SPECIALIST_CONFIG.ACAO_BR;
  const banner = document.getElementById("market-class-specialist-banner");
  if (banner) {
    banner.style.setProperty("--c", cfg.color);
    banner.innerHTML = cfg.pillars.map(p => `
      <div class="class-banner-item">
        <span class="class-banner-label">${p.label}</span>
        <span class="class-banner-val">${p.val}</span>
        <span class="class-banner-sub">${p.sub}</span>
      </div>
    `).join("");
  }
  const input = document.getElementById("market-search-input");
  if (input) input.placeholder = cfg.placeholder;
  const s4 = document.getElementById("sort-maior_dividendo-label");
  const s5 = document.getElementById("sort-mais_descontados-label");
  if (s4) s4.textContent = cfg.sort4;
  if (s5) s5.textContent = cfg.sort5;
}

/* ---------- Explorador de Mercado ---------- */
function setMarketScope(scope) {
  STATE.marketScope = scope; // 'ALL' | 'FAVORITES' | 'MINE'
  STATE.onlyMine = scope === "MINE";
  ["ALL", "FAVORITES", "MINE"].forEach(s => {
    document.getElementById(`btn-scope-${s}`)?.classList.toggle("is-active", s === scope);
  });
  renderMarketAssetsView();
}

function setPortfolioScope(onlyMine) {
  setMarketScope(onlyMine ? "MINE" : "ALL");
}

let _marketLookupTimer = null;
let _marketLookupInFlight = "";
const _marketLookupFailed = new Set();

function onMarketSearchInput(val) {
  STATE.marketSearch = val || "";
  const clearBtn = document.getElementById("market-search-clear");
  if (clearBtn) clearBtn.classList.toggle("hidden", !STATE.marketSearch.trim());
  renderMarketAssetsView();

  // Se o usuário digitou um ticker (ex: GARE11, SNAG11, BBDC3, TSLA) que ainda não está no catálogo local,
  // busca automaticamente na API (Yahoo Finance / B3) e adiciona na lista sem precisar sair da tela!
  clearTimeout(_marketLookupTimer);
  const cleanTicker = (STATE.marketSearch || "").trim().toUpperCase().replace(/\s+/g, "");
  const isTickerPattern = /^[A-Z]{4}\d{1,2}$/.test(cleanTicker) || /^[A-Z0-9.\-]{3,8}$/.test(cleanTicker);
  const alreadyInList = (STATE.lastMarketAssets || []).some(a => a.ticker.toUpperCase() === cleanTicker);

  if (isTickerPattern && !alreadyInList && !_marketLookupFailed.has(cleanTicker)) {
    _marketLookupTimer = setTimeout(() => {
      discoverMarketTickerLive(cleanTicker);
    }, 360);
  }
}

async function discoverMarketTickerLive(cleanTicker, openAfter = false) {
  if (!cleanTicker) return;
  _marketLookupInFlight = cleanTicker;
  renderMarketAssetsView();

  try {
    const guessedClass = cleanTicker.endsWith("11") && STATE.marketClass === "FII"
      ? "FII"
      : (STATE.marketClass || "ACAO_BR");
    const res = await fetch(`/api/lookup-ticker?ticker=${encodeURIComponent(cleanTicker)}&asset_class=${encodeURIComponent(guessedClass)}`);
    if (res.ok) {
      const info = await res.json();
      if (info && info.last_price > 0) {
        _marketLookupInFlight = "";
        // Recarrega a lista da categoria para já trazer o ativo salvo no SQLite
        await loadMarketClassAssets();
        if (openAfter) {
          openAssetDetail(info.ticker || cleanTicker);
        }
        return;
      }
    }
    _marketLookupFailed.add(cleanTicker);
  } catch (_) {
    _marketLookupFailed.add(cleanTicker);
  } finally {
    _marketLookupInFlight = "";
    renderMarketAssetsView();
  }
}

function clearMarketSearch() {
  clearTimeout(_marketLookupTimer);
  _marketLookupInFlight = "";
  STATE.marketSearch = "";
  const input = document.getElementById("market-search-input");
  if (input) input.value = "";
  const clearBtn = document.getElementById("market-search-clear");
  if (clearBtn) clearBtn.classList.add("hidden");
  renderMarketAssetsView();
}

function setMarketSort(sortKey) {
  STATE.marketSort = sortKey;
  document.querySelectorAll(".sort-pill").forEach(b => b.classList.remove("is-active"));
  document.getElementById(`sort-${sortKey}`)?.classList.add("is-active");
  loadMarketClassAssets();
}

async function loadMarketClassAssets() {
  const url = `/api/market/assets?asset_class=${STATE.marketClass}&sort_by=${STATE.marketSort}`;
  const res = await fetch(url);
  const data = await res.json();
  STATE.lastMarketAssets = data.assets || [];
  updateFavoriteCounters();
  renderMarketAssetsView();
}

function renderMarketAssetsView() {
  const grid = document.getElementById("market-assets-grid");
  if (!grid) return;

  let list = [...(STATE.lastMarketAssets || [])];

  // 1. Filtra por escopo (Mercado / Favoritos / Na carteira)
  if (STATE.marketScope === "FAVORITES") {
    list = list.filter(a => isFavorite(a.ticker));
  } else if (STATE.marketScope === "MINE") {
    list = list.filter(a => a.in_portfolio);
  }

  // 2. Filtra pela busca superior (ticker, nome ou setor)
  const qNorm = normalizeSearchText(STATE.marketSearch);
  if (qNorm) {
    list = list.filter(a => {
      const hay = normalizeSearchText(`${a.ticker} ${a.name || ""} ${a.sector || ""}`);
      return hay.includes(qNorm);
    });
  }

  // Contador de resultados na barra de busca
  const countEl = document.getElementById("market-result-count");
  if (countEl) {
    countEl.textContent = `${list.length} ${list.length === 1 ? "ativo" : "ativos"}`;
  }

  if (list.length === 0) {
    grid.className = "grid grid-cards";
    const cleanTicker = (STATE.marketSearch || "").trim().toUpperCase().replace(/\s+/g, "");
    const looksLikeTicker = /^[A-Z0-9.\-]{3,10}$/.test(cleanTicker);
    const isSearchingLive = _marketLookupInFlight === cleanTicker && cleanTicker.length >= 3;
    const emptyMsg = isSearchingLive
      ? `Buscando "${cleanTicker}" ao vivo na B3 / Yahoo Finance…`
      : (STATE.marketScope === "FAVORITES"
          ? "Você ainda não marcou favoritos nesta categoria. Clique na estrela ★ em qualquer ativo para salvá-lo aqui."
          : (STATE.marketScope === "MINE"
              ? "Você ainda não possui ativos desta categoria na sua carteira."
              : `Nenhum ativo encontrado para "${STATE.marketSearch}".`));

    grid.innerHTML = `
      <div class="card empty-sm" style="grid-column:1/-1;display:flex;flex-direction:column;align-items:center;gap:12px;padding:34px 20px">
        <div>${emptyMsg}</div>
        ${looksLikeTicker && !isSearchingLive ? `
          <div class="row-actions" style="justify-content:center;flex-wrap:wrap">
            <button class="btn btn-primary btn-sm" onclick="discoverMarketTickerLive('${cleanTicker}', false)">
              Buscar "${cleanTicker}" ao vivo e adicionar à lista ${ic("refresh", 14)}
            </button>
            <button class="btn btn-secondary btn-sm" onclick="openAssetDetail('${cleanTicker}')">
              Abrir Raio-X de "${cleanTicker}" ${ic("arrow-right", 14)}
            </button>
          </div>
        ` : ""}
      </div>
    `;
    return;
  }

  // Helper que retorna as 3 métricas especializadas de cada ativo conforme sua classe real
  function getSpecializedAssetMetrics(a) {
    const cls = (a.asset_class || STATE.marketClass || "ACAO_BR").toUpperCase();
    const cp = a.class_profile || {};

    if (cls === "ETF_BR") {
      return [
        {
          label: "Índice (Benchmark)",
          html: `<span class="strong" style="font-size:12px">${cp.benchmark || a.sector || "Índice B3"}</span>`,
        },
        {
          label: "Taxa de Adm.",
          html: `<span class="accent strong num">${cp.admin_fee_pct !== undefined ? Number(cp.admin_fee_pct).toFixed(2).replace(".", ",") + "% a.a." : "0,30% a.a."}</span>`,
        },
        {
          label: "Retorno 12M · CAGR",
          html: `<span class="pos strong num">+${Number(cp.return_12m_pct || 14.0).toFixed(1)}%</span> <span class="faint num">· ${Number(cp.cagr_5y_pct || 11.5).toFixed(1)}%</span>`,
        },
      ];
    }

    if (cls === "STOCK_US") {
      const pe = Number(cp.pe_ratio || a.pl || 25.0);
      const roe = Number(cp.roe || 24.0);
      const brlPrice = cp.price_brl || (a.last_price * (STATE.portfolio?.macro?.usd_brl || 5.72));
      return [
        {
          label: "Market Cap (USD)",
          html: `<span class="strong num">${cp.mcap || "US$ 200 Bi"}</span>`,
        },
        {
          label: "P/E · ROE (USD)",
          html: `<span class="num">${pe > 0 ? pe.toFixed(1) + "x" : "—"} · <strong class="accent">${roe.toFixed(0)}%</strong></span>`,
        },
        {
          label: "Em Reais · BDR",
          html: `<span class="muted num">${fmtMoney(brlPrice, "BRL")} · <strong>${cp.bdr || a.ticker}</strong></span>`,
        },
      ];
    }

    if (cls === "CRIPTO") {
      const brlPrice = cp.price_brl || (a.last_price * (STATE.portfolio?.macro?.usd_brl || 5.72));
      const dom = Number(cp.dominance_pct || 1.0);
      const ret12 = Number(cp.return_12m_pct || 65.0);
      return [
        {
          label: "Market Cap · Dom.",
          html: `<span class="strong num">${cp.mcap || "US$ 20 Bi"} <span class="faint">(${dom.toFixed(1)}%)</span></span>`,
        },
        {
          label: "Cotação em R$",
          html: `<span class="accent strong num">${fmtMoney(brlPrice, "BRL")}</span>`,
        },
        {
          label: "Performance 12M",
          html: `<span class="pos strong num">+${ret12.toFixed(1)}%</span>`,
        },
      ];
    }

    if (cls === "FII") {
      const divPerShare = a.last_dividend_per_share > 0
        ? `<span class="accent strong num">${fmtMoney(a.last_dividend_per_share, a.currency)}</span>`
        : `<span class="faint">—</span>`;
      const pvpStatus = a.pvp < 0.98 ? "Desconto" : (a.pvp <= 1.03 ? "Justo" : "Ágio");
      return [
        { label: "Últ. rend/cota", html: divPerShare },
        { label: "DY (12M Isento)", html: `<span class="strong num">${a.dy_12m > 0 ? a.dy_12m.toFixed(2) + "%" : "—"}</span>` },
        { label: "P/VP Patrimonial", html: `<span class="num">${a.pvp > 0 ? a.pvp.toFixed(2) + "x" : "—"} <span class="faint">(${pvpStatus})</span></span>` },
      ];
    }

    // ACAO_BR
    const roe = Number(cp.roe_pct || 16.5);
    return [
      {
        label: "P/L · P/VP",
        html: `<span class="num">${a.pl > 0 ? a.pl.toFixed(1) + "x" : "—"} · ${a.pvp > 0 ? a.pvp.toFixed(2) + "x" : "—"}</span>`,
      },
      {
        label: "DY (12M)",
        html: `<span class="accent strong num">${a.dy_12m > 0 ? a.dy_12m.toFixed(1) + "%" : "—"}</span>`,
      },
      {
        label: "ROE · Últ. div",
        html: `<span class="num">ROE ${roe.toFixed(0)}% · ${a.last_dividend_per_share > 0 ? fmtMoney(a.last_dividend_per_share, a.currency) : "—"}</span>`,
      },
    ];
  }

  // Modo Tiras (Lista Ordenada Horizontal, um ativo embaixo do outro)
  if (STATE.listLayout === "STRIPS") {
    grid.className = "strip-list";
    const sampleMetrics = getSpecializedAssetMetrics(list[0] || { asset_class: STATE.marketClass });
    const headerHtml = `
      <div class="strip-head">
        <div># · ★</div>
        <div>Ativo & Setor</div>
        <div class="right">Cotação</div>
        <div class="right">Var. Dia</div>
        <div class="right">${sampleMetrics[0].label}</div>
        <div class="right">${sampleMetrics[1].label}</div>
        <div class="right">${sampleMetrics[2].label}</div>
        <div class="right">Volume Dia</div>
        <div class="right">Ações</div>
      </div>
    `;

    const rowsHtml = list.map((a, idx) => {
      const rank = String(idx + 1).padStart(2, "0");
      const chgCls = a.change_pct >= 0 ? "badge-pos" : "badge-neg";
      const heldBadge = a.in_portfolio
        ? `<span class="badge badge-accent">Na carteira · ${a.user_qty}</span>`
        : "";
      const m = getSpecializedAssetMetrics(a);

      return `
        <div onclick="openAssetDetail('${a.ticker}')" class="strip-row">
          <div class="strip-rank">
            <span class="rank-num">#${rank}</span>
            ${favStarButton(a.ticker)}
          </div>

          <div class="strip-asset">
            ${classAvatar(a.asset_class, a.ticker)}
            <div style="min-width:0">
              <div class="asset-ticker">
                <span>${a.ticker}</span>
                ${heldBadge}
              </div>
              <div class="asset-name">${a.name} · <span class="faint">${a.sector || "Mercado"}</span></div>
            </div>
          </div>

          <div class="right">
            <span class="strip-cell-label">Cotação</span>
            <span class="strong num" style="font-size:14.5px">${fmtMoney(a.last_price, a.currency)}</span>
            ${a.is_stale ? `<div class="xs" style="color:var(--amber);font-size:10px" title="Cotação não sincronizada recentemente com a B3/Yahoo">desatualizada</div>` : ""}
          </div>

          <div class="right">
            <span class="strip-cell-label">Var. Dia</span>
            <span class="badge ${chgCls}">${fmtPct(a.change_pct)}</span>
          </div>

          <div class="right">
            <span class="strip-cell-label">${m[0].label}</span>
            ${m[0].html}
          </div>

          <div class="right">
            <span class="strip-cell-label">${m[1].label}</span>
            ${m[1].html}
          </div>

          <div class="right">
            <span class="strip-cell-label">${m[2].label}</span>
            ${m[2].html}
          </div>

          <div class="right">
            <span class="strip-cell-label">Volume</span>
            <span class="muted num">${fmtCompact(a.volume_day)}</span>
          </div>

          <div class="strip-actions" onclick="event.stopPropagation()">
            <button onclick="openTransactionModal('${a.ticker}','${a.asset_class}',${a.last_price},'${a.currency}')" class="btn btn-ghost btn-sm btn-icon" title="Registrar aporte em ${a.ticker}">
              ${ic("plus", 14)}
            </button>
            <button onclick="openAssetDetail('${a.ticker}')" class="btn btn-ghost btn-sm" title="Abrir Raio-X">
              Raio-X ${ic("arrow-right", 13)}
            </button>
          </div>
        </div>
      `;
    }).join("");

    grid.innerHTML = headerHtml + rowsHtml;
    return;
  }

  // Modo Grade (Cards Especializados por Classe)
  grid.className = "grid grid-cards";
  grid.innerHTML = list.map(a => {
    const chgCls = a.change_pct >= 0 ? "badge-pos" : "badge-neg";
    const heldBadge = a.in_portfolio
      ? `<span class="badge badge-accent">Na carteira · ${a.user_qty}</span>`
      : "";
    const m = getSpecializedAssetMetrics(a);

    return `
      <div onclick="openAssetDetail('${a.ticker}')" class="card asset-card">
        <div class="asset-head">
          ${classAvatar(a.asset_class, a.ticker)}
          <div class="asset-id">
            <div class="asset-ticker">
              <span>${a.ticker}</span>
              ${heldBadge}
            </div>
            <div class="asset-name">${a.name}</div>
          </div>
          <div class="asset-price">
            <div class="p">${fmtMoney(a.last_price, a.currency)}</div>
            <span class="badge ${chgCls}" style="margin-top:4px">${fmtPct(a.change_pct)}</span>
          </div>
          ${favStarButton(a.ticker)}
        </div>

        <dl class="metrics">
          <div>
            <dt>${m[0].label}</dt>
            <dd>${m[0].html}</dd>
          </div>
          <div>
            <dt>${m[1].label}</dt>
            <dd>${m[1].html}</dd>
          </div>
          <div>
            <dt>${m[2].label}</dt>
            <dd>${m[2].html}</dd>
          </div>
        </dl>

        <div class="asset-foot">
          <span>Volume <strong class="muted num">${fmtCompact(a.volume_day)}</strong></span>
          <span class="go">Abrir Raio-X ${ic("arrow-right", 14)}</span>
        </div>
      </div>
    `;
  }).join("");
}

/* ---------- Página Exclusiva do Ativo (Raio-X) ---------- */
async function openAssetDetail(ticker, period = "1M", keepTabHistory = false) {
  if (!keepTabHistory && STATE.currentTab !== "ASSET_DETAIL") {
    STATE.previousTab = STATE.currentTab;
  }
  STATE.currentTab = "ASSET_DETAIL";
  STATE.activeAssetTicker = ticker;
  STATE.activeAssetPeriod = period;

  document.getElementById("page-eyebrow").textContent = "Raio-X do ativo";
  document.getElementById("page-title").textContent = ticker;

  ["DASHBOARD", "MARKET_CLASS", "RENDA_FIXA", "DIVIDENDS"].forEach(v => {
    document.getElementById(`view-${v}`)?.classList.add("hidden");
  });
  document.getElementById("view-ASSET_DETAIL").classList.remove("hidden");

  document.querySelectorAll(".period-btn").forEach(b => b.classList.remove("is-active"));
  document.getElementById(`period-${period}`)?.classList.add("is-active");

  let res = await fetch(`/api/asset/${ticker}?period=${period}`);
  if (!res.ok) {
    // Se o ativo ainda não estava no catálogo local, descobre ao vivo via /api/lookup-ticker e tenta novamente
    const guessedClass = ticker.endsWith("11") ? "FII" : (STATE.marketClass || "ACAO_BR");
    const lookRes = await fetch(`/api/lookup-ticker?ticker=${encodeURIComponent(ticker)}&asset_class=${encodeURIComponent(guessedClass)}`);
    if (lookRes.ok) {
      res = await fetch(`/api/asset/${ticker}?period=${period}`);
    }
  }
  if (!res.ok) {
    showToast(`Não foi possível encontrar cotações para "${ticker}". Verifique o código.`);
    return;
  }
  const data = await res.json();
  STATE.activeAssetData = data;

  const a = data.asset;
  const av = document.getElementById("detail-avatar");
  if (av) {
    av.style.setProperty("--c", CLASS_COLORS[a.asset_class] || "#3ecf8e");
    av.textContent = a.ticker.slice(0, 4);
  }
  document.getElementById("detail-ticker").textContent = a.ticker;

  const detailFavBtn = document.getElementById("detail-fav-btn");
  if (detailFavBtn) {
    const fav = isFavorite(a.ticker);
    detailFavBtn.setAttribute("data-fav-ticker", a.ticker);
    detailFavBtn.classList.toggle("is-fav", fav);
    detailFavBtn.title = fav ? "Remover dos favoritos" : "Marcar como favorito";
    detailFavBtn.innerHTML = ic(fav ? "star-fill" : "star", 18);
    detailFavBtn.onclick = (ev) => toggleFavorite(a.ticker, ev);
  }

  document.getElementById("detail-class-badge").textContent = CLASS_NAMES[a.asset_class] || a.asset_class;
  document.getElementById("detail-sector-badge").textContent = a.sector || "Mercado";
  document.getElementById("detail-name").textContent = `${a.name}${a.cnpj ? " · CNPJ " + a.cnpj : ""}`;

  document.getElementById("btn-detail-buy").onclick = () => {
    openTransactionModal(a.ticker, a.asset_class, a.last_price, a.currency);
  };

  const detailDelBtn = document.getElementById("btn-detail-delete");
  if (detailDelBtn) {
    if (data.user_position && data.user_position.has_position) {
      detailDelBtn.classList.remove("hidden");
      detailDelBtn.onclick = (ev) => deleteVariablePosition(a.ticker, ev);
    } else {
      detailDelBtn.classList.add("hidden");
    }
  }

  setDetailHeaderReadout(
    a.last_price,
    data.period_change_pct,
    data.period_change_abs,
    `Cotação ${a.is_stale ? 'desatualizada / de catálogo' : 'atual'} (${period}) · passe o mouse no gráfico para inspecionar`,
    a.currency
  );

  document.getElementById("detail-low").textContent = fmtMoney(data.low_period, a.currency);
  document.getElementById("detail-high").textContent = fmtMoney(data.high_period, a.currency);

  const pmBadge = document.getElementById("detail-user-pm-badge");
  if (data.user_position && data.user_position.has_position) {
    pmBadge.classList.remove("hidden");
    document.getElementById("detail-user-pm-val").textContent = fmtMoney(data.user_position.avg_price, a.currency);
    pmBadge.style.cursor = "pointer";
    pmBadge.title = "Clique para ajustar o seu Preço Médio contábil";
    pmBadge.onclick = (ev) => openAdjustAvgPriceModal(a.ticker, data.user_position.avg_price, ev);
  } else {
    pmBadge.classList.add("hidden");
  }

  drawInteractiveAssetChart(data);

  // Strip de indicadores especializados por classe de ativo
  renderAssetFundamentalsStrip(data);

  // Painéis especializados por classe (Proventos / Estrutura ETF / Wall Street USD / On-Chain Cripto + Simulador)
  renderAssetClassSpecializedPanels(data);

  renderAiReportSection(data.reports_data);
  renderAssetNewsSection(data.news);
}

function renderAssetFundamentalsStrip(data) {
  const fStrip = document.getElementById("detail-fundamentals-strip");
  if (!fStrip) return;
  const a = data.asset;
  const cls = (a.asset_class || "ACAO_BR").toUpperCase();
  const cp = data.class_profile || a.class_profile || {};

  if (cls === "ETF_BR") {
    fStrip.innerHTML = `
      <div>
        <div class="stat-label">Índice de referência</div>
        <div class="stat-value accent">${cp.benchmark || a.sector || "Índice B3"}</div>
      </div>
      <div>
        <div class="stat-label">Taxa de administração</div>
        <div class="stat-value">${Number(cp.admin_fee_pct || 0.30).toFixed(2).replace(".", ",")}% a.a.</div>
      </div>
      <div>
        <div class="stat-label">Retorno (12M)</div>
        <div class="stat-value pos">+${Number(cp.return_12m_pct || 14.0).toFixed(1)}%</div>
      </div>
      <div>
        <div class="stat-label">CAGR (5 Anos)</div>
        <div class="stat-value">+${Number(cp.cagr_5y_pct || 11.8).toFixed(1)}% a.a.</div>
      </div>
      <div>
        <div class="stat-label">Exposição cambial</div>
        <div class="stat-value">${cp.fx_exposure || "Real (BRL)"}</div>
      </div>
      <div>
        <div class="stat-label">Liquidez diária B3</div>
        <div class="stat-value">${fmtCompact(a.volume_day)}</div>
      </div>
    `;
    return;
  }

  if (cls === "STOCK_US") {
    const brlPrice = cp.price_brl || (a.last_price * (STATE.portfolio?.macro?.usd_brl || 5.72));
    const pe = Number(cp.pe_ratio || a.pl || 28.0);
    fStrip.innerHTML = `
      <div>
        <div class="stat-label">Equivalente em Reais</div>
        <div class="stat-value accent">${fmtMoney(brlPrice, "BRL")}</div>
      </div>
      <div>
        <div class="stat-label">Market Cap (USD)</div>
        <div class="stat-value">${cp.mcap || "US$ 200 Bi"}</div>
      </div>
      <div>
        <div class="stat-label">P/E Ratio (P/L USD)</div>
        <div class="stat-value">${pe.toFixed(1)}x</div>
      </div>
      <div>
        <div class="stat-label">ROE · Margem Líq.</div>
        <div class="stat-value">${Number(cp.roe || 24).toFixed(1)}% · ${Number(cp.margin || 20).toFixed(1)}%</div>
      </div>
      <div>
        <div class="stat-label">CAGR Receita (5A)</div>
        <div class="stat-value pos">+${Number(cp.cagr_rev || 14).toFixed(1)}% a.a.</div>
      </div>
      <div>
        <div class="stat-label">Bolsa · BDR na B3</div>
        <div class="stat-value">${cp.exchange || "NASDAQ"} · ${cp.bdr || a.ticker}</div>
      </div>
    `;
    return;
  }

  if (cls === "CRIPTO") {
    const brlPrice = cp.price_brl || (a.last_price * (STATE.portfolio?.macro?.usd_brl || 5.72));
    fStrip.innerHTML = `
      <div>
        <div class="stat-label">Cotação em Reais (24/7)</div>
        <div class="stat-value accent">${fmtMoney(brlPrice, "BRL")}</div>
      </div>
      <div>
        <div class="stat-label">Market Cap · Dominância</div>
        <div class="stat-value">${cp.mcap || "US$ 20 Bi"} (${Number(cp.dominance_pct || 1).toFixed(1)}%)</div>
      </div>
      <div>
        <div class="stat-label">Oferta & Escassez</div>
        <div class="stat-value">${cp.supply || "Limitada"}</div>
      </div>
      <div>
        <div class="stat-label">Máxima Histórica (ATH)</div>
        <div class="stat-value">${fmtMoney(cp.ath_usd || a.last_price * 1.2, "USD")} (${Number(cp.ath_distance_pct || -12).toFixed(1)}%)</div>
      </div>
      <div>
        <div class="stat-label">Performance (12M)</div>
        <div class="stat-value pos">+${Number(cp.return_12m_pct || 65).toFixed(1)}%</div>
      </div>
      <div>
        <div class="stat-label">Volume Global 24h</div>
        <div class="stat-value">${fmtCompact(a.volume_day)}</div>
      </div>
    `;
    return;
  }

  const pvpStatus = a.pvp < 0.98 ? "Desconto" : (a.pvp <= 1.03 ? "Justo" : "Ágio");
  if (cls === "FII") {
    fStrip.innerHTML = `
      <div>
        <div class="stat-label">Últ. rendimento / cota</div>
        <div class="stat-value accent">${a.last_dividend_per_share > 0 ? fmtMoney(a.last_dividend_per_share, a.currency) : "—"}</div>
      </div>
      <div>
        <div class="stat-label">DY 12M (Isento IR)</div>
        <div class="stat-value">${a.dy_12m > 0 ? a.dy_12m.toFixed(2) + "% a.a." : "—"}</div>
      </div>
      <div>
        <div class="stat-label">P/VP patrimonial</div>
        <div class="stat-value">${a.pvp > 0 ? a.pvp.toFixed(2) + "x · " + pvpStatus : "—"}</div>
      </div>
      <div>
        <div class="stat-label">Vacância / Adimplência</div>
        <div class="stat-value">${Number(cp.vacancy_pct || 0) === 0 ? "0,0% (Adimplente)" : Number(cp.vacancy_pct).toFixed(1) + "%"}</div>
      </div>
      <div>
        <div class="stat-label">Cap Rate Implícito</div>
        <div class="stat-value">${Number(cp.cap_rate_pct || a.dy_12m * 0.95).toFixed(2)}% a.a.</div>
      </div>
      <div>
        <div class="stat-label">Liquidez diária B3</div>
        <div class="stat-value">${fmtCompact(a.volume_day)}</div>
      </div>
    `;
    return;
  }

  // ACAO_BR
  fStrip.innerHTML = `
    <div>
      <div class="stat-label">Múltiplo P/L · EV/EBITDA</div>
      <div class="stat-value">${a.pl > 0 ? a.pl.toFixed(1) + "x" : "—"} · ${Number(cp.ev_ebitda || 6.5).toFixed(1)}x</div>
    </div>
    <div>
      <div class="stat-label">P/VP patrimonial</div>
      <div class="stat-value">${a.pvp > 0 ? a.pvp.toFixed(2) + "x · " + pvpStatus : "—"}</div>
    </div>
    <div>
      <div class="stat-label">ROE · Margem Líquida</div>
      <div class="stat-value accent">${Number(cp.roe_pct || 16.5).toFixed(1)}% · ${Number(cp.net_margin_pct || 16).toFixed(1)}%</div>
    </div>
    <div>
      <div class="stat-label">Dívida Líq. / EBITDA</div>
      <div class="stat-value">${Number(cp.net_debt_ebitda || 1.15).toFixed(2)}x</div>
    </div>
    <div>
      <div class="stat-label">Dividend Yield (12M)</div>
      <div class="stat-value">${a.dy_12m > 0 ? a.dy_12m.toFixed(2) + "% a.a." : "—"}</div>
    </div>
    <div>
      <div class="stat-label">Liquidez diária B3</div>
      <div class="stat-value">${fmtCompact(a.volume_day)}</div>
    </div>
  `;
}

function renderAssetClassSpecializedPanels(data) {
  const specCard = document.getElementById("detail-specialist-card");
  const simCard = document.getElementById("detail-simulator-card");
  if (!specCard || !simCard) return;

  const a = data.asset;
  const cls = (a.asset_class || "ACAO_BR").toUpperCase();
  const cp = data.class_profile || a.class_profile || {};
  const up = data.user_position || {};

  const userPosHtml = up.has_position
    ? `
      <div>
        <div class="kv-row"><span>Quantidade na carteira</span><strong>${up.quantity} ${cls === "CRIPTO" ? a.ticker : "cotas/ações"}</strong></div>
        <div class="kv-row"><span>Seu preço médio</span><strong class="gold">${fmtMoney(up.avg_price, a.currency)}</strong></div>
        <div class="kv-row"><span>Saldo atual no ativo</span><strong>${fmtMoney(up.current_value, a.currency)} <span class="${up.profit_pct >= 0 ? "pos" : "neg"}">(${fmtPct(up.profit_pct)})</span></strong></div>
      </div>
    `
    : `<div class="faint small">Você ainda não possui <strong class="muted">${a.ticker}</strong> na carteira. Use o simulador abaixo para projetar cenários:</div>`;

  // 1. Especialização para ETF_BR (Acumulação Automática / Sem dividendos mensais)
  if (cls === "ETF_BR") {
    specCard.innerHTML = `
      <div class="card-head">
        <div>
          <div class="card-title">${ic("layers", 16)} Raio-X estrutural do ETF</div>
          <div class="card-sub">Fundo de Índice de Acumulação Total Return na B3</div>
        </div>
        <span class="badge badge-accent badge-lg">Taxa ${Number(cp.admin_fee_pct || 0.30).toFixed(2).replace(".", ",")}% a.a.</span>
      </div>

      <div class="div-highlight">
        <div class="mini">
          <div class="stat-label">Retorno Acumulado (12M)</div>
          <div class="big">+${Number(cp.return_12m_pct || 14.0).toFixed(1)}%</div>
          <div class="stat-foot">Dividendos reinvestidos na cota</div>
        </div>
        <div class="mini">
          <div class="stat-label">CAGR (5 Anos)</div>
          <div class="mid pos">+${Number(cp.cagr_5y_pct || 11.8).toFixed(1)}% a.a.</div>
          <div class="stat-foot">Crescimento composto anual</div>
        </div>
        <div class="mini">
          <div class="stat-label">Gestora Institucional</div>
          <div class="mid">${cp.manager || "Gestora B3"}</div>
          <div class="stat-foot">Custódia B3</div>
        </div>
      </div>

      <div style="margin-top:18px">
        <div class="kv-row"><span>Índice de Referência (Benchmark)</span><strong>${cp.benchmark || a.sector}</strong></div>
        <div class="kv-row"><span>Composição da Cesta</span><strong>${cp.holdings_count || "Ampla diversificação"}</strong></div>
        <div class="kv-row"><span>Exposição Cambial</span><strong>${cp.fx_exposure || "Real (BRL)"}</strong></div>
        <div class="kv-row"><span>Política de Dividendos</span><strong class="accent">${cp.structure || "Acumulação Automática (Total Return)"}</strong></div>
        <div class="kv-row"><span>Regra Tributária B3</span><strong>${cp.tax_rule || "15% IR na venda com lucro"}</strong></div>
      </div>
    `;

    const initQty = up.has_position ? up.quantity : 50;
    simCard.innerHTML = `
      <div>
        <div class="card-title">${ic("calculator", 16)} Simulador de acumulação composta (ETF)</div>
        <div class="card-sub">Projeção de crescimento patrimonial pelo CAGR do índice (${Number(cp.cagr_5y_pct || 11.8).toFixed(1)}% a.a.)</div>
      </div>
      <div id="detail-user-pos-box">${userPosHtml}</div>
      <div class="sim-box">
        <div class="field">
          <label for="sim-shares-input">Quantidade de cotas do ETF (${a.ticker})</label>
          <input type="number" id="sim-shares-input" class="input" value="${initQty}" min="1" step="5" oninput="updateDividendSimulator()" />
        </div>
        <div class="grid-2 grid">
          <div>
            <div class="stat-label">Aporte inicial hoje</div>
            <div id="sim-invested-needed" class="stat-value">R$ 0,00</div>
          </div>
          <div>
            <div class="stat-label">Projeção em 5 anos</div>
            <div id="sim-monthly-income" class="stat-value accent">R$ 0,00</div>
          </div>
        </div>
        <div class="kv-row" style="padding-top:8px;border-top:1px solid var(--border)">
          <span>Projeção em 10 anos (Juros Compostos)</span>
          <strong id="sim-extra-projection" class="pos">R$ 0,00</strong>
        </div>
      </div>
    `;
    updateDividendSimulator();
    return;
  }

  // 2. Especialização para STOCK_US (Crescimento Global em Dólar / Wall Street)
  if (cls === "STOCK_US") {
    const usdBrl = Number(cp.usd_brl || STATE.portfolio?.macro?.usd_brl || 5.72);
    const priceBrl = Number(cp.price_brl || a.last_price * usdBrl);
    const pe = Number(cp.pe_ratio || a.pl || 28.0);

    specCard.innerHTML = `
      <div class="card-head">
        <div>
          <div class="card-title">${ic("globe", 16)} Métricas globais em Dólar (Wall Street)</div>
          <div class="card-sub">Fundamentos corporativos NYSE / NASDAQ e paridade cambial</div>
        </div>
        <span class="badge badge-accent badge-lg">${cp.exchange || "NASDAQ"} · USD</span>
      </div>

      <div class="div-highlight">
        <div class="mini">
          <div class="stat-label">Preço convertido (PTAX)</div>
          <div class="big">${fmtMoney(priceBrl, "BRL")}</div>
          <div class="stat-foot">Câmbio R$ ${usdBrl.toFixed(2).replace(".", ",")} / US$</div>
        </div>
        <div class="mini">
          <div class="stat-label">Market Cap Global</div>
          <div class="mid">${cp.mcap || "US$ 250 Bi"}</div>
          <div class="stat-foot">Valor de mercado em USD</div>
        </div>
        <div class="mini">
          <div class="stat-label">BDR Equivalente B3</div>
          <div class="mid accent">${cp.bdr || a.ticker}</div>
          <div class="stat-foot">Negociado em Reais</div>
        </div>
      </div>

      <div style="margin-top:18px">
        <div class="kv-row"><span>Múltiplo P/E (Preço / Lucro USD)</span><strong>${pe.toFixed(1)}x</strong></div>
        <div class="kv-row"><span>ROE (Retorno s/ Patrimônio)</span><strong class="pos">${Number(cp.roe || 25).toFixed(1)}% a.a.</strong></div>
        <div class="kv-row"><span>Margem Líquida Operacional</span><strong>${Number(cp.margin || 22).toFixed(1)}%</strong></div>
        <div class="kv-row"><span>Crescimento Receita (CAGR 5A)</span><strong class="accent">+${Number(cp.cagr_rev || 14).toFixed(1)}% a.a. (USD)</strong></div>
        <div class="kv-row"><span>Free Cash Flow Yield</span><strong>${Number(cp.fcf_yield || 3.0).toFixed(1)}% a.a. + Recompra de Ações</strong></div>
      </div>
    `;

    const initQty = up.has_position ? up.quantity : 10;
    simCard.innerHTML = `
      <div>
        <div class="card-title">${ic("calculator", 16)} Simulador patrimonial dolarizado (USD / R$)</div>
        <div class="card-sub">Conversão cambial instantânea e projeção composta em moeda forte</div>
      </div>
      <div id="detail-user-pos-box">${userPosHtml}</div>
      <div class="sim-box">
        <div class="field">
          <label for="sim-shares-input">Quantidade de ações (${a.ticker} na ${cp.exchange || "NASDAQ"})</label>
          <input type="number" id="sim-shares-input" class="input" value="${initQty}" min="0.1" step="1" oninput="updateDividendSimulator()" />
        </div>
        <div class="grid-2 grid">
          <div>
            <div class="stat-label">Valor em Dólar (USD)</div>
            <div id="sim-invested-needed" class="stat-value">US$ 0.00</div>
          </div>
          <div>
            <div class="stat-label">Equivalente hoje em R$</div>
            <div id="sim-monthly-income" class="stat-value accent">R$ 0,00</div>
          </div>
        </div>
        <div class="kv-row" style="padding-top:8px;border-top:1px solid var(--border)">
          <span>Projeção estimada em 5 anos (USD / R$)</span>
          <strong id="sim-extra-projection" class="pos">US$ 0.00</strong>
        </div>
      </div>
    `;
    updateDividendSimulator();
    return;
  }

  // 3. Especialização para CRIPTO (Tokenomics, On-Chain & Escassez Digital)
  if (cls === "CRIPTO") {
    const usdBrl = Number(cp.usd_brl || STATE.portfolio?.macro?.usd_brl || 5.72);
    const priceBrl = Number(cp.price_brl || a.last_price * usdBrl);

    specCard.innerHTML = `
      <div class="card-head">
        <div>
          <div class="card-title">${ic("cpu", 16)} Telemetria On-Chain & Tokenomics</div>
          <div class="card-sub">Arquitetura da rede, escassez programada e ciclo de mercado 24/7</div>
        </div>
        <span class="badge badge-accent badge-lg">Dom. ${Number(cp.dominance_pct || 1).toFixed(1)}%</span>
      </div>

      <div class="div-highlight">
        <div class="mini">
          <div class="stat-label">Cotação em Reais (24/7)</div>
          <div class="big">${fmtMoney(priceBrl, "BRL")}</div>
          <div class="stat-foot">1 ${a.ticker} = ${fmtMoney(a.last_price, "USD")}</div>
        </div>
        <div class="mini">
          <div class="stat-label">Máxima Histórica (ATH)</div>
          <div class="mid">${fmtMoney(cp.ath_usd || a.last_price * 1.2, "USD")}</div>
          <div class="stat-foot">${Number(cp.ath_distance_pct || -12).toFixed(1)}% do topo histórico</div>
        </div>
        <div class="mini">
          <div class="stat-label">Market Cap Rede</div>
          <div class="mid pos">${cp.mcap || "US$ 20 Bi"}</div>
          <div class="stat-foot">Liquidez global 24h</div>
        </div>
      </div>

      <div style="margin-top:18px">
        <div class="kv-row"><span>Rede & Arquitetura</span><strong>${cp.network || "Layer 1 Blockchain"}</strong></div>
        <div class="kv-row"><span>Mecanismo de Consenso</span><strong>${cp.consensus || "Proof-of-Stake"}</strong></div>
        <div class="kv-row"><span>Oferta Circulante / Limite</span><strong class="accent">${cp.supply || "Limitada"}</strong></div>
        <div class="kv-row"><span>Política de Emissão Anual</span><strong>${cp.inflation_aa || "< 1,5% a.a."}</strong></div>
        <div class="kv-row"><span>Caso de Uso Principal</span><strong>${cp.use_case || "Reserva de Valor & Web3"}</strong></div>
      </div>
    `;

    const initQty = up.has_position ? up.quantity : (a.ticker === "BTC" ? 0.05 : 1);
    simCard.innerHTML = `
      <div>
        <div class="card-title">${ic("calculator", 16)} Simulador de acumulação cripto (USD / R$)</div>
        <div class="card-sub">Calcule frações de ${a.ticker}, conversão em Reais e retorno na retomada do ATH</div>
      </div>
      <div id="detail-user-pos-box">${userPosHtml}</div>
      <div class="sim-box">
        <div class="field">
          <label for="sim-shares-input">Quantidade de ${a.ticker} (aceita frações ex: 0.05)</label>
          <input type="number" id="sim-shares-input" class="input" value="${initQty}" min="0.0001" step="0.05" oninput="updateDividendSimulator()" />
        </div>
        <div class="grid-2 grid">
          <div>
            <div class="stat-label">Valor atual em USD</div>
            <div id="sim-invested-needed" class="stat-value">US$ 0.00</div>
          </div>
          <div>
            <div class="stat-label">Valor atual em Reais</div>
            <div id="sim-monthly-income" class="stat-value accent">R$ 0,00</div>
          </div>
        </div>
        <div class="kv-row" style="padding-top:8px;border-top:1px solid var(--border)">
          <span>Valor na Máxima Histórica (ATH ${fmtMoney(cp.ath_usd || a.last_price * 1.25, "USD")})</span>
          <strong id="sim-extra-projection" class="pos">R$ 0,00</strong>
        </div>
      </div>
    `;
    updateDividendSimulator();
    return;
  }

  // 4. FII & ACAO_BR (Proventos por cota + Simulador de Renda Passiva)
  const divInfo = data.dividend_info || {};
  let barsHtml = `<div class="empty-sm" style="grid-column:1/-1">Sem distribuições mensais registradas nos últimos 12 meses.</div>`;
  if (divInfo.history_12m && divInfo.history_12m.length > 0) {
    const maxVal = Math.max(...divInfo.history_12m.map(h => h.amount_per_share), 0.01);
    barsHtml = divInfo.history_12m.map(h => {
      const pctH = Math.max(8, Math.round((h.amount_per_share / maxVal) * 100));
      return `
        <div class="bar-col">
          <span class="bar-val">${h.amount_per_share > 0 ? h.amount_per_share.toFixed(2).replace(".", ",") : ""}</span>
          <div class="bar" style="height:${pctH}%"></div>
          <span class="bar-lbl">${h.month.split("/")[0]}</span>
        </div>
      `;
    }).join("");
  }

  specCard.innerHTML = `
    <div class="card-head">
      <div>
        <div class="card-title">${ic("coins", 16)} Proventos por ${cls === "FII" ? "cota (Isento IR)" : "ação (Dividendos & JCP)"}</div>
        <div class="card-sub">Último pagamento anunciado e histórico de 12 meses</div>
      </div>
      <span id="detail-div-yield-badge" class="badge badge-accent badge-lg">DY 12M · ${Number(divInfo.dy_12m || 0).toFixed(2)}%</span>
    </div>
    <div class="div-highlight">
      <div class="mini">
        <div class="stat-label">Último valor por ${cls === "FII" ? "cota" : "ação"}</div>
        <div id="detail-div-per-share" class="big">${divInfo.last_dividend_per_share > 0 ? fmtMoney(divInfo.last_dividend_per_share, a.currency) : "—"}</div>
        <div id="detail-div-monthly-pct" class="stat-foot">${divInfo.monthly_yield_pct > 0 ? `${divInfo.monthly_yield_pct.toFixed(2)}% sobre a cotação` : "Provento recorrente"}</div>
      </div>
      <div class="mini">
        <div class="stat-label">Data com (Ex-Date)</div>
        <div id="detail-div-ex-date" class="mid">${divInfo.last_ex_date || "—"}</div>
        <div class="stat-foot">Direito ao provento</div>
      </div>
      <div class="mini">
        <div class="stat-label">Pagamento</div>
        <div id="detail-div-pay-date" class="mid">${divInfo.last_pay_date || "—"}</div>
        <div class="stat-foot">Data prevista</div>
      </div>
    </div>
    <div style="margin-top:20px">
      <div class="eyebrow">Histórico de distribuições (12 meses)</div>
      <div id="detail-div-bars" class="bars">${barsHtml}</div>
    </div>
  `;

  const initQty = up.has_position ? up.quantity : 100;
  const posHtmlWithDiv = up.has_position
    ? `
      <div>
        <div class="kv-row"><span>Quantidade na carteira</span><strong>${up.quantity} ${cls === "FII" ? "cotas" : "ações"}</strong></div>
        <div class="kv-row"><span>Seu preço médio</span><strong class="gold">${fmtMoney(up.avg_price, a.currency)}</strong></div>
        <div class="kv-row"><span>Saldo atual no ativo</span><strong>${fmtMoney(up.current_value, a.currency)} <span class="${up.profit_pct >= 0 ? "pos" : "neg"}">(${fmtPct(up.profit_pct)})</span></strong></div>
        <div class="kv-row"><span>Renda no último provento</span><strong class="accent">${fmtMoney(up.estimated_next_dividend, a.currency)}</strong></div>
      </div>
    `
    : userPosHtml;

  simCard.innerHTML = `
    <div>
      <div class="card-title">${ic("calculator", 16)} Sua posição & simulador de renda passiva</div>
      <div class="card-sub">Quanto suas ${cls === "FII" ? "cotas" : "ações"} rendem — ou simule outra quantidade</div>
    </div>
    <div id="detail-user-pos-box">${posHtmlWithDiv}</div>
    <div class="sim-box">
      <div class="field">
        <label for="sim-shares-input">Quantidade de ${cls === "FII" ? "cotas" : "ações"} (${a.ticker})</label>
        <input type="number" id="sim-shares-input" class="input" value="${initQty}" min="1" step="10" oninput="updateDividendSimulator()" />
      </div>
      <div class="grid-2 grid">
        <div>
          <div class="stat-label">Investimento necessário</div>
          <div id="sim-invested-needed" class="stat-value">R$ 0,00</div>
        </div>
        <div>
          <div class="stat-label">Renda por distribuição</div>
          <div id="sim-monthly-income" class="stat-value accent">R$ 0,00</div>
        </div>
      </div>
      <div class="kv-row" style="padding-top:8px;border-top:1px solid var(--border)">
        <span>Renda passiva anual estimada (DY ${Number(a.dy_12m || 0).toFixed(1)}%)</span>
        <strong id="sim-extra-projection" class="pos">R$ 0,00 / ano</strong>
      </div>
    </div>
  `;
  updateDividendSimulator();
}

function loadAssetDetailPeriod(period) {
  if (!STATE.activeAssetTicker) return;
  openAssetDetail(STATE.activeAssetTicker, period, true);
}

function closeAssetDetail() {
  switchMainTab(STATE.previousTab || "DASHBOARD");
}

function setDetailHeaderReadout(price, changePct, changeAbs, dateLabel, currency = "BRL") {
  document.getElementById("detail-hover-price").textContent = fmtMoney(price, currency);
  const chgEl = document.getElementById("detail-hover-change");
  const sign = changeAbs >= 0 ? "+" : "";
  chgEl.textContent = `${fmtPct(changePct)} (${sign}${fmtMoney(changeAbs, currency)})`;
  chgEl.className = `badge badge-lg ${changePct >= 0 ? "badge-pos" : "badge-neg"}`;
  document.getElementById("detail-hover-date").textContent = dateLabel;
}

/* ---------- Gráfico Interativo de Preço (Canvas DPI) ---------- */
function drawInteractiveAssetChart(data) {
  const canvas = document.getElementById("asset-interactive-chart");
  if (!canvas) return;
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const W = Math.max(280, rect.width);
  const H = Math.max(220, rect.height);
  canvas.width = W * dpr;
  canvas.height = H * dpr;

  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const points = data.points || [];
  if (points.length < 2) return;

  const prices = points.map(p => p.price);
  const userPm = data.user_position && data.user_position.has_position ? data.user_position.avg_price : null;
  let minP = Math.min(...prices);
  let maxP = Math.max(...prices);
  if (userPm && userPm > 0) {
    minP = Math.min(minP, userPm * 0.985);
    maxP = Math.max(maxP, userPm * 1.015);
  }
  const padY = (maxP - minP) * 0.14 || 1.0;
  minP -= padY;
  maxP += padY;

  const padLeft = 8;
  const padRight = 62;
  const padTop = 18;
  const padBottom = 28;
  const plotW = W - padLeft - padRight;
  const plotH = H - padTop - padBottom;

  const isPositive = points[points.length - 1].price >= points[0].price;
  const mainColor = isPositive ? (cssVar("--pos") || "#3ecf8e") : (cssVar("--neg") || "#f2555a");
  const gridColor = cssVar("--chart-grid") || "rgba(255,255,255,0.06)";
  const textColor = cssVar("--chart-text") || "#6b7079";
  const tooltipBg = cssVar("--chart-tooltip") || "#16191e";
  const textMain = cssVar("--text") || "#edeef0";

  function xForIdx(i) {
    return padLeft + (i / (points.length - 1)) * plotW;
  }
  function yForPrice(p) {
    return padTop + (1 - (p - minP) / (maxP - minP)) * plotH;
  }

  function renderChart(hoverIdx = null) {
    ctx.clearRect(0, 0, W, H);

    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1;
    ctx.fillStyle = textColor;
    ctx.font = "500 11px 'Geist Mono', monospace";
    ctx.textAlign = "left";

    for (let g = 0; g <= 4; g++) {
      const gy = padTop + (g / 4) * plotH;
      const gp = maxP - (g / 4) * (maxP - minP);
      ctx.beginPath();
      ctx.moveTo(padLeft, gy);
      ctx.lineTo(padLeft + plotW, gy);
      ctx.stroke();
      ctx.fillText(gp.toFixed(2).replace(".", ","), padLeft + plotW + 8, gy + 4);
    }

    ctx.textAlign = "center";
    const stepX = Math.max(1, Math.floor((points.length - 1) / 5));
    for (let i = 0; i < points.length; i += stepX) {
      ctx.fillText(points[i].label, xForIdx(i), H - 8);
    }

    // Linha tracejada do Preço Médio do usuário
    if (userPm && userPm > 0) {
      const py = yForPrice(userPm);
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "#e8b04b";
      ctx.lineWidth = 1.25;
      ctx.beginPath();
      ctx.moveTo(padLeft, py);
      ctx.lineTo(padLeft + plotW, py);
      ctx.stroke();
      ctx.fillStyle = "#e8b04b";
      ctx.font = "600 10.5px Geist, sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(`PM ${userPm.toFixed(2).replace(".", ",")}`, padLeft + 6, py - 6);
      ctx.restore();
    }

    // Gradiente de área
    const grad = ctx.createLinearGradient(0, padTop, 0, padTop + plotH);
    grad.addColorStop(0, isPositive ? "rgba(62, 207, 142, 0.24)" : "rgba(242, 85, 90, 0.24)");
    grad.addColorStop(1, "rgba(0, 0, 0, 0)");

    ctx.beginPath();
    ctx.moveTo(xForIdx(0), padTop + plotH);
    points.forEach((pt, idx) => ctx.lineTo(xForIdx(idx), yForPrice(pt.price)));
    ctx.lineTo(xForIdx(points.length - 1), padTop + plotH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Linha principal
    ctx.beginPath();
    points.forEach((pt, idx) => {
      const px = xForIdx(idx);
      const py = yForPrice(pt.price);
      if (idx === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.strokeStyle = mainColor;
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.stroke();

    // Crosshair no hover
    if (hoverIdx !== null && hoverIdx >= 0 && hoverIdx < points.length) {
      const pt = points[hoverIdx];
      const hx = xForIdx(hoverIdx);
      const hy = yForPrice(pt.price);

      ctx.save();
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = textColor;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(hx, padTop);
      ctx.lineTo(hx, padTop + plotH);
      ctx.stroke();
      ctx.restore();

      ctx.beginPath();
      ctx.arc(hx, hy, 5, 0, Math.PI * 2);
      ctx.fillStyle = mainColor;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = tooltipBg;
      ctx.stroke();

      const tipText1 = fmtMoney(pt.price, data.asset.currency);
      const tipText2 = pt.label;
      ctx.font = "600 12px Geist, sans-serif";
      const tw = Math.max(ctx.measureText(tipText1).width, ctx.measureText(tipText2).width) + 22;
      const th = 42;
      let tx = hx - tw / 2;
      if (tx < padLeft) tx = padLeft;
      if (tx + tw > padLeft + plotW) tx = padLeft + plotW - tw;
      let ty = hy - th - 12;
      if (ty < 4) ty = hy + 14;

      ctx.fillStyle = tooltipBg;
      ctx.strokeStyle = mainColor;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(tx, ty, tw, th, 8);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = textMain;
      ctx.textAlign = "center";
      ctx.font = "600 12px Geist, sans-serif";
      ctx.fillText(tipText1, tx + tw / 2, ty + 17);
      ctx.fillStyle = textColor;
      ctx.font = "500 10.5px 'Geist Mono', monospace";
      ctx.fillText(tipText2, tx + tw / 2, ty + 33);
    }
  }

  renderChart(null);

  function handlePointer(clientX) {
    const cRect = canvas.getBoundingClientRect();
    const relX = clientX - cRect.left - padLeft;
    const ratio = Math.max(0, Math.min(1, relX / plotW));
    const idx = Math.round(ratio * (points.length - 1));
    const pt = points[idx];
    const firstP = points[0].price;
    const diffAbs = pt.price - firstP;
    const diffPct = firstP > 0 ? (diffAbs / firstP) * 100.0 : 0.0;
    setDetailHeaderReadout(pt.price, diffPct, diffAbs, pt.label, data.asset.currency);
    renderChart(idx);
  }

  canvas.onmousemove = (e) => handlePointer(e.clientX);
  canvas.ontouchmove = (e) => {
    if (e.touches && e.touches[0]) handlePointer(e.touches[0].clientX);
  };
  canvas.onmouseleave = () => {
    setDetailHeaderReadout(
      data.asset.last_price,
      data.period_change_pct,
      data.period_change_abs,
      `Cotação atual (${data.period}) · passe o mouse no gráfico para inspecionar`,
      data.asset.currency
    );
    renderChart(null);
  };
}

function updateDividendSimulator() {
  if (!STATE.activeAssetData) return;
  const a = STATE.activeAssetData.asset;
  const cls = (a.asset_class || "ACAO_BR").toUpperCase();
  const cp = STATE.activeAssetData.class_profile || a.class_profile || {};
  const inputEl = document.getElementById("sim-shares-input");
  const qty = parseFloat(inputEl ? inputEl.value : "100") || 0;
  const investedNeeded = qty * a.last_price;
  const usdBrl = Number(cp.usd_brl || STATE.portfolio?.macro?.usd_brl || 5.72);

  const elInv = document.getElementById("sim-invested-needed");
  const elInc = document.getElementById("sim-monthly-income");
  const elExtra = document.getElementById("sim-extra-projection");

  if (cls === "ETF_BR") {
    const cagr = Number(cp.cagr_5y_pct || 11.8) / 100.0;
    const proj5y = investedNeeded * Math.pow(1 + cagr, 5);
    const proj10y = investedNeeded * Math.pow(1 + cagr, 10);
    if (elInv) elInv.textContent = fmtMoney(investedNeeded, "BRL");
    if (elInc) elInc.textContent = fmtMoney(proj5y, "BRL");
    if (elExtra) elExtra.textContent = fmtMoney(proj10y, "BRL");
    return;
  }

  if (cls === "STOCK_US") {
    const cagr = Math.min(0.22, Math.max(0.08, Number(cp.cagr_rev || 12.0) / 100.0));
    const brlNow = investedNeeded * usdBrl;
    const usd5y = investedNeeded * Math.pow(1 + cagr, 5);
    const brl5y = usd5y * usdBrl;
    if (elInv) elInv.textContent = fmtMoney(investedNeeded, "USD");
    if (elInc) elInc.textContent = fmtMoney(brlNow, "BRL");
    if (elExtra) elExtra.textContent = `${fmtMoney(usd5y, "USD")} (${fmtMoney(brl5y, "BRL")})`;
    return;
  }

  if (cls === "CRIPTO") {
    const brlNow = investedNeeded * usdBrl;
    const athUsd = Number(cp.ath_usd || a.last_price * 1.25);
    const valAtAthUsd = qty * athUsd;
    const valAtAthBrl = valAtAthUsd * usdBrl;
    if (elInv) elInv.textContent = fmtMoney(investedNeeded, "USD");
    if (elInc) elInc.textContent = fmtMoney(brlNow, "BRL");
    if (elExtra) elExtra.textContent = `${fmtMoney(valAtAthUsd, "USD")} (${fmtMoney(valAtAthBrl, "BRL")})`;
    return;
  }

  // FII & ACAO_BR
  const monthlyDiv = qty * a.last_dividend_per_share;
  const annualDiv = investedNeeded * (Number(a.dy_12m || 0) / 100.0);
  if (elInv) elInv.textContent = fmtMoney(investedNeeded, a.currency);
  if (elInc) elInc.textContent = fmtMoney(monthlyDiv, a.currency);
  if (elExtra) elExtra.textContent = `${fmtMoney(annualDiv, a.currency)} / ano`;
}

function parseFlexibleDateMs(rawStr, isoStr = "") {
  if (isoStr) {
    const tIso = Date.parse(isoStr);
    if (!Number.isNaN(tIso)) return tIso;
  }
  const s = String(rawStr || "").trim();
  if (!s) return 0;

  // Formato brasileiro DD/MM/YYYY [HH:MM[:SS]]
  const mBr = s.match(/(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?/);
  if (mBr) {
    const [, dd, mm, yyyy, hh = "00", min = "00", ss = "00"] = mBr;
    return new Date(Number(yyyy), Number(mm) - 1, Number(dd), Number(hh), Number(min), Number(ss)).getTime();
  }

  // Formato ISO YYYY-MM-DD
  const mIso = s.match(/(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2})(?::(\d{2}))?)?/);
  if (mIso) {
    const [, yyyy, mm, dd, hh = "00", min = "00", ss = "00"] = mIso;
    return new Date(Number(yyyy), Number(mm) - 1, Number(dd), Number(hh), Number(min), Number(ss)).getTime();
  }

  const parsed = Date.parse(s);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function formatDatePtBr(rawStr, isoStr = "") {
  const ms = parseFlexibleDateMs(rawStr, isoStr);
  if (!ms) return rawStr || "—";
  const d = new Date(ms);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  const hh = d.getHours();
  const min = d.getMinutes();
  if (hh || min) {
    return `${dd}/${mm}/${yyyy} ${String(hh).padStart(2, "0")}:${String(min).padStart(2, "0")}`;
  }
  return `${dd}/${mm}/${yyyy}`;
}

/* ---------- Funções de Apoio aos Modelos de Decisão (Acelerador & Resumo IA) ---------- */
function renderValuationAccelerator(marginPct, currentPrice, currency = "R$") {
  const m = Number(marginPct) || 0;
  const p = Number(currentPrice) || 0;

  let zoneKey = "justo";
  let zoneName = "Preço Justo";
  let zoneBadgeClass = "zone-justo";
  let needlePct = 50;

  if (m < -20.0) {
    zoneKey = "muito-caro";
    zoneName = "Muito Caro";
    zoneBadgeClass = "zone-muito-caro";
    needlePct = Math.max(6, Math.min(18, 10 + (m + 40) * 0.3));
  } else if (m < -5.0) {
    zoneKey = "caro";
    zoneName = "Caro";
    zoneBadgeClass = "zone-caro";
    needlePct = Math.max(22, Math.min(38, 30 + (m + 12.5) * 0.8));
  } else if (m <= 5.0) {
    zoneKey = "justo";
    zoneName = "Preço Justo";
    zoneBadgeClass = "zone-justo";
    needlePct = Math.max(42, Math.min(58, 50 + m * 1.5));
  } else if (m <= 25.0) {
    zoneKey = "barato";
    zoneName = "Barato";
    zoneBadgeClass = "zone-barato";
    needlePct = Math.max(62, Math.min(78, 70 + (m - 15) * 0.8));
  } else {
    zoneKey = "muito-barato";
    zoneName = "Muito Barato";
    zoneBadgeClass = "zone-muito-barato";
    needlePct = Math.max(82, Math.min(94, 88 + (m - 35) * 0.2));
  }

  needlePct = Math.max(5, Math.min(95, needlePct));

  return `
    <div class="valuation-accelerator">
      <div class="accelerator-head">
        <span class="accelerator-title">${ic("gauge", 13)} Termômetro de Valuation · Acelerador de Preço</span>
        <span class="accelerator-zone-badge ${zoneBadgeClass}">
          ${zoneName} · Margem ${m >= 0 ? "+" : ""}${m.toFixed(1)}%
        </span>
      </div>

      <div class="accelerator-track-container">
        <div class="accelerator-pointer" style="left: ${needlePct.toFixed(1)}%;">
          <div class="pointer-bubble">${currency} ${p.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
          <div class="pointer-arrow"></div>
          <div class="pointer-needle-line"></div>
        </div>

        <div class="accelerator-track">
          <div class="acc-seg seg-muito-caro ${zoneKey === 'muito-caro' ? 'active' : ''}"></div>
          <div class="acc-seg seg-caro ${zoneKey === 'caro' ? 'active' : ''}"></div>
          <div class="acc-seg seg-justo ${zoneKey === 'justo' ? 'active' : ''}"></div>
          <div class="acc-seg seg-barato ${zoneKey === 'barato' ? 'active' : ''}"></div>
          <div class="acc-seg seg-muito-barato ${zoneKey === 'muito-barato' ? 'active' : ''}"></div>
        </div>
      </div>

      <div class="accelerator-labels">
        <span class="${zoneKey === 'muito-caro' ? 'is-active' : ''}" style="${zoneKey === 'muito-caro' ? 'color:#ef4444;font-weight:750' : ''}">Muito Caro</span>
        <span class="${zoneKey === 'caro' ? 'is-active' : ''}" style="${zoneKey === 'caro' ? 'color:#f97316;font-weight:750' : ''}">Caro</span>
        <span class="${zoneKey === 'justo' ? 'is-active' : ''}" style="${zoneKey === 'justo' ? 'color:#eab308;font-weight:750' : ''}">Justo</span>
        <span class="${zoneKey === 'barato' ? 'is-active' : ''}" style="${zoneKey === 'barato' ? 'color:#22c55e;font-weight:750' : ''}">Barato</span>
        <span class="${zoneKey === 'muito-barato' ? 'is-active' : ''}" style="${zoneKey === 'muito-barato' ? 'color:#10b981;font-weight:750' : ''}">Muito Barato</span>
      </div>
    </div>
  `;
}

function renderExecutiveAiConclusion(ec, asset) {
  if (!ec) return "";
  const verdictCls = ec.buy_verdict === "BOM PARA COMPRAR"
    ? "badge-good"
    : (ec.buy_verdict === "RISCO MODERADO" ? "badge-warn" : "badge-danger");

  const bulletsHtml = (ec.key_arguments || []).map(arg => `
    <li><span class="pos">${ic("check", 13)}</span><span>${arg}</span></li>
  `).join("");

  const riskCol = ec.risk_level?.includes("Baixo") ? "var(--pos)" : (ec.risk_level?.includes("Elevado") ? "var(--neg)" : "var(--gold)");
  const buyCol = ec.buy_verdict === "BOM PARA COMPRAR" ? "var(--pos)" : (ec.buy_verdict === "RISCO MODERADO" ? "var(--gold)" : "var(--neg)");

  return `
    <div class="executive-ai-summary-card">
      <div class="exec-header">
        <div class="exec-title-group">
          <div class="exec-title-ic">${ic("sparkles", 18)}</div>
          <div>
            <div class="exec-title-text">Resumo Geral da IA · Diagnóstico & Decisão Executiva</div>
            <div class="exec-subtitle-text">Parecer consolidado de estabilidade, valuation e oportunidade de alocação</div>
          </div>
        </div>
        <div class="exec-badges-group">
          <span class="badge badge-accent">${ec.stability_badge || "Estabilidade Analisada"}</span>
          <span class="exec-decision-badge ${verdictCls}">${ic("target", 13)} ${ec.buy_badge || ec.buy_verdict}</span>
        </div>
      </div>

      <div class="exec-content-grid">
        <div class="exec-narrative-block">
          <div class="exec-headline-phrase">${esc(ec.summary_headline || "")}</div>
          <p class="exec-narrative-text">${esc(ec.verdict_narrative || "")}</p>
          ${ec.action_plan ? `
            <div class="exec-action-callout">
              <span class="ic">${ic("trending-up", 16)}</span>
              <div>
                <strong>Recomendação de Aporte:</strong> ${esc(ec.action_plan)}
              </div>
            </div>
          ` : ""}
        </div>

        <div class="exec-metrics-block">
          <div class="exec-kpi-grid">
            <div class="exec-kpi-box">
              <span>Score Estabilidade</span>
              <strong style="color:var(--accent)">${Number(ec.stability_score || 85)}/100</strong>
            </div>
            <div class="exec-kpi-box">
              <span>Classificação</span>
              <strong style="font-size:12px">${esc(ec.stability_label ? ec.stability_label.split('(')[0].trim() : 'Estável')}</strong>
            </div>
            <div class="exec-kpi-box">
              <span>Nível de Risco</span>
              <strong style="color:${riskCol}">${esc(ec.risk_level || "Moderado")}</strong>
            </div>
            <div class="exec-kpi-box">
              <span>Decisão de Compra</span>
              <strong style="color:${buyCol}">${esc(ec.buy_verdict || "")}</strong>
            </div>
          </div>

          <ul class="exec-arguments-list">
            ${bulletsHtml}
          </ul>
        </div>
      </div>
    </div>
  `;
}

/* ---------- Relatórios Oficiais + Leitura IA ---------- */
function renderAiReportSection(repData) {
  const aiBox = document.getElementById("detail-ai-report-box");
  const docsList = document.getElementById("detail-official-docs-list");
  if (!repData) return;

  const ai = repData.ai_interpretation;
  if (ai) {
    const metricsHtml = (ai.key_metrics || []).map(m => `
      <div>
        <div class="stat-label">${esc(m.label)}</div>
        <div class="strong small" style="margin-top:3px;color:${m.status === "good" ? "var(--pos)" : "var(--text)"}">${esc(m.value)}</div>
      </div>
    `).join("");

    const bullsHtml = (ai.bullish_points || []).map(b => `<li><span class="pos">${ic("check", 14)}</span><span>${esc(b)}</span></li>`).join("");
    const bearsHtml = (ai.bearish_risks || []).map(r => `<li><span class="gold">${ic("alert", 14)}</span><span>${esc(r)}</span></li>`).join("");

    const pdfBadge = ai.pdf_pages_read && ai.pdf_pages_read > 0
      ? `<span class="badge badge-info">PDF extraído · ${Number(ai.pdf_pages_read)} págs</span>`
      : `<span class="badge">B3 / CVM</span>`;

    const excerptsHtml = ai.pdf_excerpts && ai.pdf_excerpts.length > 0
      ? `
        <div>
          <div class="row between" style="margin-bottom:6px">
            <span class="eyebrow">Trechos do documento oficial</span>
            ${ai.pdf_url ? `<a href="${sanitizeUrl(ai.pdf_url)}" target="_blank" rel="noopener noreferrer" class="link xs">Baixar PDF ${ic("download", 12)}</a>` : ""}
          </div>
          <ul class="excerpts">
            ${ai.pdf_excerpts.map(ex => `<li>“${esc(ex)}”</li>`).join("")}
          </ul>
        </div>
      `
      : "";

    // Esquema dos 5 Pilares Fundamentalistas em Lista Vertical Completa:
    // 1. Indicadores de Valuation · 2. Indicadores de Endividamento · 3. Eficiência · 4. Rentabilidade · 5. Crescimento
    const pillarsList = ai.pillars_analysis || [];
    const pillarsHtml = pillarsList.length > 0
      ? `
        <div class="pillars-section">
          <div class="row between wrap gap-2">
            <span class="eyebrow">Diagnóstico Completo IA nos 5 Pilares (Lista Vertical Detalhada)</span>
            <span class="xs faint">${pillarsList.length} categorias · 25 indicadores analisados</span>
          </div>
          <div class="pillars-grid">
            ${pillarsList.map((p, idx) => {
              const num = String(idx + 1).padStart(2, "0");
              const bCls = p.status === "good" ? "badge-pos" : (p.status === "warn" ? "badge-gold" : "badge-accent");
              const kvHtml = (p.metrics || []).map(m => `
                <div class="pillar-kv">
                  <span>${esc(m.label)}</span>
                  <strong>${esc(m.value)}</strong>
                </div>
              `).join("");
              return `
                <div class="pillar-card">
                  <div class="pillar-head">
                    <div class="pillar-title">
                      <span class="pillar-num">${num}</span>
                      <span>${esc(p.title)}</span>
                    </div>
                    <span class="badge ${bCls}">${esc(p.badge || "OK")}</span>
                  </div>
                  <div class="pillar-metrics">${kvHtml}</div>
                  <p class="pillar-analysis">${esc(p.analysis || "")}</p>
                </div>
              `;
            }).join("")}
          </div>
        </div>
      `
      : "";

    // Viabilidade por Semestre/Trimestre + Fórmulas de Décio Bazin e Benjamin Graham (quando aplicáveis)
    const vm = ai.valuation_models || {};
    const viab = vm.viability;
    const bazin = vm.bazin;
    const graham = vm.graham;

    let viabilityHtml = "";
    if (viab && Array.isArray(viab.periods) && viab.periods.length > 0) {
      const vBadgeCls = viab.status === "good" ? "badge-pos" : (viab.status === "warn" ? "badge-gold" : "badge-accent");
      const periodsRows = viab.periods.map(pr => {
        const prBadgeCls = pr.status === "good" ? "badge-pos" : (pr.status === "warn" ? "badge-gold" : "badge-accent");
        return `
          <div class="viability-row">
            <div class="viability-row-top">
              <span class="viability-period">${ic("calendar", 13)} ${esc(pr.period)}</span>
              <span class="badge ${prBadgeCls}">${esc(pr.badge)}</span>
            </div>
            <p class="viability-summary">${esc(pr.summary)}</p>
          </div>
        `;
      }).join("");

      viabilityHtml = `
        <div class="viability-card">
          <div class="viability-head">
            <div>
              <div class="strong" style="font-size:13px">Viabilidade de Investimento IA por Trimestre / Semestre</div>
              <div class="xs faint" style="margin-top:2px">Acompanhamento evolutivo de resultados, múltiplos e ponto de entrada</div>
            </div>
            <div class="row gap-2 wrap">
              <span class="viability-score">Score IA: ${Number(viab.score || 80)}/100</span>
              <span class="badge ${vBadgeCls}">${esc(viab.overall_call || "EM ANÁLISE")}</span>
            </div>
          </div>
          <div class="viability-timeline">
            ${periodsRows}
          </div>
        </div>
      `;
    }

    let formulasCardsHtml = "";
    if (bazin && bazin.applicable) {
      const bzCls = bazin.status === "good" ? "badge-pos" : (bazin.status === "warn" ? "badge-gold" : "badge-accent");
      const cur = bazin.currency || "R$";
      const margin6Color = bazin.margin_6pct >= 0 ? "var(--pos)" : "var(--neg)";
      const bzAcceleratorHtml = renderValuationAccelerator(bazin.margin_6pct, bazin.current_price, cur);

      formulasCardsHtml += `
        <div class="formula-card">
          <div class="formula-head">
            <div>
              <div class="formula-title">
                <span class="pillar-num">BZ</span>
                <span>Fórmula de Décio Bazin (Preço Teto por Dividendos)</span>
              </div>
              <div class="formula-equation">${esc(bazin.formula)}</div>
            </div>
            <span class="badge ${bzCls}">${esc(bazin.verdict)}</span>
          </div>
          ${bzAcceleratorHtml}
          <div class="formula-metrics">
            <div class="formula-metric-cell">
              <span>Cotação Atual</span>
              <strong>${cur} ${Number(bazin.current_price).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
            </div>
            <div class="formula-metric-cell">
              <span>Provento Anual (12M)</span>
              <strong>${cur} ${Number(bazin.annual_dividend_per_share).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${bazin.current_dy_pct}% a.a.)</strong>
            </div>
            <div class="formula-metric-cell">
              <span>Preço Teto Bazin (6%)</span>
              <strong style="color:var(--pos)">${cur} ${Number(bazin.ceiling_price_6pct).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
            </div>
            <div class="formula-metric-cell">
              <span>Teto Conservador (${bazin.conservative_rate_pct}%)</span>
              <strong>${cur} ${Number(bazin.ceiling_price_conservative).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
            </div>
            <div class="formula-metric-cell">
              <span>Margem de Segurança (6%)</span>
              <strong style="color:${margin6Color}">${bazin.margin_6pct >= 0 ? "+" : ""}${bazin.margin_6pct}%</strong>
            </div>
          </div>
          <p class="formula-desc">${esc(bazin.explanation)}</p>
        </div>
      `;
    }

    if (graham && graham.applicable) {
      const grCls = graham.status === "good" ? "badge-pos" : (graham.status === "warn" ? "badge-gold" : "badge-accent");
      const cur = graham.currency || "R$";
      const marginGrColor = graham.safety_margin_pct >= 0 ? "var(--pos)" : "var(--neg)";
      const grAcceleratorHtml = renderValuationAccelerator(graham.safety_margin_pct, graham.current_price, cur);

      formulasCardsHtml += `
        <div class="formula-card">
          <div class="formula-head">
            <div>
              <div class="formula-title">
                <span class="pillar-num">GR</span>
                <span>Fórmula de Benjamin Graham (Valor Intrínseco)</span>
              </div>
              <div class="formula-equation">${esc(graham.formula)}</div>
            </div>
            <span class="badge ${grCls}">${esc(graham.verdict)}</span>
          </div>
          ${grAcceleratorHtml}
          <div class="formula-metrics">
            <div class="formula-metric-cell">
              <span>Cotação Atual</span>
              <strong>${cur} ${Number(graham.current_price).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
            </div>
            <div class="formula-metric-cell">
              <span>LPA (Lucro / Cota)</span>
              <strong>${cur} ${Number(graham.lpa).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
            </div>
            <div class="formula-metric-cell">
              <span>VPA (Valor Patrimonial)</span>
              <strong>${cur} ${Number(graham.vpa).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
            </div>
            <div class="formula-metric-cell">
              <span>Valor Intrínseco (Graham)</span>
              <strong style="color:var(--pos)">${cur} ${Number(graham.intrinsic_value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
            </div>
            <div class="formula-metric-cell">
              <span>Margem de Segurança</span>
              <strong style="color:${marginGrColor}">${graham.safety_margin_pct >= 0 ? "+" : ""}${graham.safety_margin_pct}%</strong>
            </div>
          </div>
          <p class="formula-desc">${esc(graham.explanation)}</p>
        </div>
      `;
    }

    const valuationModelsHtml = (viabilityHtml || formulasCardsHtml)
      ? `
        <div class="valuation-section">
          <div class="row between wrap gap-2">
            <span class="eyebrow">Modelos de Decisão: Viabilidade Trimestral/Semestral · Bazin · Graham</span>
          </div>
          ${viabilityHtml}
          ${formulasCardsHtml ? `<div class="formulas-list">${formulasCardsHtml}</div>` : ""}
        </div>
      `
      : "";

    const execHtml = renderExecutiveAiConclusion(ai.executive_conclusion, STATE.activeAssetData?.asset);

    aiBox.innerHTML = `
      <div class="ai-box">
        <div class="row between wrap gap-2">
          <div>
            <div class="strong">${esc(ai.analyzed_document || "Relatório Oficial")}</div>
            <div class="xs faint" style="margin-top:2px">
              ${esc(repData.official_portal || ai.document_source || "B3 / CVM")}
              ${ai.document_date ? ` · ${esc(ai.document_date)}` : ""}
            </div>
          </div>
          <div class="row gap-2">
            ${pdfBadge}
            <span class="badge badge-pos">${esc(ai.verdict_badge || "Análise concluída")}</span>
          </div>
        </div>

        <p class="ai-summary">${esc(ai.executive_summary)}</p>
        ${valuationModelsHtml}
        ${pillarsHtml}
        ${execHtml}
        ${excerptsHtml}
        <div class="metric-grid">${metricsHtml}</div>

        <div class="pros-cons">
          <div class="pc">
            <div class="pc-title pos">${ic("check-circle", 14)}Destaques positivos</div>
            <ul>${bullsHtml}</ul>
          </div>
          <div class="pc">
            <div class="pc-title gold">${ic("alert", 14)}Pontos de atenção</div>
            <ul>${bearsHtml}</ul>
          </div>
        </div>

        ${ai.dividend_guidance ? `<div class="guidance">${ic("target", 16)}<span>${esc(ai.dividend_guidance)}</span></div>` : ""}
      </div>
    `;
  }

  // Ordena relatórios dos mais recentes primeiro e exibe no máximo 7 PDFs na sequência
  const sortedDocs = [...(repData.reports || [])]
    .map(d => ({
      ...d,
      _ms: parseFlexibleDateMs(d.date, d.date_iso),
      _numId: parseInt(String(d.raw_id || "0").replace(/\D/g, ""), 10) || 0,
    }))
    .sort((a, b) => (b._ms - a._ms) || (b._numId - a._numId))
    .slice(0, 7);

  docsList.innerHTML = sortedDocs.map((d, idx) => {
    const seq = String(idx + 1).padStart(2, "0");
    const dateFmt = formatDatePtBr(d.date, d.date_iso);
    const dlBtn = d.download_url
      ? `<a href="${sanitizeUrl(d.download_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-secondary">${ic("download", 13)}PDF</a>`
      : "";
    return `
      <div class="doc-row">
        <div class="row gap-3" style="min-width:0">
          <span class="rank-num">#${seq}</span>
          <div style="min-width:0">
            <div class="doc-title">${esc(d.title)}</div>
            <div class="xs faint">${esc(d.source)} · Entrega <strong class="muted">${esc(dateFmt)}</strong>${d.reference ? " · Ref. " + esc(d.reference) : ""}</div>
          </div>
        </div>
        <div class="row gap-2">
          ${dlBtn}
          <a href="${sanitizeUrl(d.url || '#')}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-ghost">Abrir ${ic("arrow-up-right", 13)}</a>
        </div>
      </div>
    `;
  }).join("");
}

async function reanalyzeAssetReport() {
  if (!STATE.activeAssetTicker) return;
  const btn = document.getElementById("btn-reanalyze-ai");
  const prevHtml = btn.innerHTML;
  btn.textContent = "Interpretando…";
  try {
    const res = await fetch(`/api/asset/${STATE.activeAssetTicker}/analyze-report`, { method: "POST" });
    const data = await res.json();
    if (STATE.activeAssetData && data.ai_interpretation) {
      STATE.activeAssetData.reports_data.ai_interpretation = data.ai_interpretation;
      renderAiReportSection(STATE.activeAssetData.reports_data);
      showToast("Relatório reinterpretado com sucesso.");
    }
  } finally {
    btn.innerHTML = prevHtml;
  }
}

/* ---------- Radar de Notícias ---------- */
function renderAssetNewsSection(news) {
  if (!news) return;
  const badge = document.getElementById("detail-news-sentiment-badge");
  const sent = news.overall_sentiment || "NEUTRO";
  badge.textContent = sent;
  badge.className = `badge ${sent.includes("POSITIVO") || sent.includes("OTIMISTA") ? "badge-pos" : sent.includes("NEGATIVO") || sent.includes("CAUTELOSO") ? "badge-neg" : ""}`;

  const listEl = document.getElementById("detail-news-list");
  const nowMs = Date.now();
  const maxAgeMs = 90 * 24 * 60 * 60 * 1000; // 3 meses (90 dias)

  // Filtra últimos 3 meses, ordena das mais recentes primeiro e limita a no máximo 7 notícias
  const sortedNews = [...(news.items || [])]
    .map(n => ({
      ...n,
      _ms: parseFlexibleDateMs(n.published, n.published_iso),
    }))
    .filter(n => !n._ms || (nowMs - n._ms <= maxAgeMs))
    .sort((a, b) => b._ms - a._ms)
    .slice(0, 7);

  if (sortedNews.length === 0) {
    listEl.innerHTML = `<div class="empty-sm">Nenhuma notícia publicada nos últimos 3 meses para este ativo.</div>`;
    return;
  }

  listEl.innerHTML = `
    <div class="news-grid-horizontal">
      ${sortedNews.map((n, idx) => {
        const seq = String(idx + 1).padStart(2, "0");
        const sCls = n.sentiment === "POSITIVO" ? "badge-pos" : n.sentiment === "NEGATIVO" ? "badge-neg" : "";
        const dateFmt = formatDatePtBr(n.published, n.published_iso);
        return `
          <a href="${encodeURI(n.link || '#')}" target="_blank" rel="noopener noreferrer" class="news-card-strip">
            <div class="news-meta">
              <span><strong class="mono faint" style="margin-right:6px">#${seq}</strong>${esc(n.source)} · <strong class="muted">${esc(dateFmt)}</strong></span>
              <span class="badge ${sCls}">${esc(n.sentiment)}</span>
            </div>
            <div class="news-title">${esc(n.title)}</div>
            <div class="row between" style="margin-top:6px">
              <span class="xs faint">Ler notícia completa</span>
              <span class="link xs">${ic("arrow-up-right", 12)}</span>
            </div>
          </a>
        `;
      }).join("")}
    </div>
  `;
}

/* ---------- View: Renda Fixa ---------- */
function renderFixedIncomeView(fiList) {
  const el = document.getElementById("fixed-income-list");
  const sumEl = document.getElementById("fixed-income-summary");
  if (!el) return;

  if (!fiList || fiList.length === 0) {
    if (sumEl) sumEl.innerHTML = "";
    el.innerHTML = `<div class="card empty-sm" style="grid-column:1/-1">Nenhum título ou caixinha cadastrado ainda.</div>`;
    return;
  }

  const totalInv = fiList.reduce((a, b) => a + b.invested_amount, 0);
  const totalNet = fiList.reduce((a, b) => a + b.net_amount, 0);
  const totalProf = totalNet - totalInv;
  const totalPct = totalInv > 0 ? (totalProf / totalInv) * 100 : 0;

  if (sumEl) {
    sumEl.innerHTML = `
      <div class="card card-pad">
        <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:18px">
          <div>
            <div class="stat-label">Saldo líquido total</div>
            <div class="stat-value">${fmtMoney(totalNet)}</div>
          </div>
          <div>
            <div class="stat-label">Total aplicado</div>
            <div class="stat-value muted">${fmtMoney(totalInv)}</div>
          </div>
          <div>
            <div class="stat-label">Rendimento líquido acumulado</div>
            <div class="stat-value pos">+${fmtMoney(totalProf)} <span class="xs">(${fmtPct(totalPct)})</span></div>
          </div>
          <div>
            <div class="stat-label">Títulos ativos</div>
            <div class="stat-value">${fiList.length}</div>
          </div>
        </div>
      </div>
    `;
  }

  el.innerHTML = fiList.map(f => renderFixedIncomeCardHtml(f, true)).join("");
}

/* ---------- View: Proventos ---------- */
function renderDividendsView(divs) {
  const tbody = document.getElementById("dividends-tbody");
  const sumEl = document.getElementById("dividends-summary");
  if (!tbody) return;

  if (!divs || divs.length === 0) {
    if (sumEl) sumEl.innerHTML = "";
    tbody.innerHTML = `<tr><td colspan="7" class="empty-sm">Nenhum provento registrado ainda.</td></tr>`;
    return;
  }

  const total = divs.reduce((a, d) => a + Number(d.total_amount || 0), 0);
  const estMonthly = STATE.portfolio ? STATE.portfolio.kpis.estimated_monthly_divs_brl : 0;

  if (sumEl) {
    sumEl.innerHTML = `
      <div class="card card-pad">
        <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:18px">
          <div>
            <div class="stat-label">Total recebido em proventos</div>
            <div class="stat-value accent">${fmtMoney(total)}</div>
          </div>
          <div>
            <div class="stat-label">Renda passiva mensal estimada</div>
            <div class="stat-value">${fmtMoney(estMonthly)}<span class="faint small"> /mês</span></div>
          </div>
          <div>
            <div class="stat-label">Pagamentos registrados</div>
            <div class="stat-value">${divs.length}</div>
          </div>
        </div>
      </div>
    `;
  }

  tbody.innerHTML = divs.map(d => `
    <tr>
      <td class="mono muted">${esc(d.pay_date)}</td>
      <td><span class="strong" style="cursor:pointer" onclick="openAssetDetail('${esc(d.ticker)}')">${esc(d.ticker)}</span></td>
      <td><span class="badge badge-pos">${esc(d.div_type)}</span></td>
      <td class="r accent">${fmtMoney(d.amount_per_share, d.currency)}</td>
      <td class="r">${Number(d.shares_qty) || 0}</td>
      <td class="r strong accent">${fmtMoney(d.total_amount, d.currency)}</td>
      <td class="r">
        <button onclick="deleteDividend(${d.id})" class="btn-icon sm danger" title="Excluir">${ic("trash", 14)}</button>
      </td>
    </tr>
  `).join("");
}

/* ---------- Modais e Formulários ---------- */
function openModal(id) {
  document.getElementById(id)?.classList.add("is-open");
}

function closeModal(id) {
  document.getElementById(id)?.classList.remove("is-open");
}

function openAddPicker() {
  openModal("modal-add-picker");
}

function openAddInvestmentModal(type = "FII") {
  if (["CAIXINHA", "RENDA_FIXA", "TESOURO"].includes(type)) {
    openFixedIncomeModal(type);
  } else {
    openTransactionModal("", type, "", type === "STOCK_US" || type === "CRIPTO" ? "USD" : "BRL");
  }
}

function setTxType(type) {
  document.getElementById("tx-type").value = type;
  document.getElementById("txtype-BUY")?.classList.toggle("is-active", type === "BUY");
  document.getElementById("txtype-SELL")?.classList.toggle("is-active", type === "SELL");
}

function openAdjustAvgPriceModal(ticker, currentAvgPrice, ev) {
  if (ev) ev.stopPropagation();
  const t = (ticker || "").toUpperCase().trim();
  const modal = document.getElementById("modal-adjust-avg-price");
  if (!modal) return;

  const tInput = document.getElementById("adjust-pm-ticker");
  const pInput = document.getElementById("adjust-pm-input");
  const subEl = document.getElementById("adjust-pm-sub");
  const infoEl = document.getElementById("adjust-pm-info");

  if (tInput) tInput.value = t;
  if (pInput) {
    pInput.value = currentAvgPrice && Number(currentAvgPrice) > 0 ? Number(currentAvgPrice).toFixed(2) : "";
    setTimeout(() => pInput.focus(), 150);
  }
  if (subEl) subEl.textContent = `Ajustar Preço Médio contábil de ${t}`;
  if (infoEl) {
    const pos = (STATE.portfolio?.positions || []).find(p => p.ticker === t);
    if (pos) {
      infoEl.innerHTML = `Posição atual: <strong>${pos.quantity} cotas</strong> de ${pos.name} · Cotação de mercado: <strong>${fmtMoney(pos.current_price, pos.currency)}</strong>`;
    } else {
      infoEl.textContent = `Ativo ${t} em custódia.`;
    }
  }

  modal.classList.add("is-open");
}

async function submitAdjustAvgPrice(ev) {
  if (ev) ev.preventDefault();
  const t = document.getElementById("adjust-pm-ticker")?.value;
  const val = parseFloat(document.getElementById("adjust-pm-input")?.value);
  if (!t || isNaN(val) || val <= 0) {
    showToast("Informe um Preço Médio válido maior que zero.");
    return;
  }

  const btn = document.getElementById("btn-save-adjust-pm");
  const prevTxt = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Salvando…";
  }

  try {
    const res = await fetch(`/api/portfolio/position/${encodeURIComponent(t)}/adjust-avg-price`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ avg_price: val }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Falha ao ajustar Preço Médio.");
    }
    showToast(`Preço Médio de ${t} ajustado para R$ ${val.toFixed(2)} com sucesso!`);
    closeModal("modal-adjust-avg-price");
    await refreshAll();
  } catch (err) {
    showToast(err.message || "Erro ao salvar Preço Médio.");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = prevTxt;
    }
  }
}

function openTransactionModal(ticker = "", assetClass = "FII", price = "", currency = "BRL") {
  setTxType("BUY");
  document.getElementById("tx-ticker").value = ticker;
  document.getElementById("tx-class").value = assetClass;
  document.getElementById("tx-price").value = price;
  document.getElementById("tx-currency").value = currency;
  document.getElementById("tx-lookup-feedback").textContent = "";
  updateTxTotalPreview();
  openModal("modal-transaction");
}

function quickPickTicker(ticker, assetClass) {
  document.getElementById("tx-ticker").value = ticker;
  document.getElementById("tx-class").value = assetClass;
  updateTxCurrency();
  lookupTickerPrice();
}

async function lookupTickerPrice() {
  const ticker = document.getElementById("tx-ticker").value.trim().toUpperCase();
  const cls = document.getElementById("tx-class").value;
  const fb = document.getElementById("tx-lookup-feedback");
  if (!ticker) return;

  fb.textContent = "Buscando cotação atual…";
  try {
    const res = await fetch(`/api/lookup-ticker?ticker=${encodeURIComponent(ticker)}&asset_class=${encodeURIComponent(cls)}`);
    if (res.ok) {
      const info = await res.json();
      if (info && info.last_price > 0) {
        const priceEl = document.getElementById("tx-price");
        if (!priceEl.value || parseFloat(priceEl.value) <= 0) {
          priceEl.value = info.last_price;
        }
        fb.textContent = `${info.name || info.ticker} · Cotação atual ${fmtMoney(info.last_price, info.currency || "BRL")}`;
        updateTxTotalPreview();
      } else {
        fb.textContent = "Informe o preço pago por cota abaixo.";
      }
    }
  } catch (e) {
    fb.textContent = "";
  }
}

function updateTxTotalPreview() {
  const q = parseFloat(document.getElementById("tx-qty").value || "0");
  const p = parseFloat(document.getElementById("tx-price").value || "0");
  const curr = document.getElementById("tx-currency").value || "BRL";
  const el = document.getElementById("tx-total-preview");
  if (el) el.textContent = fmtMoney(q * p, curr);
}

function updateTxCurrency() {
  const cls = document.getElementById("tx-class").value;
  document.getElementById("tx-currency").value = cls === "STOCK_US" || cls === "CRIPTO" ? "USD" : "BRL";
  updateTxTotalPreview();
}

async function submitTransaction() {
  const payload = {
    tx_type: document.getElementById("tx-type").value,
    asset_class: document.getElementById("tx-class").value,
    ticker: document.getElementById("tx-ticker").value.trim().toUpperCase(),
    tx_date: document.getElementById("tx-date").value,
    quantity: parseFloat(document.getElementById("tx-qty").value || "0"),
    unit_price: parseFloat(document.getElementById("tx-price").value || "0"),
    currency: document.getElementById("tx-currency").value,
    broker: document.getElementById("tx-broker").value,
  };
  if (!payload.ticker || payload.quantity <= 0 || payload.unit_price <= 0) {
    showToast("Preencha código, quantidade e preço corretamente.");
    return;
  }
  await fetch("/api/transactions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  document.getElementById("tx-qty").value = "";
  document.getElementById("tx-price").value = "";
  closeModal("modal-transaction");
  showToast(`${payload.ticker} salvo na carteira.`);
  await refreshAll();
}

let _toastTimer = null;
function showToast(msg) {
  const el = document.getElementById("toast-notification");
  const txt = document.getElementById("toast-text");
  if (!el || !txt) return;
  txt.textContent = msg;
  el.classList.add("is-visible");
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("is-visible"), 3200);
}

async function deleteVariablePosition(ticker, ev) {
  if (ev && ev.stopPropagation) ev.stopPropagation();
  await fetch(`/api/portfolio/position/${encodeURIComponent(ticker)}`, { method: "DELETE" });
  showToast(`${ticker} removido da carteira.`);
  await refreshAll();
}

async function deleteIndividualTransaction(txId, ev) {
  if (ev && ev.stopPropagation) ev.stopPropagation();
  await fetch(`/api/transactions/${txId}`, { method: "DELETE" });
  showToast("Lançamento excluído.");
  await refreshAll();
}

async function clearEntirePortfolio() {
  const answer = prompt("ATENÇÃO: Ação irreversível!\nPara confirmar a exclusão de TODOS os investimentos da sua conta, digite ZERAR abaixo:");
  if (answer !== "ZERAR") {
    if (answer !== null) showToast("Operação cancelada.");
    return;
  }
  try {
    const res = await fetch("/api/portfolio/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation: "CONFIRMAR_ZERAR_CARTEIRA" }),
    });
    if (res.ok) {
      showToast("Carteira zerada com sucesso.");
      await refreshAll();
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || "Falha ao zerar carteira.");
    }
  } catch (e) {
    showToast("Erro ao conectar ao servidor.");
  }
}

function openFixedIncomeModal(defaultCategory = "CAIXINHA") {
  const catEl = document.getElementById("fi-category");
  if (catEl && ["CAIXINHA", "RENDA_FIXA", "TESOURO", "FUNDO_INV"].includes(defaultCategory)) {
    catEl.value = defaultCategory;
  }
  if (defaultCategory === "CAIXINHA") applyFixedIncomePreset("CAIXINHA_NUBANK");
  else if (defaultCategory === "TESOURO") applyFixedIncomePreset("TESOURO_IPCA");
  else if (defaultCategory === "RENDA_FIXA") applyFixedIncomePreset("CDB_CDI");
  openModal("modal-fixed-income");
}

function applyFixedIncomePreset(preset) {
  document.querySelectorAll(".fi-preset").forEach(b => b.classList.remove("is-active"));
  document.getElementById(`preset-${preset}`)?.classList.add("is-active");

  const cat = document.getElementById("fi-category");
  const issuer = document.getElementById("fi-issuer");
  const name = document.getElementById("fi-name");
  const indexer = document.getElementById("fi-indexer");
  const rate = document.getElementById("fi-rate");
  const exempt = document.getElementById("fi-exempt");

  if (preset === "CAIXINHA_NUBANK") {
    cat.value = "CAIXINHA"; issuer.value = "Nubank"; name.value = "Caixinha Nubank (Reserva)";
    indexer.value = "CDI"; rate.value = "100"; exempt.checked = false;
  } else if (preset === "CAIXINHA_TURBO") {
    cat.value = "CAIXINHA"; issuer.value = "Nubank / Mercado Pago"; name.value = "Caixinha Turbo 110% CDI";
    indexer.value = "CDI"; rate.value = "110"; exempt.checked = false;
  } else if (preset === "CDB_CDI") {
    cat.value = "RENDA_FIXA"; issuer.value = "Banco / Corretora"; name.value = "CDB Liquidez Diária";
    indexer.value = "CDI"; rate.value = "105"; exempt.checked = false;
  } else if (preset === "CDB_IPCA") {
    cat.value = "RENDA_FIXA"; issuer.value = "Banco / Corretora"; name.value = "CDB IPCA+";
    indexer.value = "IPCA"; rate.value = "6.8"; exempt.checked = false;
  } else if (preset === "LCI_LCA") {
    cat.value = "RENDA_FIXA"; issuer.value = "Banco Inter / Itaú / BB"; name.value = "LCI / LCA Isenta de IR";
    indexer.value = "CDI"; rate.value = "93"; exempt.checked = true;
  } else if (preset === "TESOURO_IPCA") {
    cat.value = "TESOURO"; issuer.value = "Tesouro Nacional"; name.value = "Tesouro IPCA+ 2029";
    indexer.value = "IPCA"; rate.value = "6.45"; exempt.checked = false;
  } else if (preset === "TESOURO_SELIC") {
    cat.value = "TESOURO"; issuer.value = "Tesouro Nacional"; name.value = "Tesouro Selic";
    indexer.value = "SELIC"; rate.value = "0.10"; exempt.checked = false;
  }
  updateFiIndexerHint();
}

function updateFiIndexerHint() {
  const idx = document.getElementById("fi-indexer").value;
  const lbl = document.getElementById("fi-rate-label");
  if (!lbl) return;
  if (idx === "CDI") lbl.textContent = "Taxa (% do CDI — ex: 100)";
  else if (idx === "IPCA") lbl.textContent = "Taxa fixa acima do IPCA (% a.a.)";
  else if (idx === "SELIC") lbl.textContent = "Taxa extra + Selic (% a.a.)";
  else lbl.textContent = "Taxa prefixada (% ao ano)";
}

async function submitFixedIncome() {
  const category = document.getElementById("fi-category") ? document.getElementById("fi-category").value : "RENDA_FIXA";
  const marketValRaw = parseFloat(document.getElementById("fi-market-value")?.value || "0");
  const payload = {
    title_name: document.getElementById("fi-name").value.trim() || "Aplicação Renda Fixa",
    issuer: document.getElementById("fi-issuer").value.trim() || "Banco",
    asset_class: category,
    indexer: document.getElementById("fi-indexer").value,
    rate_value: parseFloat(document.getElementById("fi-rate").value || "100"),
    invested_amount: parseFloat(document.getElementById("fi-amount").value || "0"),
    start_date: document.getElementById("fi-start").value,
    maturity_date: document.getElementById("fi-maturity").value,
    tax_exempt: document.getElementById("fi-exempt").checked ? 1 : 0,
    broker: document.getElementById("fi-issuer").value.trim() || "Nubank",
  };
  if (marketValRaw > 0) {
    payload.market_value = marketValRaw;
  }
  if (payload.invested_amount <= 0) {
    showToast("Informe o valor aplicado em R$.");
    return;
  }
  await fetch("/api/fixed-income", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  document.getElementById("fi-amount").value = "";
  const mvEl = document.getElementById("fi-market-value");
  if (mvEl) mvEl.value = "";
  closeModal("modal-fixed-income");
  showToast(`${payload.title_name} adicionado.`);
  await refreshAll();
}

function openAdjustFixedIncomeModal(id) {
  const fiList = (window.__CURRENT_DATA && window.__CURRENT_DATA.fixed_income) || [];
  const fi = fiList.find(x => x.id === id);
  if (!fi) return;

  const sub = document.getElementById("fi-adj-title-sub");
  if (sub) sub.textContent = `${fi.title_name} (${fi.issuer})`;

  const idEl = document.getElementById("fi-adj-id");
  const amtEl = document.getElementById("fi-adj-amount");
  const mktEl = document.getElementById("fi-adj-market");
  const startEl = document.getElementById("fi-adj-start");
  const rateEl = document.getElementById("fi-adj-rate");

  if (idEl) idEl.value = fi.id;
  if (amtEl) amtEl.value = fi.invested_amount || "";
  if (mktEl) mktEl.value = fi.market_value || fi.gross_amount || "";
  if (startEl) startEl.value = fi.start_date || "";
  if (rateEl) rateEl.value = fi.rate_value || "";

  openModal("modal-adjust-fi");
}

async function submitAdjustFixedIncome() {
  const fiId = parseInt(document.getElementById("fi-adj-id")?.value || "0", 10);
  if (!fiId) return;

  const amount = parseFloat(document.getElementById("fi-adj-amount")?.value || "0");
  const market = parseFloat(document.getElementById("fi-adj-market")?.value || "0");
  const startDate = document.getElementById("fi-adj-start")?.value || "";
  const rateVal = parseFloat(document.getElementById("fi-adj-rate")?.value || "0");

  const payload = {};
  if (amount > 0) payload.invested_amount = amount;
  if (market > 0) payload.market_value = market;
  if (startDate) payload.start_date = startDate;
  if (rateVal >= 0) payload.rate_value = rateVal;

  try {
    const res = await fetch(`/api/fixed-income/${fiId}/adjust`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "Erro ao ajustar título.", "error");
      return;
    }
    showToast("Título de renda fixa atualizado com sucesso!");
    closeModal("modal-adjust-fi");
    await refreshAll(true);
  } catch (err) {
    showToast("Erro de rede ao salvar alterações.", "error");
  }
}

async function deleteFixedIncome(id, ev) {
  if (ev && ev.stopPropagation) ev.stopPropagation();
  await fetch(`/api/fixed-income/${id}`, { method: "DELETE" });
  showToast("Título removido da carteira.");
  await refreshAll();
}

function openDividendModal() {
  openModal("modal-dividend");
}

async function submitDividend() {
  const payload = {
    ticker: document.getElementById("div-ticker").value.trim().toUpperCase(),
    pay_date: document.getElementById("div-date").value,
    amount_per_share: parseFloat(document.getElementById("div-per-share").value || "0"),
    shares_qty: parseFloat(document.getElementById("div-qty").value || "0"),
  };
  if (!payload.ticker || payload.amount_per_share <= 0 || payload.shares_qty <= 0) {
    showToast("Preencha os dados do provento corretamente.");
    return;
  }
  await fetch("/api/dividends", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  closeModal("modal-dividend");
  showToast("Provento registrado.");
  await refreshAll();
}

async function deleteDividend(id) {
  await fetch(`/api/dividends/${id}`, { method: "DELETE" });
  showToast("Provento removido.");
  await refreshAll();
}

async function openMobileModal() {
  const res = await fetch("/api/system/mobile-access");
  const data = await res.json();
  document.getElementById("mobile-url-box").textContent = data.mobile_url;
  document.getElementById("mobile-qr-img").src = data.qr_api_url;
  openModal("modal-mobile");
}

/* =====================================================================
   Sincronização B3 via Excel (.xlsx) / CSV
   ===================================================================== */
let _b3PendingPayload = null;

async function openB3SyncModal() {
  _b3PendingPayload = null;
  const prevBox = document.getElementById("b3-preview-container");
  if (prevBox) {
    prevBox.innerHTML = "";
    prevBox.classList.add("hidden");
  }
  const btnConfirm = document.getElementById("btn-confirm-b3-sync");
  if (btnConfirm) btnConfirm.disabled = true;

  const titleEl = document.getElementById("b3-drop-title");
  const subEl = document.getElementById("b3-drop-sub");
  if (titleEl) titleEl.textContent = "Arraste sua planilha da B3 (.xlsx ou .csv) aqui ou clique para selecionar";
  if (subEl) subEl.textContent = "Suporta relatórios de Posição Consolidada, Negociação (Compras/Vendas) e Movimentação (Proventos)";

  const fileInput = document.getElementById("b3-file-input");
  if (fileInput) fileInput.value = "";

  openModal("modal-b3-sync");
  hydrateIcons(document.getElementById("modal-b3-sync"));
  await loadB3SyncLogs();
}

function setB3SyncMode(mode) {
  const m = mode === "REPLACE" ? "REPLACE" : "MERGE";
  const input = document.getElementById("b3-sync-mode");
  if (input) input.value = m;
  document.getElementById("b3mode-MERGE")?.classList.toggle("is-active", m === "MERGE");
  document.getElementById("b3mode-REPLACE")?.classList.toggle("is-active", m === "REPLACE");

  const hint = document.getElementById("b3-mode-hint");
  if (hint) {
    hint.textContent = m === "MERGE"
      ? "Reconcilia quantidades com a custódia da B3 e ignora lançamentos ou proventos já registrados."
      : "Atenção: Substitui apenas os ativos das classes custodiadas na B3 (Ações, FIIs, ETFs ou Tesouro) encontradas no arquivo. Ações dos EUA, criptomoedas e reservas manuais são 100% preservadas.";
  }
}

function onB3DragOver(ev) {
  ev.preventDefault();
  ev.stopPropagation();
  document.getElementById("b3-dropzone")?.classList.add("is-dragover");
}

function onB3DragLeave(ev) {
  ev.preventDefault();
  ev.stopPropagation();
  document.getElementById("b3-dropzone")?.classList.remove("is-dragover");
}

function onB3Drop(ev) {
  ev.preventDefault();
  ev.stopPropagation();
  document.getElementById("b3-dropzone")?.classList.remove("is-dragover");
  if (ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files.length > 0) {
    onB3FileSelected(ev.dataTransfer.files);
  }
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = err => reject(err);
    reader.readAsDataURL(file);
  });
}

async function onB3FileSelected(fileList) {
  if (!fileList || fileList.length === 0) return;
  const file = fileList[0];
  const titleEl = document.getElementById("b3-drop-title");
  const subEl = document.getElementById("b3-drop-sub");
  const prevBox = document.getElementById("b3-preview-container");
  const btnConfirm = document.getElementById("btn-confirm-b3-sync");

  if (titleEl) titleEl.textContent = `Lendo arquivo: ${file.name}…`;
  if (subEl) subEl.textContent = "Analisando abas e estrutura da B3…";

  try {
    const b64 = await readFileAsBase64(file);
    const res = await fetch("/api/b3/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        content_base64: b64,
        sync_mode: document.getElementById("b3-sync-mode")?.value || "MERGE",
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Não foi possível interpretar a planilha.");
    }

    _b3PendingPayload = {
      filename: file.name,
      content_base64: b64,
    };

    const preview = data.preview;
    if (titleEl) titleEl.textContent = `Arquivo pronto: ${file.name}`;
    if (subEl) subEl.textContent = `${preview.counts.total_items} registros identificados em ${preview.sheets_detected.length} aba(s) · Clique para trocar arquivo`;

    renderB3Preview(preview);
    if (btnConfirm) {
      btnConfirm.disabled = preview.counts.total_items === 0;
    }
  } catch (err) {
    _b3PendingPayload = null;
    if (btnConfirm) btnConfirm.disabled = true;
    if (titleEl) titleEl.textContent = "Falha ao ler arquivo";
    if (subEl) subEl.textContent = err.message || "Verifique se o arquivo é um .xlsx ou .csv válido da B3.";
    if (prevBox) {
      prevBox.classList.remove("hidden");
      prevBox.innerHTML = `<div class="callout" style="border-color:var(--neg)"><span class="neg">${esc(err.message)}</span></div>`;
    }
  }
}

function renderB3Preview(preview) {
  const prevBox = document.getElementById("b3-preview-container");
  if (!prevBox) return;
  prevBox.classList.remove("hidden");

  const c = preview.counts || {};
  const sheetsBadges = (preview.sheets_detected || [])
    .map(s => `<span class="badge badge-outline">${esc(s.sheet)}: <strong>${Number(s.items) || 0}</strong></span>`)
    .join(" ");

  const hasOnlyPositions = (preview.positions || []).length > 0 && (!preview.transactions || preview.transactions.length === 0);

  // Monta lista resumida dos itens detectados
  const sampleRows = [];
  (preview.positions || []).slice(0, 10).forEach(p => {
    let pmHtml = "";
    if (p.has_existing && p.existing_pm > 0) {
      pmHtml = `<span class="badge badge-outline" title="Preço Médio já existente na carteira (será 100% mantido)">R$ ${Number(p.existing_pm).toFixed(2)} (Mantido)</span>`;
    } else {
      const initVal = p.avg_price > 0 ? p.avg_price : "";
      pmHtml = `<input type="number" step="0.01" min="0.01" class="input input-sm b3-pm-input" data-ticker="${esc(p.ticker)}" value="${initVal}" placeholder="R$ ${Number(p.close_price).toFixed(2)}" style="width:115px;padding:3px 6px;text-align:right" title="Informe seu Preço Médio de compra ou deixe em branco para estimar pelo fechamento" />`;
    }
    sampleRows.push(`
      <tr>
        <td><span class="badge badge-accent">Posição</span></td>
        <td class="strong">${esc(p.ticker)} <span class="xs faint">${esc((p.name || '').slice(0, 20))}</span></td>
        <td class="xs muted">${esc(CLASS_NAMES[p.asset_class] || p.asset_class)}</td>
        <td class="r mono">${Number(p.quantity) || 0}</td>
        <td class="r mono" title="Cotação de fechamento">${fmtMoney(p.close_price, p.currency)}</td>
        <td class="r">${pmHtml}</td>
        <td class="r strong mono">${fmtMoney(p.total_brl)}</td>
      </tr>
    `);
  });
  (preview.transactions || []).slice(0, 8).forEach(t => {
    sampleRows.push(`
      <tr>
        <td><span class="badge ${t.tx_type === 'BUY' ? 'badge-pos' : 'badge-neg'}">${t.tx_type === 'BUY' ? 'Compra' : 'Venda'}</span></td>
        <td class="strong">${esc(t.ticker)} <span class="xs faint">${esc(t.tx_date)}</span></td>
        <td class="xs muted">${esc(t.broker)}</td>
        <td class="r mono">${Number(t.quantity) || 0}</td>
        <td class="r mono">${fmtMoney(t.unit_price, t.currency)}</td>
        <td class="r xs pos font-semibold">Real (Negociação)</td>
        <td class="r strong mono">${fmtMoney(t.total_brl)}</td>
      </tr>
    `);
  });
  (preview.fixed_income || []).slice(0, 5).forEach(f => {
    sampleRows.push(`
      <tr>
        <td><span class="badge badge-gold">${f.asset_class === 'TESOURO' ? 'Tesouro' : 'Renda Fixa'}</span></td>
        <td class="strong">${esc((f.title_name || '').slice(0, 26))}</td>
        <td class="xs muted">${esc(f.indexer)} (${Number(f.rate_value) || 0}%)</td>
        <td class="r mono">1</td>
        <td class="r mono">${fmtMoney(f.market_value || f.invested_amount)}</td>
        <td class="r mono">${fmtMoney(f.invested_amount)}</td>
        <td class="r strong mono">${fmtMoney(f.market_value || f.invested_amount)}</td>
      </tr>
    `);
  });
  (preview.dividends || []).slice(0, 5).forEach(d => {
    sampleRows.push(`
      <tr>
        <td><span class="badge badge-pos">${esc(d.div_type)}</span></td>
        <td class="strong">${esc(d.ticker)} <span class="xs faint">${esc(d.pay_date)}</span></td>
        <td class="xs muted">Provento B3</td>
        <td class="r mono">${Number(d.shares_qty) || 0}</td>
        <td class="r mono">${fmtMoney(d.amount_per_share)}</td>
        <td class="r mono">—</td>
        <td class="r strong pos mono">+${fmtMoney(d.total_amount)}</td>
      </tr>
    `);
  });

  const soldList = preview.sold_positions || [];
  soldList.forEach(s => {
    sampleRows.push(`
      <tr style="opacity:0.88;background:color-mix(in srgb, var(--neg) 4%, transparent)">
        <td><span class="badge badge-neg">Zerar Venda</span></td>
        <td class="strong">${esc(s.ticker)} <span class="xs faint">${esc((s.name || '').slice(0, 20))}</span></td>
        <td class="xs muted">Não consta mais na B3</td>
        <td class="r mono font-semibold" style="color:var(--neg)">-${Number(s.quantity) || 0}</td>
        <td class="r mono">—</td>
        <td class="r xs neg font-semibold">Posição será zerada</td>
        <td class="r strong mono">R$ 0,00</td>
      </tr>
    `);
  });

  const soldPositionsHtml = soldList.length > 0 ? `
    <div class="callout" style="border-color:color-mix(in srgb, var(--neg) 40%, var(--border));background:color-mix(in srgb, var(--neg) 6%, var(--surface))">
      <div class="row gap-2 align-start">
        <span data-icon="alert-circle" data-size="16" style="color:var(--neg);margin-top:2px"></span>
        <div class="stack" style="gap:3px">
          <div class="xs strong" style="color:var(--neg)">Ativos Vendidos Detectados (${soldList.length})</div>
          <div class="xs muted">
            Os seguintes ativos constam na sua carteira do SIM mas <strong>não constam mais nesta planilha de custódia da B3</strong>.
            No modo <strong>MERGE</strong>, a posição deles será <strong>automaticamente zerada</strong> para refletir a venda na B3:
          </div>
          <div class="row gap-2 wrap" style="margin-top:4px">
            ${soldList.map(s => `
              <span class="badge badge-neg">
                <strong>${esc(s.ticker)}</strong> (${s.quantity} ${s.quantity === 1 ? 'cota zerada' : 'cotas zeradas'})
              </span>
            `).join(" ")}
          </div>
        </div>
      </div>
    </div>
  ` : "";

  const positionWarningHtml = hasOnlyPositions ? `
    <div class="callout" style="border-color:color-mix(in srgb, var(--accent) 40%, var(--border));background:color-mix(in srgb, var(--accent) 6%, var(--surface))">
      <div class="row gap-2 align-start">
        <span data-icon="info" data-size="16" style="color:var(--accent);margin-top:2px"></span>
        <div class="stack" style="gap:3px">
          <div class="xs strong" style="color:var(--accent)">Relatório de Posição B3 (Apenas Cotação de Fechamento)</div>
          <div class="xs muted">
            A B3 informa a quantidade e a cotação de fechamento do dia (sem histórico de compras).
            <br/>• <strong>Ativos já cadastrados:</strong> o SIM <strong>manterá o seu Preço Médio original</strong> intacto e apenas ajustará a quantidade.
            <br/>• <strong>Novos ativos:</strong> você pode digitar o seu Preço Médio de compra na coluna abaixo antes de sincronizar.
            <br/>• <strong>Dica de ouro:</strong> Para ter Preço Médio e lucro 100% exatos com o histórico completo de compras, importe o <strong>Relatório de Negociação</strong> na Área do Investidor B3 (<em>Extratos → Negociação</em>).
          </div>
        </div>
      </div>
    </div>
  ` : "";

  prevBox.innerHTML = `
    <div class="b3-preview-card stack" style="gap:12px">
      <div class="row between wrap gap-2">
        <div>
          <div class="xs eyebrow" style="color:var(--accent)">Pré-visualização da planilha B3</div>
          <div class="strong" style="margin-top:2px">${c.total_items || 0} registros prontos para sincronizar</div>
        </div>
        <div class="row gap-2 wrap">${sheetsBadges}</div>
      </div>

      ${soldPositionsHtml}
      ${positionWarningHtml}

      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:10px">
        <div class="card card-pad" style="padding:10px 12px;background:var(--surface)">
          <div class="xs faint">Posições Custódia</div>
          <div class="strong" style="font-size:16px">${c.positions || 0}</div>
        </div>
        ${soldList.length > 0 ? `
          <div class="card card-pad" style="padding:10px 12px;background:var(--surface)">
            <div class="xs faint">Vendidos a Zerar</div>
            <div class="strong neg" style="font-size:16px">${soldList.length}</div>
          </div>
        ` : ""}
        <div class="card card-pad" style="padding:10px 12px;background:var(--surface)">
          <div class="xs faint">Negociações (C/V)</div>
          <div class="strong" style="font-size:16px">${c.transactions || 0}</div>
        </div>
        <div class="card card-pad" style="padding:10px 12px;background:var(--surface)">
          <div class="xs faint">Tesouro &amp; R. Fixa</div>
          <div class="strong" style="font-size:16px">${c.fixed_income || 0}</div>
        </div>
        <div class="card card-pad" style="padding:10px 12px;background:var(--surface)">
          <div class="xs faint">Proventos</div>
          <div class="strong pos" style="font-size:16px">${c.dividends || 0}</div>
        </div>
        <div class="card card-pad" style="padding:10px 12px;background:var(--surface)">
          <div class="xs faint">Volume Identificado</div>
          <div class="strong accent" style="font-size:15px">${fmtMoney(preview.estimated_value_brl || 0)}</div>
        </div>
      </div>

      ${sampleRows.length > 0 ? `
        <div class="table-wrap" style="max-height:240px;overflow-y:auto;border:1px solid var(--border);border-radius:10px">
          <table class="table">
            <thead>
              <tr>
                <th>Tipo</th><th>Ativo / Título</th><th>Detalhe</th>
                <th class="r">Qtd</th><th class="r">Fechamento</th><th class="r">Preço Médio</th><th class="r">Total</th>
              </tr>
            </thead>
            <tbody>${sampleRows.join("")}</tbody>
          </table>
        </div>
      ` : ""}
    </div>
  `;
  lucide.createIcons();
}

async function confirmB3Sync() {
  if (!_b3PendingPayload) return;
  const btn = document.getElementById("btn-confirm-b3-sync");
  const prevHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Sincronizando carteira…";
  }

  try {
    const syncMode = document.getElementById("b3-sync-mode")?.value || "MERGE";

    // Coleta preços médios personalizados preenchidos pelo usuário no preview
    const customPms = {};
    document.querySelectorAll(".b3-pm-input").forEach(inp => {
      const val = parseFloat(inp.value);
      const tick = inp.getAttribute("data-ticker");
      if (tick && !isNaN(val) && val > 0) {
        customPms[tick] = val;
      }
    });

    const res = await fetch("/api/b3/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: _b3PendingPayload.filename,
        content_base64: _b3PendingPayload.content_base64,
        sync_mode: syncMode,
        positions_avg_prices: customPms,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Falha ao sincronizar.");
    }

    showToast(data.summary || "Sincronização B3 concluída com sucesso!");
    closeModal("modal-b3-sync");
    await refreshAll();
  } catch (err) {
    showToast(err.message || "Erro na sincronização B3.");
    if (btn) btn.disabled = false;
  } finally {
    if (btn) btn.innerHTML = prevHtml;
  }
}

async function loadB3SyncLogs() {
  const listEl = document.getElementById("b3-logs-list");
  if (!listEl) return;
  try {
    const res = await fetch("/api/b3/logs");
    if (!res.ok) return;
    const data = await res.json();
    const logs = data.logs || [];
    if (logs.length === 0) {
      listEl.innerHTML = `<div class="xs faint">Nenhuma sincronização B3 realizada ainda.</div>`;
      return;
    }
    listEl.innerHTML = logs.slice(0, 4).map(l => `
      <div class="b3-log-item">
        <div>
          <div class="xs strong">${esc(l.filename)} <span class="badge badge-outline" style="margin-left:6px">${esc(l.sync_mode)}</span></div>
          <div class="xs faint" style="margin-top:2px">${esc(l.summary_text)}</div>
        </div>
        <div class="xs mono faint">${esc(l.synced_at)}</div>
      </div>
    `).join("");
  } catch (e) {}
}

/* =====================================================================
   Radar IA de Oportunidades & Configurações da IA
   ===================================================================== */
let _currentRadarData = null;

async function loadAiRadarView(force = false) {
  const btnScan = document.getElementById("btn-scan-radar");
  const prevHtml = btnScan ? btnScan.innerHTML : "";
  if (force && btnScan) {
    btnScan.disabled = true;
    btnScan.textContent = "Escaneando B3 & CVM…";
  }

  try {
    const res = await fetch(`/api/ai/radar?force=${force ? "true" : "false"}`);
    if (!res.ok) throw new Error("Não foi possível carregar o Radar IA.");
    const data = await res.json();
    _currentRadarData = data;
    renderAiRadarView(data);
  } catch (err) {
    console.error("Erro ao carregar Radar IA:", err);
    showToast(err.message || "Erro ao consultar IA.");
  } finally {
    if (force && btnScan) {
      btnScan.disabled = false;
      btnScan.innerHTML = prevHtml;
      hydrateIcons(btnScan);
    }
  }
}

function renderAiRadarView(data) {
  if (!data) return;
  const badgeEl = document.getElementById("ai-radar-badge");
  const subEl = document.getElementById("ai-radar-engine-sub");
  const execEl = document.getElementById("ai-radar-executive-text");
  const kpisEl = document.getElementById("ai-radar-daily-kpis");
  const actionsEl = document.getElementById("ai-radar-actions-list");
  const alertsEl = document.getElementById("ai-radar-portfolio-alerts");
  const alertsCount = document.getElementById("ai-radar-alerts-count");
  const oppsGrid = document.getElementById("ai-radar-opportunities-grid");

  const errBox = document.getElementById("ai-radar-error-box");
  if (data.ai_error) {
    if (badgeEl) {
      badgeEl.textContent = "IA COM FALHA (NATIVO ATIVO)";
      badgeEl.className = "badge badge-neg";
    }
    if (errBox) {
      errBox.innerHTML = `
        <div style="background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.35);border-radius:8px;padding:12px 14px;display:flex;gap:10px;align-items:flex-start">
          <span style="font-size:16px;line-height:1">⚠️</span>
          <div style="flex:1">
            <div style="font-weight:600;font-size:13px;color:var(--text-primary)">Falha na Conexão com o Provedor de IA</div>
            <div class="xs" style="color:var(--danger);margin-top:2px;font-family:monospace">${esc(data.ai_error)}</div>
            <div class="xs faint" style="margin-top:4px">O SIM alternou automaticamente para o motor analítico quantitativo nativo. Verifique se sua chave de API, saldo ou limite de cota estão corretos nas Configurações.</div>
          </div>
        </div>
      `;
      errBox.classList.remove("hidden");
    }
  } else {
    if (badgeEl) {
      badgeEl.textContent = data.ai_generated ? "LLM ATIVA" : "QUANTITATIVO CNPI";
      badgeEl.className = `badge ${data.ai_generated ? "badge-pos" : "badge-outline"}`;
    }
    if (errBox) {
      errBox.innerHTML = "";
      errBox.classList.add("hidden");
    }
  }
  if (subEl) {
    subEl.textContent = `Gerado às ${data.generated_at} via ${data.ai_provider_used} · Perfil: ${data.investor_profile}`;
  }
  if (execEl) {
    execEl.textContent = data.executive_briefing || "Nenhum parecer disponível.";
  }

  const evo = data.daily_evolution || {};
  const dayPos = (evo.day_change_brl || 0) >= 0;
  if (kpisEl) {
    kpisEl.innerHTML = `
      <div class="card card-pad" style="padding:14px;background:var(--surface)">
        <div class="stat-label">Patrimônio Consolidado</div>
        <div class="stat-value">${fmtMoney(evo.total_patrimony_brl || 0)}</div>
        <div class="xs faint" style="margin-top:2px">${evo.positions_count || 0} ativos em custódia</div>
      </div>
      <div class="card card-pad" style="padding:14px;background:var(--surface)">
        <div class="stat-label">Desempenho no Dia</div>
        <div class="stat-value ${dayPos ? "pos" : "neg"}">${fmtPct(evo.day_change_pct || 0)} (${fmtMoney(evo.day_change_brl || 0)})</div>
        <div class="xs faint" style="margin-top:2px">Variação acumulada no pregão</div>
      </div>
      <div class="card card-pad" style="padding:14px;background:var(--surface)">
        <div class="stat-label">Renda Passiva Estimada</div>
        <div class="stat-value accent">${fmtMoney(evo.estimated_monthly_divs_brl || 0)}<span class="xs faint"> /mês</span></div>
        <div class="xs faint" style="margin-top:2px">Proventos projetados</div>
      </div>
      <div class="card card-pad" style="padding:14px;background:var(--surface)">
        <div class="stat-label">Maior Alta / Baixa Hoje</div>
        <div class="row between" style="margin-top:4px">
          <span class="xs strong pos">${evo.top_gainer ? `${evo.top_gainer.ticker} ${fmtPct(evo.top_gainer.change_pct)}` : "—"}</span>
          <span class="xs strong neg">${evo.top_loser ? `${evo.top_loser.ticker} ${fmtPct(evo.top_loser.change_pct)}` : "—"}</span>
        </div>
        <div class="xs faint" style="margin-top:4px">Destaques da carteira</div>
      </div>
    `;
  }

  if (actionsEl) {
    const acts = data.action_recommendations || [];
    actionsEl.innerHTML = acts.map((act, idx) => `
      <div class="row gap-2" style="align-items:flex-start">
        <span class="rank-num" style="width:20px;height:20px;font-size:11px">#${idx + 1}</span>
        <span class="xs" style="line-height:1.5">${esc(act)}</span>
      </div>
    `).join("");
  }

  const alerts = data.portfolio_alerts || [];
  if (alertsCount) alertsCount.textContent = `${alerts.length} alertas`;
  if (alertsEl) {
    if (alerts.length === 0) {
      alertsEl.innerHTML = `<div class="empty-sm">Nenhum evento de risco ou oscilação atípica na carteira no momento.</div>`;
    } else {
      alertsEl.innerHTML = alerts.map(a => `
        <div class="callout" style="border-color:${a.severity === 'OPORTUNIDADE_CARTEIRA' ? 'var(--accent)' : 'var(--gold)'}">
          <div class="row between wrap gap-2" style="width:100%">
            <div class="row gap-2">
              <span class="badge ${a.severity === 'OPORTUNIDADE_CARTEIRA' ? 'badge-pos' : 'badge-gold'}">${esc(a.badge)}</span>
              <strong class="strong cursor-pointer" onclick="openAssetDetail('${esc(a.ticker)}')">${esc(a.ticker)}</strong>
            </div>
            <button class="btn btn-sm btn-ghost" onclick="openAssetDetail('${esc(a.ticker)}')">Ver Raio-X ${ic("arrow-right", 12)}</button>
          </div>
          <div class="xs strong" style="margin-top:6px">${esc(a.title)}</div>
          <div class="xs faint" style="margin-top:2px">${esc(a.detail)}</div>
        </div>
      `).join("");
    }
  }

  const opps = data.opportunities || [];
  if (oppsGrid) {
    if (opps.length === 0) {
      oppsGrid.innerHTML = `<div class="card empty-sm" style="grid-column:1/-1">Nenhuma assimetria atendeu aos filtros estritos no momento.</div>`;
    } else {
      oppsGrid.innerHTML = opps.map(o => {
        const inPort = o.in_portfolio ? `<span class="badge badge-accent">Na sua carteira</span>` : "";
        const reasonsHtml = (o.reasons || []).map(r => `<li>${esc(r)}</li>`).join("");
        return `
          <div class="card card-pad stack" style="gap:12px;position:relative">
            <div class="row between wrap gap-2">
              <div class="row gap-2">
                ${classAvatar(o.asset_class, o.ticker)}
                <div>
                  <div class="row gap-2">
                    <span class="strong cursor-pointer" style="font-size:16px" onclick="openAssetDetail('${esc(o.ticker)}')">${esc(o.ticker)}</span>
                    ${inPort}
                  </div>
                  <div class="xs faint truncate" style="max-width:180px">${esc(o.name)}</div>
                </div>
              </div>
              <div style="text-align:right">
                <div class="badge badge-pos" style="font-size:12px;font-weight:700">Score ${Number(o.score || 0)}/100</div>
                <div class="xs faint" style="margin-top:2px">${esc(o.opportunity_tag)}</div>
              </div>
            </div>

            <!-- Métricas resumidas -->
            <div class="grid" style="grid-template-columns:repeat(4,1fr);gap:8px;background:var(--surface-2);padding:10px;border-radius:10px;text-align:center">
              <div>
                <div class="xs faint">Cotação</div>
                <div class="xs strong mono">${fmtMoney(o.last_price, o.currency)}</div>
              </div>
              <div>
                <div class="xs faint">DY 12M</div>
                <div class="xs strong pos mono">${Number(o.dy_12m || 0).toFixed(1)}%</div>
              </div>
              <div>
                <div class="xs faint">${o.asset_class === 'FII' ? 'P/VP' : 'P/L'}</div>
                <div class="xs strong mono">${o.asset_class === 'FII' ? (Number(o.pvp || 1).toFixed(2) + 'x') : (o.pl > 0 ? Number(o.pl).toFixed(1) + 'x' : 'N/A')}</div>
              </div>
              <div>
                <div class="xs faint">Hoje</div>
                <div class="xs strong mono ${o.change_pct >= 0 ? 'pos' : 'neg'}">${fmtPct(o.change_pct)}</div>
              </div>
            </div>

            <!-- Motivos quantitativos -->
            <div class="xs" style="background:var(--bg-elev);padding:10px 12px;border-radius:8px">
              <div class="xs eyebrow" style="color:var(--accent);margin-bottom:4px">Por que é oportunidade agora:</div>
              <ul style="margin:0;padding-left:16px;line-height:1.45" class="faint">${reasonsHtml}</ul>
            </div>

            ${o.latest_report ? `
              <div class="xs faint">
                <strong class="muted">Relatório Oficial:</strong> ${esc(o.latest_report)}
              </div>
            ` : ""}
            ${o.latest_news ? `
              <div class="xs faint truncate">
                <strong class="muted">Notícia:</strong> ${esc(o.latest_news)}
              </div>
            ` : ""}

            <div class="row gap-2 between" style="margin-top:auto;padding-top:6px">
              <button class="btn btn-sm btn-ghost" onclick="openAssetDetail('${esc(o.ticker)}')">
                <span>Raio-X Completo</span> ${ic("arrow-right", 12)}
              </button>
              <button class="btn btn-sm btn-primary" onclick="openTransactionModal('${esc(o.ticker)}', '${esc(o.asset_class)}', '${o.last_price}')">
                ${ic("plus", 13)}<span>Lançar Aporte</span>
              </button>
            </div>
          </div>
        `;
      }).join("");
    }
  }

  hydrateIcons(document.getElementById("view-AI_RADAR"));
}

/* ---------- Modal de Configurações de IA & WhatsApp ---------- */
async function openAiSettingsModal() {
  try {
    const res = await fetch("/api/settings");
    if (res.ok) {
      const data = await res.json();
      const provEl = document.getElementById("ai-setting-provider");
      const modEl = document.getElementById("ai-setting-model");
      const keyEl = document.getElementById("ai-setting-apikey");
      const profEl = document.getElementById("ai-setting-profile");
      const dyEl = document.getElementById("ai-setting-mindy");
      const keyStatus = document.getElementById("ai-key-status");

      // WhatsApp fields
      const waEnabled = document.getElementById("wa-setting-enabled");
      const waProv = document.getElementById("wa-setting-provider");
      const waPhone = document.getElementById("wa-setting-phone");
      const waKey = document.getElementById("wa-setting-apikey");
      const waUrl = document.getElementById("wa-setting-url");
      const waInst = document.getElementById("wa-setting-instance");
      const waTime = document.getElementById("wa-setting-time");
      const waKeyStatus = document.getElementById("wa-key-status");
      const waLastSent = document.getElementById("wa-last-sent-hint");

      if (provEl) provEl.value = data.ai_provider || "GEMINI";
      if (modEl) modEl.value = data.ai_model || "gemini-2.5-flash";
      if (keyEl) keyEl.value = "";
      if (profEl) profEl.value = data.investor_profile || "RENDA_E_VALOR";
      if (dyEl) dyEl.value = data.min_dy_target || 8.0;

      if (keyStatus) {
        keyStatus.innerHTML = data.ai_api_key_configured
          ? `<span class="pos">Chave salva ativa: ${data.ai_api_key_masked}</span>`
          : `<span class="gold">Nenhuma chave salva no momento.</span>`;
      }

      if (waEnabled) waEnabled.checked = Boolean(data.whatsapp_enabled);
      if (waProv) waProv.value = data.whatsapp_provider || "CALLMEBOT";
      if (waPhone) waPhone.value = data.whatsapp_phone || "";
      if (waKey) waKey.value = "";
      if (waUrl) waUrl.value = data.whatsapp_instance_url || "";
      if (waInst) waInst.value = data.whatsapp_instance_id || "";
      if (waTime) waTime.value = data.whatsapp_daily_time || "18:30";

      if (waKeyStatus) {
        waKeyStatus.innerHTML = data.whatsapp_apikey_configured
          ? `<span class="pos">Chave WhatsApp ativa: ${data.whatsapp_apikey_masked}</span>`
          : `<span class="gold">Nenhuma chave de WhatsApp salva.</span>`;
      }
      if (waLastSent) {
        waLastSent.textContent = data.whatsapp_last_daily_sent
          ? `Último envio diário: ${data.whatsapp_last_daily_sent}`
          : "Nenhum relatório diário disparado ainda.";
      }

      const waSchedStatus = document.getElementById("wa-scheduler-status-hint");
      if (waSchedStatus) {
        if (data.whatsapp_scheduler_status && data.whatsapp_scheduler_status.status_text) {
          waSchedStatus.innerHTML = `<span class="pos strong">● Agendador:</span> ${data.whatsapp_scheduler_status.status_text}`;
        } else {
          waSchedStatus.textContent = "Disparo automático em dias úteis a partir deste horário (pula fins de semana e feriados B3).";
        }
      }

      onAiProviderChanged();
      onWhatsAppProviderChanged();
    }
  } catch (e) {}

  document.getElementById("ai-test-feedback").textContent = "";
  document.getElementById("wa-test-feedback").textContent = "";
  openModal("modal-ai-settings");
}

function onWhatsAppProviderChanged() {
  const prov = document.getElementById("wa-setting-provider")?.value || "CALLMEBOT";
  const urlField = document.getElementById("wa-field-url");
  const instField = document.getElementById("wa-field-instance");
  const callmebotInst = document.getElementById("wa-callmebot-instructions");

  if (urlField) urlField.classList.toggle("hidden", prov === "CALLMEBOT");
  if (instField) instField.classList.toggle("hidden", prov !== "EVOLUTION");
  if (callmebotInst) callmebotInst.classList.toggle("hidden", prov !== "CALLMEBOT");
}

function toggleWaKeyVisibility() {
  const input = document.getElementById("wa-setting-apikey");
  if (!input) return;
  input.type = input.type === "password" ? "text" : "password";
}

async function testWhatsAppMessage() {
  const btn = document.getElementById("btn-test-wa");
  const fb = document.getElementById("wa-test-feedback");
  const phone = document.getElementById("wa-setting-phone")?.value.trim() || "";

  if (!phone) {
    if (fb) fb.innerHTML = "<span class='neg'>Informe seu número com DDD no campo acima antes de testar.</span>";
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = "Enviando…";
  }
  if (fb) fb.innerHTML = "<span class='faint'>Disparando mensagem de teste no WhatsApp…</span>";

  try {
    const res = await fetch("/api/whatsapp/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha ao enviar mensagem.");
    if (fb) {
      fb.innerHTML = `
        <span class="pos strong">Mensagem de teste enviada com sucesso para ${data.phone}!</span><br/>
        <span class="xs faint">Verifique o seu WhatsApp.</span>
      `;
    }
  } catch (err) {
    if (fb) fb.innerHTML = `<span class="neg strong">Erro no envio: ${err.message}</span>`;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span data-icon="send" data-size="13"></span><span>Enviar Teste</span>`;
      hydrateIcons(btn);
    }
  }
}

async function dispatchDailyWhatsAppNow(force = false) {
  const btn = document.getElementById("btn-dispatch-wa");
  const fb = document.getElementById("wa-test-feedback");

  if (btn) {
    btn.disabled = true;
    btn.textContent = "Gerando & enviando…";
  }
  if (fb) fb.innerHTML = "<span class='faint'>Processando relatório executivo da carteira para envio no WhatsApp…</span>";

  try {
    const url = force ? "/api/whatsapp/dispatch-daily?force=true" : "/api/whatsapp/dispatch-daily";
    const res = await fetch(url, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha ao disparar relatório diário.");

    if (data.status === "skipped") {
      if (fb) {
        fb.innerHTML = `
          <div style="background:rgba(234,179,8,0.1);border:1px solid rgba(234,179,8,0.3);padding:8px 10px;border-radius:6px;margin-top:6px;line-height:1.4">
            <span class="gold strong">ℹ️ Envio pulado:</span> ${data.detail}<br/>
            <button type="button" class="btn btn-secondary xs" style="margin-top:6px" onclick="dispatchDailyWhatsAppNow(true)">
              <span data-icon="send" data-size="11"></span><span>Forçar Envio Mesmo Assim</span>
            </button>
          </div>
        `;
        hydrateIcons(fb);
      }
      return;
    }

    if (fb) {
      fb.innerHTML = `
        <span class="pos strong">Relatório diário enviado com sucesso para ${data.phone}!</span><br/>
        <span class="xs faint">Disparo registrado às ${data.sent_at}.</span>
      `;
    }
    const lastSentHint = document.getElementById("wa-last-sent-hint");
    if (lastSentHint) lastSentHint.textContent = `Último envio diário: ${data.sent_at}`;
    showToast("Relatório diário enviado no WhatsApp!");
  } catch (err) {
    if (fb) fb.innerHTML = `<span class="neg strong">Erro no disparo: ${err.message}</span>`;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span data-icon="message-circle" data-size="13"></span><span>Enviar Relatório Agora</span>`;
      hydrateIcons(btn);
    }
  }
}

async function saveAiSettings() {
  const prov = document.getElementById("ai-setting-provider")?.value || "GEMINI";
  const model = document.getElementById("ai-setting-model")?.value.trim() || "gemini-2.5-flash";
  const key = document.getElementById("ai-setting-apikey")?.value.trim() || "";
  const prof = document.getElementById("ai-setting-profile")?.value || "RENDA_E_VALOR";
  const minDy = parseFloat(document.getElementById("ai-setting-mindy")?.value || "8.0");

  // WhatsApp
  const waEnabled = document.getElementById("wa-setting-enabled")?.checked || false;
  const waProv = document.getElementById("wa-setting-provider")?.value || "CALLMEBOT";
  const waPhone = document.getElementById("wa-setting-phone")?.value.trim() || "";
  const waKey = document.getElementById("wa-setting-apikey")?.value.trim() || "";
  const waUrl = document.getElementById("wa-setting-url")?.value.trim() || "";
  const waInst = document.getElementById("wa-setting-instance")?.value.trim() || "";
  const waTime = document.getElementById("wa-setting-time")?.value || "18:30";

  const payload = {
    ai_provider: prov,
    ai_model: model,
    investor_profile: prof,
    min_dy_target: minDy,
    whatsapp_enabled: waEnabled,
    whatsapp_provider: waProv,
    whatsapp_phone: waPhone,
    whatsapp_instance_url: waUrl,
    whatsapp_instance_id: waInst,
    whatsapp_daily_time: waTime,
  };
  if (key) payload.ai_api_key = key;
  if (waKey) payload.whatsapp_apikey = waKey;

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Erro ao salvar configurações.");
    showToast("Configurações salvas com sucesso!");
    closeModal("modal-ai-settings");
    if (STATE.currentTab === "AI_RADAR") {
      loadAiRadarView(true);
    }
  } catch (err) {
    showToast(err.message || "Erro ao salvar.");
  }
}

/* =====================================================================
   Módulo de Autenticação, Usuários & Segurança por PIN
   ===================================================================== */
let _authMode = "LOGIN"; // 'LOGIN' | 'SETUP' | 'REGISTER'
let _authCurrentPin = "";
let _availableUsers = [];

function toggleUserMenu(ev) {
  if (ev) ev.stopPropagation();
  const menu = document.getElementById("user-dropdown-menu");
  if (menu) menu.classList.toggle("hidden");
}

window.addEventListener("click", () => {
  const menu = document.getElementById("user-dropdown-menu");
  if (menu && !menu.classList.contains("hidden")) {
    menu.classList.add("hidden");
  }
});

function setCurrentUser(user) {
  STATE.currentUser = user;
  const nameEl = document.getElementById("topbar-username");
  const infoEl = document.getElementById("user-dropdown-info");
  if (nameEl) nameEl.textContent = user.username || "Lucas";
  if (infoEl) infoEl.textContent = `Conectado como ${user.username || "Lucas"}`;
}

async function checkAuthStatus() {
  try {
    const res = await fetch("/api/auth/status");
    const data = await res.json();
    if (data.setup_required) {
      openAuthModal("SETUP");
      return false;
    }
    if (!data.authenticated) {
      openAuthModal("LOGIN");
      return false;
    }
    setCurrentUser(data.current_user);
    return true;
  } catch (err) {
    console.error("Erro ao verificar autenticação:", err);
    return false;
  }
}

async function loadAuthUsersList() {
  try {
    const res = await fetch("/api/auth/users");
    if (!res.ok) return [];
    const data = await res.json();
    _availableUsers = data.users || [];
    const select = document.getElementById("auth-user-select");
    if (select) {
      select.innerHTML = _availableUsers.map(u => `<option value="${esc(u.username)}">${esc(u.username)}</option>`).join("");
      if (STATE.currentUser) {
        select.value = STATE.currentUser.username;
      }
    }
    return _availableUsers;
  } catch (e) {
    return [];
  }
}

async function openAuthModal(mode = "LOGIN", prefillUser = "") {
  _authMode = mode;
  _authCurrentPin = "";
  updatePinDots();

  const titleEl = document.getElementById("auth-modal-title");
  const subEl = document.getElementById("auth-modal-sub");
  const userField = document.getElementById("auth-user-field");
  const userInputField = document.getElementById("auth-username-input-field");
  const userInput = document.getElementById("auth-username-input");
  const confirmField = document.getElementById("auth-pin-confirm-field");
  const confirmInput = document.getElementById("auth-pin-confirm-input");
  const submitBtnLabel = document.getElementById("btn-auth-submit-label");
  const toggleBtn = document.getElementById("btn-auth-toggle-mode");
  const errFb = document.getElementById("auth-error-feedback");

  if (errFb) errFb.textContent = "";
  if (confirmInput) confirmInput.value = "";

  if (mode === "SETUP") {
    if (titleEl) titleEl.textContent = "Definir PIN de Acesso";
    if (subEl) subEl.textContent = "Crie seu PIN de 4 a 6 dígitos para proteger sua carteira na rede";
    if (userField) userField.classList.add("hidden");
    if (userInputField) userInputField.classList.remove("hidden");
    if (userInput) userInput.value = prefillUser || "Lucas";
    if (confirmField) confirmField.classList.remove("hidden");
    if (submitBtnLabel) submitBtnLabel.textContent = "Criar PIN & Entrar";
    if (toggleBtn) toggleBtn.classList.add("hidden");
  } else if (mode === "REGISTER") {
    if (titleEl) titleEl.textContent = "Nova Conta de Amigo";
    if (subEl) subEl.textContent = "Crie uma conta individual com carteira e configurações separadas";
    if (userField) userField.classList.add("hidden");
    if (userInputField) userInputField.classList.remove("hidden");
    if (userInput) userInput.value = prefillUser || "";
    if (confirmField) confirmField.classList.remove("hidden");
    if (submitBtnLabel) submitBtnLabel.textContent = "Criar Conta";
    if (toggleBtn) {
      toggleBtn.classList.remove("hidden");
      toggleBtn.textContent = "← Já tenho conta (Fazer Login)";
    }
  } else {
    // LOGIN
    _authMode = "LOGIN";
    if (titleEl) titleEl.textContent = "Desbloquear Carteira";
    if (subEl) subEl.textContent = "Digite seu PIN pessoal de segurança";
    if (userInputField) userInputField.classList.add("hidden");
    if (confirmField) confirmField.classList.add("hidden");
    if (submitBtnLabel) submitBtnLabel.textContent = "Desbloquear";
    if (toggleBtn) {
      toggleBtn.classList.remove("hidden");
      toggleBtn.textContent = "Criar nova conta de amigo";
    }
    await loadAuthUsersList();
    if (userField) userField.classList.toggle("hidden", _availableUsers.length <= 1);
  }

  openModal("modal-auth");
}

function toggleAuthMode() {
  if (_authMode === "LOGIN") {
    openAuthModal("REGISTER");
  } else {
    openAuthModal("LOGIN");
  }
}

function onAuthUserChanged() {
  _authCurrentPin = "";
  updatePinDots();
  const errFb = document.getElementById("auth-error-feedback");
  if (errFb) errFb.textContent = "";
}

function updatePinDots() {
  const container = document.getElementById("pin-dots-container");
  if (!container) return;
  const dots = container.querySelectorAll(".pin-dot");
  dots.forEach((d, idx) => {
    d.classList.toggle("filled", idx < _authCurrentPin.length);
  });
}

function pressPinDigit(digit) {
  if (_authCurrentPin.length >= 6) return;
  _authCurrentPin += String(digit);
  updatePinDots();
  const errFb = document.getElementById("auth-error-feedback");
  if (errFb) errFb.textContent = "";
}

function backspacePinDigit() {
  if (_authCurrentPin.length > 0) {
    _authCurrentPin = _authCurrentPin.slice(0, -1);
    updatePinDots();
  }
}

function clearPinInput() {
  _authCurrentPin = "";
  updatePinDots();
}

// Suporte a digitação direta pelo teclado físico no modal de autenticação
window.addEventListener("keydown", (ev) => {
  const authModal = document.getElementById("modal-auth");
  if (!authModal || !authModal.classList.contains("is-open")) return;

  // Ignorar se o foco estiver em um input de texto normal (como nome ou confirmação)
  if (ev.target && (ev.target.id === "auth-username-input" || ev.target.id === "auth-pin-confirm-input")) {
    if (ev.key === "Enter") submitAuthModal();
    return;
  }

  if (ev.key >= "0" && ev.key <= "9") {
    pressPinDigit(ev.key);
    ev.preventDefault();
  } else if (ev.key === "Backspace") {
    backspacePinDigit();
    ev.preventDefault();
  } else if (ev.key === "Enter") {
    submitAuthModal();
    ev.preventDefault();
  }
});

async function submitAuthModal() {
  const errFb = document.getElementById("auth-error-feedback");
  if (errFb) errFb.textContent = "";

  if (_authCurrentPin.length < 4) {
    if (errFb) errFb.textContent = "O PIN deve ter no mínimo 4 dígitos.";
    return;
  }

  const confirmInput = document.getElementById("auth-pin-confirm-input");
  if ((_authMode === "SETUP" || _authMode === "REGISTER")) {
    const confVal = confirmInput?.value.trim() || "";
    if (confVal !== _authCurrentPin) {
      if (errFb) errFb.textContent = "Os PINs informados não coincidem.";
      return;
    }
  }

  const btn = document.getElementById("btn-auth-submit");
  if (btn) btn.disabled = true;

  try {
    let endpoint = "/api/auth/login";
    let body = {};

    if (_authMode === "SETUP") {
      endpoint = "/api/auth/setup";
      const uName = document.getElementById("auth-username-input")?.value.trim() || "Lucas";
      body = { username: uName, pin: _authCurrentPin };
    } else if (_authMode === "REGISTER") {
      endpoint = "/api/auth/register";
      const uName = document.getElementById("auth-username-input")?.value.trim() || "";
      if (!uName) {
        if (errFb) errFb.textContent = "Informe um nome para o novo titular.";
        if (btn) btn.disabled = false;
        return;
      }
      body = { username: uName, pin: _authCurrentPin };
    } else {
      const select = document.getElementById("auth-user-select");
      const uName = select?.value || "Lucas";
      body = { username: uName, pin: _authCurrentPin };
    }

    const res = await _nativeFetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Falha na autenticação.");
    }

    localStorage.setItem("sim_auth_token", data.token);
    setCurrentUser(data.user);
    closeModal("modal-auth");
    showToast(`Bem-vindo, ${data.user.username}!`);
    await syncFavoritesFromServer();
    await refreshAll();
  } catch (err) {
    if (errFb) errFb.textContent = err.message || "Erro ao autenticar.";
    clearPinInput();
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function logoutCurrentUser() {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch (e) {}
  localStorage.removeItem("sim_auth_token");
  STATE.currentUser = null;
  showToast("Sessão encerrada com segurança.");
  openAuthModal("LOGIN");
}

function openChangePinModal() {
  const cur = document.getElementById("chpin-current");
  const np = document.getElementById("chpin-new");
  const cp = document.getElementById("chpin-confirm");
  const fb = document.getElementById("chpin-feedback");
  if (cur) cur.value = "";
  if (np) np.value = "";
  if (cp) cp.value = "";
  if (fb) fb.textContent = "";
  openModal("modal-change-pin");
}

async function submitChangePin(ev) {
  if (ev) ev.preventDefault();
  const cur = document.getElementById("chpin-current")?.value.trim() || "";
  const np = document.getElementById("chpin-new")?.value.trim() || "";
  const cp = document.getElementById("chpin-confirm")?.value.trim() || "";
  const fb = document.getElementById("chpin-feedback");
  if (fb) fb.textContent = "";

  if (np !== cp) {
    if (fb) fb.textContent = "A confirmação do novo PIN não coincide.";
    return;
  }
  if (np.length < 4) {
    if (fb) fb.textContent = "O novo PIN deve ter pelo menos 4 dígitos.";
    return;
  }

  try {
    const res = await fetch("/api/auth/change-pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_pin: cur, new_pin: np }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erro ao alterar PIN.");
    showToast("PIN alterado com sucesso!");
    closeModal("modal-change-pin");
  } catch (err) {
    if (fb) fb.textContent = err.message || "Falha ao alterar PIN.";
  }
}

async function runAiTest() {
  const btn = document.getElementById("btn-test-ai");
  const fb = document.getElementById("ai-test-feedback");
  const prov = document.getElementById("ai-setting-provider")?.value || "GEMINI";
  const model = document.getElementById("ai-setting-model")?.value.trim() || "gemini-2.5-flash";
  const key = document.getElementById("ai-setting-apikey")?.value.trim() || "";

  if (btn) {
    btn.disabled = true;
    btn.textContent = "Testando…";
  }
  if (fb) fb.innerHTML = "<span class='faint'>Conectando ao provedor de IA com a chave informada…</span>";

  try {
    const res = await fetch("/api/ai/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ai_provider: prov, ai_model: model, ai_api_key: key }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha na comunicação com o modelo.");
    if (fb) {
      fb.innerHTML = `
        <span class="pos strong">✅ Comunicação realizada com sucesso!</span><br/>
        <span class="xs faint">Resposta do modelo (${esc(data.provider || prov)}): <em>“${esc(data.reply || data.status)}”</em></span>
      `;
    }
  } catch (err) {
    if (fb) fb.innerHTML = `<span class="neg strong">❌ Falha: ${esc(err.message)}</span>`;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span data-icon="sparkles" data-size="13"></span><span>Testar Chave Agora</span>`;
      hydrateIcons(btn);
    }
  }
}

window.addEventListener("DOMContentLoaded", initApp);

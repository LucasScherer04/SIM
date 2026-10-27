let STATE = {
  portfolio: null,
  currentTab: "DASHBOARD",
  previousTab: "DASHBOARD",
  portfolioSubTab: "CHART", // 'CHART' ou 'CATEGORIES'
  donutMode: "CATEGORY", // 'CATEGORY' ou 'ASSET'
  categoryListFilter: "ALL",
  marketClass: "ACAO_BR",
  marketSort: "em_alta",
  onlyMine: false,
  privacyMode: false,
  activeAssetTicker: null,
  activeAssetPeriod: "1M",
  activeAssetData: null,
};

const CLASS_COLORS = {
  FII: "#3b82f6",
  ACAO_BR: "#10b981",
  CAIXINHA: "#a855f7",
  RENDA_FIXA: "#6366f1",
  TESOURO: "#14b8a6",
  FUNDO_INV: "#eab308",
  ETF_BR: "#06b6d4",
  STOCK_US: "#f59e0b",
  CRIPTO: "#ec4899",
};

const ASSET_PALETTE = [
  "#10b981", "#3b82f6", "#a855f7", "#f59e0b", "#ec4899",
  "#06b6d4", "#6366f1", "#14b8a6", "#eab308", "#f43f5e",
  "#84cc16", "#fb923c", "#38bdf8", "#c084fc"
];

const CLASS_NAMES = {
  FII: "Fundos Imobiliários (FIIs)",
  ACAO_BR: "Ações Brasileiras (B3)",
  CAIXINHA: "Caixinhas & Liquidez Diária (Nubank / Bancos)",
  RENDA_FIXA: "CDB, LCI, LCA & Renda Fixa (CDI / IPCA+)",
  TESOURO: "Tesouro Direto (Tesouro IPCA+ / Selic)",
  FUNDO_INV: "Fundos de Investimento",
  ETF_BR: "ETFs & Índices (B3)",
  STOCK_US: "Stocks EUA (NYSE / NASDAQ)",
  CRIPTO: "Criptomoedas (Tempo Real)",
};

const CLASS_ICONS = {
  FII: "🏢",
  ACAO_BR: "🇧🇷",
  CAIXINHA: "💜",
  RENDA_FIXA: "🏦",
  TESOURO: "🏛️",
  FUNDO_INV: "📈",
  ETF_BR: "🌎",
  STOCK_US: "🇺🇸",
  CRIPTO: "₿",
};

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

async function initApp() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("tx-date").value = today;
  document.getElementById("fi-start").value = today;
  document.getElementById("div-date").value = today;
  document.getElementById("fi-maturity").value = "2028-12-31";

  await refreshAll();
  setInterval(() => refreshAll(true), 30000);
}

async function refreshAll(silent = false) {
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
  }
}

function renderMacroTicker(m) {
  if (!m) return;
  const items = [
    { label: "IBOV", val: Number(m.ibov).toLocaleString("pt-BR", { maximumFractionDigits: 0 }) + " pts", chg: m.ibov_change },
    { label: "DÓLAR", val: "R$ " + Number(m.usd_brl).toFixed(2).replace(".", ","), chg: m.usd_change },
    { label: "S&P 500", val: Number(m.sp500).toLocaleString("pt-BR", { maximumFractionDigits: 0 }), chg: m.sp500_change },
    { label: "BITCOIN", val: "US$ " + Number(m.btc_usd).toLocaleString("pt-BR", { maximumFractionDigits: 0 }), chg: m.btc_change },
    { label: "SELIC META", val: Number(m.selic).toFixed(2).replace(".", ",") + "% a.a.", chg: null },
    { label: "CDI ATUAL", val: Number(m.cdi).toFixed(2).replace(".", ",") + "% a.a.", chg: null },
    { label: "IPCA 12M", val: Number(m.ipca_12m).toFixed(2).replace(".", ",") + "%", chg: null },
  ];
  const bar = document.getElementById("macro-ticker-bar");
  bar.innerHTML = items.map(it => {
    let chgHtml = "";
    if (it.chg !== null && it.chg !== undefined) {
      const cls = it.chg >= 0 ? "text-emerald-400" : "text-rose-400";
      chgHtml = `<span class="${cls} font-bold">${fmtPct(it.chg)}</span>`;
    }
    return `
      <div class="flex items-center gap-1.5">
        <span class="text-slate-400 font-bold">${it.label}:</span>
        <span class="text-slate-100 font-semibold">${it.val}</span>
        ${chgHtml}
      </div>
    `;
  }).join('<span class="text-slate-700">|</span>');

  if (m.updated_at) {
    document.getElementById("last-sync-badge").textContent = "Atualizado às " + m.updated_at;
  }
}

function switchPortfolioSubTab(subTab) {
  STATE.portfolioSubTab = subTab;
  const bChart = document.getElementById("subtab-CHART");
  const bCat = document.getElementById("subtab-CATEGORIES");
  const vChart = document.getElementById("portfolio-subview-CHART");
  const vCat = document.getElementById("portfolio-subview-CATEGORIES");

  if (subTab === "CHART") {
    bChart.classList.add("pill-active");
    bChart.classList.remove("text-slate-300");
    bCat.classList.remove("pill-active");
    bCat.classList.add("text-slate-300");
    vChart.classList.remove("hidden");
    vCat.classList.add("hidden");
    if (STATE.portfolio) renderPortfolioDonutAndBars(STATE.portfolio);
  } else {
    bCat.classList.add("pill-active");
    bCat.classList.remove("text-slate-300");
    bChart.classList.remove("pill-active");
    bChart.classList.add("text-slate-300");
    vCat.classList.remove("hidden");
    vChart.classList.add("hidden");
    if (STATE.portfolio) renderCategorizedInvestments(STATE.portfolio);
  }
}

function setDonutMode(mode) {
  STATE.donutMode = mode;
  const bCat = document.getElementById("donut-mode-CATEGORY");
  const bAsset = document.getElementById("donut-mode-ASSET");
  if (mode === "CATEGORY") {
    bCat.classList.add("pill-active");
    bCat.classList.remove("text-slate-300");
    bAsset.classList.remove("pill-active");
    bAsset.classList.add("text-slate-300");
  } else {
    bAsset.classList.add("pill-active");
    bAsset.classList.remove("text-slate-300");
    bCat.classList.remove("pill-active");
    bCat.classList.add("text-slate-300");
  }
  if (STATE.portfolio) {
    renderPortfolioDonutAndBars(STATE.portfolio);
  }
}

function setCategoryListFilter(catKey) {
  STATE.categoryListFilter = catKey;
  document.querySelectorAll(".cat-filter-btn").forEach(b => {
    b.classList.remove("pill-active");
    b.classList.add("bg-slate-800", "text-slate-300");
  });
  const active = document.getElementById(`catfilter-${catKey}`);
  if (active) {
    active.classList.add("pill-active");
    active.classList.remove("bg-slate-800", "text-slate-300");
  }
  if (STATE.portfolio) {
    renderCategorizedInvestments(STATE.portfolio);
  }
}

function renderDashboard(data) {
  const k = data.kpis;
  const kpiContainer = document.getElementById("kpi-cards-container");
  const profitCls = k.total_profit_brl >= 0 ? "text-emerald-400" : "text-rose-400";
  const dayCls = k.day_change_brl >= 0 ? "text-emerald-400" : "text-rose-400";

  kpiContainer.innerHTML = `
    <div class="glass-card rounded-2xl p-4 border-l-4 border-l-emerald-500">
      <div class="text-[11px] uppercase font-bold text-slate-400">Patrimônio Líquido Total</div>
      <div class="text-xl sm:text-2xl font-black text-white mt-1">${fmtMoney(k.total_current_brl)}</div>
      <div class="text-xs text-slate-400 mt-1">Equiv. Dólar: <strong class="text-slate-200">${fmtMoney(k.total_current_usd, "USD")}</strong></div>
    </div>
    <div class="glass-card rounded-2xl p-4">
      <div class="text-[11px] uppercase font-bold text-slate-400">Valor Total Investido</div>
      <div class="text-xl sm:text-2xl font-bold text-slate-100 mt-1">${fmtMoney(k.total_invested_brl)}</div>
      <div class="text-xs text-slate-400 mt-1">Custo de Aquisição</div>
    </div>
    <div class="glass-card rounded-2xl p-4">
      <div class="text-[11px] uppercase font-bold text-slate-400">Lucro / Rentabilidade</div>
      <div class="text-xl sm:text-2xl font-black ${profitCls} mt-1">${fmtMoney(k.total_profit_brl)}</div>
      <div class="text-xs font-bold ${profitCls} mt-1">${fmtPct(k.total_profit_pct)} sobre custo</div>
    </div>
    <div class="glass-card rounded-2xl p-4">
      <div class="text-[11px] uppercase font-bold text-slate-400">Variação do Dia</div>
      <div class="text-xl sm:text-2xl font-bold ${dayCls} mt-1">${fmtMoney(k.day_change_brl)}</div>
      <div class="text-xs font-bold ${dayCls} mt-1">${fmtPct(k.day_change_pct)} hoje</div>
    </div>
    <div class="glass-card rounded-2xl p-4 border-l-4 border-l-blue-500">
      <div class="text-[11px] uppercase font-bold text-slate-400">Renda Passiva (Dividendos)</div>
      <div class="text-xl sm:text-2xl font-black text-blue-400 mt-1">${fmtMoney(k.total_dividends_brl)}</div>
      <div class="text-xs text-slate-300 mt-1">Est. Mensal: <strong class="text-emerald-400">${fmtMoney(k.estimated_monthly_divs_brl)}/mês</strong></div>
    </div>
  `;

  const totalHoldings = (data.positions ? data.positions.length : 0) + (data.fixed_income ? data.fixed_income.length : 0);
  const countBadge = document.getElementById("portfolio-count-badge");
  if (countBadge) countBadge.textContent = totalHoldings;

  const emptyState = document.getElementById("portfolio-empty-state");
  const clearBtn = document.getElementById("btn-clear-portfolio");
  if (totalHoldings === 0) {
    emptyState.classList.remove("hidden");
    if (clearBtn) clearBtn.classList.add("hidden");
  } else {
    emptyState.classList.add("hidden");
    if (clearBtn) clearBtn.classList.remove("hidden");
  }

  document.getElementById("usd-equivalent-badge").textContent = `Câmbio Dólar: R$ ${Number(data.macro.usd_brl).toFixed(2)}`;

  renderPortfolioDonutAndBars(data);
  renderCategorizedInvestments(data);
}

function renderPortfolioDonutAndBars(data) {
  const barsContainer = document.getElementById("allocation-bars-list");
  if (!barsContainer) return;

  let slices = [];
  if (STATE.donutMode === "ASSET") {
    const assets = data.allocation_by_asset || [];
    slices = assets.map((a, idx) => ({
      key: a.code,
      label: `${a.code}`,
      sublabel: a.name !== a.code ? a.name : a.category_label,
      current_brl: a.current_brl,
      invested_brl: a.invested_brl,
      profit_brl: a.profit_brl,
      profit_pct: a.profit_pct,
      pct: a.weight_pct,
      color: ASSET_PALETTE[idx % ASSET_PALETTE.length],
      asset_class: a.asset_class,
      is_fixed_income: a.is_fixed_income,
    }));
  } else {
    const alloc = (data.allocation || []).filter(it => it.current_brl > 0 || it.target_pct > 0);
    slices = alloc.map(it => ({
      key: it.asset_class,
      label: `${CLASS_ICONS[it.asset_class] || "📊"} ${it.label}`,
      sublabel: `${it.count || 0} ativo(s) na carteira · Meta: ${it.target_pct}%`,
      current_brl: it.current_brl,
      invested_brl: it.invested_brl || 0,
      profit_brl: it.profit_brl || 0,
      profit_pct: it.profit_pct || 0,
      pct: it.current_pct,
      color: CLASS_COLORS[it.asset_class] || "#10b981",
      asset_class: it.asset_class,
    }));
  }

  renderInteractiveDonutCanvas(slices, data.kpis.total_current_brl);

  const activeSlices = slices.filter(s => s.current_brl > 0);
  if (activeSlices.length === 0) {
    barsContainer.innerHTML = `
      <div class="p-6 rounded-xl bg-slate-900/70 border border-slate-800 text-center space-y-2">
        <div class="text-sm font-bold text-slate-200">Nenhum investimento na carteira ainda</div>
        <p class="text-xs text-slate-400">Clique em <strong>"+ Adicionar à Carteira"</strong> no topo para cadastrar suas Ações, FIIs, Caixinha Nubank, CDB ou Tesouro IPCA+.</p>
      </div>
    `;
    return;
  }

  barsContainer.innerHTML = activeSlices.map((item, idx) => {
    const profCls = item.profit_brl >= 0 ? "text-emerald-400" : "text-rose-400";
    const clickAction = STATE.donutMode === "ASSET" && !item.is_fixed_income
      ? `openAssetDetail('${item.key}')`
      : `openCategoryFromDonut('${item.asset_class}')`;
    return `
      <div class="space-y-1.5 cursor-pointer bg-slate-900/65 hover:bg-slate-800/80 border border-slate-800/80 p-3 rounded-xl transition"
           onmouseenter="highlightDonutSlice(${idx})"
           onmouseleave="highlightDonutSlice(null)"
           onclick="${clickAction}">
        <div class="flex items-center justify-between text-xs">
          <div class="flex items-center gap-2 min-w-0">
            <span class="w-3 h-3 rounded-full shrink-0" style="background:${item.color}"></span>
            <div class="truncate">
              <span class="font-bold text-white">${item.label}</span>
              <span class="text-[11px] text-slate-400 block truncate">${item.sublabel}</span>
            </div>
          </div>
          <div class="text-right shrink-0 ml-2">
            <div class="font-mono font-bold text-white">${fmtMoney(item.current_brl)} <span class="text-emerald-400">(${item.pct.toFixed(1)}%)</span></div>
            <div class="text-[11px] font-mono ${profCls}">Lucro: ${fmtMoney(item.profit_brl)} (${fmtPct(item.profit_pct)})</div>
          </div>
        </div>
        <div class="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
          <div class="h-full rounded-full transition-all duration-300" style="width:${Math.min(100, Math.max(2, item.pct))}%; background:${item.color}"></div>
        </div>
      </div>
    `;
  }).join("");
}

function openCategoryFromDonut(assetClass) {
  switchPortfolioSubTab("CATEGORIES");
  const filterKey = ["ETF_BR", "FUNDO_INV", "STOCK_US", "CRIPTO"].includes(assetClass) ? "OUTROS" : assetClass;
  setCategoryListFilter(filterKey);
}

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
    const x = e.clientX - rect.left - canvas.width / 2;
    const y = e.clientY - rect.top - canvas.height / 2;
    const dist = Math.sqrt(x * x + y * y);
    if (dist < 58 || dist > 122) {
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
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h / 2;
  const radius = 94;
  const baseLineWidth = 30;

  const total = activeSlices.reduce((acc, it) => acc + it.current_brl, 0);

  if (total <= 0) {
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.strokeStyle = "#1e293b";
    ctx.lineWidth = baseLineWidth;
    ctx.stroke();

    ctx.fillStyle = "#64748b";
    ctx.font = "bold 12px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("CARTEIRA VAZIA", cx, cy - 4);
    ctx.fillStyle = "#94a3b8";
    ctx.font = "11px Inter, sans-serif";
    ctx.fillText("R$ 0,00", cx, cy + 14);
    return;
  }

  let startAngle = -Math.PI / 2;
  activeSlices.forEach((item, idx) => {
    const sliceAngle = (item.current_brl / total) * (Math.PI * 2);
    const isHovered = hoverIdx === idx;
    const gap = activeSlices.length > 1 ? 0.025 : 0;
    ctx.beginPath();
    ctx.arc(cx, cy, isHovered ? radius + 4 : radius, startAngle, startAngle + Math.max(0.01, sliceAngle - gap));
    ctx.strokeStyle = item.color;
    ctx.lineWidth = isHovered ? baseLineWidth + 6 : baseLineWidth;
    ctx.stroke();
    startAngle += sliceAngle;
  });

  if (hoverIdx !== null && activeSlices[hoverIdx]) {
    const s = activeSlices[hoverIdx];
    const cleanTitle = s.label.replace(/^[^\wA-Za-zÀ-ÿ]+/, "").slice(0, 16);
    ctx.fillStyle = "#cbd5e1";
    ctx.font = "bold 11px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(cleanTitle, cx, cy - 16);

    ctx.fillStyle = s.color;
    ctx.font = "900 18px Inter, sans-serif";
    ctx.fillText(`${s.pct.toFixed(1)}%`, cx, cy + 5);

    ctx.fillStyle = "#f8fafc";
    ctx.font = "bold 11px monospace";
    ctx.fillText(fmtMoney(s.current_brl), cx, cy + 23);
  } else {
    ctx.fillStyle = "#94a3b8";
    ctx.font = "bold 11px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("PATRIMÔNIO", cx, cy - 14);

    ctx.fillStyle = "#10b981";
    ctx.font = "900 15px Inter, sans-serif";
    ctx.fillText(fmtMoney(totalBrl), cx, cy + 6);

    ctx.fillStyle = "#cbd5e1";
    ctx.font = "bold 11px Inter, sans-serif";
    ctx.fillText(`${activeSlices.length} ${STATE.donutMode === "ASSET" ? "Ativo(s)" : "Categoria(s)"}`, cx, cy + 24);
  }
}

function renderCategorizedInvestments(data) {
  const container = document.getElementById("categorized-investments-container");
  if (!container) return;

  const positions = data.positions || [];
  const fixedIncome = data.fixed_income || [];
  const totalPortfolioBrl = data.kpis.total_current_brl || 0;

  const categoryConfigs = [
    {
      key: "FII",
      filterGroup: "FII",
      icon: "🏢",
      title: "Fundos Imobiliários (FIIs & Fiagros)",
      subtitle: "Renda passiva mensal isenta de Imposto de Renda",
      borderColor: "border-l-blue-500",
      badgeCls: "bg-blue-500/15 text-blue-300 border-blue-500/30",
      addAction: "openAddInvestmentModal('FII')",
      addLabel: "+ Adicionar FII",
      isVariable: true,
      items: positions.filter(p => p.asset_class === "FII"),
    },
    {
      key: "ACAO_BR",
      filterGroup: "ACAO_BR",
      icon: "🇧🇷",
      title: "Ações Brasileiras (B3)",
      subtitle: "Participação em empresas listadas na Bolsa do Brasil",
      borderColor: "border-l-emerald-500",
      badgeCls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
      addAction: "openAddInvestmentModal('ACAO_BR')",
      addLabel: "+ Adicionar Ação",
      isVariable: true,
      items: positions.filter(p => p.asset_class === "ACAO_BR"),
    },
    {
      key: "CAIXINHA",
      filterGroup: "CAIXINHA",
      icon: "💜",
      title: "Caixinhas & Liquidez Diária (Nubank / Bancos)",
      subtitle: "Reserva de emergência e caixinhas rendendo % do CDI todos os dias úteis",
      borderColor: "border-l-purple-500",
      badgeCls: "bg-purple-500/15 text-purple-300 border-purple-500/30",
      addAction: "openAddInvestmentModal('CAIXINHA')",
      addLabel: "+ Adicionar Caixinha",
      isVariable: false,
      items: fixedIncome.filter(f => f.asset_class === "CAIXINHA"),
    },
    {
      key: "RENDA_FIXA",
      filterGroup: "RENDA_FIXA",
      icon: "🏦",
      title: "CDBs, LCIs, LCAs, Debêntures & Fundos DI (CDI / IPCA+ / Pré)",
      subtitle: "Títulos bancários pós-fixados (% CDI), híbridos (IPCA+) e isentos de IR (LCI/LCA)",
      borderColor: "border-l-indigo-500",
      badgeCls: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
      addAction: "openAddInvestmentModal('RENDA_FIXA')",
      addLabel: "+ Adicionar CDB / LCI / IPCA+",
      isVariable: false,
      items: fixedIncome.filter(f => f.asset_class === "RENDA_FIXA" || f.asset_class === "FUNDO_INV"),
    },
    {
      key: "TESOURO",
      filterGroup: "TESOURO",
      icon: "🏛️",
      title: "Tesouro Direto (Tesouro IPCA+, Tesouro Selic, Prefixado)",
      subtitle: "Títulos públicos federais corrigidos pela inflação (IPCA+) ou Taxa Selic",
      borderColor: "border-l-teal-500",
      badgeCls: "bg-teal-500/15 text-teal-300 border-teal-500/30",
      addAction: "openAddInvestmentModal('TESOURO')",
      addLabel: "+ Adicionar Tesouro Direto",
      isVariable: false,
      items: fixedIncome.filter(f => f.asset_class === "TESOURO"),
    },
    {
      key: "OUTROS",
      filterGroup: "OUTROS",
      icon: "🌎",
      title: "ETFs, Fundos de Investimento, Stocks EUA & Criptomoedas",
      subtitle: "Diversificação global, ETFs, fundos de cotas e criptoativos",
      borderColor: "border-l-amber-500",
      badgeCls: "bg-amber-500/15 text-amber-300 border-amber-500/30",
      addAction: "openAddInvestmentModal('ETF_BR')",
      addLabel: "+ Adicionar ETF / Fundo / Cripto",
      isVariable: true,
      items: positions.filter(p => ["ETF_BR", "FUNDO_INV", "STOCK_US", "CRIPTO"].includes(p.asset_class)),
    },
  ];

  const filteredCategories = categoryConfigs.filter(cat => {
    if (STATE.categoryListFilter !== "ALL") {
      return cat.filterGroup === STATE.categoryListFilter;
    }
    return true;
  });

  container.innerHTML = filteredCategories.map(cat => {
    const catInvested = cat.items.reduce((acc, it) => acc + (cat.isVariable ? it.invested_brl : it.invested_amount), 0);
    const catCurrent = cat.items.reduce((acc, it) => acc + (cat.isVariable ? it.current_brl : it.net_amount), 0);
    const catProfit = catCurrent - catInvested;
    const catProfitPct = catInvested > 0 ? (catProfit / catInvested) * 100.0 : 0.0;
    const catWeightPct = totalPortfolioBrl > 0 ? (catCurrent / totalPortfolioBrl) * 100.0 : 0.0;
    const profCls = catProfit >= 0 ? "text-emerald-400" : "text-rose-400";

    let bodyHtml = "";
    if (cat.items.length === 0) {
      bodyHtml = `
        <div class="p-5 rounded-xl bg-slate-900/50 border border-slate-800/70 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-400">
          <span>Você ainda não cadastrou ativos na categoria <strong>${cat.title}</strong>.</span>
          <button onclick="${cat.addAction}" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-emerald-400 font-bold border border-slate-700 shrink-0">
            ${cat.addLabel}
          </button>
        </div>
      `;
    } else if (cat.isVariable) {
      const rowsHtml = cat.items.map(p => {
        const chgCls = p.change_pct >= 0 ? "text-emerald-400" : "text-rose-400";
        const pProfCls = p.profit_brl >= 0 ? "text-emerald-400" : "text-rose-400";
        const divTxt = p.last_dividend_per_share > 0 ? `${fmtMoney(p.last_dividend_per_share, p.currency)}/cota` : "—";
        return `
          <tr class="hover:bg-slate-800/50 transition">
            <td class="py-3 px-3 cursor-pointer" onclick="openAssetDetail('${p.ticker}')">
              <div class="font-bold text-white hover:text-emerald-400 transition">${p.ticker}</div>
              <div class="text-[11px] text-slate-400 truncate max-w-[170px]">${p.name} · ${p.broker || "Corretora"}</div>
            </td>
            <td class="py-3 px-3 text-right font-mono font-bold text-slate-100">${p.quantity}</td>
            <td class="py-3 px-3 text-right font-mono text-slate-300">${fmtMoney(p.avg_price, p.currency)}</td>
            <td class="py-3 px-3 text-right font-mono font-bold text-white">
              ${fmtMoney(p.current_price, p.currency)}
              <span class="block text-[10px] ${chgCls}">${fmtPct(p.change_pct)} hoje</span>
            </td>
            <td class="py-3 px-3 text-right font-mono text-emerald-400 font-semibold">${divTxt}</td>
            <td class="py-3 px-3 text-right font-mono text-slate-300">${fmtMoney(p.invested_brl)}</td>
            <td class="py-3 px-3 text-right font-mono font-black text-white">
              ${fmtMoney(p.current_brl)}
              <span class="block text-[10px] text-slate-400 font-normal">${p.weight_pct.toFixed(1)}% da carteira</span>
            </td>
            <td class="py-3 px-3 text-right font-mono ${pProfCls}">
              <div class="font-bold">${fmtMoney(p.profit_brl)}</div>
              <div class="text-[11px]">${fmtPct(p.profit_pct)}</div>
            </td>
            <td class="py-3 px-3 text-center">
              <div class="flex items-center justify-center gap-1.5">
                <button onclick="openAssetDetail('${p.ticker}')" class="px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/30 text-emerald-400 text-xs font-bold border border-emerald-500/30" title="Ver Gráfico Interativo, Dividendos e Relatório IA">
                  📈 Raio-X
                </button>
                <button onclick="openTransactionModal('${p.ticker}','${p.asset_class}',${p.current_price},'${p.currency}')" class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold border border-slate-700" title="Registrar nova compra ou venda deste ativo">
                  + / -
                </button>
                <button onclick="deleteVariablePosition('${p.ticker}')" class="px-2 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/25 text-rose-400 text-xs border border-rose-500/20" title="Remover ativo da carteira">
                  🗑️
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join("");

      bodyHtml = `
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs sm:text-sm">
            <thead>
              <tr class="border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                <th class="py-2.5 px-3">Ativo / Corretora</th>
                <th class="py-2.5 px-3 text-right">Qtd Cotas</th>
                <th class="py-2.5 px-3 text-right">Preço Médio</th>
                <th class="py-2.5 px-3 text-right">Cotação Atual</th>
                <th class="py-2.5 px-3 text-right">Últ. Div/Cota</th>
                <th class="py-2.5 px-3 text-right">Valor Investido</th>
                <th class="py-2.5 px-3 text-right">Saldo Atual</th>
                <th class="py-2.5 px-3 text-right">Lucro / Rentab.</th>
                <th class="py-2.5 px-3 text-center">Ações</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60">${rowsHtml}</tbody>
          </table>
        </div>
      `;
    } else {
      // Renda Fixa, Caixinhas Nubank, CDB, LCI, LCA, Tesouro IPCA+
      const cardsHtml = cat.items.map(f => {
        const fProfCls = f.net_profit >= 0 ? "text-emerald-400" : "text-rose-400";
        return `
          <div class="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between space-y-3">
            <div class="flex items-start justify-between gap-2">
              <div>
                <div class="flex flex-wrap items-center gap-1.5">
                  <span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${cat.badgeCls}">${f.rate_label}</span>
                  <span class="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300">${f.tax_exempt ? "Isento de IR" : "IR Regressivo (" + f.ir_rate + "%)"}</span>
                </div>
                <h4 class="font-bold text-sm sm:text-base text-white mt-1.5">${f.title_name}</h4>
                <p class="text-xs text-slate-400">${f.issuer} · Aplicado em ${f.start_date} (${f.days_elapsed} dias)</p>
              </div>
              <button onclick="deleteFixedIncome(${f.id})" title="Remover da carteira" class="px-2 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/25 text-rose-400 text-xs border border-rose-500/20">
                🗑️
              </button>
            </div>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-3 border-t border-slate-800/80 text-xs">
              <div>
                <span class="text-slate-400 block text-[11px]">Valor Aplicado</span>
                <strong class="text-slate-200 font-mono">${fmtMoney(f.invested_amount)}</strong>
              </div>
              <div>
                <span class="text-slate-400 block text-[11px]">Saldo Bruto Hoje</span>
                <strong class="text-slate-200 font-mono">${fmtMoney(f.gross_amount)}</strong>
              </div>
              <div>
                <span class="text-slate-400 block text-[11px]">Rendimento Líquido</span>
                <strong class="${fProfCls} font-mono">+${fmtMoney(f.net_profit)} (${fmtPct(f.net_profit_pct)})</strong>
              </div>
              <div>
                <span class="text-slate-400 block text-[11px]">Saldo Líquido Atual</span>
                <strong class="text-emerald-400 text-sm font-black font-mono">${fmtMoney(f.net_amount)}</strong>
              </div>
            </div>
          </div>
        `;
      }).join("");

      bodyHtml = `<div class="grid grid-cols-1 md:grid-cols-2 gap-4">${cardsHtml}</div>`;
    }

    return `
      <div class="glass-card rounded-2xl p-5 border-l-4 ${cat.borderColor} space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
          <div class="flex items-center gap-3">
            <span class="text-2xl">${cat.icon}</span>
            <div>
              <div class="flex items-center gap-2">
                <h3 class="font-bold text-base text-white">${cat.title}</h3>
                <span class="px-2 py-0.5 rounded-full text-[11px] font-bold ${cat.badgeCls}">${cat.items.length} ativo(s)</span>
              </div>
              <p class="text-xs text-slate-400">${cat.subtitle}</p>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-4">
            <div class="text-right text-xs">
              <span class="text-slate-400 block">Subtotal da Categoria (${catWeightPct.toFixed(1)}%)</span>
              <span class="font-mono font-black text-base text-white">${fmtMoney(catCurrent)}</span>
              <span class="font-mono text-[11px] ${profCls} ml-1">(${fmtPct(catProfitPct)})</span>
            </div>
            <button onclick="${cat.addAction}" class="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-emerald-400 font-bold text-xs border border-slate-700 transition">
              ${cat.addLabel}
            </button>
          </div>
        </div>
        ${bodyHtml}
      </div>
    `;
  }).join("");
}

async function loadRebalance() {
  const val = parseFloat(document.getElementById("input-rebalance-amount").value || "2000");
  const res = await fetch(`/api/rebalance?contribution_brl=${val}`);
  const data = await res.json();
  const box = document.getElementById("rebalance-results");
  box.innerHTML = data.suggestions.slice(0, 4).map(s => `
    <div class="flex items-center justify-between p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs">
      <div>
        <div class="font-bold text-slate-200">${s.label}</div>
        <div class="text-[11px] text-slate-400">Atual: ${s.current_pct}% → Meta: ${s.target_pct}%</div>
      </div>
      <div class="text-right">
        <div class="font-black text-emerald-400 text-sm">+ ${fmtMoney(s.suggested_contribution_brl)}</div>
        <div class="text-[10px] text-slate-400">Aporte sugerido</div>
      </div>
    </div>
  `).join("");
}

function switchMainTab(tabKey) {
  STATE.currentTab = tabKey;
  document.querySelectorAll(".nav-tab").forEach(btn => btn.classList.remove("tab-active"));
  const activeBtn = document.getElementById(`tab-${tabKey}`);
  if (activeBtn) activeBtn.classList.add("tab-active");

  document.getElementById("view-DASHBOARD").classList.add("hidden");
  document.getElementById("view-MARKET_CLASS").classList.add("hidden");
  document.getElementById("view-ASSET_DETAIL").classList.add("hidden");
  document.getElementById("view-RENDA_FIXA").classList.add("hidden");
  document.getElementById("view-DIVIDENDS").classList.add("hidden");

  if (tabKey === "DASHBOARD") {
    document.getElementById("view-DASHBOARD").classList.remove("hidden");
  } else if (tabKey === "RENDA_FIXA") {
    document.getElementById("view-RENDA_FIXA").classList.remove("hidden");
  } else if (tabKey === "DIVIDENDS") {
    document.getElementById("view-DIVIDENDS").classList.remove("hidden");
  } else {
    STATE.marketClass = tabKey;
    document.getElementById("view-MARKET_CLASS").classList.remove("hidden");
    document.getElementById("market-class-title").textContent = CLASS_NAMES[tabKey] || "Explorador de Ativos";
    loadMarketClassAssets();
  }
}

function setPortfolioScope(onlyMine) {
  STATE.onlyMine = onlyMine;
  const bAll = document.getElementById("btn-filter-all");
  const bMine = document.getElementById("btn-filter-mine");
  if (onlyMine) {
    bMine.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 text-slate-950";
    bAll.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700";
  } else {
    bAll.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 text-slate-950";
    bMine.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700";
  }
  loadMarketClassAssets();
}

function setMarketSort(sortKey) {
  STATE.marketSort = sortKey;
  document.querySelectorAll(".sort-pill").forEach(b => b.classList.remove("pill-active"));
  const btn = document.getElementById(`sort-${sortKey}`);
  if (btn) btn.classList.add("pill-active");
  loadMarketClassAssets();
}

async function loadMarketClassAssets() {
  const url = `/api/market/assets?asset_class=${STATE.marketClass}&sort_by=${STATE.marketSort}&only_mine=${STATE.onlyMine}`;
  const res = await fetch(url);
  const data = await res.json();
  const grid = document.getElementById("market-assets-grid");

  if (!data.assets || data.assets.length === 0) {
    grid.innerHTML = `<div class="col-span-full glass-card rounded-2xl p-8 text-center text-slate-400 text-sm">Nenhum ativo encontrado neste filtro.</div>`;
    return;
  }

  grid.innerHTML = data.assets.map(a => {
    const chgCls = a.change_pct >= 0 ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" : "text-rose-400 bg-rose-500/10 border-rose-500/30";
    const heldBadge = a.in_portfolio
      ? `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Na Carteira (${a.user_qty})</span>`
      : "";
    const divPerShareBadge = a.last_dividend_per_share > 0
      ? `<span class="text-emerald-400 font-bold">${fmtMoney(a.last_dividend_per_share, a.currency)} / cota</span>`
      : `<span class="text-slate-500">—</span>`;

    return `
      <div onclick="openAssetDetail('${a.ticker}')" class="glass-card rounded-2xl p-5 hover:border-emerald-500/60 cursor-pointer transition group flex flex-col justify-between">
        <div>
          <div class="flex items-start justify-between gap-2">
            <div>
              <div class="flex items-center gap-2">
                <span class="text-lg font-black text-white group-hover:text-emerald-400 transition">${a.ticker}</span>
                ${heldBadge}
              </div>
              <p class="text-xs text-slate-400 truncate max-w-[210px]">${a.name}</p>
            </div>
            <div class="text-right">
              <div class="text-lg font-black text-white">${fmtMoney(a.last_price, a.currency)}</div>
              <span class="inline-block px-2 py-0.5 rounded text-xs font-bold border ${chgCls} mt-0.5">${fmtPct(a.change_pct)}</span>
            </div>
          </div>

          <div class="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-slate-800/80 text-xs">
            <div>
              <span class="text-[10px] text-slate-400 uppercase block">Últ. Div/Cota</span>
              ${divPerShareBadge}
            </div>
            <div>
              <span class="text-[10px] text-slate-400 uppercase block">DY (12M)</span>
              <strong class="text-slate-200">${a.dy_12m > 0 ? a.dy_12m.toFixed(1) + "%" : "—"}</strong>
            </div>
            <div>
              <span class="text-[10px] text-slate-400 uppercase block">${a.asset_class === "FII" ? "P/VP" : "P/VP · P/L"}</span>
              <strong class="text-slate-200">${a.pvp > 0 ? a.pvp.toFixed(2) + "x" : "—"}${a.pl > 0 ? " · " + a.pl.toFixed(1) : ""}</strong>
            </div>
          </div>
        </div>

        <div class="flex items-center justify-between mt-4 pt-2.5 border-t border-slate-800/50 text-[11px] text-slate-400">
          <span>Vol. Dia: <strong class="text-slate-300">${fmtCompact(a.volume_day)}</strong></span>
          <span class="text-emerald-400 font-bold group-hover:translate-x-0.5 transition">Abrir Raio-X, Gráfico & IA →</span>
        </div>
      </div>
    `;
  }).join("");
}

/* ==================== EXCLUSIVE ASSET DETAIL PAGE & INTERACTIVE CHART ==================== */
async function openAssetDetail(ticker, period = "1M", keepTabHistory = false) {
  if (!keepTabHistory && STATE.currentTab !== "ASSET_DETAIL") {
    STATE.previousTab = STATE.currentTab;
  }
  STATE.currentTab = "ASSET_DETAIL";
  STATE.activeAssetTicker = ticker;
  STATE.activeAssetPeriod = period;

  document.getElementById("view-DASHBOARD").classList.add("hidden");
  document.getElementById("view-MARKET_CLASS").classList.add("hidden");
  document.getElementById("view-RENDA_FIXA").classList.add("hidden");
  document.getElementById("view-DIVIDENDS").classList.add("hidden");
  document.getElementById("view-ASSET_DETAIL").classList.remove("hidden");

  document.querySelectorAll(".period-btn").forEach(b => b.classList.remove("pill-active"));
  const pBtn = document.getElementById(`period-${period}`);
  if (pBtn) pBtn.classList.add("pill-active");

  const res = await fetch(`/api/asset/${ticker}?period=${period}`);
  if (!res.ok) return;
  const data = await res.json();
  STATE.activeAssetData = data;

  const a = data.asset;
  document.getElementById("detail-ticker").textContent = a.ticker;
  document.getElementById("detail-class-badge").textContent = a.asset_class;
  document.getElementById("detail-sector-badge").textContent = a.sector || "Mercado";
  document.getElementById("detail-name").textContent = `${a.name} ${a.cnpj ? "· CNPJ/ID: " + a.cnpj : ""}`;

  document.getElementById("btn-detail-buy").onclick = () => {
    openTransactionModal(a.ticker, a.asset_class, a.last_price, a.currency);
  };

  setDetailHeaderReadout(
    a.last_price,
    data.period_change_pct,
    data.period_change_abs,
    `Cotação Atual (${period}) — Passe o mouse no gráfico para inspecionar datas`,
    a.currency
  );

  document.getElementById("detail-low").textContent = fmtMoney(data.low_period, a.currency);
  document.getElementById("detail-high").textContent = fmtMoney(data.high_period, a.currency);

  const pmBadge = document.getElementById("detail-user-pm-badge");
  if (data.user_position && data.user_position.has_position) {
    pmBadge.classList.remove("hidden");
    document.getElementById("detail-user-pm-val").textContent = fmtMoney(data.user_position.avg_price, a.currency);
  } else {
    pmBadge.classList.add("hidden");
  }

  // Draw Interactive Crosshair Chart
  drawInteractiveAssetChart(data);

  // Fundamental metrics strip
  const fStrip = document.getElementById("detail-fundamentals-strip");
  const pvpStatus = a.pvp < 0.98 ? "Desconto" : (a.pvp <= 1.03 ? "Justo" : "Ágio");
  fStrip.innerHTML = `
    <div class="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
      <span class="text-[10px] uppercase text-slate-400">Último Dividendo / Cota</span>
      <div class="text-sm font-black text-emerald-400 mt-0.5">${a.last_dividend_per_share > 0 ? fmtMoney(a.last_dividend_per_share, a.currency) : "—"}</div>
    </div>
    <div class="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
      <span class="text-[10px] uppercase text-slate-400">Dividend Yield (12M)</span>
      <div class="text-sm font-bold text-white mt-0.5">${a.dy_12m > 0 ? a.dy_12m.toFixed(2) + "% a.a." : "—"}</div>
    </div>
    <div class="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
      <span class="text-[10px] uppercase text-slate-400">P/VP (Patrimonial)</span>
      <div class="text-sm font-bold text-white mt-0.5">${a.pvp > 0 ? a.pvp.toFixed(2) + "x (" + pvpStatus + ")" : "—"}</div>
    </div>
    <div class="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
      <span class="text-[10px] uppercase text-slate-400">Múltiplo P/L</span>
      <div class="text-sm font-bold text-white mt-0.5">${a.pl > 0 ? a.pl.toFixed(1) + "x" : "Isento / FII"}</div>
    </div>
    <div class="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
      <span class="text-[10px] uppercase text-slate-400">Liquidez / Volume Dia</span>
      <div class="text-sm font-bold text-white mt-0.5">${fmtCompact(a.volume_day)}</div>
    </div>
    <div class="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
      <span class="text-[10px] uppercase text-slate-400">Moeda Base</span>
      <div class="text-sm font-bold text-white mt-0.5">${a.currency}</div>
    </div>
  `;

  // Dividend Per Share Spotlight
  const divInfo = data.dividend_info;
  document.getElementById("detail-div-yield-badge").textContent = `DY 12M: ${Number(divInfo.dy_12m).toFixed(2)}%`;
  document.getElementById("detail-div-per-share").textContent =
    divInfo.last_dividend_per_share > 0 ? `${fmtMoney(divInfo.last_dividend_per_share, a.currency)} / cota` : "Sem distribuição";
  document.getElementById("detail-div-monthly-pct").textContent =
    divInfo.monthly_yield_pct > 0 ? `Equivale a ${divInfo.monthly_yield_pct.toFixed(2)}% de retorno no mês` : "Ativo de acumulação";
  document.getElementById("detail-div-ex-date").textContent = divInfo.last_ex_date || "—";
  document.getElementById("detail-div-pay-date").textContent = divInfo.last_pay_date || "—";

  const barsEl = document.getElementById("detail-div-bars");
  if (divInfo.history_12m && divInfo.history_12m.length > 0) {
    const maxVal = Math.max(...divInfo.history_12m.map(h => h.amount_per_share), 0.01);
    barsEl.innerHTML = divInfo.history_12m.map(h => {
      const pctH = Math.max(8, Math.round((h.amount_per_share / maxVal) * 100));
      return `
        <div class="flex flex-col items-center justify-end h-full group relative">
          <span class="text-[9px] font-mono text-emerald-400 mb-1">${h.amount_per_share > 0 ? h.amount_per_share.toFixed(2) : ""}</span>
          <div class="w-full rounded-t bg-emerald-500/70 group-hover:bg-emerald-400 transition" style="height:${pctH}%"></div>
          <span class="text-[9px] text-slate-400 mt-1">${h.month.split("/")[0]}</span>
        </div>
      `;
    }).join("");
  } else {
    barsEl.innerHTML = `<div class="col-span-12 text-center text-xs text-slate-500 pb-6">Ativo de crescimento (não distribui dividendos mensais por cota).</div>`;
  }

  // User position & Simulator
  const up = data.user_position;
  const posBox = document.getElementById("detail-user-pos-box");
  if (up && up.has_position) {
    document.getElementById("sim-shares-input").value = up.quantity;
    posBox.innerHTML = `
      <div class="flex justify-between"><span>Cotas/Ações na sua carteira:</span><strong class="text-white">${up.quantity}</strong></div>
      <div class="flex justify-between"><span>Seu Preço Médio:</span><strong class="text-amber-300">${fmtMoney(up.avg_price, a.currency)}</strong></div>
      <div class="flex justify-between"><span>Saldo Atual no Ativo:</span><strong class="text-white">${fmtMoney(up.current_value, a.currency)} (${fmtPct(up.profit_pct)})</strong></div>
      <div class="flex justify-between border-t border-slate-800 pt-1.5"><span>Você recebe no último provento:</span><strong class="text-emerald-400">${fmtMoney(up.estimated_next_dividend, a.currency)}</strong></div>
    `;
  } else {
    document.getElementById("sim-shares-input").value = 100;
    posBox.innerHTML = `<div class="text-slate-400">Você ainda não possui <strong>${a.ticker}</strong> cadastrado na carteira. Use o simulador abaixo para calcular quanto receberia de dividendos:</div>`;
  }
  updateDividendSimulator();

  // Official Reports & AI Interpretation
  renderAiReportSection(data.reports_data);

  // News Section
  renderAssetNewsSection(data.news);
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
  chgEl.className =
    changePct >= 0
      ? "text-xs sm:text-sm font-bold px-2.5 py-0.5 rounded-md bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
      : "text-xs sm:text-sm font-bold px-2.5 py-0.5 rounded-md bg-rose-500/15 text-rose-400 border border-rose-500/30";
  document.getElementById("detail-hover-date").textContent = dateLabel;
}

function drawInteractiveAssetChart(data) {
  const canvas = document.getElementById("asset-interactive-chart");
  if (!canvas) return;
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = (rect.width - 16) * dpr;
  canvas.height = (rect.height - 16) * dpr;

  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  const W = rect.width - 16;
  const H = rect.height - 16;

  const points = data.points || [];
  if (points.length < 2) return;

  const prices = points.map(p => p.price);
  const userPm = data.user_position && data.user_position.has_position ? data.user_position.avg_price : null;
  let minP = Math.min(...prices);
  let maxP = Math.max(...prices);
  if (userPm && userPm > 0) {
    minP = Math.min(minP, userPm * 0.98);
    maxP = Math.max(maxP, userPm * 1.02);
  }
  const padY = (maxP - minP) * 0.12 || 1.0;
  minP -= padY;
  maxP += padY;

  const padLeft = 12;
  const padRight = 58;
  const padTop = 18;
  const padBottom = 26;
  const plotW = W - padLeft - padRight;
  const plotH = H - padTop - padBottom;

  const isPositive = points[points.length - 1].price >= points[0].price;
  const mainColor = isPositive ? "#10b981" : "#f43f5e";

  function xForIdx(i) {
    return padLeft + (i / (points.length - 1)) * plotW;
  }
  function yForPrice(p) {
    return padTop + (1 - (p - minP) / (maxP - minP)) * plotH;
  }

  function renderChart(hoverIdx = null) {
    ctx.clearRect(0, 0, W, H);

    // Horizontal grid lines & right price labels
    ctx.strokeStyle = "rgba(148, 163, 184, 0.1)";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#64748b";
    ctx.font = "11px monospace";
    ctx.textAlign = "left";

    for (let g = 0; g <= 4; g++) {
      const gy = padTop + (g / 4) * plotH;
      const gp = maxP - (g / 4) * (maxP - minP);
      ctx.beginPath();
      ctx.moveTo(padLeft, gy);
      ctx.lineTo(padLeft + plotW, gy);
      ctx.stroke();
      ctx.fillText(gp.toFixed(2).replace(".", ","), padLeft + plotW + 6, gy + 4);
    }

    // X axis labels
    ctx.textAlign = "center";
    const stepX = Math.max(1, Math.floor((points.length - 1) / 5));
    for (let i = 0; i < points.length; i += stepX) {
      const lx = xForIdx(i);
      ctx.fillText(points[i].label, lx, H - 6);
    }

    // User's Average Price (Preço Médio) dashed line
    if (userPm && userPm > 0) {
      const py = yForPrice(userPm);
      ctx.save();
      ctx.setLineDash([5, 5]);
      ctx.strokeStyle = "#f59e0b";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(padLeft, py);
      ctx.lineTo(padLeft + plotW, py);
      ctx.stroke();
      ctx.fillStyle = "#fbbf24";
      ctx.font = "bold 10px sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(`Seu PM: ${userPm.toFixed(2).replace(".", ",")}`, padLeft + 6, py - 5);
      ctx.restore();
    }

    // Gradient Area Fill
    const grad = ctx.createLinearGradient(0, padTop, 0, padTop + plotH);
    grad.addColorStop(0, isPositive ? "rgba(16, 185, 129, 0.32)" : "rgba(244, 63, 94, 0.32)");
    grad.addColorStop(1, "rgba(9, 13, 22, 0.0)");

    ctx.beginPath();
    ctx.moveTo(xForIdx(0), padTop + plotH);
    points.forEach((pt, idx) => ctx.lineTo(xForIdx(idx), yForPrice(pt.price)));
    ctx.lineTo(xForIdx(points.length - 1), padTop + plotH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Price Line
    ctx.beginPath();
    points.forEach((pt, idx) => {
      const px = xForIdx(idx);
      const py = yForPrice(pt.price);
      if (idx === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.strokeStyle = mainColor;
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Hover Crosshair & Floating Tooltip
    if (hoverIdx !== null && hoverIdx >= 0 && hoverIdx < points.length) {
      const pt = points[hoverIdx];
      const hx = xForIdx(hoverIdx);
      const hy = yForPrice(pt.price);

      // Vertical crosshair line
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(hx, padTop);
      ctx.lineTo(hx, padTop + plotH);
      ctx.stroke();
      ctx.restore();

      // Highlight circle
      ctx.beginPath();
      ctx.arc(hx, hy, 5.5, 0, Math.PI * 2);
      ctx.fillStyle = mainColor;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();

      // Floating Tooltip Box on Canvas
      const tipText1 = `${fmtMoney(pt.price, data.asset.currency)}`;
      const tipText2 = `${pt.label}`;
      ctx.font = "bold 12px sans-serif";
      const tw = Math.max(ctx.measureText(tipText1).width, ctx.measureText(tipText2).width) + 20;
      const th = 40;
      let tx = hx - tw / 2;
      if (tx < padLeft) tx = padLeft;
      if (tx + tw > padLeft + plotW) tx = padLeft + plotW - tw;
      let ty = hy - th - 12;
      if (ty < 4) ty = hy + 14;

      ctx.fillStyle = "rgba(15, 23, 42, 0.95)";
      ctx.strokeStyle = mainColor;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(tx, ty, tw, th, 8);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.font = "bold 12px sans-serif";
      ctx.fillText(tipText1, tx + tw / 2, ty + 16);
      ctx.fillStyle = "#94a3b8";
      ctx.font = "11px sans-serif";
      ctx.fillText(tipText2, tx + tw / 2, ty + 32);
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
    setDetailHeaderReadout(
      pt.price,
      diffPct,
      diffAbs,
      `Data/Hora selecionada: ${pt.label}`,
      data.asset.currency
    );
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
      `Cotação Atual (${data.period}) — Passe o mouse no gráfico para inspecionar datas`,
      data.asset.currency
    );
    renderChart(null);
  };
}

function updateDividendSimulator() {
  if (!STATE.activeAssetData) return;
  const a = STATE.activeAssetData.asset;
  const qty = parseFloat(document.getElementById("sim-shares-input").value || "100");
  const investedNeeded = qty * a.last_price;
  const monthlyDiv = qty * a.last_dividend_per_share;
  document.getElementById("sim-invested-needed").textContent = fmtMoney(investedNeeded, a.currency);
  document.getElementById("sim-monthly-income").textContent = fmtMoney(monthlyDiv, a.currency);
}

function renderAiReportSection(repData) {
  const aiBox = document.getElementById("detail-ai-report-box");
  const docsList = document.getElementById("detail-official-docs-list");
  if (!repData) return;

  const ai = repData.ai_interpretation;
  if (ai) {
    const metricsHtml = (ai.key_metrics || []).map(m => `
      <div class="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800">
        <span class="text-[10px] uppercase text-slate-400 block">${m.label}</span>
        <strong class="text-xs sm:text-sm ${m.status === "good" ? "text-emerald-400" : "text-slate-100"}">${m.value}</strong>
      </div>
    `).join("");

    const bullsHtml = (ai.bullish_points || []).map(b => `<li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">✓</span><span>${b}</span></li>`).join("");
    const bearsHtml = (ai.bearish_risks || []).map(r => `<li class="flex items-start gap-2"><span class="text-amber-400 font-bold">⚠️</span><span>${r}</span></li>`).join("");

    const pdfPagesBadge = ai.pdf_pages_read && ai.pdf_pages_read > 0
      ? `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">✅ PDF Real Extraído (${ai.pdf_pages_read} págs via PyMuPDF)</span>`
      : `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-800 text-slate-300">Sincronizado B3 / CVM</span>`;

    const excerptsHtml = ai.pdf_excerpts && ai.pdf_excerpts.length > 0
      ? `
        <div class="p-3 rounded-xl bg-slate-950/90 border border-slate-800 space-y-1.5 text-xs">
          <div class="font-bold text-blue-400 text-[11px] uppercase flex items-center justify-between">
            <span>📑 Trechos Extraídos Diretamente do PDF Oficial (${ai.document_source || "B3/CVM"})</span>
            ${ai.pdf_url ? `<a href="${ai.pdf_url}" target="_blank" rel="noopener" class="text-emerald-400 hover:underline">Baixar PDF Analisado ⬇</a>` : ""}
          </div>
          <ul class="space-y-1 text-slate-300 italic text-[11px] leading-relaxed">
            ${ai.pdf_excerpts.map(ex => `<li>"…${ex}…"</li>`).join("")}
          </ul>
        </div>
      `
      : "";

    aiBox.innerHTML = `
      <div class="p-4 rounded-xl bg-slate-900/95 border border-emerald-500/30 space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="space-y-1">
            <span class="text-xs font-bold text-emerald-400 uppercase tracking-wide block">📄 ${ai.analyzed_document || "Relatório Oficial"}</span>
            <div class="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
              <span>Fonte: <strong class="text-slate-200">${repData.official_portal || ai.document_source || "B3 / CVM"}</strong></span>
              ${ai.document_date ? `<span>· Publicado em: <strong class="text-slate-200">${ai.document_date}</strong></span>` : ""}
              ${pdfPagesBadge}
            </div>
          </div>
          <span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">${ai.verdict_badge || "ANÁLISE CONCLUÍDA"}</span>
        </div>
        <p class="text-xs sm:text-sm text-slate-200 leading-relaxed">${ai.executive_summary}</p>
        ${excerptsHtml}
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">${metricsHtml}</div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 text-xs">
          <div class="p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/20">
            <div class="font-bold text-emerald-400 mb-1.5">Pontos Positivos Extraídos</div>
            <ul class="space-y-1.5 text-slate-300">${bullsHtml}</ul>
          </div>
          <div class="p-3 rounded-xl bg-amber-950/20 border border-amber-500/20">
            <div class="font-bold text-amber-400 mb-1.5">Pontos de Atenção / Riscos</div>
            <ul class="space-y-1.5 text-slate-300">${bearsHtml}</ul>
          </div>
        </div>
        <div class="p-2.5 rounded-lg bg-slate-800/80 text-xs text-slate-200 font-medium">
          🎯 <strong>${ai.dividend_guidance || ""}</strong>
        </div>
      </div>
    `;
  }

  docsList.innerHTML = (repData.reports || []).map(d => {
    const dlBtn = d.download_url
      ? `<a href="${d.download_url}" target="_blank" rel="noopener" class="px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 font-bold">Baixar PDF ⬇</a>`
      : "";
    return `
      <div class="flex flex-wrap items-center justify-between gap-2 p-3 rounded-xl bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 transition text-xs">
        <div>
          <div class="font-bold text-slate-100">${d.title}</div>
          <div class="text-[11px] text-slate-400">${d.source} · Entrega: <strong class="text-slate-300">${d.date}</strong> ${d.reference ? "(Ref: " + d.reference + ")" : ""}</div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          ${dlBtn}
          <a href="${d.url}" target="_blank" rel="noopener" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold border border-slate-700">Visualizar ↗</a>
        </div>
      </div>
    `;
  }).join("");
}

async function reanalyzeAssetReport() {
  if (!STATE.activeAssetTicker) return;
  const btn = document.getElementById("btn-reanalyze-ai");
  btn.textContent = "⏳ Lendo e interpretando relatório...";
  try {
    const res = await fetch(`/api/asset/${STATE.activeAssetTicker}/analyze-report`, { method: "POST" });
    const data = await res.json();
    if (STATE.activeAssetData && data.ai_interpretation) {
      STATE.activeAssetData.reports_data.ai_interpretation = data.ai_interpretation;
      renderAiReportSection(STATE.activeAssetData.reports_data);
    }
  } finally {
    btn.textContent = "✨ Reinterpretar Relatório";
  }
}

function renderAssetNewsSection(news) {
  if (!news) return;
  const badge = document.getElementById("detail-news-sentiment-badge");
  badge.textContent = news.overall_sentiment || "NEUTRO";
  const listEl = document.getElementById("detail-news-list");
  listEl.innerHTML = (news.items || []).map(n => {
    const sCls =
      n.sentiment === "POSITIVO"
        ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
        : n.sentiment === "NEGATIVO"
        ? "bg-rose-500/15 text-rose-400 border-rose-500/30"
        : "bg-slate-800 text-slate-300 border-slate-700";
    return `
      <a href="${n.link}" target="_blank" rel="noopener" class="block p-3 rounded-xl bg-slate-900/85 hover:bg-slate-800/90 border border-slate-800 transition space-y-1.5">
        <div class="flex items-center justify-between gap-2 text-[10px]">
          <span class="font-bold text-slate-400 uppercase">${n.source} · ${n.published}</span>
          <span class="px-2 py-0.5 rounded border font-bold ${sCls}">${n.sentiment}</span>
        </div>
        <div class="text-xs font-semibold text-slate-100 leading-snug">${n.title}</div>
      </a>
    `;
  }).join("");
}

function renderFixedIncomeView(fiList) {
  const el = document.getElementById("fixed-income-list");
  if (!fiList || fiList.length === 0) {
    el.innerHTML = `<div class="col-span-full text-center text-slate-400 p-6 text-sm">Nenhum título de Renda Fixa cadastrado.</div>`;
    return;
  }
  el.innerHTML = fiList.map(f => `
    <div class="glass-card rounded-2xl p-5 border-l-4 border-l-indigo-500 flex flex-col justify-between space-y-3">
      <div>
        <div class="flex items-start justify-between gap-2">
          <div>
            <span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300">${f.rate_label}</span>
            <h3 class="font-bold text-base text-white mt-1.5">${f.title_name}</h3>
            <p class="text-xs text-slate-400">${f.issuer} · Venc: ${f.maturity_date}</p>
          </div>
          <button onclick="deleteFixedIncome(${f.id})" title="Remover" class="text-slate-500 hover:text-rose-400 text-xs">🗑️</button>
        </div>
        <div class="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-slate-800 text-xs">
          <div>
            <span class="text-slate-400 block">Valor Aplicado:</span>
            <strong class="text-slate-200">${fmtMoney(f.invested_amount)}</strong>
          </div>
          <div>
            <span class="text-slate-400 block">Saldo Bruto Hoje:</span>
            <strong class="text-slate-200">${fmtMoney(f.gross_amount)}</strong>
          </div>
          <div>
            <span class="text-slate-400 block">Alíquota IR (${f.days_elapsed}d):</span>
            <strong class="text-amber-300">${f.tax_exempt ? "Isento (0%)" : f.ir_rate + "% (-" + fmtMoney(f.ir_tax) + ")"}</strong>
          </div>
          <div>
            <span class="text-slate-400 block">Saldo Líquido:</span>
            <strong class="text-emerald-400 text-sm font-black">${fmtMoney(f.net_amount)} (${fmtPct(f.net_profit_pct)})</strong>
          </div>
        </div>
      </div>
    </div>
  `).join("");
}

function renderDividendsView(divs) {
  const tbody = document.getElementById("dividends-tbody");
  if (!divs || divs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-slate-400">Nenhum dividendo registrado.</td></tr>`;
    return;
  }
  tbody.innerHTML = divs.map(d => `
    <tr class="hover:bg-slate-800/40">
      <td class="py-2.5 px-3 font-mono text-slate-300">${d.pay_date}</td>
      <td class="py-2.5 px-3 font-bold text-white cursor-pointer hover:text-emerald-400" onclick="openAssetDetail('${d.ticker}')">${d.ticker}</td>
      <td class="py-2.5 px-3 text-slate-300">${d.div_type}</td>
      <td class="py-2.5 px-3 text-right font-mono text-emerald-400">${fmtMoney(d.amount_per_share, d.currency)}</td>
      <td class="py-2.5 px-3 text-right font-mono text-slate-300">${d.shares_qty}</td>
      <td class="py-2.5 px-3 text-right font-mono font-bold text-emerald-400">${fmtMoney(d.total_amount, d.currency)}</td>
      <td class="py-2.5 px-3 text-center">
        <button onclick="deleteDividend(${d.id})" class="text-slate-500 hover:text-rose-400">🗑️</button>
      </td>
    </tr>
  `).join("");
}

function togglePrivacy() {
  STATE.privacyMode = !STATE.privacyMode;
  if (STATE.portfolio) {
    renderDashboard(STATE.portfolio);
    renderFixedIncomeView(STATE.portfolio.fixed_income);
    renderDividendsView(STATE.portfolio.dividends);
  }
}

function openAddInvestmentModal(type = "FII") {
  if (["CAIXINHA", "RENDA_FIXA", "TESOURO"].includes(type)) {
    openFixedIncomeModal(type);
  } else {
    openTransactionModal("", type, "", type === "STOCK_US" || type === "CRIPTO" ? "USD" : "BRL");
  }
}

function openTransactionModal(ticker = "", assetClass = "FII", price = "", currency = "BRL") {
  document.getElementById("tx-ticker").value = ticker;
  document.getElementById("tx-class").value = assetClass;
  document.getElementById("tx-price").value = price;
  document.getElementById("tx-currency").value = currency;
  document.getElementById("tx-lookup-feedback").textContent = "";
  updateTxTotalPreview();
  const m = document.getElementById("modal-transaction");
  m.classList.remove("hidden");
  m.classList.add("flex");
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

  fb.textContent = "⏳ Buscando cotação atual...";
  try {
    const res = await fetch(`/api/lookup-ticker?ticker=${encodeURIComponent(ticker)}&asset_class=${encodeURIComponent(cls)}`);
    if (res.ok) {
      const info = await res.json();
      if (info && info.last_price > 0) {
        const priceEl = document.getElementById("tx-price");
        if (!priceEl.value || parseFloat(priceEl.value) <= 0) {
          priceEl.value = info.last_price;
        }
        fb.textContent = `✓ ${info.name || info.ticker} — Cotação atual: ${fmtMoney(info.last_price, info.currency || "BRL")}`;
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
  if (el) {
    el.textContent = fmtMoney(q * p, curr);
  }
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
    alert("Preencha o Código (Ticker), Quantidade de Cotas e Preço Pago corretamente.");
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
  await refreshAll();
}

async function deleteVariablePosition(ticker) {
  if (!confirm(`Deseja remover ${ticker} da sua carteira?`)) return;
  await fetch(`/api/portfolio/position/${encodeURIComponent(ticker)}`, { method: "DELETE" });
  await refreshAll();
}

async function clearEntirePortfolio() {
  if (!confirm("Tem certeza que deseja zerar todos os investimentos da sua carteira?")) return;
  await fetch("/api/portfolio/clear", { method: "POST" });
  await refreshAll();
}

function openFixedIncomeModal(defaultCategory = "CAIXINHA") {
  const catEl = document.getElementById("fi-category");
  if (catEl && ["CAIXINHA", "RENDA_FIXA", "TESOURO", "FUNDO_INV"].includes(defaultCategory)) {
    catEl.value = defaultCategory;
  }
  if (defaultCategory === "CAIXINHA") {
    applyFixedIncomePreset("CAIXINHA_NUBANK");
  } else if (defaultCategory === "TESOURO") {
    applyFixedIncomePreset("TESOURO_IPCA");
  } else if (defaultCategory === "RENDA_FIXA") {
    applyFixedIncomePreset("CDB_CDI");
  }
  const m = document.getElementById("modal-fixed-income");
  m.classList.remove("hidden");
  m.classList.add("flex");
}

function applyFixedIncomePreset(preset) {
  const cat = document.getElementById("fi-category");
  const issuer = document.getElementById("fi-issuer");
  const name = document.getElementById("fi-name");
  const indexer = document.getElementById("fi-indexer");
  const rate = document.getElementById("fi-rate");
  const exempt = document.getElementById("fi-exempt");

  if (preset === "CAIXINHA_NUBANK") {
    cat.value = "CAIXINHA";
    issuer.value = "Nubank";
    name.value = "Caixinha Nubank (Reserva)";
    indexer.value = "CDI";
    rate.value = "100";
    exempt.checked = false;
  } else if (preset === "CAIXINHA_TURBO") {
    cat.value = "CAIXINHA";
    issuer.value = "Nubank / Mercado Pago";
    name.value = "Caixinha Turbo 110% CDI";
    indexer.value = "CDI";
    rate.value = "110";
    exempt.checked = false;
  } else if (preset === "CDB_CDI") {
    cat.value = "RENDA_FIXA";
    issuer.value = "Banco / Corretora";
    name.value = "CDB Liquidez Diária";
    indexer.value = "CDI";
    rate.value = "105";
    exempt.checked = false;
  } else if (preset === "CDB_IPCA") {
    cat.value = "RENDA_FIXA";
    issuer.value = "Banco / Corretora";
    name.value = "CDB IPCA+";
    indexer.value = "IPCA";
    rate.value = "6.8";
    exempt.checked = false;
  } else if (preset === "LCI_LCA") {
    cat.value = "RENDA_FIXA";
    issuer.value = "Banco Inter / Itaú / BB";
    name.value = "LCI / LCA Isenta de IR";
    indexer.value = "CDI";
    rate.value = "93";
    exempt.checked = true;
  } else if (preset === "TESOURO_IPCA") {
    cat.value = "TESOURO";
    issuer.value = "Tesouro Nacional";
    name.value = "Tesouro IPCA+ 2029";
    indexer.value = "IPCA";
    rate.value = "6.45";
    exempt.checked = false;
  } else if (preset === "TESOURO_SELIC") {
    cat.value = "TESOURO";
    issuer.value = "Tesouro Nacional";
    name.value = "Tesouro Selic";
    indexer.value = "SELIC";
    rate.value = "0.10";
    exempt.checked = false;
  }
  updateFiIndexerHint();
}

function updateFiIndexerHint() {
  const idx = document.getElementById("fi-indexer").value;
  const lbl = document.getElementById("fi-rate-label");
  if (!lbl) return;
  if (idx === "CDI") lbl.textContent = "Taxa (% do CDI — ex: 100 p/ 100% CDI)";
  else if (idx === "IPCA") lbl.textContent = "Taxa Fixa Acima do IPCA (% a.a. — ex: 6.5)";
  else if (idx === "SELIC") lbl.textContent = "Taxa Extra + Selic (% a.a. — ex: 0.1)";
  else lbl.textContent = "Taxa Prefixada (% ao ano — ex: 12.5)";
}

async function submitFixedIncome() {
  const category = document.getElementById("fi-category") ? document.getElementById("fi-category").value : "RENDA_FIXA";
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
  if (payload.invested_amount <= 0) {
    alert("Informe o valor aplicado em R$.");
    return;
  }
  await fetch("/api/fixed-income", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  document.getElementById("fi-amount").value = "";
  closeModal("modal-fixed-income");
  await refreshAll();
}

async function deleteFixedIncome(id) {
  if (!confirm("Deseja remover este título/caixinha da sua carteira?")) return;
  await fetch(`/api/fixed-income/${id}`, { method: "DELETE" });
  await refreshAll();
}

function openDividendModal() {
  const m = document.getElementById("modal-dividend");
  m.classList.remove("hidden");
  m.classList.add("flex");
}

async function submitDividend() {
  const payload = {
    ticker: document.getElementById("div-ticker").value.trim().toUpperCase(),
    pay_date: document.getElementById("div-date").value,
    amount_per_share: parseFloat(document.getElementById("div-per-share").value || "0"),
    shares_qty: parseFloat(document.getElementById("div-qty").value || "0"),
  };
  if (!payload.ticker || payload.amount_per_share <= 0 || payload.shares_qty <= 0) {
    alert("Preencha os dados do provento corretamente.");
    return;
  }
  await fetch("/api/dividends", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  closeModal("modal-dividend");
  await refreshAll();
}

async function deleteDividend(id) {
  await fetch(`/api/dividends/${id}`, { method: "DELETE" });
  await refreshAll();
}

async function openMobileModal() {
  const res = await fetch("/api/system/mobile-access");
  const data = await res.json();
  document.getElementById("mobile-url-box").textContent = data.mobile_url;
  document.getElementById("mobile-qr-img").src = data.qr_api_url;
  const m = document.getElementById("modal-mobile");
  m.classList.remove("hidden");
  m.classList.add("flex");
}

function closeModal(id) {
  const m = document.getElementById(id);
  m.classList.add("hidden");
  m.classList.remove("flex");
}

window.addEventListener("DOMContentLoaded", initApp);

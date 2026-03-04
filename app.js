// Backend URL
const API = "https://bekzod-1.onrender.com/";

const el = (id) => document.getElementById(id);
const money = (n) => (Number(n || 0)).toLocaleString("uz-UZ");

let cachedProducts = [];

function setStatus(ok, text) {
  const s = el("apiStatus");
  s.textContent = text;
  s.style.opacity = ok ? "1" : "0.7";
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  return res.json();
}

async function ping() {
  try {
    const r = await api("/");
    setStatus(true, "API: OK");
    return r;
  } catch (e) {
    setStatus(false, "API: OFF");
    return null;
  }
}

function renderProducts(list) {
  const box = el("productsList");
  box.innerHTML = "";

  list.forEach((p) => {
    const div = document.createElement("div");
    div.className = "item";
    div.innerHTML = `
      <div>
        <div class="name">${p.name || "—"}</div>
        <div class="meta">Qoldiq: <b>${p.stockQty ?? 0}</b> | Sotish: <b>${money(p.sellPrice)}</b> | Tannarx(avg): <b>${money(p.averageCost)}</b></div>
      </div>
      <button class="btn" data-del="${p._id}">O'chirish</button>
    `;
    box.appendChild(div);
  });

  box.querySelectorAll("button[data-del]").forEach((b) => {
    b.addEventListener("click", async () => {
      const id = b.getAttribute("data-del");
      await api(`/products/${id}`, { method: "DELETE" });
      await loadProducts();
    });
  });
}

function fillSelects(products) {
  const makeOptions = (selId) => {
    const sel = el(selId);
    sel.innerHTML = `<option value="">Mahsulot tanlang</option>`;
    products.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p._id;
      opt.textContent = `${p.name} (qoldiq: ${p.stockQty ?? 0})`;
      sel.appendChild(opt);
    });
  };

  makeOptions("inProduct");
  makeOptions("saleProduct");
}

async function loadProducts() {
  cachedProducts = await api("/products");
  renderProducts(cachedProducts);
  fillSelects(cachedProducts);
}

function setupTabs() {
  const tabs = document.querySelectorAll(".tab");
  tabs.forEach((t) => {
    t.addEventListener("click", () => {
      tabs.forEach((x) => x.classList.remove("active"));
      t.classList.add("active");

      const name = t.dataset.tab;
      ["products","stockin","sale","reports"].forEach((k) => {
        el("tab-" + k).classList.toggle("hidden", k !== name);
      });
    });
  });
}

function setupTelegram() {
  const tg = window.Telegram?.WebApp;
  if (!tg) return;

  tg.ready();
  tg.expand();

  const u = tg.initDataUnsafe?.user;
  if (u) el("tgUser").textContent = `Telegram: ${u.first_name || ""} ${u.last_name || ""} (@${u.username || ""})`;
}

async function main() {
  setupTabs();
  setupTelegram();

  await ping();
  await loadProducts();

  el("btnRefresh").addEventListener("click", loadProducts);

  el("btnAddProduct").addEventListener("click", async () => {
    const name = el("pName").value.trim();
    const sellPrice = Number(el("pSell").value || 0);

    if (!name) return alert("Mahsulot nomini kiriting");

    await api("/products", {
      method: "POST",
      body: JSON.stringify({ name, sellPrice }),
    });

    el("pName").value = "";
    el("pSell").value = "";
    await loadProducts();
  });

  el("btnStockIn").addEventListener("click", async () => {
    const productId = el("inProduct").value;
    const qty = Number(el("inQty").value || 0);
    const buyPrice = Number(el("inBuy").value || 0);

    if (!productId) return alert("Mahsulot tanlang");
    if (qty <= 0) return alert("Miqdor > 0 bo‘lsin");
    if (buyPrice < 0) return alert("Kirim narxi xato");

    const r = await api("/stock-in", {
      method: "POST",
      body: JSON.stringify({ items: [{ productId, qty, buyPrice }] }),
    });

    el("inResult").textContent = `✅ Kirim: ${JSON.stringify(r)}`;
    el("inQty").value = "";
    el("inBuy").value = "";
    await loadProducts();
  });

  el("btnSale").addEventListener("click", async () => {
    const productId = el("saleProduct").value;
    const qty = Number(el("saleQty").value || 0);
    const sellPrice = Number(el("salePrice").value || 0);

    if (!productId) return alert("Mahsulot tanlang");
    if (qty <= 0) return alert("Miqdor > 0 bo‘lsin");

    const r = await api("/sales", {
      method: "POST",
      body: JSON.stringify({ items: [{ productId, qty, sellPrice }], paymentType: "cash" }),
    });

    if (r.error) {
      el("saleResult").textContent = `❌ Xato: ${JSON.stringify(r)}`;
      return;
    }

    el("saleResult").textContent = `✅ Sotuv: tushum=${money(r.totals.totalRevenue)} foyda=${money(r.totals.totalProfit)}`;
    el("saleQty").value = "";
    el("salePrice").value = "";
    await loadProducts();
  });

  // auto set year/month
  const now = new Date();
  el("repYear").value = now.getFullYear();
  el("repMonth").value = now.getMonth() + 1;

  el("btnReport").addEventListener("click", async () => {
    const year = Number(el("repYear").value);
    const month = Number(el("repMonth").value);

    const r = await api(`/reports/monthly?year=${year}&month=${month}`);

    el("kRevenue").textContent = money(r.revenue);
    el("kCost").textContent = money(r.cost);
    el("kProfit").textContent = money(r.profit);
    el("kCount").textContent = r.salesCount ?? 0;
  });
}


main();






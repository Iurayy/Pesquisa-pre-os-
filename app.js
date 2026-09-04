const API_URL = "[https://alerta-precos.onrender.com/analyze](https://alerta-precos.onrender.com/analyze)";

let folders = JSON.parse(localStorage.getItem("setup_folders_v3")) || [
  {
    id: "folder_default",
    name: "Setup Ryzen AM5",
    budget: 6000.0,
    items: [
      { category: "CPU", target_spec: "AMD Ryzen 5 7600 ou similar" },
      { category: "GPU", target_spec: "RX 9060 XT 16GB ou similar" },
      { category: "RAM", target_spec: "32GB DDR5 6000MHz" }
    ],
    analysisResult: null
  }
];

let activeFolderId = folders[0].id;
let currentView = "comparison";

function saveFolders() {
  localStorage.setItem("setup_folders_v3", JSON.stringify(folders));
}

function getActiveFolder() {
  return folders.find(f => f.id === activeFolderId) || folders[0];
}

function switchView(viewName) {
  currentView = viewName;
  document.getElementById("tabBtnComparison").classList.toggle("active", viewName === "comparison");
  document.getElementById("tabBtnSpecs").classList.toggle("active", viewName === "specs");
  document.getElementById("viewComparison").classList.toggle("active", viewName === "comparison");
  document.getElementById("viewSpecs").classList.toggle("active", viewName === "specs");
}

function renderFolders() {
  const list = document.getElementById("folderList");
  list.innerHTML = "";
  folders.forEach(f => {
    const li = document.createElement("li");
    li.className = `folder-item ${f.id === activeFolderId ? "active" : ""}`;
    li.innerHTML = `<span>📁 ${f.name}</span>`;
    li.onclick = () => {
      activeFolderId = f.id;
      renderFolders();
      loadActiveFolder();
      document.getElementById("sidebarLeft").classList.remove("open");
    };
    list.appendChild(li);
  });
}

function loadActiveFolder() {
  const f = getActiveFolder();
  document.getElementById("currentFolderTitle").textContent = f.name;
  document.getElementById("mobileFolderLabel").textContent = f.name;
  document.getElementById("budgetInput").value = f.budget;
  document.getElementById("accordionCount").textContent = f.items.length;

  const chipList = document.getElementById("configuredItemsList");
  chipList.innerHTML = "";
  f.items.forEach((it, idx) => {
    const li = document.createElement("li");
    li.className = "chip";
    li.innerHTML = `<strong>${it.category}:</strong> ${it.target_spec} <span onclick="removeConfiguredItem(${idx})">&times;</span>`;
    chipList.appendChild(li);
  });

  renderComparisonView(f.analysisResult);
  renderSpecsView(f.analysisResult);
  updateBudgetSidebar();
}

function removeConfiguredItem(index) {
  const f = getActiveFolder();
  f.items.splice(index, 1);
  saveFolders();
  loadActiveFolder();
}

function renderComparisonView(result) {
  const container = document.getElementById("componentsContainer");
  const reportBox = document.getElementById("reportContent");
  container.innerHTML = "";

  if (!result || !result.items || result.items.length === 0) {
    container.innerHTML = `<div class="empty-state"><p>Nenhum produto analisado ainda. Adicione itens acima e clique em <strong>"Pesquisar com IA"</strong>.</p></div>`;
    reportBox.textContent = "Aguardando pesquisa...";
    return;
  }

  reportBox.textContent = result.summary_report || "Sem parecer disponível.";

  result.items.forEach((item, itemIdx) => {
    const card = document.createElement("div");
    card.className = "comp-card";

    const mainBox = document.createElement("div");
    mainBox.className = "main-product-box";
    mainBox.innerHTML = `
      <div class="main-info">
        <span class="cat-tag">${item.category}</span>
        <h4>${item.name}</h4>
        <a href="${item.store_url || '#'}" target="_blank" rel="noopener noreferrer" class="btn-store">
          🛒 Ir para Loja ↗
        </a>
      </div>
      <div class="main-price-wrap">
        <span class="main-price">R$ ${Number(item.price || 0).toFixed(2)}</span>
      </div>
    `;

    mainBox.ondragover = (e) => { e.preventDefault(); mainBox.classList.add("drag-over"); };
    mainBox.ondragleave = () => mainBox.classList.remove("drag-over");
    mainBox.ondrop = (e) => {
      e.preventDefault();
      mainBox.classList.remove("drag-over");
      const simData = JSON.parse(e.dataTransfer.getData("application/json"));
      swapWithSimilar(itemIdx, simData);
    };

    card.appendChild(mainBox);

    if (item.similars && item.similars.length > 0) {
      const simWrap = document.createElement("div");
      simWrap.className = "similars-container";
      simWrap.innerHTML = `<span class="similars-heading">Alternativas Similares em ${item.category}:</span>`;

      item.similars.forEach(sim => {
        const simEl = document.createElement("div");
        simEl.className = "similar-card";
        simEl.draggable = true;
        simEl.innerHTML = `
          <div>
            <div class="similar-title">${sim.name}</div>
            <div class="similar-note">${sim.note || ""}</div>
          </div>
          <div class="similar-actions">
            <span class="similar-price">R$ ${Number(sim.price || 0).toFixed(2)}</span>
            <a href="${sim.store_url || '#'}" target="_blank" rel="noopener noreferrer" class="btn-store">Loja ↗</a>
            <button type="button" class="btn-swap" onclick='swapWithSimilar(${itemIdx}, ${JSON.stringify(sim).replace(/'/g, "&apos;")})'>⇄ Usar</button>
          </div>
        `;
        simEl.ondragstart = (e) => {
          e.dataTransfer.setData("application/json", JSON.stringify(sim));
        };
        simWrap.appendChild(simEl);
      });
      card.appendChild(simWrap);
    }

    container.appendChild(card);
  });
}

function swapWithSimilar(itemIdx, simData) {
  const f = getActiveFolder();
  const item = f.analysisResult.items[itemIdx];

  const oldMain = {
    name: item.name,
    price: item.price,
    store_url: item.store_url,
    note: "Substituído anteriormente",
    specs: item.specs || []
  };

  item.name = simData.name;
  item.price = simData.price;
  item.store_url = simData.store_url;
  item.specs = simData.specs || item.specs;

  item.similars.push(oldMain);
  item.similars = item.similars.filter(s => s.name !== simData.name);

  saveFolders();
  renderComparisonView(f.analysisResult);
  renderSpecsView(f.analysisResult);
  updateBudgetSidebar();
}

function renderSpecsView(result) {
  const container = document.getElementById("specsContainer");
  container.innerHTML = "";

  if (!result || !result.items || result.items.length === 0) {
    container.innerHTML = `<div class="empty-state"><p>Execute uma pesquisa para visualizar as especificações técnicas.</p></div>`;
    return;
  }

  result.items.forEach(item => {
    const card = document.createElement("div");
    card.className = "spec-card";

    let icon = "📦";
    const catUpper = (item.category || "").toUpperCase();
    if (catUpper.includes("CPU") || catUpper.includes("PROCESSADOR")) icon = "⚡";
    else if (catUpper.includes("GPU") || catUpper.includes("VÍDEO") || catUpper.includes("VIDEO")) icon = "🎮";
    else if (catUpper.includes("RAM") || catUpper.includes("MEMÓRIA")) icon = "🧠";
    else if (catUpper.includes("MONITOR")) icon = "🖥️";
    else if (catUpper.includes("FONTE")) icon = "🔌";
    else if (catUpper.includes("SSD") || catUpper.includes("HD")) icon = "💾";

    const specsHtml = (item.specs || [
      "Categoria: " + item.category,
      "Preço de referência: R$ " + Number(item.price || 0).toFixed(2),
      "Disponível no mercado nacional"
    ]).map(s => `<li>${s}</li>`).join("");

    card.innerHTML = `
      <div class="spec-header">
        <div>
          <span class="cat-tag">${item.category}</span>
          <h4>${item.name}</h4>
        </div>
        <a href="${item.store_url || '#'}" target="_blank" rel="noopener noreferrer" class="btn-store">Ver Loja ↗</a>
      </div>
      <div class="spec-image-box">
        <span>${icon}</span>
        <span class="spec-image-label">${item.category}</span>
      </div>
      <ul class="spec-list">
        ${specsHtml}
      </ul>
    `;
    container.appendChild(card);
  });
}

function updateBudgetSidebar() {
  const f = getActiveFolder();
  const budget = parseFloat(document.getElementById("budgetInput").value) || 0;
  f.budget = budget;
  saveFolders();

  let total = 0;
  const list = document.getElementById("selectedSummaryList");
  list.innerHTML = "";

  if (f.analysisResult && f.analysisResult.items) {
    f.analysisResult.items.forEach(it => {
      total += Number(it.price || 0);
      const li = document.createElement("li");
      li.innerHTML = `<span>${(it.name || "").substring(0, 22)}...</span><strong>R$ ${Number(it.price || 0).toFixed(2)}</strong>`;
      list.appendChild(li);
    });
  }

  const remaining = budget - total;
  document.getElementById("totalCurrentPrice").textContent = `R$ ${total.toFixed(2)}`;

  const remEl = document.getElementById("remainingBalance");
  remEl.textContent = `R$ ${remaining.toFixed(2)}`;
  remEl.style.color = remaining < 0 ? "var(--danger)" : "var(--success)";

  const pct = budget > 0 ? Math.min((total / budget) * 100, 100) : 0;
  document.getElementById("progressPercent").textContent = `${Math.round(budget > 0 ? (total / budget) * 100 : 0)}%`;

  const progressEl = document.getElementById("budgetProgress");
  progressEl.style.width = `${pct}%`;
  progressEl.style.background = remaining < 0 ? "var(--danger)" : "var(--success)";
}

document.getElementById("toggleFoldersMobile").onclick = () => {
  document.getElementById("sidebarLeft").classList.toggle("open");
  document.getElementById("sidebarRight").classList.remove("open");
};
document.getElementById("toggleBudgetMobile").onclick = () => {
  document.getElementById("sidebarRight").classList.toggle("open");
  document.getElementById("sidebarLeft").classList.remove("open");
};

document.getElementById("newFolderBtn").addEventListener("click", () => {
  const name = prompt("Nome da pasta/projeto (ex: Câmera & Lentes, Teclados Custom):");
  if (name) {
    const newId = `folder_${Date.now()}`;
    folders.push({
      id: newId,
      name: name,
      budget: 5000.0,
      items: [],
      analysisResult: null
    });
    activeFolderId = newId;
    saveFolders();
    renderFolders();
    loadActiveFolder();
  }
});

document.getElementById("addSpecBtn").addEventListener("click", () => {
  const cat = document.getElementById("inputCat").value.trim();
  const spec = document.getElementById("inputSpec").value.trim();
  if (cat && spec) {
    const f = getActiveFolder();
    f.items.push({ category: cat, target_spec: spec });
    document.getElementById("inputCat").value = "";
    document.getElementById("inputSpec").value = "";
    saveFolders();
    loadActiveFolder();
  }
});

document.getElementById("budgetInput").addEventListener("input", updateBudgetSidebar);

document.getElementById("runAnalysisBtn").addEventListener("click", async () => {
  const f = getActiveFolder();
  if (f.items.length === 0) return alert("Adicione pelo menos um produto para pesquisar!");

  const btn = document.getElementById("runAnalysisBtn");
  const spinner = document.getElementById("loadingSpinner");
  const btnText = document.getElementById("runBtnText");

  btn.disabled = true;
  spinner.classList.remove("hidden");
  btnText.textContent = "Pesquisando...";

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        folder_name: f.name,
        total_budget: f.budget,
        items: f.items,
        notify_telegram: true
      })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Erro HTTP ${res.status}`);
    const data = await res.json();
    f.analysisResult = data;
    saveFolders();
    renderComparisonView(data);
    renderSpecsView(data);
    updateBudgetSidebar();
  } } catch (err) {
    console.error("Detalhes do erro:", err);
    alert("Erro retornado pelo servidor:\n" + err.message);
  } finally {
    btn.disabled = false;
    spinner.classList.add("hidden");
    btnText.textContent = "Pesquisar com IA";
  }
});

renderFolders();
loadActiveFolder();

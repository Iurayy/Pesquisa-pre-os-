const API_URL = "https://alerta-precos.onrender.com/analyze";

let folders = JSON.parse(localStorage.getItem("setup_folders")) || [
  {
    id: "folder_1",
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

function saveFolders() {
  localStorage.setItem("setup_folders", JSON.stringify(folders));
}

function getActiveFolder() {
  return folders.find(f => f.id === activeFolderId);
}

// RENDERIZAR PASTAS NA ESQUERDA
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
    };
    list.appendChild(li);
  });
}

// CARREGAR CONTEÚDO DA PASTA ATIVA
function loadActiveFolder() {
  const f = getActiveFolder();
  document.getElementById("currentFolderTitle").textContent = f.name;
  document.getElementById("budgetInput").value = f.budget;
  document.getElementById("accordionCount").textContent = f.items.length;

  // Lista configurada
  const chipList = document.getElementById("configuredItemsList");
  chipList.innerHTML = "";
  f.items.forEach((it, idx) => {
    const li = document.createElement("li");
    li.className = "chip";
    li.innerHTML = `<strong>${it.category}:</strong> ${it.target_spec} <span onclick="removeConfiguredItem(${idx})">&times;</span>`;
    chipList.appendChild(li);
  });

  renderComponents(f.analysisResult);
  updateRightSidebar();
}

function removeConfiguredItem(index) {
  const f = getActiveFolder();
  f.items.splice(index, 1);
  saveFolders();
  loadActiveFolder();
}

// RENDERIZAR COMPONENTES E SIMILARES
function renderComponents(result) {
  const container = document.getElementById("componentsContainer");
  const reportBox = document.getElementById("reportContent");
  container.innerHTML = "";

  if (!result || !result.items) {
    reportBox.textContent = "Clique em 'Atualizar com IA' para buscar os componentes e similares.";
    return;
  }

  reportBox.textContent = result.summary_report || "Sem relatório disponível.";

  result.items.forEach((item, itemIdx) => {
    const card = document.createElement("div");
    card.className = "comp-card";

    // Dropzone do item principal
    const dropZone = document.createElement("div");
    dropZone.className = "drop-zone-main";
    dropZone.innerHTML = `
      <div class="main-info">
        <span class="cat-tag">${item.category}</span>
        <h4>${item.name}</h4>
      </div>
      <div class="main-price">R$ ${item.price.toFixed(2)}</div>
    `;

    // Eventos Drag & Drop
    dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); };
    dropZone.ondragleave = () => dropZone.classList.remove("drag-over");
    dropZone.ondrop = (e) => {
      e.preventDefault();
      dropZone.classList.remove("drag-over");
      const simData = JSON.parse(e.dataTransfer.getData("application/json"));
      
      // Troca item principal pelo similar
      const oldMain = { name: item.name, price: item.price, note: "Substituído" };
      item.name = simData.name;
      item.price = simData.price;
      
      // Coloca o antigo nos similares
      item.similars.push(oldMain);
      item.similars = item.similars.filter(s => s.name !== simData.name);

      saveFolders();
      renderComponents(result);
      updateRightSidebar();
    };

    card.appendChild(dropZone);

    // Lista de Similares
    if (item.similars && item.similars.length > 0) {
      const simWrap = document.createElement("div");
      simWrap.className = "similars-wrap";
      simWrap.innerHTML = `<span class="similars-title">Similares (Arraste para cima para trocar):</span>`;

      item.similars.forEach(sim => {
        const simEl = document.createElement("div");
        simEl.className = "similar-item";
        simEl.draggable = true;
        simEl.innerHTML = `
          <div><strong>${sim.name}</strong> <small style="color:#8b949e">(${sim.note || ""})</small></div>
          <div><strong>R$ ${sim.price.toFixed(2)}</strong></div>
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

// ATUALIZAR SIDEBAR DIREITA (TOTALIZADOR EM TEMPO REAL)
function updateRightSidebar() {
  const f = getActiveFolder();
  const budget = parseFloat(document.getElementById("budgetInput").value) || 0;
  f.budget = budget;
  saveFolders();

  let total = 0;
  const list = document.getElementById("selectedSummaryList");
  list.innerHTML = "";

  if (f.analysisResult && f.analysisResult.items) {
    f.analysisResult.items.forEach(it => {
      total += it.price;
      const li = document.createElement("li");
      li.innerHTML = `<span>${it.category}</span><strong>R$ ${it.price.toFixed(2)}</strong>`;
      list.appendChild(li);
    });
  }

  const remaining = budget - total;
  document.getElementById("totalCurrentPrice").textContent = `R$ ${total.toFixed(2)}`;
  
  const remEl = document.getElementById("remainingBalance");
  remEl.textContent = `R$ ${remaining.toFixed(2)}`;
  remEl.style.color = remaining < 0 ? "var(--danger)" : "var(--success)";

  const pct = budget > 0 ? Math.min((total / budget) * 100, 100) : 0;
  const progressEl = document.getElementById("budgetProgress");
  progressEl.style.width = `${pct}%`;
  progressEl.style.background = remaining < 0 ? "var(--danger)" : "var(--success)";
}

// CRIAR NOVA PASTA
document.getElementById("newFolderBtn").addEventListener("click", () => {
  const name = prompt("Nome da nova pasta/projeto:");
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

// ADICIONAR ITEM NA LISTA
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

// ALTERAR ORÇAMENTO
document.getElementById("budgetInput").addEventListener("input", () => {
  updateRightSidebar();
});

// DISPARAR CONSULTA IA
document.getElementById("runAnalysisBtn").addEventListener("click", async () => {
  const f = getActiveFolder();
  if (f.items.length === 0) return alert("Adicione ao menos um item nesta pasta!");

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
    const data = await res.json();
    f.analysisResult = data;
    saveFolders();
    renderComponents(data);
    updateRightSidebar();
  } catch (err) {
    alert("Erro ao consultar a IA. Tente novamente.");
  } finally {
    btn.disabled = false;
    spinner.classList.add("hidden");
    btnText.textContent = "Atualizar com IA";
  }
});

// INICIALIZAR
renderFolders();
loadActiveFolder();

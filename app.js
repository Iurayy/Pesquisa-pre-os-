const API_URL = "https://alerta-precos.onrender.com/analyze";

let items = [
  { category: "CPU", target_spec: "AMD Ryzen 5 7600 ou similar" },
  { category: "GPU", target_spec: "RX 9060 XT 16GB ou similar" },
  { category: "RAM", target_spec: "32GB DDR5 6000MHz" }
];

const itemsList = document.getElementById("itemsList");
const itemCount = document.getElementById("itemCount");
const addItemBtn = document.getElementById("addItemBtn");
const itemCategory = document.getElementById("itemCategory");
const itemSpec = document.getElementById("itemSpec");
const analyzeBtn = document.getElementById("analyzeBtn");
const btnSpinner = document.getElementById("btnSpinner");
const resultSection = document.getElementById("resultSection");
const resultContent = document.getElementById("resultContent");

function renderItems() {
  itemsList.innerHTML = "";
  items.forEach((item, index) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <div><strong>${item.category}:</strong> ${item.target_spec}</div>
      <button onclick="removeItem(${index})">&times;</button>
    `;
    itemsList.appendChild(li);
  });
  itemCount.textContent = `${items.length} itens`;
}

function removeItem(index) {
  items.splice(index, 1);
  renderItems();
}

addItemBtn.addEventListener("click", () => {
  const cat = itemCategory.value.trim();
  const spec = itemSpec.value.trim();
  if (cat && spec) {
    items.push({ category: cat, target_spec: spec });
    itemCategory.value = "";
    itemSpec.value = "";
    renderItems();
  }
});

analyzeBtn.addEventListener("click", async () => {
  if (items.length === 0) return alert("Adicione ao menos um item!");

  analyzeBtn.disabled = true;
  btnSpinner.style.display = "inline-block";

  const payload = {
    folder_name: document.getElementById("folderName").value,
    total_budget: parseFloat(document.getElementById("totalBudget").value) || 0,
    items: items,
    notify_telegram: document.getElementById("notifyTelegram").checked
  };

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    resultContent.textContent = data.analysis;
    resultSection.classList.remove("hidden");
    resultSection.scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    alert("Erro ao consultar a API. Tente novamente.");
  } finally {
    analyzeBtn.disabled = false;
    btnSpinner.style.display = "none";
  }
});

renderItems();

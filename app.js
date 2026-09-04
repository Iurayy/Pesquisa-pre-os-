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

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || `Erro HTTP ${res.status}`);
    }

    f.analysisResult = data;
    saveFolders();
    renderComparisonView(data);
    renderSpecsView(data);
    updateBudgetSidebar();
  } catch (err) {
    console.error("Erro na consulta:", err);
    alert("Erro retornado pelo servidor:\n" + err.message);
  } finally {
    btn.disabled = false;
    spinner.classList.add("hidden");
    btnText.textContent = "Pesquisar com IA";
  }
});

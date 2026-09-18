import { api } from "./api.js";
import { MapManager } from "./map.js";

document.addEventListener("DOMContentLoaded", () => {
  const mapManager = new MapManager("map");

  // ==========================================
  // ELEMENTOS DOM
  // ==========================================
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  // Consulta Unitária
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("search-input");
  const searchNumberInput = document.getElementById("search-number-input");
  const searchBtn = document.getElementById("search-btn");
  const btnGps = document.getElementById("btn-gps");

  // Resultado
  const resultContainer = document.getElementById("result-container");
  const resultBadge = document.getElementById("result-badge");
  const resultTitle = document.getElementById("result-title");
  const resultDesc = document.getElementById("result-desc");
  const metaTech = document.getElementById("meta-tech");
  const metaPop = document.getElementById("meta-pop");
  const metaRegion = document.getElementById("meta-region");
  const metaDistance = document.getElementById("meta-distance");

  // Lote
  const dropzone = document.getElementById("dropzone");
  const fileBatchInput = document.getElementById("file-batch-input");
  const progressContainer = document.getElementById("progress-container");
  const progressBarFill = document.getElementById("progress-bar-fill");
  const progressText = document.getElementById("progress-text");
  const progressPercent = document.getElementById("progress-percent");
  const countViable = document.getElementById("count-viable");
  const countAnalysis = document.getElementById("count-analysis");
  const countUnviable = document.getElementById("count-unviable");
  const batchDownloadBtn = document.getElementById("batch-download-btn");

  // Camadas (Manchas)
  const layersListContainer = document.getElementById("layers-list-container");
  const layerUploadForm = document.getElementById("layer-upload-form");
  const layerFileInput = document.getElementById("layer-file-input");
  const layerNameInput = document.getElementById("layer-name-input");
  const layerTechSelect = document.getElementById("layer-tech-select");
  const layerPopSelect = document.getElementById("layer-pop-select");
  const layerUploadBtn = document.getElementById("layer-upload-btn");

  // POPs
  const popsListContainer = document.getElementById("pops-list-container");
  const popCreateForm = document.getElementById("pop-create-form");

  // ==========================================
  // CARREGAR DADOS INICIAIS
  // ==========================================
  async function loadCoverageLayers() {
    try {
      const geojson = await api.getLayersGeoJSON();
      mapManager.renderCoverage(geojson);
      await renderLayersList();
    } catch (err) {
      console.error("Erro ao carregar coberturas:", err);
    }
  }

  async function renderLayersList() {
    try {
      const layers = await api.getLayers();
      layersListContainer.innerHTML = "";

      if (layers.length === 0) {
        layersListContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 0.5rem 0;">Nenhuma mancha cadastrada.</div>`;
        return;
      }

      layers.forEach(layer => {
        const item = document.createElement("div");
        item.className = "layer-item";
        item.innerHTML = `
          <div class="layer-info" style="flex: 1; min-width: 0;">
            <div class="layer-color-dot" style="background-color: ${layer.color};"></div>
            <div style="min-width: 0;">
              <div class="layer-title" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${layer.name}</div>
              <div class="layer-subtitle">${layer.technology} • ${layer.polygon_count} polígono(s)${layer.pop_name ? ` • POP: ${layer.pop_name}` : ''}</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 0.75rem; margin-left: 0.5rem;">
            <label class="switch" title="${layer.enabled ? 'Clique para desativar' : 'Clique para ativar'}">
              <input type="checkbox" class="layer-toggle-checkbox" data-id="${layer.id}" ${layer.enabled ? 'checked' : ''}>
              <span class="slider"></span>
            </label>
            <button type="button" class="btn-icon-danger btn-delete-layer" data-id="${layer.id}" data-name="${layer.name}" title="Excluir mancha">
              <i class="fa-solid fa-trash-can"></i>
            </button>
          </div>
        `;
        layersListContainer.appendChild(item);
      });

      // Eventos de toggle (ativar/desativar)
      layersListContainer.querySelectorAll(".layer-toggle-checkbox").forEach(cb => {
        cb.addEventListener("change", async (e) => {
          const layerId = e.target.dataset.id;
          try {
            await api.toggleLayer(layerId);
            const geojson = await api.getLayersGeoJSON();
            mapManager.renderCoverage(geojson);
          } catch (err) {
            alert(`Falha ao alterar status da camada: ${err.message}`);
            e.target.checked = !e.target.checked;
          }
        });
      });

      // Eventos de exclusão de camada
      layersListContainer.querySelectorAll(".btn-delete-layer").forEach(btn => {
        btn.addEventListener("click", async (e) => {
          const btnEl = e.currentTarget;
          const layerId = btnEl.dataset.id;
          const layerName = btnEl.dataset.name;

          if (confirm(`Deseja realmente remover a mancha "${layerName}" do sistema?`)) {
            try {
              await api.deleteLayer(layerId);
              await loadCoverageLayers();
            } catch (err) {
              alert(`Falha ao excluir camada: ${err.message}`);
            }
          }
        });
      });

    } catch (err) {
      console.error(err);
    }
  }

  // ==========================================
  // GESTÃO DE POPS (PONTOS DE PRESENÇA)
  // ==========================================
  async function loadPops() {
    try {
      const pops = await api.getPops();
      mapManager.renderPops(pops);
      renderPopsList(pops);
      populatePopSelect(pops);
    } catch (err) {
      console.error("Erro ao carregar POPs:", err);
    }
  }

  function renderPopsList(pops) {
    if (!popsListContainer) return;
    popsListContainer.innerHTML = "";

    if (pops.length === 0) {
      popsListContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 0.5rem 0;">Nenhum POP cadastrado no momento.</div>`;
      return;
    }

    pops.forEach(pop => {
      const card = document.createElement("div");
      card.className = "pop-card";
      card.innerHTML = `
        <div class="pop-info">
          <div class="pop-name">
            <span>${pop.name}</span>
            <span class="pop-badge">${pop.technology || 'GPON'}</span>
          </div>
          <div class="pop-detail">
            ${pop.city ? `<strong>Cidade:</strong> ${pop.city} • ` : ''}
            ${pop.capacity ? `<strong>Capacidade:</strong> ${pop.capacity}<br/>` : ''}
            ${pop.address ? `<strong>Endereço:</strong> ${pop.address}<br/>` : ''}
            <span style="color: #64748b; font-size: 0.7rem;">Lat: ${pop.latitude.toFixed(4)}, Lon: ${pop.longitude.toFixed(4)}</span>
          </div>
        </div>
        <button type="button" class="btn-icon-danger btn-delete-pop" data-id="${pop.id}" data-name="${pop.name}" title="Excluir POP">
          <i class="fa-solid fa-trash-can"></i>
        </button>
      `;
      popsListContainer.appendChild(card);
    });

    // Eventos de exclusão de POP
    popsListContainer.querySelectorAll(".btn-delete-pop").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const btnEl = e.currentTarget;
        const popId = btnEl.dataset.id;
        const popName = btnEl.dataset.name;

        if (confirm(`Deseja realmente excluir o POP "${popName}"?`)) {
          try {
            await api.deletePop(popId);
            await loadPops();
          } catch (err) {
            alert(`Falha ao excluir POP: ${err.message}`);
          }
        }
      });
    });
  }

  function populatePopSelect(pops) {
    if (!layerPopSelect) return;
    layerPopSelect.innerHTML = `<option value="">-- Selecione um POP (Opcional) --</option>`;
    pops.forEach(pop => {
      const opt = document.createElement("option");
      opt.value = pop.id;
      opt.textContent = `${pop.name} (${pop.city || 'Sem cidade'})`;
      layerPopSelect.appendChild(opt);
    });
  }

  if (popCreateForm) {
    popCreateForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("pop-name-input").value.trim();
      const city = document.getElementById("pop-city-input").value.trim();
      const technology = document.getElementById("pop-tech-select").value;
      const address = document.getElementById("pop-address-input").value.trim();
      const lat = parseFloat(document.getElementById("pop-lat-input").value);
      const lon = parseFloat(document.getElementById("pop-lon-input").value);
      const capacity = document.getElementById("pop-capacity-input").value.trim();

      if (!name || isNaN(lat) || isNaN(lon)) {
        alert("Preencha ao menos Nome, Latitude e Longitude válidos.");
        return;
      }

      const submitBtn = document.getElementById("pop-submit-btn");
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span class="spinner"></span> Salvando...`;

      try {
        await api.createPop({
          name,
          city: city || null,
          technology,
          address: address || null,
          latitude: lat,
          longitude: lon,
          capacity: capacity || null
        });
        popCreateForm.reset();
        await loadPops();
        alert(`POP "${name}" cadastrado com sucesso!`);
      } catch (err) {
        alert(`Falha ao cadastrar POP: ${err.message}`);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<i class="fa-solid fa-plus"></i> Salvar POP`;
      }
    });
  }

  // ==========================================
  // NAVEGAÇÃO ENTRE ABAS
  // ==========================================
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add("active");
    });
  });

  // ==========================================
  // CONSULTA UNITÁRIA (COM NÚMERO SEPARADO)
  // ==========================================
  async function executeSearch(query, number = null, lat = null, lon = null) {
    if (!query && (lat === null || lon === null)) return;

    searchBtn.disabled = true;
    searchBtn.innerHTML = `<span class="spinner"></span> Consultando...`;
    resultContainer.style.display = "none";

    try {
      const data = await api.checkViability(query, number, lat, lon);
      displayViabilityResult(data);
    } catch (err) {
      alert(`Falha na consulta: ${err.message}`);
    } finally {
      searchBtn.disabled = false;
      searchBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Consultar Viabilidade`;
    }
  }

  function displayViabilityResult(data) {
    const card = document.getElementById("result-card-inner");
    card.className = "result-card";

    resultBadge.className = "badge";
    if (data.status === "VIAVEL") {
      card.classList.add("viable");
      resultBadge.classList.add("viable");
      resultBadge.innerHTML = `<i class="fa-solid fa-circle-check"></i> Viável para Instalação`;
    } else if (data.status === "EM_ANALISE") {
      card.classList.add("analysis");
      resultBadge.classList.add("analysis");
      resultBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Em Análise Técnica`;
    } else {
      card.classList.add("unviable");
      resultBadge.classList.add("unviable");
      resultBadge.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Inviável no Momento`;
    }

    resultTitle.textContent = data.display_name || data.input_query || "Localização Consultada";
    resultDesc.textContent = data.message;

    const poly = data.matched_polygon;
    metaTech.textContent = poly ? poly.technology : "N/A";
    metaPop.textContent = poly ? (poly.pop || "POP Padrão") : "N/A";
    metaRegion.textContent = poly ? poly.region : "Fora de Cobertura";
    metaDistance.textContent = data.distance_to_nearest_meters > 0 ? `${data.distance_to_nearest_meters}m` : "0m (No Perímetro)";

    resultContainer.style.display = "block";

    // Marcar no mapa
    if (data.location && data.location.latitude && data.location.longitude) {
      mapManager.setQueryResult(
        data.location.latitude,
        data.location.longitude,
        data.status,
        data.message
      );
    }
  }

  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = searchInput.value.trim();
    const num = searchNumberInput ? searchNumberInput.value.trim() : null;
    executeSearch(q, num);
  });

  // Localização atual do dispositivo (GPS)
  btnGps.addEventListener("click", () => {
    if (!navigator.geolocation) {
      alert("Geolocalização não suportada pelo seu navegador.");
      return;
    }
    btnGps.disabled = true;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        btnGps.disabled = false;
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        searchInput.value = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
        if (searchNumberInput) searchNumberInput.value = "";
        executeSearch(null, null, lat, lon);
      },
      (err) => {
        btnGps.disabled = false;
        alert("Não foi possível obter sua localização: " + err.message);
      }
    );
  });

  // ==========================================
  // PROCESSAMENTO EM LOTE (BULK CHECK)
  // ==========================================
  dropzone.addEventListener("click", () => fileBatchInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleBatchUpload(e.dataTransfer.files[0]);
    }
  });

  fileBatchInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleBatchUpload(e.target.files[0]);
    }
  });

  async function handleBatchUpload(file) {
    progressContainer.style.display = "block";
    batchDownloadBtn.style.display = "none";
    progressBarFill.style.width = "0%";
    progressPercent.textContent = "0%";
    progressText.textContent = `Enviando ${file.name}...`;

    try {
      const res = await api.uploadBatch(file);
      pollBatchStatus(res.job_id);
    } catch (err) {
      alert(`Falha no envio do lote: ${err.message}`);
      progressContainer.style.display = "none";
    }
  }

  function pollBatchStatus(jobId) {
    const interval = setInterval(async () => {
      try {
        const job = await api.getBatchStatus(jobId);

        progressBarFill.style.width = `${job.progress_percentage}%`;
        progressPercent.textContent = `${job.progress_percentage}%`;
        progressText.textContent = `Processando linha ${job.processed_rows} de ${job.total_rows}...`;

        countViable.textContent = job.viable_count;
        countAnalysis.textContent = job.analysis_count;
        countUnviable.textContent = job.unviable_count;

        if (job.status === "COMPLETED") {
          clearInterval(interval);
          progressText.textContent = `Concluído com sucesso! (${job.total_rows} linhas analisadas)`;
          batchDownloadBtn.href = job.download_csv_url;
          batchDownloadBtn.style.display = "flex";
        } else if (job.status === "FAILED") {
          clearInterval(interval);
          progressText.textContent = `Erro no processamento: ${job.error_message}`;
        }
      } catch (err) {
        clearInterval(interval);
        console.error(err);
      }
    }, 800);
  }

  // ==========================================
  // GESTÃO E UPLOAD DE MANCHAS (GEOJSON / KMZ)
  // ==========================================
  layerUploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!layerFileInput.files.length) {
      alert("Selecione um arquivo .geojson ou .kmz.");
      return;
    }

    layerUploadBtn.disabled = true;
    layerUploadBtn.innerHTML = `<span class="spinner"></span> Importando Camada...`;

    const formData = new FormData();
    formData.append("file", layerFileInput.files[0]);
    if (layerNameInput.value.trim()) {
      formData.append("name", layerNameInput.value.trim());
    }
    formData.append("technology", layerTechSelect.value);
    if (layerPopSelect && layerPopSelect.value) {
      formData.append("pop_id", layerPopSelect.value);
    }

    try {
      const res = await api.uploadLayer(formData);
      alert(res.message);
      layerFileInput.value = "";
      layerNameInput.value = "";
      await loadCoverageLayers();
    } catch (err) {
      alert(`Falha ao importar: ${err.message}`);
    } finally {
      layerUploadBtn.disabled = false;
      layerUploadBtn.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i> Fazer Upload e Ativar`;
    }
  });

  // Inicialização Geral
  loadCoverageLayers();
  loadPops();
});

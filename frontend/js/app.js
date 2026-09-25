import { api } from "./api.js?v=2.2.0";
import { MapManager } from "./map.js?v=2.2.0";

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
  const searchLayerSelect = document.getElementById("search-layer-select");
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

  // Lote e Monitoramento de Carga
  const dropzone = document.getElementById("dropzone");
  const fileBatchInput = document.getElementById("file-batch-input");
  const batchLayerSelect = document.getElementById("batch-layer-select");
  const progressContainer = document.getElementById("progress-container");
  const progressBarFill = document.getElementById("progress-bar-fill");
  const progressText = document.getElementById("progress-text");
  const progressPercent = document.getElementById("progress-percent");
  const countViable = document.getElementById("count-viable");
  const countAnalysis = document.getElementById("count-analysis");
  const countUnviable = document.getElementById("count-unviable");
  const countError = document.getElementById("count-error");
  const batchDownloadBtn = document.getElementById("batch-download-btn");
  const batchCancelBtn = document.getElementById("batch-cancel-btn");
  const batchJobBadge = document.getElementById("batch-job-badge");
  const batchQueueInfo = document.getElementById("batch-queue-info");
  const batchCurrentItem = document.getElementById("batch-current-item");
  const statSpeed = document.getElementById("stat-speed");
  const statElapsed = document.getElementById("stat-elapsed");
  const statEta = document.getElementById("stat-eta");
  const statRows = document.getElementById("stat-rows");
  const serverLoadBadge = document.getElementById("server-load-badge");
  const serverLoadText = document.getElementById("server-load-text");
  const sysCpuRam = document.getElementById("sys-cpu-ram");
  const sysQueueJobs = document.getElementById("sys-queue-jobs");

  // Arquivo Selecionado e Parâmetros Customizados do Lote
  const batchFileSelected = document.getElementById("batch-file-selected");
  const batchFileIcon = document.getElementById("batch-file-icon");
  const batchFileName = document.getElementById("batch-file-name");
  const batchFileSize = document.getElementById("batch-file-size");
  const btnRemoveBatchFile = document.getElementById("btn-remove-batch-file");
  const batchParamsCard = document.getElementById("batch-params-card");
  const btnResetBatchParams = document.getElementById("btn-reset-batch-params");
  const batchParamTolerance = document.getElementById("batch-param-tolerance");
  const batchParamMaxAnalysis = document.getElementById("batch-param-max-analysis");
  const btnStartBatch = document.getElementById("btn-start-batch");

  // Mapeamento e Validação Geográfica do Lote
  const batchMapPanel = document.getElementById("batch-map-panel");
  const btnToggleBatchMap = document.getElementById("btn-toggle-batch-map");
  const btnToggleBatchMapText = document.getElementById("btn-toggle-batch-map-text");
  const btnZoomBatchMap = document.getElementById("btn-zoom-batch-map");
  const btnClearBatchMap = document.getElementById("btn-clear-batch-map");
  const batchPointsLoadedCount = document.getElementById("batch-points-loaded-count");
  const filterMapViable = document.getElementById("filter-map-viable");
  const filterMapAnalysis = document.getElementById("filter-map-analysis");
  const filterMapUnviable = document.getElementById("filter-map-unviable");
  const badgeCountViable = document.getElementById("badge-count-viable");
  const badgeCountAnalysis = document.getElementById("badge-count-analysis");
  const badgeCountUnviable = document.getElementById("badge-count-unviable");
  const batchDownloadKmzBtn = document.getElementById("batch-download-kmz-btn");
  const batchDownloadKmzAnalysisBtn = document.getElementById("batch-download-kmz-analysis-btn");

  // Barra de ferramentas flutuante do lote no mapa
  const mapBatchToolbar = document.getElementById("map-batch-toolbar");
  const mapBatchChipTotal = document.getElementById("map-batch-chip-total");
  const btnMapBatchClose = document.getElementById("btn-map-batch-close");
  const mapQuickViable = document.getElementById("map-quick-viable");
  const mapQuickAnalysis = document.getElementById("map-quick-analysis");
  const mapQuickUnviable = document.getElementById("map-quick-unviable");
  const mapCntViable = document.getElementById("map-cnt-viable");
  const mapCntAnalysis = document.getElementById("map-cnt-analysis");
  const mapCntUnviable = document.getElementById("map-cnt-unviable");
  const btnMapQuickZoom = document.getElementById("btn-map-quick-zoom");
  const btnMapQuickFocusAnalysis = document.getElementById("btn-map-quick-focus-analysis");

  let currentBatchPoints = null;
  let isBatchPlotted = false;

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
  function populateLayerSelects(layers) {
    const selects = [searchLayerSelect, batchLayerSelect].filter(Boolean);
    const primaryLayers = layers.filter(l => l.enabled && l.is_primary);
    const primaryNames = primaryLayers.map(l => l.name).join(", ");

    selects.forEach(sel => {
      const currentVal = sel.value;
      sel.innerHTML = "";

      // 1. Se houver camadas principais definidas, criar opção de Principais no topo
      if (primaryLayers.length > 0) {
        const optPrimary = document.createElement("option");
        optPrimary.value = "__primary__";
        optPrimary.textContent = `⭐ Manchas Principais (${primaryNames})`;
        sel.appendChild(optPrimary);
      }

      // 2. Opção para Todas as Manchas Ativas (Geral)
      const optAll = document.createElement("option");
      optAll.value = "";
      optAll.textContent = "🌐 Todas as Manchas Ativas (Geral)";
      sel.appendChild(optAll);

      // 3. Opções individuais para cada mancha ativa
      layers.forEach(layer => {
        if (layer.enabled) {
          const opt = document.createElement("option");
          opt.value = layer.id;
          opt.textContent = `${layer.is_primary ? '⭐ ' : ''}${layer.name} (${layer.technology})`;
          sel.appendChild(opt);
        }
      });

      // Manter seleção anterior se ainda existir; caso contrário, pré-selecionar principais se existirem
      if (currentVal && Array.from(sel.options).some(o => o.value === currentVal)) {
        sel.value = currentVal;
      } else if (primaryLayers.length > 0) {
        sel.value = "__primary__";
      } else {
        sel.value = "";
      }
    });
  }

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
      populateLayerSelects(layers);
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
              <div class="layer-title" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; gap: 0.4rem;">
                ${layer.is_primary ? '<i class="fa-solid fa-star" style="color: #fbbf24; font-size: 0.75rem;" title="Mancha Principal"></i>' : ''}
                <span>${layer.name}</span>
              </div>
              <div class="layer-subtitle">${layer.technology} • ${layer.polygon_count} polígono(s)${layer.pop_name ? ` • POP: ${layer.pop_name}` : ''}</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 0.65rem; margin-left: 0.5rem;">
            <button type="button" 
                    class="btn-star ${layer.is_primary ? 'active' : ''} btn-toggle-primary" 
                    data-id="${layer.id}" 
                    title="${layer.is_primary ? 'Mancha Principal do sistema (clique para desmarcar)' : 'Marcar como Mancha Principal do sistema'}">
              <i class="fa-${layer.is_primary ? 'solid' : 'regular'} fa-star"></i>
              <span>Principal</span>
            </button>
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

      // Eventos de marcar/desmarcar Principal
      layersListContainer.querySelectorAll(".btn-toggle-primary").forEach(btn => {
        btn.addEventListener("click", async (e) => {
          const btnEl = e.currentTarget;
          const layerId = btnEl.dataset.id;
          try {
            await api.toggleLayerPrimary(layerId);
            await renderLayersList();
          } catch (err) {
            alert(`Falha ao alterar status principal: ${err.message}`);
          }
        });
      });

      // Eventos de toggle (ativar/desativar)
      layersListContainer.querySelectorAll(".layer-toggle-checkbox").forEach(cb => {
        cb.addEventListener("change", async (e) => {
          const layerId = e.target.dataset.id;
          try {
            await api.toggleLayer(layerId);
            const geojson = await api.getLayersGeoJSON();
            mapManager.renderCoverage(geojson);
            await renderLayersList();
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

    let selectedLayer = searchLayerSelect ? searchLayerSelect.value : null;
    if (selectedLayer === "__primary__") {
      selectedLayer = "primary";
    }

    try {
      const data = await api.checkViability(query, number, lat, lon, selectedLayer || null);
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

    // Exibir sobreposições caso haja múltiplos polígonos atendendo o ponto
    const overlapsEl = document.getElementById("result-overlaps");
    if (overlapsEl) {
      if (data.all_matched_polygons && data.all_matched_polygons.length > 1) {
        overlapsEl.style.display = "block";
        overlapsEl.innerHTML = `
          <div style="color: var(--text-main); font-weight: 600; margin-bottom: 0.35rem;">
            <i class="fa-solid fa-layer-group" style="color: var(--primary);"></i> Coberturas Sobrepostas (${data.all_matched_polygons.length}):
          </div>
          <div style="display: flex; flex-direction: column; gap: 0.25rem;">
            ${data.all_matched_polygons.map((p, idx) => `
              <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(255,255,255,0.04); border: 1px solid var(--border); padding: 0.3rem 0.6rem; border-radius: 4px; font-size: 0.78rem;">
                <span>${idx === 0 ? '⭐ <strong>(Principal)</strong> ' : ''}${p.polygon_name}</span>
                <span style="color: var(--primary); font-size: 0.72rem;">${p.technology} • ${p.pop || 'POP'}</span>
              </div>
            `).join('')}
          </div>
        `;
      } else {
        overlapsEl.style.display = "none";
        overlapsEl.innerHTML = "";
      }
    }

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
  // MONITORAMENTO DO SERVIDOR & CARGA
  // ==========================================
  async function refreshSystemStatus() {
    try {
      const status = await api.getSystemStatus();
      if (!status) return;

      // Atualizar badge de carga
      if (serverLoadBadge && serverLoadText) {
        serverLoadBadge.className = `server-badge ${status.status === "healthy" ? "normal" : status.status === "warning" ? "warning" : "busy"}`;
        serverLoadText.textContent = `Servidor: ${status.server_load}`;
      }

      // Atualizar card de CPU / RAM
      if (sysCpuRam) {
        const cpuStr = status.cpu_percent !== null && status.cpu_percent !== undefined ? `${status.cpu_percent}%` : "Ativo";
        const memStr = status.memory_percent !== null && status.memory_percent !== undefined ? `${status.memory_percent}%` : "OK";
        sysCpuRam.textContent = `${cpuStr} / ${memStr}`;
      }

      // Atualizar fila
      if (sysQueueJobs) {
        const total = status.active_batch_jobs || 0;
        sysQueueJobs.textContent = `${total} lote(s) ativo(s)`;
      }
    } catch (e) {
      console.warn("Monitoramento do sistema indisponível:", e);
    }
  }

  // Monitorar carga a cada 4 segundos
  setInterval(refreshSystemStatus, 4000);
  refreshSystemStatus();

  // ==========================================
  // PROCESSAMENTO EM LOTE (BULK CHECK)
  // ==========================================
  let selectedBatchFile = null;

  function formatBytes(bytes, decimals = 1) {
    if (!bytes || bytes === 0) return "0 Bytes";
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
  }

  function setSelectedFile(file) {
    if (!file) return;
    selectedBatchFile = file;
    if (batchFileName) batchFileName.textContent = file.name;
    if (batchFileSize) batchFileSize.textContent = formatBytes(file.size);
    if (batchFileIcon) {
      const isExcel = file.name.endsWith(".xlsx") || file.name.endsWith(".xls");
      batchFileIcon.className = isExcel ? "fa-solid fa-file-excel" : "fa-solid fa-file-csv";
      if (batchFileIcon.parentElement) {
        batchFileIcon.parentElement.className = isExcel ? "file-icon-badge excel" : "file-icon-badge";
      }
    }
    if (batchFileSelected) batchFileSelected.style.display = "flex";
    if (btnStartBatch) {
      btnStartBatch.style.display = "flex";
      btnStartBatch.disabled = false;
      btnStartBatch.innerHTML = `<i class="fa-solid fa-play"></i> Iniciar Análise de Viabilidade`;
    }
    if (dropzone) dropzone.style.display = "none";
  }

  function clearSelectedFile() {
    selectedBatchFile = null;
    fileBatchInput.value = "";
    if (batchFileSelected) batchFileSelected.style.display = "none";
    if (btnStartBatch) btnStartBatch.style.display = "none";
    if (dropzone) dropzone.style.display = "block";
  }

  if (btnRemoveBatchFile) {
    btnRemoveBatchFile.addEventListener("click", clearSelectedFile);
  }

  if (btnResetBatchParams) {
    btnResetBatchParams.addEventListener("click", () => {
      if (batchParamTolerance) batchParamTolerance.value = "5.0";
      if (batchParamMaxAnalysis) batchParamMaxAnalysis.value = "100.0";
    });
  }

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
      setSelectedFile(e.dataTransfer.files[0]);
    }
  });

  fileBatchInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  });

  if (btnStartBatch) {
    btnStartBatch.addEventListener("click", () => {
      if (!selectedBatchFile) {
        alert("Por favor, selecione uma planilha CSV ou Excel antes de iniciar.");
        return;
      }
      const tolVal = batchParamTolerance ? parseFloat(batchParamTolerance.value) : 5.0;
      const maxVal = batchParamMaxAnalysis ? parseFloat(batchParamMaxAnalysis.value) : 100.0;
      handleBatchUpload(selectedBatchFile, {
        toleranciaBorda: isNaN(tolVal) ? 5.0 : tolVal,
        maxDistanciaAnalise: isNaN(maxVal) ? 100.0 : maxVal
      });
    });
  }

  function setBatchBadge(type, label) {
    if (!batchJobBadge) return;
    batchJobBadge.className = `batch-state-pill ${type}`;
    if (type === "processing" || type === "queued") {
      batchJobBadge.innerHTML = `<span class="spinner-mini"></span> ${label}`;
    } else {
      batchJobBadge.textContent = label;
    }
  }

  async function handleBatchUpload(file, options = {}) {
    progressContainer.style.display = "block";
    batchDownloadBtn.style.display = "none";
    if (batchMapPanel) batchMapPanel.style.display = "none";
    if (mapBatchToolbar) mapBatchToolbar.style.display = "none";
    mapManager.clearBatchPoints();
    isBatchPlotted = false;
    currentBatchPoints = null;
    if (btnToggleBatchMap) {
      btnToggleBatchMap.innerHTML = `<i class="fa-solid fa-layer-group"></i> <span id="btn-toggle-batch-map-text">Plotar no Mapa</span>`;
    }

    if (btnStartBatch) {
      btnStartBatch.disabled = true;
      btnStartBatch.innerHTML = `<span class="spinner-mini"></span> Processando Lote...`;
    }

    if (batchCancelBtn) {
      batchCancelBtn.style.display = "inline-flex";
      batchCancelBtn.disabled = false;
      batchCancelBtn.innerHTML = `<i class="fa-solid fa-ban"></i> Interromper Lote`;
    }
    progressBarFill.style.width = "0%";
    progressPercent.textContent = "0%";
    progressText.textContent = `Enviando arquivo ${file.name}...`;
    if (batchCurrentItem) batchCurrentItem.style.display = "none";
    if (batchQueueInfo) batchQueueInfo.style.display = "none";

    setBatchBadge("processing", "Enviando");

    try {
      let selectedBatchLayer = batchLayerSelect ? batchLayerSelect.value : null;
      if (selectedBatchLayer === "__primary__") {
        selectedBatchLayer = "primary";
      }
      const res = await api.uploadBatch(file, selectedBatchLayer || null, options);
      currentBatchJobId = res.job_id;
      pollBatchStatus(res.job_id);
      refreshSystemStatus();
    } catch (err) {
      alert(`Falha no envio do lote: ${err.message}`);
      progressContainer.style.display = "none";
      if (btnStartBatch) {
        btnStartBatch.disabled = false;
        btnStartBatch.innerHTML = `<i class="fa-solid fa-play"></i> Iniciar Análise de Viabilidade`;
      }
    }
  }

  function showBatchMapControls(job) {
    if (!batchMapPanel) return;

    batchMapPanel.style.display = "block";

    // Atualizar badges de contadores
    if (badgeCountViable) badgeCountViable.textContent = job.viable_count;
    if (badgeCountAnalysis) badgeCountAnalysis.textContent = job.analysis_count;
    if (badgeCountUnviable) badgeCountUnviable.textContent = job.unviable_count;

    if (mapCntViable) mapCntViable.textContent = job.viable_count;
    if (mapCntAnalysis) mapCntAnalysis.textContent = job.analysis_count;
    if (mapCntUnviable) mapCntUnviable.textContent = job.unviable_count;

    const totalGeocoded = (job.viable_count || 0) + (job.analysis_count || 0) + (job.unviable_count || 0);
    if (mapBatchChipTotal) mapBatchChipTotal.textContent = `${totalGeocoded} pts`;
    if (batchPointsLoadedCount) batchPointsLoadedCount.textContent = `${totalGeocoded} com coordenadas`;

    // Configurar URLs para download KMZ (Google Earth)
    if (batchDownloadKmzBtn) {
      batchDownloadKmzBtn.href = api.getBatchKmzUrl(job.job_id);
      batchDownloadKmzBtn.setAttribute("download", `viabilidade_lote_${job.job_id.slice(0, 8)}.kmz`);
    }

    if (batchDownloadKmzAnalysisBtn) {
      if (job.analysis_count > 0) {
        batchDownloadKmzAnalysisBtn.style.display = "inline-flex";
        batchDownloadKmzAnalysisBtn.href = api.getBatchKmzUrl(job.job_id, "EM_ANALISE");
        batchDownloadKmzAnalysisBtn.setAttribute("download", `viabilidade_em_analise_${job.job_id.slice(0, 8)}.kmz`);
      } else {
        batchDownloadKmzAnalysisBtn.style.display = "none";
      }
    }
  }

  async function toggleBatchMapPlot() {
    if (!currentBatchJobId) return;

    if (isBatchPlotted) {
      mapManager.clearBatchPoints();
      isBatchPlotted = false;
      if (btnToggleBatchMap) {
        btnToggleBatchMap.innerHTML = `<i class="fa-solid fa-layer-group"></i> <span id="btn-toggle-batch-map-text">Plotar no Mapa</span>`;
      }
      if (mapBatchToolbar) mapBatchToolbar.style.display = "none";
      return;
    }

    if (btnToggleBatchMap) {
      btnToggleBatchMap.disabled = true;
      btnToggleBatchMap.innerHTML = `<span class="spinner-mini"></span> <span>Carregando Pontos...</span>`;
    }

    try {
      if (!currentBatchPoints) {
        const res = await api.getBatchResults(currentBatchJobId);
        currentBatchPoints = res.points || [];
      }

      if (!currentBatchPoints.length) {
        alert("Nenhum ponto com coordenadas válidas disponível para visualização no mapa.");
        return;
      }

      const activeFilters = {
        VIAVEL: filterMapViable ? filterMapViable.checked : true,
        EM_ANALISE: filterMapAnalysis ? filterMapAnalysis.checked : true,
        INVIAVEL: filterMapUnviable ? filterMapUnviable.checked : true
      };

      mapManager.renderBatchPoints(currentBatchPoints, { fitBounds: true, activeFilters });
      isBatchPlotted = true;

      if (btnToggleBatchMap) {
        btnToggleBatchMap.innerHTML = `<i class="fa-solid fa-eye-slash"></i> <span id="btn-toggle-batch-map-text">Ocultar do Mapa</span>`;
      }
      if (mapBatchToolbar) mapBatchToolbar.style.display = "block";
      if (batchPointsLoadedCount) {
        batchPointsLoadedCount.textContent = `(${currentBatchPoints.length} pontos mapeados)`;
      }
    } catch (err) {
      alert(`Falha ao plotar pontos: ${err.message}`);
    } finally {
      if (btnToggleBatchMap) btnToggleBatchMap.disabled = false;
    }
  }

  function syncFilterStatus(category, checked) {
    if (category === "VIAVEL") {
      if (filterMapViable) filterMapViable.checked = checked;
      if (mapQuickViable) mapQuickViable.checked = checked;
    } else if (category === "EM_ANALISE") {
      if (filterMapAnalysis) filterMapAnalysis.checked = checked;
      if (mapQuickAnalysis) mapQuickAnalysis.checked = checked;
    } else if (category === "INVIAVEL") {
      if (filterMapUnviable) filterMapUnviable.checked = checked;
      if (mapQuickUnviable) mapQuickUnviable.checked = checked;
    }
    mapManager.setBatchVisibility(category, checked);
  }

  function pollBatchStatus(jobId) {
    if (batchPollInterval) clearInterval(batchPollInterval);

    batchPollInterval = setInterval(async () => {
      try {
        const job = await api.getBatchStatus(jobId);

        // Barra de progresso e porcentagem
        progressBarFill.style.width = `${job.progress_percentage}%`;
        progressPercent.textContent = `${job.progress_percentage}%`;

        // Descrição do estágio atual
        progressText.textContent = job.current_stage || `Processando linha ${job.processed_rows} de ${job.total_rows}...`;

        // Item preview
        if (job.current_item_preview && job.status === "PROCESSING") {
          batchCurrentItem.textContent = `Avaliando: ${job.current_item_preview}`;
          batchCurrentItem.style.display = "block";
        } else {
          batchCurrentItem.style.display = "none";
        }

        // Estatísticas de velocidade e tempo
        if (statSpeed) statSpeed.textContent = `${job.processing_rate || 0} lin/s`;
        if (statElapsed) statElapsed.textContent = job.elapsed_time_formatted || "00:00";
        if (statEta) statEta.textContent = job.eta_formatted || "--:--";
        if (statRows) statRows.textContent = `${job.processed_rows} / ${job.total_rows}`;

        // Contadores
        countViable.textContent = job.viable_count;
        countAnalysis.textContent = job.analysis_count;
        countUnviable.textContent = job.unviable_count;
        if (countError) countError.textContent = job.error_count;

        // Fila & Estados
        if (job.status === "QUEUED") {
          setBatchBadge("queued", `Na Fila (${job.queue_position}º)`);
          if (batchQueueInfo) {
            batchQueueInfo.textContent = `Aguardando liberação de recursos do servidor`;
            batchQueueInfo.style.display = "inline";
          }
        } else if (job.status === "PROCESSING") {
          setBatchBadge("processing", "Processando");
          if (batchQueueInfo) batchQueueInfo.style.display = "none";
        } else if (job.status === "COMPLETED") {
          clearInterval(batchPollInterval);
          setBatchBadge("completed", "Concluído");
          if (batchQueueInfo) batchQueueInfo.style.display = "none";
          if (batchCancelBtn) batchCancelBtn.style.display = "none";
          if (btnStartBatch) {
            btnStartBatch.disabled = false;
            btnStartBatch.innerHTML = `<i class="fa-solid fa-rotate-right"></i> Reprocessar Lote`;
          }
          batchDownloadBtn.href = job.download_csv_url;
          batchDownloadBtn.innerHTML = `<i class="fa-solid fa-file-arrow-down"></i> Baixar Relatório (.CSV)`;
          batchDownloadBtn.style.display = "inline-flex";
          showBatchMapControls(job);
          refreshSystemStatus();
        } else if (job.status === "CANCELLED") {
          clearInterval(batchPollInterval);
          setBatchBadge("cancelled", "Cancelado");
          if (batchQueueInfo) batchQueueInfo.style.display = "none";
          if (batchCancelBtn) batchCancelBtn.style.display = "none";
          if (btnStartBatch) {
            btnStartBatch.disabled = false;
            btnStartBatch.innerHTML = `<i class="fa-solid fa-play"></i> Iniciar Análise de Viabilidade`;
          }
          progressText.textContent = job.current_stage || "Processamento cancelado pelo usuário.";
          if (job.download_csv_url) {
            batchDownloadBtn.href = job.download_csv_url;
            batchDownloadBtn.innerHTML = `<i class="fa-solid fa-file-arrow-down"></i> Baixar Dados Parciais (${job.processed_rows} linhas)`;
            batchDownloadBtn.style.display = "inline-flex";
            if (job.processed_rows > 0) {
              showBatchMapControls(job);
            }
          }
          refreshSystemStatus();
        } else if (job.status === "FAILED") {
          clearInterval(batchPollInterval);
          setBatchBadge("failed", "Falha");
          if (batchQueueInfo) batchQueueInfo.style.display = "none";
          if (batchCancelBtn) batchCancelBtn.style.display = "none";
          if (btnStartBatch) {
            btnStartBatch.disabled = false;
            btnStartBatch.innerHTML = `<i class="fa-solid fa-play"></i> Iniciar Análise de Viabilidade`;
          }
          progressText.textContent = `Erro: ${job.error_message}`;
          refreshSystemStatus();
        }
      } catch (err) {
        clearInterval(batchPollInterval);
        console.error("Erro no polling de status:", err);
      }
    }, 700);
  }

  // Cancelar processamento do lote
  if (batchCancelBtn) {
    batchCancelBtn.addEventListener("click", async () => {
      if (!currentBatchJobId) return;
      const ok = confirm("Deseja interromper o processamento deste lote? Os registros já verificados até o momento serão salvos na planilha.");
      if (!ok) return;

      batchCancelBtn.disabled = true;
      batchCancelBtn.innerHTML = `<span class="spinner-mini"></span> Interrompendo...`;
      try {
        await api.cancelBatch(currentBatchJobId);
      } catch (err) {
        alert(`Erro ao solicitar cancelamento: ${err.message}`);
        batchCancelBtn.disabled = false;
        batchCancelBtn.innerHTML = `<i class="fa-solid fa-ban"></i> Interromper Lote`;
      }
    });
  }

  // Event Listeners para o Mapeamento e Validação do Lote
  if (btnToggleBatchMap) btnToggleBatchMap.addEventListener("click", toggleBatchMapPlot);
  if (btnZoomBatchMap) btnZoomBatchMap.addEventListener("click", () => mapManager.zoomToBatch());
  if (btnClearBatchMap) btnClearBatchMap.addEventListener("click", () => {
    mapManager.clearBatchPoints();
    isBatchPlotted = false;
    if (btnToggleBatchMap) {
      btnToggleBatchMap.innerHTML = `<i class="fa-solid fa-layer-group"></i> <span id="btn-toggle-batch-map-text">Plotar no Mapa</span>`;
    }
    if (mapBatchToolbar) mapBatchToolbar.style.display = "none";
  });

  // Sincronização dos filtros (Sidebar e Barra flutuante do mapa)
  if (filterMapViable) filterMapViable.addEventListener("change", (e) => syncFilterStatus("VIAVEL", e.target.checked));
  if (mapQuickViable) mapQuickViable.addEventListener("change", (e) => syncFilterStatus("VIAVEL", e.target.checked));

  if (filterMapAnalysis) filterMapAnalysis.addEventListener("change", (e) => syncFilterStatus("EM_ANALISE", e.target.checked));
  if (mapQuickAnalysis) mapQuickAnalysis.addEventListener("change", (e) => syncFilterStatus("EM_ANALISE", e.target.checked));

  if (filterMapUnviable) filterMapUnviable.addEventListener("change", (e) => syncFilterStatus("INVIAVEL", e.target.checked));
  if (mapQuickUnviable) mapQuickUnviable.addEventListener("change", (e) => syncFilterStatus("INVIAVEL", e.target.checked));

  // Ações da Barra Flutuante do Mapa
  if (btnMapBatchClose) btnMapBatchClose.addEventListener("click", () => {
    mapManager.clearBatchPoints();
    isBatchPlotted = false;
    if (btnToggleBatchMap) {
      btnToggleBatchMap.innerHTML = `<i class="fa-solid fa-layer-group"></i> <span id="btn-toggle-batch-map-text">Plotar no Mapa</span>`;
    }
    if (mapBatchToolbar) mapBatchToolbar.style.display = "none";
  });

  if (btnMapQuickZoom) btnMapQuickZoom.addEventListener("click", () => mapManager.zoomToBatch());

  if (btnMapQuickFocusAnalysis) btnMapQuickFocusAnalysis.addEventListener("click", async () => {
    if (!isBatchPlotted) {
      await toggleBatchMapPlot();
    }
    syncFilterStatus("EM_ANALISE", true);
    mapManager.zoomToBatch("EM_ANALISE");
  });

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

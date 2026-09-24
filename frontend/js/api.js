const API_BASE = ""; // Caminho relativo ao mesmo host da API FastAPI

export const api = {
  /**
   * Consulta a viabilidade técnica de um endereço, CEP ou coordenadas.
   * Suporta parâmetro opcional 'layers' para restringir a consulta a mapas específicos.
   */
  async checkViability(query, number = null, lat = null, lon = null, layers = null) {
    const payload = {};
    if (lat !== null && lon !== null) {
      payload.latitude = parseFloat(lat);
      payload.longitude = parseFloat(lon);
    } else {
      payload.query = query;
      if (number && number.trim()) {
        payload.number = number.trim();
      }
    }

    if (layers) {
      payload.layers = layers;
    }

    const res = await fetch(`${API_BASE}/api/viability/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Erro desconhecido na consulta" }));
      throw new Error(err.detail || `Erro HTTP ${res.status}`);
    }

    return await res.json();
  },

  /**
   * Busca todas as manchas ativas em formato GeoJSON para renderização no mapa Leaflet.
   */
  async getLayersGeoJSON() {
    const res = await fetch(`${API_BASE}/api/layers/geojson`);
    if (!res.ok) throw new Error("Falha ao carregar geometrias de cobertura.");
    return await res.json();
  },

  /**
   * Lista os metadados das camadas cadastradas.
   */
  async getLayers() {
    const res = await fetch(`${API_BASE}/api/layers`);
    if (!res.ok) throw new Error("Falha ao carregar lista de camadas.");
    return await res.json();
  },

  /**
   * Ativa ou desativa uma camada.
   */
  async toggleLayer(layerId) {
    const res = await fetch(`${API_BASE}/api/layers/${layerId}/toggle`, {
      method: "POST"
    });
    if (!res.ok) throw new Error("Falha ao alternar status da camada.");
    return await res.json();
  },

  /**
   * Marca ou desmarca uma camada como principal/padrão do sistema.
   */
  async toggleLayerPrimary(layerId) {
    const res = await fetch(`${API_BASE}/api/layers/${layerId}/primary`, {
      method: "POST"
    });
    if (!res.ok) throw new Error("Falha ao alternar status principal da camada.");
    return await res.json();
  },

  /**
   * Exclui uma camada do sistema.
   */
  async deleteLayer(layerId) {
    const res = await fetch(`${API_BASE}/api/layers/${layerId}`, {
      method: "DELETE"
    });
    if (!res.ok) throw new Error("Falha ao excluir camada.");
    return await res.json();
  },

  /**
   * Faz upload de arquivo GeoJSON ou KMZ para cadastro de nova cobertura.
   */
  async uploadLayer(formData) {
    const res = await fetch(`${API_BASE}/api/layers/upload`, {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Falha ao enviar arquivo" }));
      throw new Error(err.detail || "Erro no upload da camada.");
    }
    return await res.json();
  },

  /**
   * Lista todos os POPs cadastrados.
   */
  async getPops() {
    const res = await fetch(`${API_BASE}/api/pops`);
    if (!res.ok) throw new Error("Falha ao carregar POPs.");
    return await res.json();
  },

  /**
   * Cria um novo POP.
   */
  async createPop(popData) {
    const res = await fetch(`${API_BASE}/api/pops`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(popData)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Falha ao criar POP" }));
      throw new Error(err.detail || "Erro ao criar POP.");
    }
    return await res.json();
  },

  /**
   * Exclui um POP.
   */
  async deletePop(popId) {
    const res = await fetch(`${API_BASE}/api/pops/${popId}`, {
      method: "DELETE"
    });
    if (!res.ok) throw new Error("Falha ao excluir POP.");
    return await res.json();
  },

  /**
   * Envia arquivo CSV ou XLSX para processamento em lote.
   * Suporta parâmetro opcional 'layers' para filtrar manchas no processamento.
   */
  async uploadBatch(file, layers = null) {
    const formData = new FormData();
    formData.append("file", file);
    if (layers) {
      formData.append("layers", Array.isArray(layers) ? layers.join(",") : layers);
    }

    const res = await fetch(`${API_BASE}/api/batch/upload`, {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Falha ao enviar lote" }));
      throw new Error(err.detail || "Erro no upload do lote.");
    }
    return await res.json();
  },

  /**
   * Consulta o status do processamento em lote.
   */
  async getBatchStatus(jobId) {
    const res = await fetch(`${API_BASE}/api/batch/status/${jobId}`);
    if (!res.ok) throw new Error("Falha ao verificar status do lote.");
    return await res.json();
  },

  /**
   * Cancela um processamento em lote.
   */
  async cancelBatch(jobId) {
    const res = await fetch(`${API_BASE}/api/batch/cancel/${jobId}`, {
      method: "POST"
    });
    if (!res.ok) throw new Error("Falha ao cancelar o processamento em lote.");
    return await res.json();
  },

  /**
   * Obtém métricas e status de carregamento do servidor em tempo real.
   */
  async getSystemStatus() {
    const res = await fetch(`${API_BASE}/api/system/status`);
    if (!res.ok) throw new Error("Falha ao obter status do sistema.");
    return await res.json();
  },

  /**
   * Obtém os pontos analisados do lote para plotagem no mapa Leaflet.
   */
  async getBatchResults(jobId, status = null) {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    const res = await fetch(`${API_BASE}/api/batch/results/${jobId}${query}`);
    if (!res.ok) throw new Error("Falha ao obter resultados mapeados do lote.");
    return await res.json();
  },

  /**
   * Retorna o link de download direto do arquivo KMZ (Google Earth).
   */
  getBatchKmzUrl(jobId, status = null) {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    return `${API_BASE}/api/batch/export-kmz/${jobId}${query}`;
  }
};

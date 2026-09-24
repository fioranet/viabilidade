export class MapManager {
  constructor(containerId = "map") {
    this.containerId = containerId;
    this.map = null;
    this.coverageLayer = null;
    this.queryMarker = null;
    this.distanceLine = null;
    this.popsLayer = null;
    
    // Motor de Renderização Canvas para alta performance com milhares de pontos de lote
    this.canvasRenderer = null;
    this.batchLayers = {
      VIAVEL: null,
      EM_ANALISE: null,
      INVIAVEL: null
    };
    this.batchLayersActive = {
      VIAVEL: true,
      EM_ANALISE: true,
      INVIAVEL: true
    };
    this.batchPoints = [];
    
    this.initMap();
  }

  initMap() {
    // Inicializar no centro de São Paulo por padrão
    this.map = L.map(this.containerId, {
      zoomControl: false
    }).setView([-23.565, -46.66], 12);

    // Inicializar Canvas Renderer ultra leve (evita criar nós DOM para cada ponto)
    this.canvasRenderer = L.canvas({ padding: 0.5 });

    // Inicializar grupos de camadas para o lote
    this.batchLayers.VIAVEL = L.layerGroup();
    this.batchLayers.EM_ANALISE = L.layerGroup();
    this.batchLayers.INVIAVEL = L.layerGroup();

    // Adicionar controle de zoom no canto superior direito
    L.control.zoom({ position: "topright" }).addTo(this.map);

    // 1. OpenStreetMap Padrão (Oficial, 100% gratuito e livre de API key)
    const osmStandard = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
      maxZoom: 19
    });

    // 2. Imagem de Satélite / Aérea (ESRI World Imagery - sem necessidade de API key)
    const esriSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
      maxZoom: 19
    });

    // 3. OpenStreetMap Humanitarian (HOT - ruas e bairros nítidos)
    const osmHot = L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors, Humanitarian OpenStreetMap Team',
      maxZoom: 19
    });

    // Definir OSM Standard como camada base ativa inicial
    osmStandard.addTo(this.map);

    // Controle seletor de camadas base no canto superior direito
    L.control.layers({
      "Mapa OpenStreetMap": osmStandard,
      "Satélite / Aéreo (Esri)": esriSatellite,
      "OpenStreetMap (HOT)": osmHot
    }, null, { position: "topright" }).addTo(this.map);
  }

  /**
   * Renderiza a FeatureCollection de manchas no mapa.
   */
  renderCoverage(geojson) {
    if (this.coverageLayer) {
      this.map.removeLayer(this.coverageLayer);
    }

    this.coverageLayer = L.geoJSON(geojson, {
      style: (feature) => {
        const props = feature.properties || {};
        const color = props.color || this.getColorByTech(props.technology);
        return {
          color: color,
          weight: 2,
          opacity: 0.9,
          fillColor: color,
          fillOpacity: 0.28
        };
      },
      onEachFeature: (feature, layer) => {
        const props = feature.properties || {};
        
        // Popup informativo ao clicar
        const popupContent = `
          <div style="font-family: inherit; font-size: 13px; min-width: 200px;">
            <div style="font-weight: 700; font-size: 14px; margin-bottom: 4px; color: #1e293b;">
              ${props.name || 'Mancha de Cobertura'}
            </div>
            <div style="color: #64748b; margin-bottom: 8px; font-size: 12px;">
              ${props.region || ''}
            </div>
            <hr style="border: 0; border-top: 1px solid #e2e8f0; margin-bottom: 8px;" />
            <div style="display: grid; grid-template-columns: 80px 1fr; gap: 4px;">
              <span style="color: #64748b;">Tecnologia:</span>
              <strong style="color: #0f172a;">${props.technology || 'Fibra GPON'}</strong>
              <span style="color: #64748b;">POP Central:</span>
              <span style="color: #0f172a;">${props.pop || 'POP 01'}</span>
              <span style="color: #64748b;">Status:</span>
              <span style="color: #10b981; font-weight: 600;">Ativo</span>
            </div>
          </div>
        `;
        layer.bindPopup(popupContent);

        // Efeitos de Hover
        layer.on({
          mouseover: (e) => {
            const l = e.target;
            l.setStyle({
              weight: 3.5,
              fillOpacity: 0.5
            });
          },
          mouseout: (e) => {
            this.coverageLayer.resetStyle(e.target);
          }
        });
      }
    }).addTo(this.map);

    // Ajustar o zoom para englobar todas as manchas
    if (this.coverageLayer.getLayers().length > 0) {
      this.map.fitBounds(this.coverageLayer.getBounds(), { padding: [40, 40] });
    }
  }

  getColorByTech(tech) {
    if (!tech) return "#10b981";
    if (tech.includes("Neutra")) return "#3b82f6";
    if (tech.includes("Rádio")) return "#f59e0b";
    return "#10b981";
  }

  /**
   * Adiciona o Pin do resultado da consulta no mapa com animação de pulso.
   */
  setQueryResult(lat, lon, status, message) {
    if (this.queryMarker) {
      this.map.removeLayer(this.queryMarker);
    }
    if (this.distanceLine) {
      this.map.removeLayer(this.distanceLine);
    }

    let color = "#10b981";
    let iconClass = "viable";
    if (status === "EM_ANALISE") {
      color = "#f59e0b";
      iconClass = "analysis";
    } else if (status === "INVIAVEL") {
      color = "#ef4444";
      iconClass = "unviable";
    }

    // Criar ícone SVG customizado com halo pulsante
    const customIcon = L.divIcon({
      className: `custom-pin-container ${iconClass}`,
      html: `
        <div style="
          position: relative;
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
        ">
          <div style="
            position: absolute;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background-color: ${color};
            opacity: 0.35;
            animation: pulse 1.8s infinite;
          "></div>
          <div style="
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background-color: ${color};
            border: 3px solid #ffffff;
            box-shadow: 0 0 10px rgba(0,0,0,0.5);
          "></div>
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 16]
    });

    this.queryMarker = L.marker([lat, lon], { icon: customIcon }).addTo(this.map);
    this.queryMarker.bindPopup(`<strong>${status}</strong><br/>${message}`).openPopup();

    // Centralizar suavemente no ponto
    this.map.flyTo([lat, lon], 15, { duration: 1.2 });
  }

  /**
   * Renderiza os marcadores dos POPs cadastrados no mapa.
   */
  renderPops(pops) {
    if (!this.popsLayer) {
      this.popsLayer = L.layerGroup().addTo(this.map);
    } else {
      this.popsLayer.clearLayers();
    }

    if (!pops || !pops.length) return;

    pops.forEach(pop => {
      if (!pop.latitude || !pop.longitude) return;

      const popIcon = L.divIcon({
        className: 'pop-marker-container',
        html: `
          <div style="
            background: #6366f1;
            color: #ffffff;
            width: 28px;
            height: 28px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid #ffffff;
            box-shadow: 0 4px 10px rgba(0,0,0,0.35);
            font-size: 13px;
          ">
            <i class="fa-solid fa-server"></i>
          </div>
        `,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });

      const marker = L.marker([pop.latitude, pop.longitude], { icon: popIcon });
      
      const popupHtml = `
        <div style="font-family: inherit; font-size: 13px; min-width: 220px;">
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
            <span style="background: #6366f1; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;">POP</span>
            <strong style="color: #0f172a; font-size: 14px;">${pop.name}</strong>
          </div>
          <div style="color: #64748b; font-size: 12px; margin-bottom: 6px;">
            ${pop.city ? `<strong>Cidade:</strong> ${pop.city}<br/>` : ''}
            ${pop.address ? `<strong>Endereço:</strong> ${pop.address}<br/>` : ''}
            ${pop.capacity ? `<strong>Capacidade:</strong> ${pop.capacity}<br/>` : ''}
            ${pop.technology ? `<strong>Tecnologia:</strong> ${pop.technology}<br/>` : ''}
            ${pop.notes ? `<em>${pop.notes}</em>` : ''}
          </div>
          <div style="color: #94a3b8; font-size: 11px;">
            Coords: ${pop.latitude.toFixed(5)}, ${pop.longitude.toFixed(5)}
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml);
      this.popsLayer.addLayer(marker);
    });
  }

  /**
   * Renderiza os pontos do lote no mapa usando L.canvas() para máximo desempenho.
   * Não afeta o FPS e pode suportar milhares de pontos simultaneamente.
   */
  renderBatchPoints(points, { fitBounds = true, activeFilters = null } = {}) {
    this.clearBatchPoints();
    if (!points || !points.length) return;

    this.batchPoints = points;

    if (activeFilters) {
      this.batchLayersActive = { ...this.batchLayersActive, ...activeFilters };
    }

    const bounds = L.latLngBounds([]);
    let validCount = 0;

    points.forEach((pt) => {
      const lat = parseFloat(pt.latitude);
      const lon = parseFloat(pt.longitude);
      if (isNaN(lat) || isNaN(lon)) return;

      validCount++;
      bounds.extend([lat, lon]);

      const status = (pt.status || "").toUpperCase();
      let color = "#ef4444";
      let statusLabel = "INVIÁVEL";
      let badgeBg = "rgba(239, 68, 68, 0.15)";
      let badgeBorder = "#ef4444";
      let badgeText = "#ef4444";
      let targetLayer = this.batchLayers.INVIAVEL;
      let radius = 6;
      let weight = 1.5;
      let fillOpacity = 0.8;

      if (status === "VIAVEL") {
        color = "#10b981";
        statusLabel = "VIÁVEL";
        badgeBg = "rgba(16, 185, 129, 0.15)";
        badgeBorder = "#10b981";
        badgeText = "#10b981";
        targetLayer = this.batchLayers.VIAVEL;
        radius = 6.5;
        fillOpacity = 0.85;
      } else if (status === "EM_ANALISE") {
        color = "#f59e0b";
        statusLabel = "EM ANÁLISE (VISTORIA)";
        badgeBg = "rgba(245, 158, 11, 0.18)";
        badgeBorder = "#f59e0b";
        badgeText = "#f59e0b";
        targetLayer = this.batchLayers.EM_ANALISE;
        // Destaque visual especial: raio maior e borda mais espessa para rápida identificação e validação
        radius = 8.5;
        weight = 2.5;
        fillOpacity = 0.95;
      }

      // CircleMarker renderizado via Canvas de alto desempenho
      const marker = L.circleMarker([lat, lon], {
        renderer: this.canvasRenderer,
        radius: radius,
        fillColor: color,
        color: "#ffffff",
        weight: weight,
        opacity: 0.95,
        fillOpacity: fillOpacity
      });

      const distStr = pt.distance_meters !== null && pt.distance_meters !== undefined
        ? `${pt.distance_meters}m da borda`
        : "No Perímetro";

      const popupHtml = `
        <div style="font-family: inherit; font-size: 13px; min-width: 230px; line-height: 1.4;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="background: ${badgeBg}; border: 1px solid ${badgeBorder}; color: ${badgeText}; padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 700;">
              ${statusLabel}
            </span>
            <span style="font-size: 11px; color: #94a3b8;">Linha #${pt.row_index || ''}</span>
          </div>
          <div style="font-weight: 700; color: #0f172a; font-size: 13px; margin-bottom: 6px;">
            ${pt.address || pt.title || 'Ponto do Lote'}
          </div>
          <hr style="border: 0; border-top: 1px solid #e2e8f0; margin-bottom: 6px;" />
          <div style="display: grid; grid-template-columns: 85px 1fr; gap: 4px; font-size: 12px;">
            <span style="color: #64748b;">Distância:</span>
            <strong style="color: ${color};">${distStr}</strong>
            <span style="color: #64748b;">Mancha:</span>
            <span style="color: #0f172a;">${pt.layer_name || 'N/A'}</span>
            <span style="color: #64748b;">POP:</span>
            <span style="color: #0f172a;">${pt.pop || 'N/A'}</span>
            <span style="color: #64748b;">Tecnologia:</span>
            <span style="color: #0f172a;">${pt.technology || 'N/A'}</span>
            <span style="color: #64748b;">Coords:</span>
            <span style="color: #94a3b8; font-size: 11px;">${lat.toFixed(5)}, ${lon.toFixed(5)}</span>
          </div>
          ${pt.message ? `<div style="margin-top: 6px; font-size: 11px; color: #475569; background: #f8fafc; padding: 5px; border-radius: 4px; border-left: 3px solid ${color};">${pt.message}</div>` : ''}
        </div>
      `;

      marker.bindPopup(popupHtml);

      // Tooltip rápido ao passar o mouse
      marker.bindTooltip(`<strong>${pt.title || pt.address || 'Ponto'}</strong><br/>${statusLabel} (${distStr})`, {
        direction: "top",
        offset: [0, -radius]
      });

      if (targetLayer) {
        targetLayer.addLayer(marker);
      }
    });

    // Adicionar as camadas que estiverem marcadas como ativas
    Object.keys(this.batchLayers).forEach((st) => {
      if (this.batchLayersActive[st]) {
        this.batchLayers[st].addTo(this.map);
      }
    });

    if (fitBounds && validCount > 0 && bounds.isValid()) {
      this.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
    }
  }

  /**
   * Alterna a visibilidade de uma categoria do lote (VIAVEL, EM_ANALISE, INVIAVEL).
   */
  setBatchVisibility(status, isVisible) {
    const key = (status || "").toUpperCase();
    if (!this.batchLayers[key]) return;

    this.batchLayersActive[key] = !!isVisible;

    if (isVisible) {
      if (!this.map.hasLayer(this.batchLayers[key])) {
        this.batchLayers[key].addTo(this.map);
      }
    } else {
      if (this.map.hasLayer(this.batchLayers[key])) {
        this.map.removeLayer(this.batchLayers[key]);
      }
    }
  }

  /**
   * Ajusta o zoom do mapa para englobar os pontos do lote atualmente visíveis.
   */
  zoomToBatch(status = null) {
    const bounds = L.latLngBounds([]);
    let count = 0;

    const targetKeys = status ? [status.toUpperCase()] : Object.keys(this.batchLayers).filter(k => this.batchLayersActive[k]);

    targetKeys.forEach((k) => {
      const layer = this.batchLayers[k];
      if (layer) {
        layer.eachLayer((marker) => {
          bounds.extend(marker.getLatLng());
          count++;
        });
      }
    });

    if (count > 0 && bounds.isValid()) {
      this.map.fitBounds(bounds, { padding: [60, 60], maxZoom: 16 });
    }
  }

  /**
   * Limpa todos os pontos de lote plotados no mapa.
   */
  clearBatchPoints() {
    Object.keys(this.batchLayers).forEach((k) => {
      if (this.batchLayers[k]) {
        this.batchLayers[k].clearLayers();
        if (this.map.hasLayer(this.batchLayers[k])) {
          this.map.removeLayer(this.batchLayers[k]);
        }
      }
    });
    this.batchPoints = [];
  }

  /**
   * Verifica se há pontos de lote carregados.
   */
  hasBatchPoints() {
    return this.batchPoints && this.batchPoints.length > 0;
  }

  /**
   * Foca em um ponto específico do lote.
   */
  focusBatchPoint(lat, lon) {
    if (!lat || !lon) return;
    this.map.flyTo([lat, lon], 17, { duration: 1.0 });
  }
}


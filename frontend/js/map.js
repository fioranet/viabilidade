export class MapManager {
  constructor(containerId = "map") {
    this.containerId = containerId;
    this.map = null;
    this.coverageLayer = null;
    this.queryMarker = null;
    this.distanceLine = null;
    
    this.initMap();
  }

  initMap() {
    // Inicializar no centro de São Paulo por padrão
    this.map = L.map(this.containerId, {
      zoomControl: false
    }).setView([-23.565, -46.66], 12);

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
}


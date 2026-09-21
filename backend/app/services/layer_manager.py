import json
import uuid
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.config import LAYERS_DIR, DATA_DIR
from app.models.schemas import LayerMetadata
from app.services.spatial_engine import spatial_engine
from app.services.pop_manager import pop_manager

TECHNOLOGY_COLORS = {
    "Fibra GPON": "#10b981",       # Esmeralda
    "Rede Neutra": "#3b82f6",      # Azul
    "Rádio 5.8GHz": "#f59e0b",     # Âmbar/Laranja
    "Fibra Ponto a Ponto": "#8b5cf6", # Roxo
    "Outros": "#64748b"            # Cinza
}

LAYERS_CONFIG_FILE = DATA_DIR / "layers_config.json"

import unicodedata

def normalize_layer_key(text: str) -> str:
    """Remove acentos, converte para minúsculas e remove pontuações/espaços supérfluos."""
    if not text:
        return ""
    text_nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join([c for c in text_nfkd if not unicodedata.combining(c)])
    return stripped.strip().lower().replace("-", "_").replace(" ", "_")

class LayerManager:
    """Gerenciador de arquivos vetoriais de cobertura geográfica (GeoJSON e KMZ)."""

    def __init__(self):
        self.layers: Dict[str, Dict[str, Any]] = {}
        self.metadata: Dict[str, LayerMetadata] = {}
        self.config: Dict[str, Dict[str, Any]] = {}
        self._load_config()

    def _load_config(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if LAYERS_CONFIG_FILE.exists():
            try:
                with open(LAYERS_CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"[LayerManager] Erro ao ler layers_config.json: {e}")
                self.config = {}
        else:
            self.config = {}

    def _save_config(self):
        try:
            with open(LAYERS_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[LayerManager] Erro ao salvar layers_config.json: {e}")

    def load_all_layers(self):
        """Carrega todos os arquivos GeoJSON do diretório de layers e recria o índice espacial apenas com as camadas ativas."""
        spatial_engine.clear()
        self.layers.clear()
        self.metadata.clear()
        self._load_config()

        geojson_files = list(LAYERS_DIR.glob("*.geojson")) + list(LAYERS_DIR.glob("*.json"))

        for file_path in geojson_files:
            try:
                self._load_single_file(file_path)
            except Exception as e:
                print(f"[LayerManager] Erro ao carregar camada {file_path.name}: {e}")

        spatial_engine.build_index()
        print(f"[LayerManager] {len(self.layers)} camadas carregadas e {len(spatial_engine.geometries)} polígonos ativos indexados no STRtree.")

    def get_primary_layer_ids(self) -> List[str]:
        """Retorna a lista de IDs das camadas marcadas como principais e ativas."""
        return [lid for lid, m in self.metadata.items() if getattr(m, "is_primary", False) and m.enabled]

    def resolve_layer_ids(self, requested_layers: List[str]) -> tuple[List[str], List[str]]:
        """
        Resolve uma lista de nomes ou IDs de camadas fornecidos pelo usuário/API.
        Tolera ausência de acentos (ex: 'poa' -> 'poá'), maiúsculas/minúsculas e busca por nome ou ID.
        Suporta 'primary', 'principal' ou '__primary__' para resolver para as camadas principais ativas.
        Retorna (resolved_layer_ids, not_found_inputs).
        """
        resolved: List[str] = []
        not_found: List[str] = []

        if not requested_layers:
            return resolved, not_found

        for item in requested_layers:
            if not item or not str(item).strip():
                continue
            item_clean = str(item).strip()
            item_norm = normalize_layer_key(item_clean)

            # Caso especial: 'primary' ou 'principal' ou '__primary__'
            if item_norm in ["primary", "principal", "__primary__", "padrao", "default"]:
                primaries = self.get_primary_layer_ids()
                if primaries:
                    for pid in primaries:
                        if pid not in resolved:
                            resolved.append(pid)
                else:
                    # Se não houver principais marcadas, recorre às ativas
                    for lid, meta in self.metadata.items():
                        if meta.enabled and lid not in resolved:
                            resolved.append(lid)
                continue

            matched_id = None
            # 1. Busca exata por ID ou Nome
            for lid, meta in self.metadata.items():
                if lid == item_clean or meta.name == item_clean:
                    matched_id = lid
                    break

            # 2. Busca normalizada (sem acento, minúsculas, underscores)
            if not matched_id:
                for lid, meta in self.metadata.items():
                    if normalize_layer_key(lid) == item_norm or normalize_layer_key(meta.name) == item_norm:
                        matched_id = lid
                        break

            if matched_id:
                if matched_id not in resolved:
                    resolved.append(matched_id)
            else:
                not_found.append(item_clean)

        return resolved, not_found

    def _load_single_file(self, file_path: Path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        layer_id = file_path.stem
        cfg = self.config.get(layer_id, {})

        # Extrair ou deduzir tecnologia e nome
        name = cfg.get("name") or data.get("name") or file_path.stem.replace("_", " ").title()
        tech = cfg.get("technology") or data.get("technology") or "Fibra GPON"
        color = data.get("color") or TECHNOLOGY_COLORS.get(tech, "#10b981")
        enabled = cfg.get("enabled", True)
        is_primary = cfg.get("is_primary", False)
        pop_id = cfg.get("pop_id")
        pop_name = cfg.get("pop_name")

        # Se não tiver POP configurado, tentar inferir dos POPs existentes
        if not pop_name:
            all_pops = pop_manager.get_all()
            if all_pops:
                pop_id = all_pops[0].id
                pop_name = all_pops[0].name

        features = data.get("features", [])
        polygon_count = len(features)

        meta = LayerMetadata(
            id=layer_id,
            filename=file_path.name,
            name=name,
            technology=tech,
            color=color,
            polygon_count=polygon_count,
            enabled=enabled,
            is_primary=is_primary,
            pop_id=pop_id,
            pop_name=pop_name
        )

        self.layers[layer_id] = data
        self.metadata[layer_id] = meta

        # Se a camada estiver ativa, registrar no motor espacial
        if enabled:
            spatial_engine.add_layer_features(
                layer_id=layer_id,
                layer_name=name,
                technology=tech,
                geojson_data=data,
                default_pop=pop_name
            )

    def toggle_layer(self, layer_id: str) -> Optional[LayerMetadata]:
        """Ativa ou desativa uma camada e remonta o índice espacial."""
        meta = self.metadata.get(layer_id)
        if not meta:
            return None

        new_status = not meta.enabled
        meta.enabled = new_status

        if layer_id not in self.config:
            self.config[layer_id] = {}
        self.config[layer_id]["enabled"] = new_status
        self._save_config()

        # Recarregar motor espacial para refletir a ativação/desativação imediata
        self.load_all_layers()
        return self.metadata.get(layer_id)

    def toggle_primary(self, layer_id: str) -> Optional[LayerMetadata]:
        """Marca ou desmarca uma camada como principal/padrão do sistema."""
        meta = self.metadata.get(layer_id)
        if not meta:
            return None

        new_status = not getattr(meta, "is_primary", False)
        meta.is_primary = new_status

        if layer_id not in self.config:
            self.config[layer_id] = {}
        self.config[layer_id]["is_primary"] = new_status
        self._save_config()
        return meta

    def delete_layer(self, layer_id: str) -> bool:
        """Exclui o arquivo da camada e atualiza o motor espacial."""
        meta = self.metadata.get(layer_id)
        file_deleted = False

        if meta:
            file_path = LAYERS_DIR / meta.filename
            if file_path.exists():
                try:
                    file_path.unlink()
                    file_deleted = True
                except Exception as e:
                    print(f"[LayerManager] Erro ao deletar arquivo {file_path}: {e}")

        if not file_deleted:
            # Tentar encontrar por id direto
            for p in list(LAYERS_DIR.glob(f"{layer_id}.*")):
                try:
                    p.unlink()
                    file_deleted = True
                except Exception:
                    pass

        if layer_id in self.config:
            del self.config[layer_id]
            self._save_config()

        self.load_all_layers()
        return file_deleted

    def update_layer_pop(self, layer_id: str, pop_id: str, pop_name: str) -> Optional[LayerMetadata]:
        """Associa uma camada a um POP específico."""
        meta = self.metadata.get(layer_id)
        if not meta:
            return None

        meta.pop_id = pop_id
        meta.pop_name = pop_name

        if layer_id not in self.config:
            self.config[layer_id] = {}
        self.config[layer_id]["pop_id"] = pop_id
        self.config[layer_id]["pop_name"] = pop_name
        self._save_config()

        self.load_all_layers()
        return self.metadata.get(layer_id)

    def get_all_metadata(self) -> List[LayerMetadata]:
        return list(self.metadata.values())

    def get_combined_geojson(self) -> Dict[str, Any]:
        """Retorna uma FeatureCollection unificada com todas as camadas ativas e suas propriedades estilizadas."""
        combined_features = []

        for layer_id, layer_data in self.layers.items():
            meta = self.metadata.get(layer_id)
            if not meta or not meta.enabled:
                continue

            for feat in layer_data.get("features", []):
                props = dict(feat.get("properties", {}) or {})
                props["layer_id"] = meta.id
                props["layer_name"] = meta.name
                props["technology"] = meta.technology
                props["color"] = meta.color
                props["pop"] = meta.pop_name or props.get("pop", "POP Central")
                
                feat_copy = dict(feat)
                feat_copy["properties"] = props
                combined_features.append(feat_copy)

        return {
            "type": "FeatureCollection",
            "features": combined_features
        }

    def import_kmz_or_kml(self, file_path: Path, layer_name: str, technology: str, pop_id: Optional[str] = None, pop_name: Optional[str] = None) -> Path:
        """
        Converte um arquivo KMZ ou KML em GeoJSON padronizado e salva no diretório de layers.
        """
        kml_content = ""
        
        if file_path.suffix.lower() == ".kmz":
            with zipfile.ZipFile(file_path, 'r') as z:
                kml_names = [n for n in z.namelist() if n.lower().endswith(".kml")]
                if not kml_names:
                    raise ValueError("Nenhum arquivo KML encontrado dentro do arquivo KMZ.")
                with z.open(kml_names[0]) as kml_file:
                    kml_content = kml_file.read().decode("utf-8", errors="ignore")
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                kml_content = f.read()

        geojson_data = self._kml_to_geojson(kml_content, layer_name, technology, pop_name=pop_name)
        
        safe_name = "".join([c if c.isalnum() else "_" for c in layer_name]).strip("_").lower()
        if not safe_name:
            safe_name = f"layer_{uuid.uuid4().hex[:8]}"
        
        output_file = LAYERS_DIR / f"{safe_name}.geojson"
        with open(output_file, "w", encoding="utf-8") as out:
            json.dump(geojson_data, out, ensure_ascii=False, indent=2)

        # Salvar configuração inicial de POP
        if pop_id or pop_name:
            self.config[safe_name] = {
                "enabled": True,
                "pop_id": pop_id,
                "pop_name": pop_name,
                "technology": technology,
                "name": layer_name
            }
            self._save_config()

        # Recarregar camadas
        self.load_all_layers()
        return output_file

    def _kml_to_geojson(self, kml_text: str, layer_name: str, technology: str, pop_name: Optional[str] = None) -> Dict[str, Any]:
        """Parser leve de KML para GeoJSON padrão RFC 7946 (suporta Polygon e MultiGeometry)."""
        root = ET.fromstring(kml_text)
        
        for elem in root.iter():
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]

        def find_all(element, tag):
            return element.findall(f".//{tag}")

        def find_one(element, tag):
            return element.find(f".//{tag}")

        placemarks = find_all(root, "Placemark")
        features = []

        assigned_pop = pop_name or "POP Central"

        for p_idx, pm in enumerate(placemarks):
            name_el = find_one(pm, "name")
            desc_el = find_one(pm, "description")
            
            p_name = name_el.text.strip() if name_el is not None and name_el.text else f"{layer_name}-{p_idx+1}"
            p_desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

            polygons = find_all(pm, "Polygon")
            for poly in polygons:
                outer = find_one(poly, "outerBoundaryIs")
                if outer is None:
                    continue
                coord_el = find_one(outer, "coordinates")
                if coord_el is None or not coord_el.text:
                    continue

                import re
                clean_coords = re.sub(r"\s*,\s*", ",", coord_el.text.strip())
                raw_coords = clean_coords.split()
                ring = []
                for pt_str in raw_coords:
                    parts = pt_str.split(",")
                    if len(parts) >= 2:
                        try:
                            lon = float(parts[0])
                            lat = float(parts[1])
                            ring.append([lon, lat])
                        except ValueError:
                            continue

                if len(ring) >= 3:
                    if ring[0] != ring[-1]:
                        ring.append(ring[0])

                    feat = {
                        "type": "Feature",
                        "properties": {
                            "name": p_name,
                            "description": p_desc,
                            "technology": technology,
                            "region": p_name,
                            "pop": assigned_pop
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [ring]
                        }
                    }
                    features.append(feat)

        return {
            "type": "FeatureCollection",
            "name": layer_name,
            "technology": technology,
            "color": TECHNOLOGY_COLORS.get(technology, "#10b981"),
            "features": features
        }

# Instância singleton global
layer_manager = LayerManager()

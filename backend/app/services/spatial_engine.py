import math
from typing import List, Dict, Any, Optional, Tuple
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from shapely.strtree import STRtree
from shapely.ops import nearest_points
import pyproj

from app.models.schemas import (
    ViabilityStatus,
    Coordinates,
    PolygonMatchInfo,
    ViabilityResponse
)
from app.config import TOLERANCIA_BORDA_METROS, MAX_DISTANCIA_ANALISE_METROS

class SpatialEngine:
    """Motor Espacial de Alta Performance baseado em Shapely e STRtree."""

    def __init__(self):
        self.geometries: List[Any] = []
        self.metadata_list: List[Dict[str, Any]] = []
        self.tree: Optional[STRtree] = None
        self.geod = pyproj.Geod(ellps="WGS84")

    def _haversine_distance(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Cálculo geodésico preciso de distância em metros entre duas coordenadas WGS84."""
        try:
            _, _, distance = self.geod.inv(lon1, lat1, lon2, lat2)
            return distance
        except Exception:
            # Fallback Haversine caso pyproj falhe
            R = 6371000  # Raio da Terra em metros
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            delta_phi = math.radians(lat2 - lat1)
            delta_lambda = math.radians(lon2 - lon1)
            a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c

    def clear(self):
        """Limpa as geometrias carregadas."""
        self.geometries = []
        self.metadata_list = []
        self.tree = None

    def add_layer_features(self, layer_id: str, layer_name: str, technology: str, geojson_data: Dict[str, Any], default_pop: Optional[str] = None):
        """Adiciona features de um GeoJSON ao motor espacial."""
        features = geojson_data.get("features", [])
        for feat in features:
            geom_dict = feat.get("geometry")
            if not geom_dict:
                continue

            try:
                geom = shape(geom_dict)
            except Exception:
                continue

            props = feat.get("properties", {}) or {}
            
            # Extrair campos comuns de telecom se existirem
            region = (
                props.get("region") or props.get("regiao") or props.get("bairro") or
                props.get("cidade") or props.get("Name") or props.get("name") or "Região Coberta"
            )
            pop = default_pop or props.get("pop") or props.get("POP") or props.get("estacao") or props.get("hub") or "POP Central"
            polygon_name = props.get("name") or props.get("Name") or props.get("nome") or f"Mancha-{len(self.geometries) + 1}"
            tech = props.get("technology") or props.get("tecnologia") or technology

            meta = {
                "layer_id": layer_id,
                "layer_name": layer_name,
                "polygon_id": str(props.get("id", len(self.geometries))),
                "polygon_name": str(polygon_name),
                "region": str(region),
                "pop": str(pop),
                "technology": str(tech),
                "properties": props
            }

            self.geometries.append(geom)
            self.metadata_list.append(meta)

    def build_index(self):
        """Reconstrói a árvore espacial R-tree (STRtree) com todas as geometrias carregadas."""
        if self.geometries:
            self.tree = STRtree(self.geometries)
        else:
            self.tree = None

    def check_viability(self, latitude: float, longitude: float) -> ViabilityResponse:
        """
        Verifica a viabilidade técnica de um ponto (Lat/Long).
        Retorna ViabilityResponse detalhando se o ponto está dentro, na borda ou distante.
        """
        coord = Coordinates(latitude=latitude, longitude=longitude)
        
        if not self.tree or not self.geometries:
            return ViabilityResponse(
                status=ViabilityStatus.INVIAVEL,
                location=coord,
                distance_to_nearest_meters=0.0,
                message="Nenhuma mancha de cobertura geográfica cadastrada ou ativa no sistema."
            )

        point = Point(longitude, latitude)

        # 1. Busca por candidatos via R-Tree (STRtree)
        # query() retorna índices de geometrias cujas bounding-boxes interceptam o ponto
        candidate_indices = self.tree.query(point)

        # 2. Verificação exata Point-in-Polygon
        for idx in candidate_indices:
            geom = self.geometries[idx]
            # contains ou touches (na borda)
            if geom.contains(point) or geom.touches(point):
                meta = self.metadata_list[idx]
                matched = PolygonMatchInfo(
                    layer_id=meta["layer_id"],
                    layer_name=meta["layer_name"],
                    polygon_id=meta["polygon_id"],
                    polygon_name=meta["polygon_name"],
                    region=meta["region"],
                    pop=meta["pop"],
                    technology=meta["technology"],
                    properties=meta["properties"]
                )
                return ViabilityResponse(
                    status=ViabilityStatus.VIAVEL,
                    location=coord,
                    matched_polygon=matched,
                    distance_to_nearest_meters=0.0,
                    message=f"Viabilidade Confirmada! Atendido pela mancha '{matched.polygon_name}' via {matched.technology} ({matched.pop})."
                )

        # 3. Ponto fora das manchas: calcular a menor distância real em metros
        nearest_distance_meters = float("inf")
        nearest_meta = None

        for idx, geom in enumerate(self.geometries):
            # Encontra o ponto mais próximo na borda da geometria
            p1, p2 = nearest_points(geom, point)
            # p1 é o ponto na geometria, p2 é o ponto pesquisado
            dist_m = self._haversine_distance(p1.x, p1.y, p2.x, p2.y)
            if dist_m < nearest_distance_meters:
                nearest_distance_meters = dist_m
                nearest_meta = self.metadata_list[idx]

        # 4. Avaliar tolerância de borda e raio de extensão de rede
        nearest_distance_meters = round(nearest_distance_meters, 1)

        if nearest_distance_meters <= TOLERANCIA_BORDA_METROS:
            # Considerar viável por tolerância de borda GPS/satélite
            matched = PolygonMatchInfo(
                layer_id=nearest_meta["layer_id"],
                layer_name=nearest_meta["layer_name"],
                polygon_id=nearest_meta["polygon_id"],
                polygon_name=nearest_meta["polygon_name"],
                region=nearest_meta["region"],
                pop=nearest_meta["pop"],
                technology=nearest_meta["technology"],
                properties=nearest_meta["properties"]
            )
            return ViabilityResponse(
                status=ViabilityStatus.VIAVEL,
                location=coord,
                matched_polygon=matched,
                distance_to_nearest_meters=nearest_distance_meters,
                message=f"Viabilidade Confirmada (na borda da mancha a {nearest_distance_meters}m). Atendido por {matched.technology} ({matched.pop})."
            )

        elif nearest_distance_meters <= MAX_DISTANCIA_ANALISE_METROS:
            # Em Análise (potencial extensão de rede / lançamento de cabo drop)
            matched = PolygonMatchInfo(
                layer_id=nearest_meta["layer_id"],
                layer_name=nearest_meta["layer_name"],
                polygon_id=nearest_meta["polygon_id"],
                polygon_name=nearest_meta["polygon_name"],
                region=nearest_meta["region"],
                pop=nearest_meta["pop"],
                technology=nearest_meta["technology"],
                properties=nearest_meta["properties"]
            )
            return ViabilityResponse(
                status=ViabilityStatus.EM_ANALISE,
                location=coord,
                matched_polygon=matched,
                distance_to_nearest_meters=nearest_distance_meters,
                message=f"Em Análise Técnica! Endereço a {nearest_distance_meters}m da mancha mais próxima ({matched.polygon_name} - {matched.pop}). Viável mediante extensão de rede."
            )
        else:
            return ViabilityResponse(
                status=ViabilityStatus.INVIAVEL,
                location=coord,
                distance_to_nearest_meters=nearest_distance_meters,
                message=f"Inviável no momento. A mancha de cobertura mais próxima está a aproximadamente {nearest_distance_meters / 1000:.2f} km."
            )

# Instância singleton global do motor espacial
spatial_engine = SpatialEngine()

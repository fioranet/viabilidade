import math
from typing import List, Dict, Any, Optional, Tuple, Union, Set
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

TECH_PRIORITY = {
    "Fibra GPON": 4,
    "Fibra Ponto a Ponto": 3,
    "Rede Neutra": 2,
    "Rádio 5.8GHz": 1,
}

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

    def update_geometries(self, features_with_meta: List[Dict[str, Any]]):
        """
        Atualiza o índice espacial R-Tree com uma lista de features GeoJSON e seus metadados.
        Reconstrói o STRtree em memória para máxima velocidade.
        """
        self.geometries = []
        self.metadata_list = []

        for item in features_with_meta:
            try:
                geom_dict = item.get("geometry")
                if not geom_dict:
                    continue

                geom_obj = shape(geom_dict)
                # Garantir que é Polygon ou MultiPolygon válido
                if not geom_obj.is_valid:
                    geom_obj = geom_obj.buffer(0)

                if geom_obj.is_empty:
                    continue

                self.geometries.append(geom_obj)
                self.metadata_list.append({
                    "layer_id": item.get("layer_id"),
                    "layer_name": item.get("layer_name"),
                    "polygon_id": item.get("polygon_id"),
                    "polygon_name": item.get("polygon_name"),
                    "region": item.get("region"),
                    "pop": item.get("pop"),
                    "technology": item.get("technology", "Fibra GPON"),
                    "properties": item.get("properties", {})
                })
            except Exception as e:
                continue

        if self.geometries:
            self.tree = STRtree(self.geometries)
        else:
            self.tree = None

    def check_viability(
        self,
        latitude: float,
        longitude: float,
        target_layer_ids: Optional[Union[List[str], set]] = None,
        primary_layer_ids: Optional[Union[List[str], Set[str]]] = None
    ) -> ViabilityResponse:
        """
        Verifica a viabilidade técnica de um ponto (Lat/Long).
        Permite filtrar opcionalmente por um conjunto de IDs de camadas (target_layer_ids).
        Trata sobreposição de múltiplos polígonos, priorizando camadas primárias e tecnologias mais nobres.
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

        # Determinar conjunto de camadas primárias se não fornecido
        if primary_layer_ids is None:
            try:
                from app.services.layer_manager import layer_manager
                primary_layer_set = set(layer_manager.get_primary_layer_ids())
            except Exception:
                primary_layer_set = set()
        else:
            primary_layer_set = set(primary_layer_ids)

        # Converter para set para checagem O(1) se fornecido
        target_set = set(target_layer_ids) if target_layer_ids is not None else None

        if target_set is not None:
            has_matching_geoms = any(m["layer_id"] in target_set for m in self.metadata_list)
            if not has_matching_geoms:
                return ViabilityResponse(
                    status=ViabilityStatus.INVIAVEL,
                    location=coord,
                    distance_to_nearest_meters=0.0,
                    message="Nenhuma mancha ativa encontrada para o(s) mapa(s) especificado(s)."
                )

        point = Point(longitude, latitude)

        # 1. Busca por candidatos via R-Tree (STRtree)
        # query() retorna índices de geometrias cujas bounding-boxes interceptam o ponto
        candidate_indices = self.tree.query(point)

        # 2. Verificação exata Point-in-Polygon (coleta todas as manchas que cobrem o ponto)
        all_matches: List[PolygonMatchInfo] = []
        for idx in candidate_indices:
            meta = self.metadata_list[idx]
            if target_set is not None and meta["layer_id"] not in target_set:
                continue

            geom = self.geometries[idx]
            # contains ou touches (na borda)
            if geom.contains(point) or geom.touches(point):
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
                all_matches.append(matched)

        if all_matches:
            # Ordenar os polígonos sobrepostos por prioridade:
            # 1. Pertence à camada principal (is_primary)
            # 2. Tecnologia (Fibra GPON > P2P > Rede Neutra > Rádio)
            # 3. Nome da camada / polígono
            def match_sort_key(m: PolygonMatchInfo):
                is_prim = 1 if m.layer_id in primary_layer_set else 0
                tech_score = TECH_PRIORITY.get(m.technology, 0)
                return (is_prim, tech_score, m.layer_name or "", m.polygon_name or "")

            all_matches.sort(key=match_sort_key, reverse=True)
            best_match = all_matches[0]

            if len(all_matches) > 1:
                other_names = [f"'{m.polygon_name}' ({m.technology})" for m in all_matches[1:]]
                overlap_text = f" (Sobreposição: coberto também por {', '.join(other_names)})"
                msg = f"Viabilidade Confirmada! Atendido principalmente pela mancha '{best_match.polygon_name}' via {best_match.technology} ({best_match.pop}).{overlap_text}"
            else:
                msg = f"Viabilidade Confirmada! Atendido pela mancha '{best_match.polygon_name}' via {best_match.technology} ({best_match.pop})."

            return ViabilityResponse(
                status=ViabilityStatus.VIAVEL,
                location=coord,
                matched_polygon=best_match,
                all_matched_polygons=all_matches,
                distance_to_nearest_meters=0.0,
                message=msg
            )

        # 3. Ponto fora das manchas: calcular a menor distância real em metros apenas considerando as camadas alvo
        nearest_distance_meters = float("inf")
        nearest_meta = None

        for idx, geom in enumerate(self.geometries):
            meta = self.metadata_list[idx]
            if target_set is not None and meta["layer_id"] not in target_set:
                continue

            # Encontra o ponto mais próximo na borda da geometria
            p1, p2 = nearest_points(geom, point)
            # p1 é o ponto na geometria, p2 é o ponto pesquisado
            dist_m = self._haversine_distance(p1.x, p1.y, p2.x, p2.y)
            if dist_m < nearest_distance_meters:
                nearest_distance_meters = dist_m
                nearest_meta = meta

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
                all_matched_polygons=[matched],
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
                all_matched_polygons=[matched],
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

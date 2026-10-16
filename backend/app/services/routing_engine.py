import math
import uuid
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from app.config import UPLOADS_DIR
from app.models.schemas import (
    RoutingOptions,
    RouteStop,
    TechnicianRoute,
    RoutePlanResponse
)
from app.services.pop_manager import pop_manager

# Paleta de cores vibrantes e distintas para cada técnico/dia
TECHNICIAN_COLORS = [
    "#06b6d4", # 1: Ciano
    "#f97316", # 2: Laranja Âmbar
    "#10b981", # 3: Esmeralda
    "#8b5cf6", # 4: Violeta Claro
    "#ec4899", # 5: Rosa Choque
    "#eab308", # 6: Amarelo Dourado
    "#3b82f6", # 7: Azul Real
    "#14b8a6", # 8: Teal
    "#f43f5e", # 9: Carmim
    "#84cc16"  # 10: Lima
]

# Fator de sinuosidade urbana média para converter distância esférica em malha viária real
URBAN_CIRCUITY_FACTOR = 1.35
AVERAGE_URBAN_SPEED_KMH = 32.0 # Velocidade média urbana em deslocamento técnico

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distância ortodrômica em metros entre dois pontos geográficos."""
    r = 6371000.0  # Raio médio da Terra em metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c

class RoutingEngine:
    """
    Motor de Roteirização Inteligente para Vistorias e Instalações em Campo.
    Implementa clustering geográfico multi-técnicos, otimizador TSP 2-Opt,
    detecção de distâncias proibitivas com desdobramento em dias subsequentes
    e geração de waypoints de navegação para Google Maps e Waze.
    """

    def __init__(self):
        self.cached_plans: Dict[str, RoutePlanResponse] = {}

    def _resolve_depot(
        self,
        points: List[Dict[str, Any]],
        depot_mode: str,
        custom_lat: Optional[float] = None,
        custom_lon: Optional[float] = None,
        custom_name: Optional[str] = None
    ) -> Tuple[float, float, str]:
        """
        Determina as coordenadas e o nome do ponto de partida da equipe.
        """
        if depot_mode == "custom" and custom_lat is not None and custom_lon is not None:
            return custom_lat, custom_lon, custom_name or "Ponto de Saída Customizado"

        if depot_mode == "first_point" and points:
            first = points[0]
            return first["latitude"], first["longitude"], f"Ponto Inicial ({first.get('title', 'Origem')})"

        # Modo 'nearest_pop' ou padrão
        pops = pop_manager.get_all()
        if pops and points:
            # Calcular o centróide médio das paradas
            mean_lat = sum(p["latitude"] for p in points) / len(points)
            mean_lon = sum(p["longitude"] for p in points) / len(points)

            # Encontrar o POP mais próximo do baricentro
            best_pop = None
            min_dist = float("inf")
            for pop in pops:
                d = haversine_distance(mean_lat, mean_lon, pop.latitude, pop.longitude)
                if d < min_dist:
                    min_dist = d
                    best_pop = pop

            if best_pop:
                return best_pop.latitude, best_pop.longitude, f"POP {best_pop.name}"

        # Fallback: Usar o primeiro ponto disponível ou centro de São Paulo
        if points:
            return points[0]["latitude"], points[0]["longitude"], "Ponto Inicial (Primeira Parada)"

        return -23.5505, -46.6333, "Sede Central (SP)"

    def _cluster_points_kmeans(
        self,
        points: List[Dict[str, Any]],
        k: int
    ) -> List[List[Dict[str, Any]]]:
        """
        Particiona espacialmente os pontos em k grupos compactos usando K-Means geográfico.
        """
        if k <= 1 or len(points) <= k:
            if k == 1:
                return [points]
            return [[p] for p in points]

        # Inicialização com K-Means++ para centróides bem distribuídos
        centroids = [[points[0]["latitude"], points[0]["longitude"]]]
        while len(centroids) < k:
            dists = []
            for p in points:
                min_d = min(
                    haversine_distance(p["latitude"], p["longitude"], c[0], c[1])
                    for c in centroids
                )
                dists.append(min_d ** 2)
            
            # Escolher ponto com maior distância ponderada
            total_dist = sum(dists)
            if total_dist == 0:
                centroids.append([points[len(centroids) % len(points)]["latitude"], points[len(centroids) % len(points)]["longitude"]])
            else:
                target_dist = total_dist * 0.9
                cum_dist = 0.0
                picked = points[-1]
                for idx, p in enumerate(points):
                    cum_dist += dists[idx]
                    if cum_dist >= target_dist:
                        picked = p
                        break
                centroids.append([picked["latitude"], picked["longitude"]])

        # Loop de refinamento do K-Means (máximo 15 iterações para velocidade)
        clusters: List[List[Dict[str, Any]]] = [[] for _ in range(k)]
        for _ in range(15):
            clusters = [[] for _ in range(k)]
            for p in points:
                nearest_idx = min(
                    range(k),
                    key=lambda i: haversine_distance(p["latitude"], p["longitude"], centroids[i][0], centroids[i][1])
                )
                clusters[nearest_idx].append(p)

            # Recalcular centróides
            changed = False
            for i in range(k):
                if clusters[i]:
                    new_lat = sum(p["latitude"] for p in clusters[i]) / len(clusters[i])
                    new_lon = sum(p["longitude"] for p in clusters[i]) / len(clusters[i])
                    if abs(new_lat - centroids[i][0]) > 0.0001 or abs(new_lon - centroids[i][1]) > 0.0001:
                        centroids[i] = [new_lat, new_lon]
                        changed = True
            if not changed:
                break

        # Remover grupos vazios
        return [c for c in clusters if c]

    def _solve_tsp_2opt(
        self,
        depot_lat: float,
        depot_lon: float,
        stops: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Ordena as visitas para minimizar a distância total partindo do depot.
        Usa heurística do Vizinho Mais Próximo + Refinamento 2-Opt Local Search.
        """
        if len(stops) <= 2:
            return stops

        # 1. Construção Gulosa (Nearest Neighbor)
        unvisited = list(stops)
        route: List[Dict[str, Any]] = []
        curr_lat, curr_lon = depot_lat, depot_lon

        while unvisited:
            best_idx = min(
                range(len(unvisited)),
                key=lambda i: haversine_distance(curr_lat, curr_lon, unvisited[i]["latitude"], unvisited[i]["longitude"])
            )
            picked = unvisited.pop(best_idx)
            route.append(picked)
            curr_lat, curr_lon = picked["latitude"], picked["longitude"]

        # 2. Refinamento 2-Opt (Desata cruzamentos de arestas)
        n = len(route)
        if n < 4:
            return route

        improved = True
        iterations = 0
        while improved and iterations < 50:
            improved = False
            iterations += 1
            for i in range(n - 1):
                for j in range(i + 2, n):
                    # Ponto anterior a i (ou o depot)
                    p_prev_lat, p_prev_lon = (depot_lat, depot_lon) if i == 0 else (route[i - 1]["latitude"], route[i - 1]["longitude"])
                    p_i = route[i]
                    p_j = route[j]
                    p_next = route[j + 1] if (j + 1) < n else None

                    # Distância atual
                    d_current = haversine_distance(p_prev_lat, p_prev_lon, p_i["latitude"], p_i["longitude"])
                    if p_next:
                        d_current += haversine_distance(p_j["latitude"], p_j["longitude"], p_next["latitude"], p_next["longitude"])

                    # Distância invertida
                    d_reversed = haversine_distance(p_prev_lat, p_prev_lon, p_j["latitude"], p_j["longitude"])
                    if p_next:
                        d_reversed += haversine_distance(p_i["latitude"], p_i["longitude"], p_next["latitude"], p_next["longitude"])

                    if d_reversed + 5.0 < d_current: # Ganho significativo de pelo menos 5 metros
                        route[i : j + 1] = reversed(route[i : j + 1])
                        improved = True
                        break
                if improved:
                    break

        return route

    def generate_plan(
        self,
        points: List[Dict[str, Any]],
        options: RoutingOptions,
        job_id: Optional[str] = None
    ) -> RoutePlanResponse:
        """
        Executa o pipeline completo de roteirização:
        1. Filtra os pontos elegíveis
        2. Resolve o ponto de partida
        3. Particiona em clusters geográficos (equipes de técnicos)
        4. Otimiza a sequência de cada técnico via 2-Opt
        5. Detecta distâncias proibitivas e desdobra em dias se necessário
        6. Monta URLs de navegação e polylines Leaflet
        """
        plan_id = str(uuid.uuid4())

        # 1. Filtrar pontos com coordenadas válidas e status solicitado
        valid_points = []
        for p in points:
            lat = p.get("latitude")
            lon = p.get("longitude")
            if lat is not None and lon is not None:
                st = str(p.get("status", "")).upper()
                if not options.filter_status or st in [s.upper() for s in options.filter_status]:
                    valid_points.append(p)

        if not valid_points:
            return RoutePlanResponse(
                plan_id=plan_id,
                job_id=job_id,
                created_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                num_technicians=options.num_technicians,
                total_assigned_stops=0,
                unassigned_stops=[],
                routes=[],
                summary_message="Nenhum ponto com coordenadas válidas atendeu aos critérios de filtro selecionados."
            )

        # 2. Resolver o ponto de partida
        depot_lat, depot_lon, depot_name = self._resolve_depot(
            valid_points,
            depot_mode=options.depot_mode,
            custom_lat=options.custom_depot_lat,
            custom_lon=options.custom_depot_lon,
            custom_name=options.custom_depot_name
        )

        # 3. Particionar os pontos entre os técnicos disponíveis
        k_clusters = min(options.num_technicians, len(valid_points))
        clusters = self._cluster_points_kmeans(valid_points, k_clusters)

        generated_routes: List[TechnicianRoute] = []
        total_assigned = 0

        # 4. Processar cada grupo de técnico
        for tech_idx, cluster_pts in enumerate(clusters):
            tech_color = TECHNICIAN_COLORS[tech_idx % len(TECHNICIAN_COLORS)]
            tech_base_name = f"Técnico {tech_idx + 1}"

            # Otimizar a sequência do cluster
            sorted_stops = self._solve_tsp_2opt(depot_lat, depot_lon, cluster_pts)

            # Verificar necessidade de desdobramento em múltiplos dias
            # Fatiar em blocos de até max_stops_per_technician
            max_stops = options.max_stops_per_technician
            chunks = [sorted_stops[i : i + max_stops] for i in range(0, len(sorted_stops), max_stops)]

            for day_idx, chunk in enumerate(chunks, 1):
                route_stops: List[RouteStop] = []
                polyline_coords: List[List[float]] = [[depot_lat, depot_lon]]
                
                prev_lat, prev_lon = depot_lat, depot_lon
                accum_distance_m = 0.0
                accum_travel_minutes = 0.0
                is_excessive = False

                for seq_order, pt in enumerate(chunk, 1):
                    p_lat = pt["latitude"]
                    p_lon = pt["longitude"]
                    
                    # Distância ortodrômica com fator urbano de sinuosidade viária
                    dist_leg = haversine_distance(prev_lat, prev_lon, p_lat, p_lon) * URBAN_CIRCUITY_FACTOR
                    accum_distance_m += dist_leg

                    # Tempo de deslocamento estimado em minutos
                    travel_time_min = (dist_leg / 1000.0) / AVERAGE_URBAN_SPEED_KMH * 60.0
                    accum_travel_minutes += travel_time_min

                    # Tempo cumulativo = deslocamento total + tempo de atendimento nas visitas anteriores
                    cum_time = accum_travel_minutes + (seq_order * options.avg_service_time_minutes)

                    # Verificar se há salto com distância proibitiva (> 35 km de um único ponto para o próximo)
                    if dist_leg > 35000.0:
                        is_excessive = True

                    # URLs de Navegação Mobile
                    gmaps_url = f"https://www.google.com/maps/dir/?api=1&destination={p_lat},{p_lon}"
                    waze_url = f"https://waze.com/ul?ll={p_lat},{p_lon}&navigate=yes"

                    stop_obj = RouteStop(
                        sequence_order=seq_order,
                        point_id=str(pt.get("id", f"pt_{seq_order}")),
                        title=str(pt.get("title", f"Parada {seq_order}")),
                        address=str(pt.get("address", "Endereço não informado")),
                        latitude=p_lat,
                        longitude=p_lon,
                        status=str(pt.get("status", "EM_ANALISE")),
                        distance_from_prev_meters=round(dist_leg, 1),
                        estimated_travel_minutes=round(travel_time_min, 1),
                        cumulative_time_minutes=round(cum_time, 1),
                        google_maps_url=gmaps_url,
                        waze_url=waze_url
                    )
                    route_stops.append(stop_obj)
                    polyline_coords.append([p_lat, p_lon])
                    prev_lat, prev_lon = p_lat, p_lon

                total_dist_km = round(accum_distance_m / 1000.0, 1)
                total_duration_hours = round((accum_travel_minutes + len(chunk) * options.avg_service_time_minutes) / 60.0, 1)

                if total_dist_km > options.max_distance_km:
                    is_excessive = True

                # Montar URL de rota completa multi-paradas para o Google Maps
                # Formato: origin=...&destination=...&waypoints=...
                gmaps_multi_url = ""
                if route_stops:
                    origin_str = f"{depot_lat},{depot_lon}"
                    dest_str = f"{route_stops[-1].latitude},{route_stops[-1].longitude}"
                    if len(route_stops) > 1:
                        waypoints_str = "|".join(f"{s.latitude},{s.longitude}" for s in route_stops[:-1])
                        gmaps_multi_url = f"https://www.google.com/maps/dir/?api=1&origin={origin_str}&destination={dest_str}&waypoints={waypoints_str}"
                    else:
                        gmaps_multi_url = f"https://www.google.com/maps/dir/?api=1&origin={origin_str}&destination={dest_str}"

                warning = None
                if is_excessive:
                    warning = "Atenção: Este roteiro possui distâncias elevadas entre paradas ou ultrapassou a quilometragem recomendada."

                route_title = tech_base_name if len(chunks) == 1 else f"{tech_base_name} - Dia {day_idx}"

                generated_routes.append(TechnicianRoute(
                    technician_id=tech_idx + 1,
                    technician_name=route_title,
                    color_hex=tech_color,
                    day_number=day_idx,
                    depot_name=depot_name,
                    depot_lat=depot_lat,
                    depot_lon=depot_lon,
                    total_stops=len(route_stops),
                    total_distance_km=total_dist_km,
                    total_estimated_duration_hours=total_duration_hours,
                    is_excessive_distance=is_excessive,
                    warning_message=warning,
                    google_maps_multi_stop_url=gmaps_multi_url,
                    polyline_coords=polyline_coords,
                    stops=route_stops
                ))
                total_assigned += len(route_stops)

        summary = (
            f"Roteirização concluída com sucesso! {total_assigned} visitas foram distribuídas em "
            f"{len(generated_routes)} roteiro(s) operacional(is) partindo de '{depot_name}'."
        )

        plan_response = RoutePlanResponse(
            plan_id=plan_id,
            job_id=job_id,
            created_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            num_technicians=options.num_technicians,
            total_assigned_stops=total_assigned,
            unassigned_stops=[],
            routes=generated_routes,
            summary_message=summary,
            download_kmz_url=f"/api/routing/export-kmz/{plan_id}",
            download_csv_url=f"/api/routing/export-csv/{plan_id}"
        )

        self.cached_plans[plan_id] = plan_response
        return plan_response

    def get_plan(self, plan_id: str) -> Optional[RoutePlanResponse]:
        return self.cached_plans.get(plan_id)

    def export_plan_csv(self, plan: RoutePlanResponse, output_path: Path):
        """Gera o arquivo CSV ordenado para impressão ou envio à equipe de campo."""
        import csv

        fieldnames = [
            "Técnico/Roteiro",
            "Dia",
            "Ordem",
            "Identificação",
            "Endereço Completo",
            "Status",
            "Distância do Ponto Anterior (km)",
            "Tempo Deslocamento (min)",
            "Tempo Acumulado no Dia (min)",
            "Latitude",
            "Longitude",
            "Link Google Maps",
            "Link Waze"
        ]

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(fieldnames)

            for route in plan.routes:
                for stop in route.stops:
                    writer.writerow([
                        route.technician_name,
                        route.day_number,
                        stop.sequence_order,
                        stop.title,
                        stop.address,
                        stop.status,
                        round(stop.distance_from_prev_meters / 1000.0, 2),
                        stop.estimated_travel_minutes,
                        stop.cumulative_time_minutes,
                        stop.latitude,
                        stop.longitude,
                        stop.google_maps_url,
                        stop.waze_url
                    ])

    def export_plan_kmz(self, plan: RoutePlanResponse, output_path: Path):
        """Gera arquivo KMZ estruturado com as rotas e paradas numeradas para o Google Earth."""
        import zipfile
        import xml.sax.saxutils as saxutils

        def escape(text):
            return saxutils.escape(str(text)) if text is not None else ""

        # Montagem do XML KML
        kml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            '<Document>',
            f'  <name>Roteirização de Visitas - {escape(plan.created_at)}</name>',
            '  <description>Rotas otimizadas geradas pelo GeoViabilidade Telecom GIS Engine</description>',
        ]

        # Estilos para cada técnico
        for route in plan.routes:
            # Cor em formato KML: aabbggrr (hex invertido com alfa ff)
            hex_color = route.color_hex.lstrip("#")
            if len(hex_color) == 6:
                r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
                kml_color = f"ff{b}{g}{r}"
            else:
                kml_color = "ff00ffff"

            kml_parts.extend([
                f'  <Style id="route_line_{route.technician_id}_{route.day_number}">',
                '    <LineStyle>',
                f'      <color>{kml_color}</color>',
                '      <width>4</width>',
                '    </LineStyle>',
                '  </Style>'
            ])

        # Pastas para cada rota
        for route in plan.routes:
            kml_parts.extend([
                '  <Folder>',
                f'    <name>{escape(route.technician_name)} ({route.total_stops} visitas - {route.total_distance_km} km)</name>',
                f'    <description>Partida: {escape(route.depot_name)} | Duração estimada: {route.total_estimated_duration_hours}h</description>'
            ])

            # 1. Ponto de Partida (Depot)
            kml_parts.extend([
                '    <Placemark>',
                f'      <name>📍 BASE: {escape(route.depot_name)}</name>',
                '      <description>Ponto de partida da equipe</description>',
                f'      <Point><coordinates>{route.depot_lon},{route.depot_lat},0</coordinates></Placemark>',
                '    </Placemark>'
            ])

            # 2. Linha do Trajeto (Polyline)
            if len(route.polyline_coords) >= 2:
                coords_str = " ".join(f"{lon},{lat},0" for lat, lon in route.polyline_coords)
                kml_parts.extend([
                    '    <Placemark>',
                    f'      <name>Traçado: {escape(route.technician_name)}</name>',
                    f'      <styleUrl>#route_line_{route.technician_id}_{route.day_number}</styleUrl>',
                    '      <LineString>',
                    '        <tessellate>1</tessellate>',
                    f'        <coordinates>{coords_str}</coordinates>',
                    '      </LineString>',
                    '    </Placemark>'
                ])

            # 3. Paradas Numeradas
            for stop in route.stops:
                desc = (
                    f"<b>Parada Nº {stop.sequence_order}</b><br/>"
                    f"<b>Endereço:</b> {escape(stop.address)}<br/>"
                    f"<b>Status:</b> {escape(stop.status)}<br/>"
                    f"<b>Distância do ponto anterior:</b> {stop.distance_from_prev_meters} m<br/>"
                    f"<b>Tempo de viagem estimado:</b> {stop.estimated_travel_minutes} min<br/>"
                    f"<b>Tempo acumulado:</b> {stop.cumulative_time_minutes} min<br/><br/>"
                    f'<a href="{escape(stop.google_maps_url)}">Abrir no Google Maps</a> | '
                    f'<a href="{escape(stop.waze_url)}">Abrir no Waze</a>'
                )
                kml_parts.extend([
                    '    <Placemark>',
                    f'      <name>[{stop.sequence_order}] {escape(stop.title)}</name>',
                    f'      <description><![CDATA[{desc}]]></description>',
                    f'      <Point><coordinates>{stop.longitude},{stop.latitude},0</coordinates></Placemark>',
                    '    </Placemark>'
                ])

            kml_parts.append('  </Folder>')

        kml_parts.extend(['</Document>', '</kml>'])
        kml_content = "\n".join(kml_parts)

        # Gravar como KMZ compactado
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as kmz:
            kmz.writestr("doc.kml", kml_content.encode("utf-8"))

routing_engine = RoutingEngine()

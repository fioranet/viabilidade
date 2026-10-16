import os
import sys
from pathlib import Path

# Ajustar caminho do backend
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.routing_engine import routing_engine, haversine_distance
from app.models.schemas import RoutingOptions

def test_routing():
    print("--- INICIANDO TESTES DO MOTOR DE ROTEIRIZAÇÃO INTELIGENTE ---")

    # 1. Teste da distância Haversine
    # São Paulo (Sé) até Paulista (~2.7 km euclidiano)
    se_lat, se_lon = -23.5505, -46.6333
    paulista_lat, paulista_lon = -23.5615, -46.6559
    dist = haversine_distance(se_lat, se_lon, paulista_lat, paulista_lon)
    assert 2500 < dist < 3000, f"Distância inesperada: {dist}"
    print(f"[OK] Cálculo Haversine validado: Sé -> Paulista = {dist:.1f}m")

    # 2. Criar conjunto de pontos de teste simulando vistorias de campo
    sample_points = [
        {"id": "pt_1", "title": "Cliente Av Paulista 1000", "address": "Av Paulista, 1000", "latitude": -23.5629, "longitude": -46.6544, "status": "EM_ANALISE"},
        {"id": "pt_2", "title": "Cliente Rua Augusta 500", "address": "Rua Augusta, 500", "latitude": -23.5520, "longitude": -46.6530, "status": "EM_ANALISE"},
        {"id": "pt_3", "title": "Cliente Alameda Santos 800", "address": "Al Santos, 800", "latitude": -23.5670, "longitude": -46.6500, "status": "EM_ANALISE"},
        {"id": "pt_4", "title": "Cliente Bela Cintra 300", "address": "Rua Bela Cintra, 300", "latitude": -23.5550, "longitude": -46.6600, "status": "EM_ANALISE"},
        {"id": "pt_5", "title": "Cliente Suzano Centro", "address": "Rua General Francisco Glicério, 500", "latitude": -23.5372, "longitude": -46.3105, "status": "EM_ANALISE"},
        {"id": "pt_6", "title": "Cliente Suzano Norte", "address": "Estrada dos Fernandes, 1200", "latitude": -23.5200, "longitude": -46.3000, "status": "EM_ANALISE"},
        {"id": "pt_7", "title": "Cliente Poá Centro", "address": "Av Brasil, 100", "latitude": -23.5230, "longitude": -46.3450, "status": "EM_ANALISE"},
        {"id": "pt_8", "title": "Cliente Poá Sul", "address": "Rua Deputado Castro Ribeiro, 200", "latitude": -23.5350, "longitude": -46.3400, "status": "EM_ANALISE"},
    ]

    # Teste A: 1 Técnico para todos os pontos com limite de 5 visitas/dia (Deve desdobrar em Dia 1 e Dia 2)
    options_1tech = RoutingOptions(
        num_technicians=1,
        max_stops_per_technician=5,
        max_distance_km=80.0,
        depot_mode="first_point",
        filter_status=["EM_ANALISE"]
    )
    plan_1 = routing_engine.generate_plan(sample_points, options_1tech)
    assert len(plan_1.routes) == 2, f"Esperado 2 rotas (Dia 1 e Dia 2), obteve {len(plan_1.routes)}"
    assert plan_1.routes[0].day_number == 1
    assert plan_1.routes[1].day_number == 2
    assert plan_1.total_assigned_stops == 8
    print(f"[OK] 1 Técnico com limite de 5 paradas dividido perfeitamente em Dia 1 ({plan_1.routes[0].total_stops} pts) e Dia 2 ({plan_1.routes[1].total_stops} pts).")

    # Teste B: 2 Técnicos (Deve separar o cluster Centro/Paulista do cluster Suzano/Poá)
    options_2tech = RoutingOptions(
        num_technicians=2,
        max_stops_per_technician=10,
        max_distance_km=100.0,
        depot_mode="nearest_pop",
        filter_status=["EM_ANALISE"]
    )
    plan_2 = routing_engine.generate_plan(sample_points, options_2tech)
    assert len(plan_2.routes) == 2, f"Esperado 2 técnicos, obteve {len(plan_2.routes)}"
    print(f"[OK] 2 Técnicos alocados em clusters regionais com sucesso:")
    for r in plan_2.routes:
        print(f"     -> {r.technician_name}: {r.total_stops} paradas, {r.total_distance_km} km estimados, Duração: {r.total_estimated_duration_hours}h")

    # Teste C: Verificar URLs de navegação geradas
    first_stop = plan_2.routes[0].stops[0]
    assert "https://www.google.com/maps/dir/" in first_stop.google_maps_url
    assert "https://waze.com/ul" in first_stop.waze_url
    assert "https://www.google.com/maps/dir/" in plan_2.routes[0].google_maps_multi_stop_url
    print(f"[OK] Deep links Google Maps e Waze gerados corretamente: {first_stop.waze_url}")

    # Teste D: Exportação CSV
    csv_out = BACKEND_DIR / "data" / "uploads" / "test_roteiro.csv"
    routing_engine.export_plan_csv(plan_2, csv_out)
    assert csv_out.exists() and csv_out.stat().st_size > 0
    print(f"[OK] Exportação de planilha CSV executiva validada ({csv_out.stat().st_size} bytes).")

    # Teste E: Exportação KMZ (Google Earth)
    kmz_out = BACKEND_DIR / "data" / "uploads" / "test_roteiro.kmz"
    routing_engine.export_plan_kmz(plan_2, kmz_out)
    assert kmz_out.exists() and kmz_out.stat().st_size > 0
    print(f"[OK] Exportação de arquivo KMZ com polylines e pins validada ({kmz_out.stat().st_size} bytes).")

    print("\n==================================================")
    print("TODOS OS TESTES DO MOTOR DE ROTEIRIZAÇÃO PASSARAM!")
    print("==================================================")

if __name__ == "__main__":
    test_routing()

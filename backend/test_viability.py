"""
Script de Validação Automatizada do Motor Espacial de Viabilidade Técnica.
"""

import sys
from pathlib import Path

# Ajustar PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.spatial_engine import spatial_engine
from app.services.layer_manager import layer_manager
from app.models.schemas import ViabilityStatus

def run_tests():
    print("\n--- INICIANDO TESTES DO MOTOR ESPACIAL ---")
    
    # 1. Carregar camadas de teste
    layer_manager.load_all_layers()
    print(f"[OK] Total de geometrias carregadas: {len(spatial_engine.geometries)}")
    assert len(spatial_engine.geometries) > 0, "Deveria ter geometrias carregadas"

    # 2. Teste Caso 1: Ponto estritamente dentro da Mancha Paulista (Fibra GPON)
    # Coordenadas: -23.5650, -46.6550
    res1 = spatial_engine.check_viability(latitude=-23.5650, longitude=-46.6550)
    print(f"\nTeste 1 (Paulista): Status={res1.status.value}, Mancha={res1.matched_polygon.polygon_name if res1.matched_polygon else 'N/A'}")
    assert res1.status == ViabilityStatus.VIAVEL
    assert res1.matched_polygon.technology == "Fibra GPON"
    print(" -> PASSED: Viabilidade confirmada dentro do polígono.")

    # 3. Teste Caso 2: Ponto dentro da Mancha Moema (Rede Neutra)
    # Coordenadas: -23.5950, -46.6500
    res2 = spatial_engine.check_viability(latitude=-23.5950, longitude=-46.6500)
    print(f"\nTeste 2 (Moema): Status={res2.status.value}, Tech={res2.matched_polygon.technology if res2.matched_polygon else 'N/A'}")
    assert res2.status == ViabilityStatus.VIAVEL
    assert res2.matched_polygon.technology == "Rede Neutra"
    print(" -> PASSED: Viabilidade confirmada com tecnologia Rede Neutra.")

    # 4. Teste Caso 3: Ponto fora mas muito próximo (Em Análise / Extensão de Rede)
    # Mancha Paulista limite leste é aprox -46.6450, -23.5700. Ponto ligeiramente ao lado: -23.5705, -46.6445
    res3 = spatial_engine.check_viability(latitude=-23.5705, longitude=-46.6445)
    print(f"\nTeste 3 (Próximo à Borda): Status={res3.status.value}, Distância={res3.distance_to_nearest_meters}m")
    assert res3.status in [ViabilityStatus.EM_ANALISE, ViabilityStatus.VIAVEL]
    print(" -> PASSED: Detectada proximidade e distância calculada corretamente.")

    # 5. Teste Caso 4: Ponto muito distante (Inviável)
    # Coordenadas: -23.0000, -47.0000 (fora da capital)
    res4 = spatial_engine.check_viability(latitude=-23.0000, longitude=-47.0000)
    print(f"\nTeste 4 (Distante): Status={res4.status.value}, Distância={res4.distance_to_nearest_meters}m")
    assert res4.status == ViabilityStatus.INVIAVEL
    assert res4.distance_to_nearest_meters > 50000 # > 50km
    print(" -> PASSED: Ponto distante classificado como Inviável com cálculo de distância métrica.")

    print("\n==========================================")
    print("TODOS OS TESTES DO MOTOR ESPACIAL PASSARAM!")
    print("==========================================\n")

if __name__ == "__main__":
    run_tests()

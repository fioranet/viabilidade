import sys
import asyncio
from pathlib import Path

# Ajustar PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.batch_processor import batch_processor

async def run_api_integration_tests():
    print("\n--- INICIANDO TESTES DE INTEGRAÇÃO DA API ---")
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Teste de camadas cadastradas
        res = await client.get("/api/layers")
        assert res.status_code == 200, f"Falha GET /api/layers: {res.text}"
        layers = res.json()
        print(f"[OK] GET /api/layers: {len(layers)} camada(s) encontrada(s).")
        assert len(layers) > 0

        # 2. Teste de FeatureCollection GeoJSON
        res_geojson = await client.get("/api/layers/geojson")
        assert res_geojson.status_code == 200
        geojson_data = res_geojson.json()
        assert geojson_data["type"] == "FeatureCollection"
        print(f"[OK] GET /api/layers/geojson: {len(geojson_data['features'])} polígono(s) na FeatureCollection.")

        # 3. Teste de Consulta Unitária (Coordenadas da Paulista)
        payload = {"latitude": -23.5650, "longitude": -46.6550}
        res_check = await client.post("/api/viability/check", json=payload)
        assert res_check.status_code == 200
        check_data = res_check.json()
        print(f"[OK] POST /api/viability/check (Paulista): Status={check_data['status']}, POP={check_data['matched_polygon']['pop']}")
        assert check_data["status"] == "VIAVEL"
        assert check_data["matched_polygon"]["technology"] == "Fibra GPON"

        # 3b. Teste de Consulta Unitária filtrando por Suzano e Poá (usando array e 'poa' sem acento)
        payload_suzano = {
            "latitude": -23.5416,
            "longitude": -46.3147,
            "layers": ["suzano", "poa"]
        }
        res_suzano = await client.post("/api/viability/check", json=payload_suzano)
        assert res_suzano.status_code == 200
        suzano_data = res_suzano.json()
        print(f"[OK] POST /api/viability/check (Suzano com layers=['suzano', 'poa']): Status={suzano_data['status']}, Mancha={suzano_data['matched_polygon']['polygon_name']}")
        assert suzano_data["status"] == "VIAVEL"
        assert suzano_data["matched_polygon"]["layer_id"] == "suzano"
        assert "Suzano" in suzano_data["consulted_layers"]
        assert "Poá" in suzano_data["consulted_layers"]

        # 3c. Teste de Consulta Unitária na Paulista mas restringindo apenas para Suzano (deve dar INVIÁVEL)
        payload_paulista_suzano = {
            "latitude": -23.5650,
            "longitude": -46.6550,
            "layers": ["suzano"]
        }
        res_p_suzano = await client.post("/api/viability/check", json=payload_paulista_suzano)
        assert res_p_suzano.status_code == 200
        p_suzano_data = res_p_suzano.json()
        print(f"[OK] POST /api/viability/check (Paulista restrito a Suzano): Status={p_suzano_data['status']}, Distância={p_suzano_data['distance_to_nearest_meters']}m")
        assert p_suzano_data["status"] == "INVIAVEL"
        assert p_suzano_data["distance_to_nearest_meters"] > 25000

        # 3d. Teste com 'layers' em formato string separada por vírgula e parâmetro 'layer' singular
        payload_str = {"latitude": -23.5416, "longitude": -46.3147, "layers": "suzano, poa"}
        res_str = await client.post("/api/viability/check", json=payload_str)
        assert res_str.status_code == 200
        assert res_str.json()["status"] == "VIAVEL"

        payload_single = {"latitude": -23.5416, "longitude": -46.3147, "layer": "suzano"}
        res_single = await client.post("/api/viability/check", json=payload_single)
        assert res_single.status_code == 200
        assert res_single.json()["status"] == "VIAVEL"
        print("[OK] POST /api/viability/check (layers='suzano, poa' e layer='suzano'): Validado com sucesso.")

        # 3e. Teste de validação: camada inexistente retorna 400 Bad Request
        payload_invalid = {"latitude": -23.5416, "longitude": -46.3147, "layers": ["mapa_inexistente"]}
        res_invalid = await client.post("/api/viability/check", json=payload_invalid)
        assert res_invalid.status_code == 400
        assert "não encontrado" in res_invalid.json()["detail"]
        print(f"[OK] POST /api/viability/check (camada inexistente): 400 Bad Request retornado corretamente -> {res_invalid.json()['detail']}")

        # 3f. Teste de alternar Mancha Principal (toggle primary)
        current_pri = next((l["is_primary"] for l in (await client.get("/api/layers")).json() if l["id"] == "suzano"), False)
        if not current_pri:
            res_pri = await client.post("/api/layers/suzano/primary")
            assert res_pri.status_code == 200
            layer_meta = res_pri.json()
            assert layer_meta["is_primary"] is True
        else:
            layer_meta = {"id": "suzano", "is_primary": True}
        print(f"[OK] POST /api/layers/suzano/primary: Camada '{layer_meta['id']}' confirmada como principal com sucesso.")

        # 3g. Teste de consulta utilizando palavra-chave 'primary' / 'principal'
        payload_primary = {
            "latitude": -23.5416,
            "longitude": -46.3147,
            "layers": ["primary"]
        }
        res_check_pri = await client.post("/api/viability/check", json=payload_primary)
        assert res_check_pri.status_code == 200
        pri_check_data = res_check_pri.json()
        assert pri_check_data["status"] == "VIAVEL"
        assert pri_check_data["matched_polygon"]["layer_id"] == "suzano"
        print(f"[OK] POST /api/viability/check (layers=['primary']): Resolvido para as camadas principais ({pri_check_data['consulted_layers']}).")

        # 4. Teste de Consulta Unitária (Ponto Inviável)
        payload_inv = {"latitude": -23.0000, "longitude": -47.0000}
        res_inv = await client.post("/api/viability/check", json=payload_inv)
        assert res_inv.status_code == 200
        inv_data = res_inv.json()
        print(f"[OK] POST /api/viability/check (Inviável): Status={inv_data['status']}, Distância={inv_data['distance_to_nearest_meters']}m")
        assert inv_data["status"] == "INVIAVEL"

        # 5. Teste de Processamento em Lote filtrando por camada Suzano
        csv_data = "cliente,latitude,longitude\nCliente Suzano,-23.5416,-46.3147\nCliente Paulista,-23.5650,-46.6550\n"
        files = {"file": ("teste_lote_rapido.csv", csv_data.encode("utf-8"), "text/csv")}
        res_batch = await client.post("/api/batch/upload", files=files, data={"layers": "suzano"})
        assert res_batch.status_code == 200
        batch_info = res_batch.json()
        job_id = batch_info["job_id"]
        print(f"[OK] POST /api/batch/upload (com layers='suzano'): Job ID gerado = {job_id}")

        # O FastAPI BackgroundTasks já executa o processamento automaticamente
        # Consultar status do job
        res_status = await client.get(f"/api/batch/status/{job_id}")
        assert res_status.status_code == 200
        job_status = res_status.json()
        print(f"[OK] GET /api/batch/status: Status={job_status['status']}, Total={job_status['total_rows']}, Viáveis={job_status['viable_count']}, Inviáveis={job_status['unviable_count']}")
        assert job_status["status"] == "COMPLETED"
        assert job_status["total_rows"] == 2
        assert job_status["viable_count"] == 1  # Apenas o de Suzano é viável
        assert job_status["unviable_count"] == 1 # Paulista é inviável pois o lote foi restrito a Suzano

        # Baixar CSV enriquecido gerado
        res_dl = await client.get(f"/api/batch/download/{job_id}")
        assert res_dl.status_code == 200
        csv_content = res_dl.text
        assert "Viabilidade_Status" in csv_content
        assert "Tecnologia" in csv_content
        assert "Distancia_Borda_Metros" in csv_content
        print("[OK] GET /api/batch/download: Planilha enriquecida validada com sucesso.")

    print("\n==========================================")
    print("TODOS OS TESTES DE INTEGRAÇÃO DA API PASSARAM!")
    print("==========================================\n")

if __name__ == "__main__":
    asyncio.run(run_api_integration_tests())

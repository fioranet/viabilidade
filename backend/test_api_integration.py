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

        # 4. Teste de Consulta Unitária (Ponto Inviável)
        payload_inv = {"latitude": -23.0000, "longitude": -47.0000}
        res_inv = await client.post("/api/viability/check", json=payload_inv)
        assert res_inv.status_code == 200
        inv_data = res_inv.json()
        print(f"[OK] POST /api/viability/check (Inviável): Status={inv_data['status']}, Distância={inv_data['distance_to_nearest_meters']}m")
        assert inv_data["status"] == "INVIAVEL"

        # 5. Teste de Processamento em Lote com o CSV de Teste
        csv_path = Path(__file__).resolve().parent.parent / "sample_data" / "teste_lote.csv"
        with open(csv_path, "rb") as f:
            files = {"file": ("teste_lote.csv", f, "text/csv")}
            res_batch = await client.post("/api/batch/upload", files=files)
        assert res_batch.status_code == 200
        batch_info = res_batch.json()
        job_id = batch_info["job_id"]
        print(f"[OK] POST /api/batch/upload: Job ID gerado = {job_id}")

        # Executar processamento do job diretamente
        temp_input = Path(__file__).resolve().parent / "data" / "uploads" / "batch_input_teste_lote.csv"
        await batch_processor.execute_batch(job_id, temp_input)

        # Consultar status do job
        res_status = await client.get(f"/api/batch/status/{job_id}")
        assert res_status.status_code == 200
        job_status = res_status.json()
        print(f"[OK] GET /api/batch/status: Status={job_status['status']}, Total={job_status['total_rows']}, Viáveis={job_status['viable_count']}, Inviáveis={job_status['unviable_count']}")
        assert job_status["status"] == "COMPLETED"
        assert job_status["total_rows"] == 10
        assert job_status["viable_count"] >= 2

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

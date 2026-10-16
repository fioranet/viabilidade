import asyncio
import sys
from pathlib import Path

# Ajustar caminho do backend
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx
from app.main import app
from app.services.batch_processor import batch_processor

async def test_routing_api():
    print("--- INICIANDO TESTES DE API PARA O MÓDULO DE ROTEIRIZAÇÃO ---")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Criar um lote simulado no batch_processor com pontos para teste de API
        sample_csv = BACKEND_DIR / "sample_data" / "teste_lote.csv"
        if not sample_csv.exists():
            sample_csv = BACKEND_DIR.parent / "sample_data" / "teste_lote.csv"

        with open(sample_csv, "rb") as f:
            files = {"file": ("teste_lote.csv", f, "text/csv")}
            res_up = await client.post("/api/batch/upload", files=files)
            assert res_up.status_code == 200, f"Upload falhou: {res_up.text}"
            job_id = res_up.json()["job_id"]
            print(f"[OK] Upload de lote para teste de rota concluído: Job ID={job_id}")

        # Aguardar conclusão do processamento do lote
        for _ in range(30):
            res_st = await client.get(f"/api/batch/status/{job_id}")
            if res_st.json()["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
                break
            await asyncio.sleep(0.5)

        # 2. Testar POST /api/routing/plan
        routing_payload = {
            "job_id": job_id,
            "num_technicians": 2,
            "max_stops_per_technician": 10,
            "max_distance_km": 80.0,
            "depot_mode": "nearest_pop",
            "filter_status": ["VIAVEL", "EM_ANALISE", "INVIAVEL"] # Para garantir que pegamos os pontos
        }
        res_plan = await client.post("/api/routing/plan", json=routing_payload)
        assert res_plan.status_code == 200, f"Falha no planejamento de rotas: {res_plan.text}"
        plan_data = res_plan.json()
        plan_id = plan_data["plan_id"]
        print(f"[OK] POST /api/routing/plan: Plan ID={plan_id}, Rotas Geradas={len(plan_data['routes'])}, Visitas Alocadas={plan_data['total_assigned_stops']}")
        assert len(plan_data["routes"]) > 0
        assert "download_kmz_url" in plan_data
        assert "download_csv_url" in plan_data

        # 3. Testar GET /api/routing/export-kmz/{plan_id}
        res_kmz = await client.get(f"/api/routing/export-kmz/{plan_id}")
        assert res_kmz.status_code == 200, f"Export KMZ falhou: {res_kmz.status_code}"
        assert res_kmz.headers["content-type"] == "application/vnd.google-earth.kmz"
        assert len(res_kmz.content) > 0
        print(f"[OK] GET /api/routing/export-kmz/{plan_id}: Arquivo KMZ recebido com sucesso ({len(res_kmz.content)} bytes)")

        # 4. Testar GET /api/routing/export-csv/{plan_id}
        res_csv = await client.get(f"/api/routing/export-csv/{plan_id}")
        assert res_csv.status_code == 200, f"Export CSV falhou: {res_csv.status_code}"
        assert "text/csv" in res_csv.headers["content-type"]
        assert len(res_csv.content) > 0
        print(f"[OK] GET /api/routing/export-csv/{plan_id}: Planilha CSV recebida com sucesso ({len(res_csv.content)} bytes)")

    print("\n==================================================")
    print("TODOS OS TESTES DE API DE ROTEIRIZAÇÃO PASSARAM!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(test_routing_api())

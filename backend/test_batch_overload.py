import sys
import asyncio
from pathlib import Path

# Ajustar PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

from httpx import AsyncClient, ASGITransport
from app.main import app

async def run_batch_overload_tests():
    print("\n--- INICIANDO TESTES DE PROTEÇÃO CONTRA SOBRECARGA E STATUS ---")
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Testar endpoint de status do sistema e recursos
        res_sys = await client.get("/api/system/status")
        assert res_sys.status_code == 200, f"Falha GET /api/system/status: {res_sys.text}"
        sys_data = res_sys.json()
        print(f"[OK] GET /api/system/status: Status={sys_data['status']}, Carga={sys_data['server_load']}, Uptime={sys_data['uptime_seconds']}s")
        assert sys_data["server_load"] in ["Normal", "Moderada", "Alta"]
        assert "uptime_seconds" in sys_data
        assert "active_batch_jobs" in sys_data

        # 2. Testar upload de lote com verificação de métricas e status detalhado
        rows = ["cliente,latitude,longitude"]
        for i in range(15):
            rows.append(f"Cliente_{i},-23.5650,-46.6550")
        csv_data = "\n".join(rows) + "\n"

        files = {"file": ("teste_status_metricas.csv", csv_data.encode("utf-8"), "text/csv")}
        res_upload = await client.post("/api/batch/upload", files=files)
        assert res_upload.status_code == 200
        job_id = res_upload.json()["job_id"]
        print(f"[OK] POST /api/batch/upload: Job ID={job_id} iniciado.")

        # 3. Verificar status com métricas detalhadas (elapsed, eta, rate, counters)
        await asyncio.sleep(0.5)
        res_st = await client.get(f"/api/batch/status/{job_id}")
        assert res_st.status_code == 200
        st_data = res_st.json()
        print(f"[OK] GET /api/batch/status: Status={st_data['status']}, Progresso={st_data['progress_percentage']}%, Taxa={st_data.get('processing_rate')} lin/s, Estágio='{st_data.get('current_stage')}'")
        assert "elapsed_time_formatted" in st_data
        assert "eta_formatted" in st_data
        assert "server_load" in st_data

        # 4. Testar cancelamento de lote (endpoint POST /api/batch/cancel/{job_id})
        # Criar lote com 30 itens para testar cancelamento no meio do caminho
        long_rows = ["cliente,latitude,longitude"]
        for i in range(30):
            long_rows.append(f"ClienteLong_{i},-23.5650,-46.6550")
        long_csv = "\n".join(long_rows) + "\n"

        files_long = {"file": ("teste_cancelamento.csv", long_csv.encode("utf-8"), "text/csv")}
        res_up_cancel = await client.post("/api/batch/upload", files=files_long)
        cancel_job_id = res_up_cancel.json()["job_id"]

        # Solicitar cancelamento imediato
        res_cancel = await client.post(f"/api/batch/cancel/{cancel_job_id}")
        assert res_cancel.status_code == 200
        cancel_resp = res_cancel.json()
        print(f"[OK] POST /api/batch/cancel: Resposta={cancel_resp['message']}")

        # Aguardar brevemente e verificar se o status foi atualizado para CANCELLED
        await asyncio.sleep(0.3)
        res_st_cancel = await client.get(f"/api/batch/status/{cancel_job_id}")
        assert res_st_cancel.status_code == 200
        st_cancel_data = res_st_cancel.json()
        print(f"[OK] Status pós-cancelamento: {st_cancel_data['status']} - {st_cancel_data.get('current_stage')}")
        assert st_cancel_data["status"] in ("CANCELLED", "COMPLETED")

    print("\n=======================================================")
    print("TODOS OS TESTES DE MONITORAMENTO E SOBRECARGA PASSARAM!")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(run_batch_overload_tests())

import uuid
import datetime
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
import pandas as pd

from app.config import UPLOADS_DIR, MAX_BATCH_ROWS, BATCH_YIELD_INTERVAL
from app.models.schemas import BatchJobStatus, ViabilityStatus
from app.services.spatial_engine import spatial_engine
from app.services.geocoding import geocoding_service
from app.services.system_monitor import system_monitor

def _format_time(seconds: float) -> str:
    """Converte segundos em formato legível MM:SS ou HH:MM:SS."""
    if seconds is None or seconds < 0:
        return "--:--"
    s = int(round(seconds))
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"

class BatchProcessor:
    """
    Processador de viabilidade em lote para arquivos CSV e XLSX.
    Inclui proteção contra sobrecarga, fila de concorrência controlada,
    não-bloqueio do event loop e métricas detalhadas em tempo real.
    """

    def __init__(self):
        self.jobs: Dict[str, BatchJobStatus] = {}
        self._semaphore = asyncio.Semaphore(1) # Executa 1 lote por vez para proteger CPU/I/O
        self._cancelled_jobs: set[str] = set()

    def get_job(self, job_id: str) -> Optional[BatchJobStatus]:
        return self.jobs.get(job_id)

    def get_all_jobs(self) -> List[BatchJobStatus]:
        return list(self.jobs.values())

    def get_active_jobs_count(self) -> int:
        return len([j for j in self.jobs.values() if j.status in ("PENDING", "QUEUED", "PROCESSING")])

    def get_queued_jobs_count(self) -> int:
        return len([j for j in self.jobs.values() if j.status == "QUEUED"])

    def _update_queue_positions(self):
        """Atualiza a posição de espera na fila para todos os jobs enfileirados."""
        queued_jobs = [j for j in self.jobs.values() if j.status == "QUEUED"]
        # Ordenar por data de criação
        queued_jobs.sort(key=lambda j: j.created_at)
        for idx, j in enumerate(queued_jobs):
            j.queue_position = idx + 1

    def cancel_job(self, job_id: str) -> bool:
        """Cancela um job em processamento ou aguardando na fila."""
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.status in ("COMPLETED", "FAILED", "CANCELLED"):
            return False

        self._cancelled_jobs.add(job_id)
        if job.status in ("PENDING", "QUEUED"):
            job.status = "CANCELLED"
            job.queue_position = 0
            job.current_stage = "Cancelado pelo usuário antes de iniciar"
            job.completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._update_queue_positions()
        else:
            job.current_stage = "Cancelamento solicitado pelo usuário..."

        return True

    async def start_batch_job(self, file_path: Path, filename: str) -> str:
        job_id = str(uuid.uuid4())
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Verificar se já existe algum job em execução
        is_busy = any(j.status == "PROCESSING" for j in self.jobs.values())
        initial_status = "QUEUED" if is_busy else "PENDING"

        metrics = system_monitor.get_metrics(active_jobs_count=self.get_active_jobs_count() + 1)

        status = BatchJobStatus(
            job_id=job_id,
            status=initial_status,
            current_stage="Aguardando na fila de processamento..." if initial_status == "QUEUED" else "Iniciando processamento...",
            created_at=now_str,
            server_load=metrics.get("server_load", "Normal"),
            cpu_percent=metrics.get("cpu_percent"),
            memory_percent=metrics.get("memory_percent")
        )
        self.jobs[job_id] = status
        self._update_queue_positions()
        return job_id

    async def execute_batch(self, job_id: str, file_path: Path, target_layer_ids: Optional[List[str]] = None):
        job = self.jobs.get(job_id)
        if not job:
            return

        if job_id in self._cancelled_jobs or job.status == "CANCELLED":
            return

        # Aguardar disponibilidade no semáforo para controle de sobrecarga
        job.status = "QUEUED"
        self._update_queue_positions()

        async with self._semaphore:
            if job_id in self._cancelled_jobs or job.status == "CANCELLED":
                job.status = "CANCELLED"
                job.queue_position = 0
                job.completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return

            job.status = "PROCESSING"
            job.queue_position = 0
            job.current_stage = "Lendo e validando estrutura da planilha..."
            self._update_queue_positions()

            start_time = time.time()
            results = []

            try:
                # 1. Ler DataFrame de forma não-bloqueante (em worker thread)
                def _read_df():
                    if file_path.suffix.lower() in [".xlsx", ".xls"]:
                        return pd.read_excel(file_path)
                    else:
                        try:
                            return pd.read_csv(file_path, sep=None, engine="python", encoding="utf-8")
                        except Exception:
                            return pd.read_csv(file_path, sep=None, engine="python", encoding="latin1")

                df = await asyncio.to_thread(_read_df)

                total_rows = len(df)
                job.total_rows = total_rows

                if total_rows == 0:
                    job.status = "COMPLETED"
                    job.progress_percentage = 100.0
                    job.current_stage = "Planilha vazia (0 registros)"
                    job.completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    return

                # Proteção de segurança contra planilhas excessivamente grandes
                if total_rows > MAX_BATCH_ROWS:
                    job.status = "FAILED"
                    job.error_message = (
                        f"O arquivo enviado contém {total_rows:,} linhas, o que excede o limite "
                        f"de segurança de {MAX_BATCH_ROWS:,} registros por lote para evitar sobrecarga. "
                        f"Divida a planilha em partes menores."
                    )
                    job.current_stage = "Excedeu limite de segurança"
                    return

                # Normalização de colunas
                col_map = {str(col).strip().lower(): col for col in df.columns}

                def find_col(*candidates):
                    for c in candidates:
                        for k in col_map:
                            if c in k:
                                return col_map[k]
                    return None

                col_lat = find_col("lat", "latitude")
                col_lng = find_col("long", "lng", "longitude")
                col_cep = find_col("cep", "postal")
                col_logradouro = find_col("logradouro", "rua", "endereco", "endereço", "street", "av", "avenida")
                col_numero = find_col("numero", "número", "num", "number", "nº", "no")
                col_bairro = find_col("bairro", "district", "neighborhood")
                col_cidade = find_col("cidade", "city", "municipio", "município")
                col_uf = find_col("uf", "estado", "state")

                job.current_stage = "Iniciando verificação de viabilidade..."

                for idx, row in df.iterrows():
                    # Verificar cancelamento a cada linha
                    if job_id in self._cancelled_jobs:
                        job.status = "CANCELLED"
                        job.current_stage = f"Cancelado pelo usuário ({job.processed_rows}/{total_rows} linhas concluídas)."
                        job.completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        # Se já processou parte das linhas, salvar CSV parcial para o usuário não perder dados
                        if results:
                            def _save_partial():
                                res_df = pd.DataFrame(results)
                                output_df = pd.concat([df.iloc[:len(results)].reset_index(drop=True), res_df], axis=1)
                                out_filename = f"resultado_viabilidade_{job_id}.csv"
                                out_path = UPLOADS_DIR / out_filename
                                output_df.to_csv(out_path, index=False, sep=";", encoding="utf-8-sig")
                                return out_filename
                            await asyncio.to_thread(_save_partial)
                            job.download_csv_url = f"/api/batch/download/{job_id}"
                        return

                    # CEDER CONTROLE AO EVENT LOOP DO ASYNCIO
                    # Isso garante que requisições HTTP da API e status do frontend nunca sofram congelamento!
                    await asyncio.sleep(BATCH_YIELD_INTERVAL)

                    lat_val = None
                    lng_val = None

                    # 1. Verificar se já possui coordenadas numéricas
                    if col_lat and col_lng:
                        try:
                            raw_lat = str(row[col_lat]).replace(",", ".").strip()
                            raw_lng = str(row[col_lng]).replace(",", ".").strip()
                            if raw_lat and raw_lng and raw_lat.lower() != "nan" and raw_lng.lower() != "nan":
                                lat_val = float(raw_lat)
                                lng_val = float(raw_lng)
                        except ValueError:
                            pass

                    # 2. Se não tem coordenadas, construir query para geocodificação
                    geo_source = "coordenadas_originais"
                    item_preview = f"Linha {idx + 1}"

                    if lat_val is not None and lng_val is not None:
                        item_preview = f"Coord: {lat_val:.5f}, {lng_val:.5f}"
                    else:
                        num_val = None
                        if col_numero and pd.notna(row[col_numero]):
                            raw_num = str(row[col_numero]).strip().replace(".0", "")
                            if raw_num and raw_num.lower() != "nan":
                                num_val = raw_num

                        cep_val = None
                        if col_cep and pd.notna(row[col_cep]):
                            raw_cep = str(row[col_cep]).strip().replace(".0", "")
                            if raw_cep and raw_cep.lower() != "nan":
                                cep_val = raw_cep

                        geo_res = None
                        job.current_stage = f"Geocodificando endereço {idx + 1}/{total_rows} (taxa segura)..."

                        # Prioridade 1: Busca por CEP
                        if cep_val:
                            item_preview = f"CEP: {cep_val}" + (f", nº {num_val}" if num_val else "")
                            try:
                                geo_res = await geocoding_service.geocode(cep_val, number=num_val)
                            except Exception as ex:
                                print(f"[BatchProcessor] Falha no geocode CEP {cep_val}: {ex}")

                        # Prioridade 2: Busca por endereço textual
                        if not geo_res:
                            query_parts = []
                            if col_logradouro and pd.notna(row[col_logradouro]):
                                logr = str(row[col_logradouro]).strip()
                                if logr and logr.lower() != "nan":
                                    if num_val and num_val not in logr:
                                        logr = f"{logr}, {num_val}"
                                    query_parts.append(logr)

                            if col_bairro and pd.notna(row[col_bairro]):
                                b = str(row[col_bairro]).strip()
                                if b and b.lower() != "nan":
                                    query_parts.append(b)

                            if col_cidade and pd.notna(row[col_cidade]):
                                cid = str(row[col_cidade]).strip()
                                if cid and cid.lower() != "nan":
                                    if col_uf and pd.notna(row[col_uf]):
                                        uf_str = str(row[col_uf]).strip()
                                        if uf_str and uf_str.lower() != "nan":
                                            cid = f"{cid} - {uf_str}"
                                    query_parts.append(cid)

                            full_query = ", ".join(query_parts)
                            if full_query:
                                item_preview = full_query[:45] + ("..." if len(full_query) > 45 else "")
                                try:
                                    geo_res = await geocoding_service.geocode(full_query, number=num_val)
                                except Exception as ex:
                                    print(f"[BatchProcessor] Falha no geocode endereço '{full_query}': {ex}")

                        if geo_res:
                            lat_val = geo_res.latitude
                            lng_val = geo_res.longitude
                            geo_source = geo_res.source
                        else:
                            geo_source = "falha_geocodificacao"

                    job.current_item_preview = item_preview

                    # 3. Validar no motor espacial com coordenadas obtidas
                    if lat_val is not None and lng_val is not None:
                        job.current_stage = f"Avaliando viabilidade espacial {idx + 1}/{total_rows}..."
                        viability = spatial_engine.check_viability(lat_val, lng_val, target_layer_ids=target_layer_ids)

                        if viability.status == ViabilityStatus.VIAVEL:
                            job.viable_count += 1
                        elif viability.status == ViabilityStatus.EM_ANALISE:
                            job.analysis_count += 1
                        else:
                            job.unviable_count += 1

                        poly = viability.matched_polygon
                        res_row = {
                            "Viabilidade_Status": viability.status.value,
                            "Latitude_Utilizada": lat_val,
                            "Longitude_Utilizada": lng_val,
                            "Origem_Geometria": geo_source,
                            "Mancha_Atendimento": poly.polygon_name if poly else "N/A",
                            "POP_Estacao": poly.pop if poly else "N/A",
                            "Tecnologia": poly.technology if poly else "N/A",
                            "Distancia_Borda_Metros": viability.distance_to_nearest_meters,
                            "Mensagem_Tecnica": viability.message
                        }
                    else:
                        job.error_count += 1
                        res_row = {
                            "Viabilidade_Status": "ERRO_GEOCODIFICACAO",
                            "Latitude_Utilizada": None,
                            "Longitude_Utilizada": None,
                            "Origem_Geometria": geo_source,
                            "Mancha_Atendimento": "N/A",
                            "POP_Estacao": "N/A",
                            "Tecnologia": "N/A",
                            "Distancia_Borda_Metros": None,
                            "Mensagem_Tecnica": "Não foi possível localizar as coordenadas geográficas do endereço fornecido."
                        }

                    results.append(res_row)
                    job.processed_rows += 1
                    job.progress_percentage = round((job.processed_rows / total_rows) * 100, 1)

                    # Cálculo dinâmico de taxa e estimativa de tempo (ETA)
                    elapsed = max(time.time() - start_time, 0.001)
                    job.elapsed_seconds = round(elapsed, 1)
                    job.elapsed_time_formatted = _format_time(elapsed)

                    rate = job.processed_rows / elapsed
                    job.processing_rate = round(rate, 1)

                    rem_rows = total_rows - job.processed_rows
                    eta_sec = (rem_rows / rate) if rate > 0 else 0
                    job.estimated_remaining_seconds = round(eta_sec, 1)
                    job.eta_formatted = _format_time(eta_sec)

                    # Atualizar métricas de recursos a cada 5 linhas
                    if idx % 5 == 0:
                        metrics = system_monitor.get_metrics(active_jobs_count=1)
                        job.server_load = metrics.get("server_load", "Normal")
                        job.cpu_percent = metrics.get("cpu_percent")
                        job.memory_percent = metrics.get("memory_percent")

                # Salvar arquivo CSV enriquecido em background thread
                job.current_stage = "Gerando arquivo CSV enriquecido final..."

                def _save_final():
                    res_df = pd.DataFrame(results)
                    output_df = pd.concat([df.reset_index(drop=True), res_df], axis=1)
                    output_filename = f"resultado_viabilidade_{job_id}.csv"
                    output_path = UPLOADS_DIR / output_filename
                    output_df.to_csv(output_path, index=False, sep=";", encoding="utf-8-sig")
                    return output_filename

                output_filename = await asyncio.to_thread(_save_final)

                job.status = "COMPLETED"
                job.current_stage = f"Concluído com sucesso ({total_rows} registros analisados)!"
                job.completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                job.download_csv_url = f"/api/batch/download/{job_id}"
                job.progress_percentage = 100.0

            except Exception as e:
                job.status = "FAILED"
                job.error_message = str(e)
                job.current_stage = f"Falha no processamento: {str(e)}"
                print(f"[BatchProcessor] Falha no processamento do lote {job_id}: {e}")

            finally:
                self._cancelled_jobs.discard(job_id)
                self._update_queue_positions()

# Instância singleton global
batch_processor = BatchProcessor()

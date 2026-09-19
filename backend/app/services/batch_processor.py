import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

from app.config import UPLOADS_DIR
from app.models.schemas import BatchJobStatus, ViabilityStatus
from app.services.spatial_engine import spatial_engine
from app.services.geocoding import geocoding_service

class BatchProcessor:
    """Processador de viabilidade em lote para arquivos CSV e XLSX."""

    def __init__(self):
        self.jobs: Dict[str, BatchJobStatus] = {}

    def get_job(self, job_id: str) -> Optional[BatchJobStatus]:
        return self.jobs.get(job_id)

    async def start_batch_job(self, file_path: Path, filename: str) -> str:
        job_id = str(uuid.uuid4())
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        status = BatchJobStatus(
            job_id=job_id,
            status="PENDING",
            created_at=now_str
        )
        self.jobs[job_id] = status
        return job_id

    async def execute_batch(self, job_id: str, file_path: Path):
        job = self.jobs.get(job_id)
        if not job:
            return

        job.status = "PROCESSING"

        try:
            # Ler DataFrame com pandas
            if file_path.suffix.lower() == ".xlsx" or file_path.suffix.lower() == ".xls":
                df = pd.read_excel(file_path)
            else:
                # Tentar ler com diferentes encodings comuns no Brasil (utf-8, latin1) e separadores (, ou ;)
                try:
                    df = pd.read_csv(file_path, sep=None, engine="python", encoding="utf-8")
                except Exception:
                    df = pd.read_csv(file_path, sep=None, engine="python", encoding="latin1")

            total_rows = len(df)
            job.total_rows = total_rows

            if total_rows == 0:
                job.status = "COMPLETED"
                job.progress_percentage = 100.0
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

            results = []

            for idx, row in df.iterrows():
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
                if lat_val is None or lng_val is None:
                    # Extrair número se fornecido
                    num_val = None
                    if col_numero and pd.notna(row[col_numero]):
                        raw_num = str(row[col_numero]).strip().replace(".0", "")
                        if raw_num and raw_num.lower() != "nan":
                            num_val = raw_num

                    # Extrair CEP
                    cep_val = None
                    if col_cep and pd.notna(row[col_cep]):
                        raw_cep = str(row[col_cep]).strip().replace(".0", "")
                        if raw_cep and raw_cep.lower() != "nan":
                            cep_val = raw_cep

                    geo_res = None
                    
                    # Prioridade 1: Se tem CEP (e opcionalmente número), usa o motor de alta precisão ViaCEP+Nominatim
                    if cep_val:
                        geo_res = await geocoding_service.geocode(cep_val, number=num_val)

                    # Prioridade 2: Se não encontrou por CEP ou não tem CEP, montar endereço textual
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
                            geo_res = await geocoding_service.geocode(full_query, number=num_val)

                    if geo_res:
                        lat_val = geo_res.latitude
                        lng_val = geo_res.longitude
                        geo_source = geo_res.source
                    else:
                        geo_source = "falha_geocodificacao"

                # 3. Validar no motor espacial se encontramos coordenadas
                if lat_val is not None and lng_val is not None:
                    viability = spatial_engine.check_viability(lat_val, lng_val)
                    
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

            # Anexar colunas de resultado ao DataFrame original
            res_df = pd.DataFrame(results)
            output_df = pd.concat([df.reset_index(drop=True), res_df], axis=1)

            # Salvar arquivo CSV enriquecido
            output_filename = f"resultado_viabilidade_{job_id}.csv"
            output_path = UPLOADS_DIR / output_filename
            output_df.to_csv(output_path, index=False, sep=";", encoding="utf-8-sig")

            job.status = "COMPLETED"
            job.completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            job.download_csv_url = f"/api/batch/download/{job_id}"

        except Exception as e:
            job.status = "FAILED"
            job.error_message = str(e)
            print(f"[BatchProcessor] Falha no processamento do lote {job_id}: {e}")

# Instância singleton global
batch_processor = BatchProcessor()

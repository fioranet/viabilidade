import os
import sys
import shutil
from pathlib import Path

# Garantir que o diretório backend está no sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.config import LAYERS_DIR, UPLOADS_DIR, FRONTEND_DIR
from app.models.schemas import (
    ViabilityQueryRequest,
    ViabilityResponse,
    ViabilityStatus,
    Coordinates,
    BatchJobStatus,
    LayerMetadata,
    POP,
    POPCreate
)
from app.services.spatial_engine import spatial_engine
from app.services.geocoding import geocoding_service
from app.services.layer_manager import layer_manager
from app.services.pop_manager import pop_manager
from app.services.batch_processor import batch_processor

app = FastAPI(
    title="Sistema de Viabilidade Técnica Geográfica - ISP",
    description="Motor geoespacial de alta performance com Shapely 2.0, OpenStreetMap e processamento em lote.",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Carregar camadas imediatamente na inicialização
layer_manager.load_all_layers()

@app.on_event("startup")
async def startup_event():
    """Garante recarregamento das manchas de cobertura no motor espacial."""
    layer_manager.load_all_layers()

# ==========================================
# ENDPOINTS DE CONSULTA UNITÁRIA
# ==========================================

@app.post("/api/viability/check", response_model=ViabilityResponse, tags=["Consulta Unitária"])
async def check_viability(payload: ViabilityQueryRequest):
    """
    Realiza a checagem de viabilidade técnica.
    Pode receber endereço textual, CEP com número opcional ou coordenadas diretas (Lat, Lon).
    Opcionalmente recebe 'layers' ou 'layer' para filtrar as manchas de cobertura a serem consultadas.
    """
    # 1. Tratar seleção de mapas/camadas
    requested_layers = payload.get_requested_layers()
    target_layer_ids = None
    consulted_layer_names = None

    if requested_layers:
        resolved_ids, not_found = layer_manager.resolve_layer_ids(requested_layers)
        if not_found:
            available_layers = [f"'{m.id}' ({m.name})" for m in layer_manager.get_all_metadata()]
            raise HTTPException(
                status_code=400,
                detail=f"Camada(s) ou mapa(s) não encontrado(s): {', '.join(not_found)}. Disponíveis: {', '.join(available_layers) if available_layers else 'nenhuma cadastrada'}."
            )
        target_layer_ids = resolved_ids
        consulted_layer_names = [layer_manager.metadata[lid].name for lid in resolved_ids if lid in layer_manager.metadata]

    lat = payload.latitude
    lon = payload.longitude
    display_name = None
    source = "coordenadas_diretas"

    # Se coordenadas não foram passadas diretamente, acionar geocodificação
    if lat is None or lon is None:
        if not payload.query or not payload.query.strip():
            raise HTTPException(
                status_code=400,
                detail="É necessário fornecer um endereço, CEP ou coordenadas geográficas (latitude/longitude)."
            )
        
        geocoded = await geocoding_service.geocode(payload.query.strip(), number=payload.number)
        if not geocoded:
            return ViabilityResponse(
                status=ViabilityStatus.INVIAVEL,
                input_query=payload.query,
                location=Coordinates(latitude=0.0, longitude=0.0),
                consulted_layers=consulted_layer_names or [m.name for m in layer_manager.get_all_metadata() if m.enabled],
                message="Endereço não localizado pelo serviço de geocodificação. Verifique a grafia ou insira as coordenadas."
            )
        
        lat = geocoded.latitude
        lon = geocoded.longitude
        display_name = geocoded.display_name
        source = geocoded.source

    # Validar no motor espacial com filtro opcional de camadas
    response = spatial_engine.check_viability(lat, lon, target_layer_ids=target_layer_ids)
    response.input_query = payload.query
    response.display_name = display_name or f"Coordenadas: {lat:.6f}, {lon:.6f}"
    response.geocoding_source = source
    response.consulted_layers = consulted_layer_names or [m.name for m in layer_manager.get_all_metadata() if m.enabled]
    return response

# ==========================================
# ENDPOINTS DE GESTÃO DE CAMADAS
# ==========================================

@app.get("/api/layers", response_model=list[LayerMetadata], tags=["Camadas Geográficas"])
async def get_layers():
    """Retorna a lista de camadas cadastradas e seus metadados."""
    return layer_manager.get_all_metadata()

@app.get("/api/layers/geojson", tags=["Camadas Geográficas"])
async def get_layers_geojson():
    """Retorna todas as camadas ativas como uma FeatureCollection GeoJSON única para o Leaflet."""
    return JSONResponse(content=layer_manager.get_combined_geojson())

@app.post("/api/layers/{layer_id}/toggle", response_model=LayerMetadata, tags=["Camadas Geográficas"])
async def toggle_layer(layer_id: str):
    """Ativa ou desativa uma camada de cobertura."""
    updated = layer_manager.toggle_layer(layer_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Camada não encontrada.")
    return updated

@app.post("/api/layers/{layer_id}/primary", response_model=LayerMetadata, tags=["Camadas Geográficas"])
async def toggle_layer_primary(layer_id: str):
    """Marca ou desmarca uma camada como principal/padrão do sistema."""
    updated = layer_manager.toggle_primary(layer_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Camada não encontrada.")
    return updated

@app.delete("/api/layers/{layer_id}", tags=["Camadas Geográficas"])
async def delete_layer(layer_id: str):
    """Remove uma camada de cobertura do sistema."""
    deleted = layer_manager.delete_layer(layer_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Camada não encontrada ou não pôde ser excluída.")
    return {"status": "success", "message": f"Camada '{layer_id}' removida com sucesso."}

@app.post("/api/layers/upload", tags=["Camadas Geográficas"])
async def upload_layer(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    technology: Optional[str] = Form("Fibra GPON"),
    pop_id: Optional[str] = Form(None)
):
    """
    Faz upload de arquivo .geojson, .json ou .kmz e atualiza o motor espacial em tempo real.
    """
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in [".geojson", ".json", ".kmz", ".kml"]:
        raise HTTPException(status_code=400, detail="Formato não suportado. Envie arquivos .geojson, .json, .kml ou .kmz.")

    layer_title = name or Path(file.filename).stem.replace("_", " ").title()
    temp_path = UPLOADS_DIR / f"temp_{file.filename}"

    pop_name = None
    if pop_id:
        p_obj = pop_manager.get_by_id(pop_id)
        if p_obj:
            pop_name = p_obj.name

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        if file_ext in [".kmz", ".kml"]:
            layer_manager.import_kmz_or_kml(temp_path, layer_title, technology, pop_id=pop_id, pop_name=pop_name)
        else:
            # Salvar direto no diretório de camadas
            dest_path = LAYERS_DIR / file.filename
            shutil.copyfile(temp_path, dest_path)
            layer_id = dest_path.stem
            if pop_id or pop_name:
                layer_manager.config[layer_id] = {
                    "enabled": True,
                    "pop_id": pop_id,
                    "pop_name": pop_name,
                    "technology": technology,
                    "name": layer_title
                }
                layer_manager._save_config()
            layer_manager.load_all_layers()
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return {
        "status": "success",
        "message": f"Camada '{layer_title}' adicionada com sucesso!",
        "layers_count": len(layer_manager.layers),
        "total_polygons": len(spatial_engine.geometries)
    }

# ==========================================
# ENDPOINTS DE GESTÃO DE POPS (PONTOS DE PRESENÇA)
# ==========================================

@app.get("/api/pops", response_model=list[POP], tags=["Gestão de POPs"])
async def get_pops():
    """Lista todos os POPs (Pontos de Presença) cadastrados."""
    return pop_manager.get_all()

@app.post("/api/pops", response_model=POP, tags=["Gestão de POPs"])
async def create_pop(pop_in: POPCreate):
    """Cadastra um novo POP no sistema."""
    return pop_manager.create(pop_in)

@app.delete("/api/pops/{pop_id}", tags=["Gestão de POPs"])
async def delete_pop(pop_id: str):
    """Exclui um POP cadastrado."""
    success = pop_manager.delete(pop_id)
    if not success:
        raise HTTPException(status_code=404, detail="POP não encontrado.")
    return {"status": "success", "message": f"POP '{pop_id}' removido com sucesso."}

# ==========================================
# ENDPOINTS DE PROCESSAMENTO EM LOTE (BULK)
# ==========================================

@app.post("/api/batch/upload", tags=["Processamento em Lote"])
async def upload_batch(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    layers: Optional[str] = Form(None)
):
    """
    Recebe um arquivo CSV ou XLSX com endereços/coordenadas para verificação em lote assíncrona.
    Opcionalmente recebe 'layers' para filtrar as manchas avaliadas durante o processamento do lote.
    """
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="Envie um arquivo no formato CSV (.csv) ou Excel (.xlsx).")

    target_layer_ids = None
    if layers and layers.strip():
        req_list = [p.strip() for p in layers.split(",") if p.strip()]
        resolved_ids, not_found = layer_manager.resolve_layer_ids(req_list)
        if not_found:
            raise HTTPException(
                status_code=400,
                detail=f"Camada(s) não encontrada(s): {', '.join(not_found)}"
            )
        target_layer_ids = resolved_ids

    temp_path = UPLOADS_DIR / f"batch_input_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job_id = await batch_processor.start_batch_job(temp_path, file.filename)
    background_tasks.add_task(batch_processor.execute_batch, job_id, temp_path, target_layer_ids=target_layer_ids)

    return {
        "job_id": job_id,
        "message": "Arquivo recebido com sucesso. Processamento iniciado em segundo plano.",
        "status_url": f"/api/batch/status/{job_id}"
    }

@app.get("/api/batch/status/{job_id}", response_model=BatchJobStatus, tags=["Processamento em Lote"])
async def get_batch_status(job_id: str):
    """Retorna o progresso atual do processamento em lote."""
    job = batch_processor.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job de processamento não encontrado.")
    return job

@app.get("/api/batch/download/{job_id}", tags=["Processamento em Lote"])
async def download_batch_result(job_id: str):
    """Download da planilha com os resultados enriquecidos de viabilidade."""
    result_file = UPLOADS_DIR / f"resultado_viabilidade_{job_id}.csv"
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="Arquivo de resultado ainda não disponível ou job não concluído.")
    
    return FileResponse(
        path=result_file,
        filename=f"resultado_viabilidade_{job_id}.csv",
        media_type="text/csv"
    )

@app.get("/api/batch/template", tags=["Processamento em Lote"])
async def download_batch_template():
    """Download da planilha modelo (.CSV) para consulta em lote."""
    template_file = BACKEND_DIR.parent / "sample_data" / "teste_lote.csv"
    if not template_file.exists():
        template_file = Path("/app/sample_data/teste_lote.csv")
    if not template_file.exists():
        raise HTTPException(status_code=404, detail="Arquivo modelo não encontrado.")
    
    return FileResponse(
        path=template_file,
        filename="modelo_consulta_viabilidade.csv",
        media_type="text/csv"
    )

# ==========================================
# SERVIR FRONTEND ESTÁTICO
# ==========================================
# Servir sample_data estático para compatibilidade de links diretos
sample_dir = BACKEND_DIR.parent / "sample_data"
if not sample_dir.exists():
    sample_dir = Path("/app/sample_data")
if sample_dir.exists():
    app.mount("/sample_data", StaticFiles(directory=str(sample_dir)), name="sample_data")

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


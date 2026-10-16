from enum import Enum
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, field_validator

class ViabilityStatus(str, Enum):
    VIAVEL = "VIAVEL"
    INVIAVEL = "INVIAVEL"
    EM_ANALISE = "EM_ANALISE"

class Coordinates(BaseModel):
    latitude: float
    longitude: float

class GeocodedLocation(BaseModel):
    query: str
    latitude: float
    longitude: float
    display_name: str
    source: str # "nominatim", "viacep", "direct_coords"
    confidence: Optional[float] = None

class PolygonMatchInfo(BaseModel):
    layer_id: str
    layer_name: str
    polygon_id: Optional[str] = None
    polygon_name: Optional[str] = None
    region: Optional[str] = None
    pop: Optional[str] = None
    technology: Optional[str] = None # Ex: Fibra GPON, Rede Neutra, Radio
    properties: Dict[str, Any] = Field(default_factory=dict)

class ViabilityQueryRequest(BaseModel):
    query: Optional[str] = Field(None, description="Endereço textual ou CEP para geocodificação")
    number: Optional[str] = Field(None, description="Número opcional do imóvel para geocodificação de alta precisão")
    latitude: Optional[float] = Field(None, description="Latitude opcional para consulta direta")
    longitude: Optional[float] = Field(None, description="Longitude opcional para consulta direta")
    layers: Optional[Union[List[str], str]] = Field(
        None,
        description="Lista opcional de IDs ou nomes de mapas/camadas a serem consultados. Ex: ['suzano', 'poá'] ou 'suzano, poa'"
    )
    layer: Optional[str] = Field(
        None,
        description="ID ou nome de camada/mapa único para consulta. Ex: 'suzano'"
    )

    @field_validator("layers", mode="before")
    @classmethod
    def parse_layers(cls, v):
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return parts if parts else None
        return v

    def get_requested_layers(self) -> Optional[List[str]]:
        """Retorna a lista unificada de camadas solicitadas, ou None se nenhuma foi especificada."""
        result = []
        if isinstance(self.layers, list):
            result.extend([l.strip() for l in self.layers if isinstance(l, str) and l.strip()])
        elif isinstance(self.layers, str) and self.layers.strip():
            result.extend([p.strip() for p in self.layers.split(",") if p.strip()])

        if self.layer and self.layer.strip():
            l_val = self.layer.strip()
            if l_val not in result:
                result.append(l_val)

        return result if result else None

class ViabilityResponse(BaseModel):
    status: ViabilityStatus
    input_query: Optional[str] = None
    location: Coordinates
    display_name: Optional[str] = None
    geocoding_source: Optional[str] = None
    matched_polygon: Optional[PolygonMatchInfo] = None
    all_matched_polygons: Optional[List[PolygonMatchInfo]] = Field(None, description="Lista de todos os polígonos sobrepostos que cobrem o ponto")
    distance_to_nearest_meters: float = 0.0
    consulted_layers: Optional[List[str]] = Field(None, description="Lista de camadas consideradas na verificação")
    message: str

class BatchJobStatus(BaseModel):
    job_id: str
    status: str # "PENDING", "QUEUED", "PROCESSING", "COMPLETED", "CANCELLED", "FAILED"
    queue_position: int = 0
    total_rows: int = 0
    processed_rows: int = 0
    viable_count: int = 0
    analysis_count: int = 0
    unviable_count: int = 0
    error_count: int = 0
    progress_percentage: float = 0.0
    processing_rate: float = 0.0 # Linhas por segundo
    elapsed_seconds: float = 0.0
    elapsed_time_formatted: str = "00:00"
    estimated_remaining_seconds: Optional[float] = None
    eta_formatted: str = "--:--"
    current_stage: str = "Iniciando..."
    current_item_preview: Optional[str] = None
    server_load: str = "Normal"
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    created_at: str
    completed_at: Optional[str] = None
    download_csv_url: Optional[str] = None
    download_kmz_url: Optional[str] = None
    error_message: Optional[str] = None

class SystemStatus(BaseModel):
    status: str # "healthy", "warning", "busy"
    server_load: str # "Normal", "Moderada", "Alta"
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_available_mb: Optional[float] = None
    uptime_seconds: float = 0.0
    active_batch_jobs: int = 0
    queued_batch_jobs: int = 0
    max_batch_rows: int = 10000

class LayerMetadata(BaseModel):
    id: str
    filename: str
    name: str
    technology: str
    color: str
    polygon_count: int
    enabled: bool = True
    is_primary: bool = False
    pop_id: Optional[str] = None
    pop_name: Optional[str] = None

class POP(BaseModel):
    id: str
    name: str
    city: Optional[str] = None
    address: Optional[str] = None
    latitude: float
    longitude: float
    capacity: Optional[str] = None
    technology: Optional[str] = "Fibra GPON"
    notes: Optional[str] = None

class POPCreate(BaseModel):
    name: str
    city: Optional[str] = None
    address: Optional[str] = None
    latitude: float
    longitude: float
    capacity: Optional[str] = None
    technology: Optional[str] = "Fibra GPON"
    notes: Optional[str] = None

# ==========================================
# MODELOS DE ROTEIRIZAÇÃO INTELIGENTE (VRP / TSP)
# ==========================================

class RoutingOptions(BaseModel):
    job_id: Optional[str] = Field(None, description="ID do lote analisado para roteirização")
    num_technicians: int = Field(default=1, ge=1, le=10, description="Quantidade de técnicos disponíveis")
    max_stops_per_technician: int = Field(default=8, ge=1, le=50, description="Máximo de atendimentos por técnico por dia")
    max_distance_km: float = Field(default=60.0, description="Distância máxima tolerada de deslocamento por dia (km)")
    avg_service_time_minutes: int = Field(default=25, description="Tempo médio estimado por visita (minutos)")
    depot_mode: str = Field(default="nearest_pop", description="Modo do ponto de saída: 'nearest_pop', 'company_hq', 'first_point', 'custom'")
    custom_depot_lat: Optional[float] = None
    custom_depot_lon: Optional[float] = None
    custom_depot_name: Optional[str] = "Ponto de Partida Customizado"
    filter_status: Optional[List[str]] = Field(default=["EM_ANALISE"], description="Status dos pontos a incluir na rota")
    use_real_roads: bool = Field(default=False, description="Se True, consulta geometria viária real via OSRM")

class RouteStop(BaseModel):
    sequence_order: int
    point_id: str
    title: str
    address: str
    latitude: float
    longitude: float
    status: str
    distance_from_prev_meters: float
    estimated_travel_minutes: float
    cumulative_time_minutes: float
    google_maps_url: str
    waze_url: str

class TechnicianRoute(BaseModel):
    technician_id: int
    technician_name: str
    color_hex: str
    day_number: int = 1
    depot_name: str
    depot_lat: float
    depot_lon: float
    total_stops: int
    total_distance_km: float
    total_estimated_duration_hours: float
    is_excessive_distance: bool = False
    warning_message: Optional[str] = None
    google_maps_multi_stop_url: str
    polyline_coords: List[List[float]] = Field(default_factory=list, description="Lista de [lat, lon] para desenho no mapa")
    stops: List[RouteStop]

class RoutePlanResponse(BaseModel):
    plan_id: str
    job_id: Optional[str] = None
    created_at: str
    num_technicians: int
    total_assigned_stops: int
    unassigned_stops: List[RouteStop] = Field(default_factory=list)
    routes: List[TechnicianRoute]
    summary_message: str
    download_kmz_url: Optional[str] = None
    download_csv_url: Optional[str] = None


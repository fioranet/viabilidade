from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

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

class ViabilityResponse(BaseModel):
    status: ViabilityStatus
    input_query: Optional[str] = None
    location: Coordinates
    display_name: Optional[str] = None
    geocoding_source: Optional[str] = None
    matched_polygon: Optional[PolygonMatchInfo] = None
    distance_to_nearest_meters: float = 0.0
    message: str

class BatchJobStatus(BaseModel):
    job_id: str
    status: str # "PENDING", "PROCESSING", "COMPLETED", "FAILED"
    total_rows: int = 0
    processed_rows: int = 0
    viable_count: int = 0
    analysis_count: int = 0
    unviable_count: int = 0
    error_count: int = 0
    progress_percentage: float = 0.0
    created_at: str
    completed_at: Optional[str] = None
    download_csv_url: Optional[str] = None
    error_message: Optional[str] = None

class LayerMetadata(BaseModel):
    id: str
    filename: str
    name: str
    technology: str
    color: str
    polygon_count: int
    enabled: bool = True
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


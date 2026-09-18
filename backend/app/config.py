import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Diretórios de Dados (configuráveis via ENV para volumes persistentes no Docker/Easypanel)
data_dir_env = os.getenv("DATA_DIR")
if data_dir_env:
    DATA_DIR = Path(data_dir_env)
else:
    DATA_DIR = BASE_DIR / "data"

LAYERS_DIR = DATA_DIR / "layers"
UPLOADS_DIR = DATA_DIR / "uploads"

# Diretório do Frontend
frontend_dir_env = os.getenv("FRONTEND_DIR")
if frontend_dir_env:
    FRONTEND_DIR = Path(frontend_dir_env)
elif (BASE_DIR.parent / "frontend").exists():
    FRONTEND_DIR = BASE_DIR.parent / "frontend"
else:
    FRONTEND_DIR = BASE_DIR / "frontend"

# Criar diretórios se não existirem
DATA_DIR.mkdir(parents=True, exist_ok=True)
LAYERS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Configurações de Geocodificação
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
NOMINATIM_USER_AGENT = os.getenv("NOMINATIM_USER_AGENT", "ViabilidadeISP_Engine/1.0 (contato@nuvv.com.br)")
NOMINATIM_MIN_INTERVAL_SECONDS = float(os.getenv("NOMINATIM_MIN_INTERVAL", "1.05")) # Respeitando regra < 1 req/s do OSM

# Configurações Espaciais
# Distância máxima (em metros) para classificar como "EM_ANALISE" (potencial extensão de rede)
TOLERANCIA_BORDA_METROS = float(os.getenv("TOLERANCIA_BORDA_METROS", "5.0"))
MAX_DISTANCIA_ANALISE_METROS = float(os.getenv("MAX_DISTANCIA_ANALISE_METROS", "100.0"))

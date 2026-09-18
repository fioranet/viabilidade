import json
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.config import DATA_DIR
from app.models.schemas import POP, POPCreate

POPS_FILE = DATA_DIR / "pops.json"

DEFAULT_POPS = [
    {
        "id": "pop-suzano-centro",
        "name": "POP Suzano Centro",
        "city": "Suzano",
        "address": "Rua General Francisco Glicério, Centro, Suzano - SP",
        "latitude": -23.5375,
        "longitude": -46.3125,
        "capacity": "10 Gbps (Redundante)",
        "technology": "Fibra GPON",
        "notes": "Hub central de distribuição para Suzano e adjacências"
    },
    {
        "id": "pop-poa-estacao",
        "name": "POP Poá Estação",
        "city": "Poá",
        "address": "Avenida Brasil, Centro, Poá - SP",
        "latitude": -23.5230,
        "longitude": -46.3430,
        "capacity": "10 Gbps",
        "technology": "Fibra GPON",
        "notes": "Ponto de presença próximo à CPTM Poá"
    }
]

class POPManager:
    """Gerenciador de Pontos de Presença (POPs) do ISP."""

    def __init__(self):
        self.pops: Dict[str, POP] = {}
        self._load()

    def _load(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not POPS_FILE.exists():
            # Criar com os POPs padrão
            self.pops = {p["id"]: POP(**p) for p in DEFAULT_POPS}
            self._save()
        else:
            try:
                with open(POPS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.pops = {p["id"]: POP(**p) for p in data}
            except Exception as e:
                print(f"[POPManager] Erro ao carregar POPs: {e}")
                self.pops = {p["id"]: POP(**p) for p in DEFAULT_POPS}

    def _save(self):
        try:
            with open(POPS_FILE, "w", encoding="utf-8") as f:
                json.dump([p.model_dump() for p in self.pops.values()], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[POPManager] Erro ao salvar POPs: {e}")

    def get_all(self) -> List[POP]:
        return list(self.pops.values())

    def get_by_id(self, pop_id: str) -> Optional[POP]:
        return self.pops.get(pop_id)

    def create(self, pop_in: POPCreate) -> POP:
        pop_id = f"pop-{uuid.uuid4().hex[:8]}"
        pop = POP(id=pop_id, **pop_in.model_dump())
        self.pops[pop_id] = pop
        self._save()
        return pop

    def delete(self, pop_id: str) -> bool:
        if pop_id in self.pops:
            del self.pops[pop_id]
            self._save()
            return True
        return False

# Instância singleton global
pop_manager = POPManager()

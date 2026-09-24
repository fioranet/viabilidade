import time
import os
from typing import Dict, Any, Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class SystemMonitor:
    """Monitora o uso de recursos e saúde do servidor para prevenção de sobrecarga."""

    def __init__(self):
        self.start_time = time.time()

    def get_metrics(self, active_jobs_count: int = 0) -> Dict[str, Any]:
        uptime = round(time.time() - self.start_time, 1)
        cpu_percent: Optional[float] = None
        memory_percent: Optional[float] = None
        memory_available_mb: Optional[float] = None

        if HAS_PSUTIL:
            try:
                # Obter uso de CPU (interval=None para não bloquear)
                cpu_percent = round(psutil.cpu_percent(interval=None), 1)
                mem = psutil.virtual_memory()
                memory_percent = round(mem.percent, 1)
                memory_available_mb = round(mem.available / (1024 * 1024), 1)
            except Exception:
                pass

        # Determinar status de carga
        if cpu_percent is not None and memory_percent is not None:
            if cpu_percent >= 85 or memory_percent >= 90:
                server_load = "Alta"
                status = "busy"
            elif cpu_percent >= 60 or memory_percent >= 75 or active_jobs_count >= 2:
                server_load = "Moderada"
                status = "warning"
            else:
                server_load = "Normal"
                status = "healthy"
        else:
            if active_jobs_count >= 2:
                server_load = "Moderada"
                status = "warning"
            else:
                server_load = "Normal"
                status = "healthy"

        return {
            "status": status,
            "server_load": server_load,
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "memory_available_mb": memory_available_mb,
            "uptime_seconds": uptime,
            "active_batch_jobs": active_jobs_count
        }

system_monitor = SystemMonitor()

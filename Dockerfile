FROM python:3.11-slim

# Instalar dependências de sistema para GEOS e compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgeos-dev \
    libproj-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependências Python com pip atualizado
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código e arquivos estáticos da aplicação
COPY backend/app ./backend/app
COPY backend/data ./backend/data
COPY frontend ./frontend
COPY utils ./utils
COPY sample_data ./sample_data

# Variáveis de ambiente padrão para produção / Easypanel
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV DATA_DIR=/app/backend/data
ENV FRONTEND_DIR=/app/frontend

EXPOSE 8000

# Inicialização com suporte a porta dinâmica do Easypanel ($PORT)
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

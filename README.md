# Sistema de Consulta de Viabilidade Técnica Geográfica (GIS Telecom)

Aplicação corporativa completa (Backend + Frontend + Motor Espacial) desenvolvida para **Provedores de Internet (ISPs)** realizarem consultas de viabilidade técnica em tempo real com base em manchas poligonais de cobertura geográfica.

---

## 🚀 1. Arquitetura e Decisões Técnicas

```
                                  [ Navegador / Usuário ]
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
               [ Leaflet.js Mapa ]                       [ Painel de Busca & Lote ]
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             │ HTTP REST / JSON
                                             ▼
                                  [ FastAPI Backend Engine ]
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
           [ Motor Espacial In-Memory ]                  [ Geocodificador Resiliente ]
           • Shapely 2.0 (GEOS em C)                     • Token-Bucket Rate Limiter (1s)
           • R-Tree Index (STRtree < 0.5ms)              • Nominatim (OpenStreetMap)
           • Cálculo Métrico WGS84 Geod                  • Fallback ViaCEP / BrasilAPI
                       │                                           │
                       ▼                                           ▼
             [ data/layers/*.geojson ]                  [ sample_data/teste_lote.csv ]
```

### Por que a Abordagem In-Memory (Shapely + STRtree)?
- **Sub-milissegundo por consulta:** O `STRtree` utiliza indexação espacial R-tree compilada em C (GEOS). Checar se um ponto está dentro de dezenas ou centenas de polígonos leva **menos de 0.5ms**.
- **Zero custo de infraestrutura adicional:** Dispensa a obrigatoriedade de gerenciar e manter um container de PostgreSQL/PostGIS para provedores de pequeno e médio porte (embora o sistema possa facilmente persistir em PostGIS se necessário).
- **Classificação Tríplice Inteligente:**
  1. `VIAVEL`: Ponto estritamente contido no polígono ou na borda (tolerância de 5 metros).
  2. `EM_ANALISE`: Ponto fora da mancha, mas a uma distância viável de atendimento via extensão de rede/cabo drop (ex: até 100 metros). O sistema informa a distância exata em metros e o POP mais próximo.
  3. `INVIAVEL`: Ponto distante da rede.

---

## 📦 2. Estrutura do Projeto

```
c:/Dev/Viabilidade/
├── backend/
│   ├── app/
│   │   ├── main.py                  # Endpoints REST e montagem do frontend
│   │   ├── config.py                # Configurações de timeout, URLs e tolerâncias
│   │   ├── services/
│   │   │   ├── spatial_engine.py    # Motor Shapely com STRtree e cálculo geodésico
│   │   │   ├── geocoding.py         # Nominatim com Rate Limit + ViaCEP/BrasilAPI
│   │   │   ├── batch_processor.py   # Processador assíncrono de lotes com progresso
│   │   │   └── layer_manager.py     # Gestão, leitura e hot-reload de GeoJSON/KMZ
│   │   └── models/
│   │       └── schemas.py           # Modelos Pydantic para validação e Swagger
│   ├── data/
│   │   ├── layers/                  # Armazenamento das manchas ativas
│   │   │   └── sample_coverage.geojson # Manchas de exemplo (SP)
│   │   └── uploads/                 # Arquivos temporários e resultados de lote
│   └── requirements.txt
├── frontend/
│   ├── index.html                   # Interface SPA completa
│   ├── css/style.css                # Dark mode telecom premium
│   └── js/
│       ├── map.js                   # Visualização Leaflet com manchas e pins dinâmicos
│       ├── api.js                   # Camada de comunicação HTTP
│       └── app.js                   # Lógica das abas, busca e upload em lote
├── utils/
│   └── kmz_to_geojson.py            # Conversor autônomo KMZ/KML -> GeoJSON
├── sample_data/
│   └── teste_lote.csv               # Planilha de exemplo para teste do módulo em lote
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 🛠️ 3. Como Executar Localmente

### Pré-requisitos:
- Python 3.10 ou superior instalado.

### Passo a passo:

1. **Criar e Ativar o Ambiente Virtual:**
   ```bash
   python -m venv .venv
   
   # Windows (PowerShell):
   .venv\Scripts\Activate.ps1

   # Linux/macOS:
   source .venv/bin/activate
   ```

2. **Instalar as Dependências:**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Iniciar a Aplicação:**
   ```bash
   python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Acessar no Navegador:**
   - **Interface Web:** [http://localhost:8000](http://localhost:8000)
   - **Documentação Interativa da API (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🐳 4. Executando via Docker / Docker Compose

Para subir o sistema pronto para produção em qualquer servidor VPS:

```bash
docker-compose up --build -d
```

A aplicação estará acessível na porta `8000`. As manchas colocadas em `./backend/data/layers/` persistem automaticamente entre reinicializações dos containers.

---

## 🗺️ 5. Módulos do Sistema

### 1. Consulta Unitária
- Permite pesquisar por:
  - **Endereço Completo:** Ex: `Avenida Paulista, 1000, São Paulo`
  - **CEP:** Ex: `01310-100` ou `04028002`
  - **Coordenadas Diretas:** Ex: `-23.5650, -46.6550`
  - **GPS do Dispositivo:** Botão com mira para capturar a localização atual do navegador.
- Retorno instantâneo no mapa:
  - Destaque do polígono de cobertura.
  - Pin com status (Verde = Viável, Âmbar = Em Análise, Vermelho = Inviável).
  - Cards com Tecnologia (GPON, Rádio, Rede Neutra), POP responsável e distância métrica da borda.

### 2. Processamento em Lote (Bulk Check)
- Suporta upload de arquivos **CSV** (delimitador `,` ou `;`) e **Excel (.xlsx)**.
- O sistema reconhece colunas automaticamente: `Logradouro`, `Numero`, `Bairro`, `Cidade`, `UF`, `CEP` ou `Latitude`, `Longitude`.
- Processamento assíncrono em background sem travamento da interface.
- Barra de progresso em tempo real e contadores dinâmicos.
- Exportação com um clique de planilha `.CSV` enriquecida com as colunas:
  - `Viabilidade_Status`
  - `Latitude_Utilizada`
  - `Longitude_Utilizada`
  - `Mancha_Atendimento`
  - `POP_Estacao`
  - `Tecnologia`
  - `Distancia_Borda_Metros`
  - `Mensagem_Tecnica`

### 3. Gestão e Upload de Manchas
- Permite subir novos arquivos `.geojson` ou `.kmz` diretamente pela interface.
- O sistema converte o KMZ instantaneamente e recria o índice espacial R-tree em tempo de execução (*hot-reload*).

---

## 🔄 6. Conversão de KMZ / KML para GeoJSON

### Opção A: Script Python Autônomo (Incluso no projeto)
Não requer instalação de bibliotecas binárias de C++ ou GDAL:

```bash
# Converter um arquivo único:
python utils/kmz_to_geojson.py ./cobertura_cidade.kmz ./backend/data/layers/cobertura_cidade.geojson --tech "Fibra GPON"

# Converter uma pasta inteira em lote:
python utils/kmz_to_geojson.py ./pasta_com_kmzs/ ./backend/data/layers/ --batch --tech "Rede Neutra"
```

### Opção B: Utilitário GDAL / ogr2ogr (Alternativa nativa C++)
Caso prefira utilizar a ferramenta clássica de GIS no terminal:

```bash
# Extração direta do KML interno do KMZ para GeoJSON WGS84:
ogr2ogr -f "GeoJSON" ./cobertura.geojson "/vsizip/cobertura.kmz/doc.kml" -t_srs EPSG:4326
```

---

## 🐳 7. Deploy no Easypanel

O projeto está 100% pronto para deploy no **Easypanel** utilizando o `Dockerfile` incluso:

### Passo a Passo no Easypanel:
1. No painel do **Easypanel**, crie um novo **App** (tipo `App` ou `Service`).
2. Em **Source**, selecione **GitHub**:
   - **Repository:** `fioranet/viabilidade`
   - **Branch:** `main`
   - **Build Method:** `Dockerfile`
3. Em **Environment**, configure se desejar (opcionais, já vêm com defaults seguros):
   - `PORT=8000` (ou deixe o Easypanel injetar)
   - `NOMINATIM_USER_AGENT=ViabilidadeISP_Engine/1.0 (contato@nuvv.com.br)`
   - `TOLERANCIA_BORDA_METROS=5.0`
   - `MAX_DISTANCIA_ANALISE_METROS=100.0`
4. Em **Volumes / Mounts** (MUITO IMPORTANTE):
   - Mapeie um volume persistente para manter suas manchas e POPs mesmo após novos deploys:
   - **Host Path:** `viabilidade_data` (ou path no servidor) ➔ **Mount Path:** `/app/backend/data`
5. Em **Domains**:
   - Aponte seu subdomínio (ex: `viabilidade.nuvv.com.br` ou `api-viabilidade.nuvv.com.br`).
6. Clique em **Deploy**.

---

## 🔌 8. Integração com APIs e Sistemas Externos (API REST)

O sistema opera como um microsserviço independente (API Headless), permitindo que sites institucionais, CRMs e bots de atendimento consultem a viabilidade em tempo real.

### Seleção de Mapa / Camadas em Uso na Chamada da API

Você pode restringir a verificação para **mapas ou regiões específicas** (por exemplo, um serviço residencial comercializado apenas em Suzano e Poá, sem consultar outras cidades ou redes corporativas).

Formatos aceitos no payload:
- **Array de nomes/IDs:** `"layers": ["suzano", "poa"]` ou `["Suzano", "Poá"]`
- **String única:** `"layer": "suzano"`
- **String separada por vírgula:** `"layers": "suzano, poa"`
- **Omissão do parâmetro:** Caso omitido, a consulta avalia **todas as manchas ativas** do sistema.

> [!NOTE]
> A resolução de nomes é **insensível a maiúsculas/minúsculas e acentos** (ex: `"poa"` encontra automaticamente a camada `"poá"`). Caso informe uma camada inexistente, a API retorna `HTTP 400 Bad Request` listando as camadas disponíveis.

### Exemplo de Chamada no Frontend (JavaScript / Fetch):

```javascript
// Exemplo: Consultar viabilidade residencial apenas para Suzano e Poá:
async function consultarViabilidadeResidencial(cepOuEndereco, numero) {
  const API_URL = "https://viabilidade.nuvv.com.br/api/viability/check";

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: cepOuEndereco,
        number: numero || null,
        layers: ["suzano", "poa"] // 🎯 Restringe a consulta às áreas residenciais de Suzano e Poá
      })
    });

    const data = await response.json();

    if (data.status === "VIAVEL") {
      // Exibir feedback positivo e abrir planos residenciais disponíveis
      alert(`Parabéns! Temos cobertura para você em ${data.matched_polygon.region} via ${data.matched_polygon.technology}!`);
    } else if (data.status === "EM_ANALISE") {
      // Oferecer contato com consultor comercial (estudo de viabilidade a poucos metros)
      alert(`Estamos a apenas ${data.distance_to_nearest_meters}m da sua residência! Envie seus dados para análise técnica.`);
    } else {
      // Inviável: Capturar lead para lista de espera
      alert(`Ainda não chegamos no seu endereço para este serviço residencial.`);
    }
  } catch (error) {
    console.error("Erro ao checar viabilidade:", error);
  }
}
```

### Exemplo via cURL:

```bash
curl -X POST "http://localhost:8000/api/viability/check" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Rua General Francisco Glicério, 1000, Suzano",
    "layers": ["suzano", "poa"]
  }'
```

### Exemplo de Resposta JSON:

```json
{
  "status": "VIAVEL",
  "input_query": "Rua General Francisco Glicério, 1000, Suzano",
  "location": {
    "latitude": -23.5416,
    "longitude": -46.3147
  },
  "display_name": "Rua General Francisco Glicério, Suzano, SP",
  "geocoding_source": "nominatim",
  "matched_polygon": {
    "layer_id": "suzano",
    "layer_name": "Suzano",
    "polygon_id": "0",
    "polygon_name": "SPSZN002H",
    "region": "SPSZN002H",
    "pop": "POP Suzano Centro",
    "technology": "Rede Neutra",
    "properties": {
      "status": "Existente"
    }
  },
  "distance_to_nearest_meters": 0.0,
  "consulted_layers": [
    "Suzano",
    "Poá"
  ],
  "message": "Viabilidade Confirmada! Atendido pela mancha 'SPSZN002H' via Rede Neutra (POP Suzano Centro)."
}
```



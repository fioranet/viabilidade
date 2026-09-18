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

## 🔌 8. Integração com o Site da Nuvv (API REST)

Em vez de acoplar a lógica pesada de GIS dentro do site institucional da Nuvv (o que tornaria o site mais lento e difícil de manter), a arquitetura recomendada é manter este serviço como um **microsserviço independente (API Headless)**.

### Vantagens dessa abordagem:
- **Zero impacto na velocidade do site:** O motor geoespacial e geocodificador rodam isolados no seu container.
- **Manutenção centralizada:** Quando o time de engenharia adicionar novas manchas ou POPs na interface de gestão, o site da Nuvv já passa a consultar a base atualizada em tempo real sem precisar de novo deploy no site.
- **Segurança e Rate Limit:** Protege as requisições e caches sem expor chaves ou estruturas internas.

### Exemplo de Chamada no Frontend do Site da Nuvv (JavaScript / Fetch):

```javascript
// Exemplo de integração no formulário "Consulte sua Cobertura" do site da Nuvv:
async function consultarViabilidadeNuvv(cepOuEndereco, numero) {
  const API_URL = "https://viabilidade.nuvv.com.br/api/viability/check";

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: cepOuEndereco,
        number: numero || null
      })
    });

    const data = await response.json();

    if (data.status === "VIAVEL") {
      // Exibir feedback positivo e abrir planos disponíveis
      alert(`Parabéns! Temos cobertura para você via ${data.matched_polygon.technology}!`);
    } else if (data.status === "EM_ANALISE") {
      // Oferecer contato com consultor comercial (estudo de viabilidade)
      alert(`Estamos a poucos metros do seu endereço! Envie seus dados para análise técnica de expansão.`);
    } else {
      // Inviável: Capturar lead para lista de espera
      alert(`Ainda não chegamos no seu endereço. Cadastre seu e-mail para ser avisado quando chegarmos!`);
    }
  } catch (error) {
    console.error("Erro ao checar viabilidade:", error);
  }
}
```


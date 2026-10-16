# Projeto Arquitetural: Módulo de Roteirização Inteligente de Visitas

> **Status:** Planejamento / Proposta Arquitetural  
> **Responsáveis Especialistas:** `project-planner`, `backend-specialist`, `frontend-specialist`  
> **Sistema:** GeoViabilidade Telecom GIS Engine  

---

## 1. Visão Geral e Objetivos do Negócio

No fluxo atual, o sistema processa planilhas em lote (endereços/coordenadas) e classifica cada ponto em **VIÁVEL**, **EM ANÁLISE** (borda/vistoria necessária) ou **INVIÁVEL**.

A nova ferramenta de **Roteirização Inteligente** transformará esses pontos geocodificados em **rotas de trabalho otimizadas para equipes de campo**:
1. **Otimização de Trajeto (TSP / VRP):** Encontrar a sequência mais rápida e curta para visitar os pontos, eliminando deslocamentos em zigue-zague.
2. **Distribuição Equilibrada entre Técnicos (mTSP):** Dividir a carga de trabalho entre $N$ técnicos disponíveis (ex: 2 técnicos com 6 visitas cada, e não 1 técnico com 11 e outro com 1).
3. **Detecção de Distâncias Proibitivas e Separação Multidias / Multirroteiros:** Se pontos estiverem dispersos geograficamente (ex: cidades distantes) ou excederem o limite de horas/quilometragem do dia de trabalho, o motor segmenta os pontos em **clusters regionais** ou **dias subsequentes** (Dia 1, Dia 2).
4. **Usabilidade Operacional para o Técnico de Campo:** Geração de botões com links diretos para navegação no **Google Maps** e **Waze**, visualização interativa no Leaflet com marcadores sequenciais (`[1]`, `[2]`, `[3]`) e exportação em **KMZ** e **CSV**.

---

## 2. Modelagem Matemática e Algorítmica

O problema se enquadra na classe **VRP com Restrições de Capacidade e Tempo (Capacitated Vehicle Routing Problem with Time/Distance Constraints)**.

```
                    [ Ponto de Partida: POP / Sede / Ponto 1 ]
                                       │
                  ┌────────────────────┴────────────────────┐
                  ▼                                         ▼
         Cluster 1 (Região A)                      Cluster 2 (Região B)
    (Distância < Limite Diário)               (Distância > Limite Diário)
                  │                                         │
       ┌──────────┴──────────┐                              │
       ▼                     ▼                              ▼
  Técnico 1             Técnico 2                    Dividir em Dias
(Seq: 1→2→3→4)        (Seq: 5→6→7→8)             (Dia 1: 9→10 | Dia 2: 11→12)
```

### 2.1. Pipeline de 3 Estágios do Motor de Rota

1. **Estágio 1 - Filtragem & Depósito (Ponto de Partida):**
   - Usuário escolhe quais pontos roteirizar:
     - *Apenas Em Análise (Vistorias de Drop)* [Padrão recomendado]
     - *Apenas Viáveis (Instalações pendentes)*
     - *Todos os pontos válidos*
   - Ponto de partida configurável:
     - *POP mais próximo*: Inicia na estação/central da operadora.
     - *Sede / Endereço da Empresa*: Coordenada fixa configurável.
     - *Primeiro ponto da lista / Localização atual GPS*.

2. **Estágio 2 - Agrupamento Espacial (Clustering Restrito):**
   - **Algoritmo:** K-Means Geoespacial com restrição de cardinalidade máxima ou DBSCAN por densidade de vizinhança.
   - **Critérios de corte (Distâncias Proibitivas):**
     - Se a distância entre o ponto e o centróide mais próximo for superior ao *Raio Máximo Operacional* (ex: 35 km ou 50 km), esse ponto é isolado em um cluster separado (Roteiro Extra ou Próximo Dia).
     - Se o número de visitas acumuladas em um técnico ultrapassar a *Jornada Máxima* (ex: 8 horas totais = tempo de deslocamento + tempo estimado de permanência em cada vistoria, ex: 25 min/ponto), gera-se automaticamente uma divisão para outro dia ou outro técnico.

3. **Estágio 3 - Otimização de Rota por Cluster (TSP Solver):**
   - **Algoritmo de Ordenação:**
     - Heurística Construtiva: *Nearest Neighbor* (Vizinho Mais Próximo) partindo do ponto inicial.
     - Heurística de Melhoria Local: **2-Opt Swap Local Search** para desatar cruzamentos de trajetos (elimina rotas que cruzam entre si, garantindo a rota mais harmônica e rápida).
   - **Complexidade:** Execução instantânea no backend em Python (< 150ms para até 200 paradas), sem risco de travar o servidor FastAPI.

### 2.2. Cálculo de Distâncias e Malha Viária

Propomos suporte híbrido com dois modos:

| Modo | Fonte de Matriz de Distância | Prós | Contras | Recomendação |
|---|---|---|---|---|
| **Modo Rápido (Nativo)** | Haversine + Fator de Sinuosidade Viária Urbana (1.35x ~ 1.40x) | Instantâneo, zero custo, funciona 100% offline, sem limites de API | É uma estimativa linear corrigida das ruas | Modo padrão do sistema |
| **Modo Malha Viária Real** | OSRM (*Open Source Routing Machine*) público ou interno | Trajeto curva-a-curva real pelas ruas, tempo real com velocidades médias | Depende de chamada HTTP a servidor OSRM | Ativável por toggle na UI ("Usar malha viária real") |

---

## 3. Arquitetura de Software e Endpoints da API

### 3.1. Novo Módulo de Serviço Backend: `app/services/routing_engine.py`

Funções principais:
- `calculate_distance_matrix(points: List[Dict], mode="haversine_corrected")`
- `cluster_points_for_technicians(points, num_technicians, max_km_per_day, max_stops_per_tech)`
- `solve_tsp_2opt(depot, stops)`
- `build_navigation_links(stops)` (gera URL formatada de waypoints para Google Maps e Waze)
- `export_route_kmz(route_plan)` (gera arquivo KMZ com as linhas de caminho e marcadores numerados)

### 3.2. Novos Modelos Pydantic em `app/models/schemas.py`

```python
class RoutingOptions(BaseModel):
    num_technicians: int = Field(default=1, ge=1, le=10)
    max_stops_per_technician: int = Field(default=8, ge=1, le=50)
    max_distance_km: float = Field(default=60.0, description="Distância máxima de deslocamento por rota")
    avg_service_time_minutes: int = Field(default=25, description="Tempo médio gasto em cada visita")
    depot_mode: str = Field(default="nearest_pop", description="'nearest_pop', 'first_point', 'custom'")
    custom_depot_lat: Optional[float] = None
    custom_depot_lon: Optional[float] = None
    filter_status: Optional[List[str]] = Field(default=["EM_ANALISE"])

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

class TechnicianRoute(BaseModel):
    technician_id: int
    technician_name: str
    color_hex: str
    day_number: int
    total_stops: int
    total_distance_km: float
    total_estimated_duration_hours: float
    is_excessive_distance: bool
    warning_message: Optional[str] = None
    google_maps_multi_stop_url: str
    stops: List[RouteStop]

class RoutePlanResponse(BaseModel):
    plan_id: str
    created_at: str
    num_technicians: int
    total_assigned_stops: int
    unassigned_stops: List[RouteStop] = []
    routes: List[TechnicianRoute]
    summary_message: str
```

### 3.3. Novos Endpoints no FastAPI (`main.py`)

- `POST /api/routing/plan`: Recebe `job_id` do lote recém-processado + `RoutingOptions`, calcula o plano de roteamento e retorna o `RoutePlanResponse`.
- `GET /api/routing/export-kmz/{plan_id}`: Faz download do arquivo KMZ contendo o traçado visual das rotas e os pontos numerados por técnico.
- `GET /api/routing/export-csv/{plan_id}`: Planilha de ordem de visitas sequencial pronta para impressão ou envio por WhatsApp aos técnicos.

---

## 4. Design da Interface do Usuário (UI/UX)

Seguindo o design system do GeoViabilidade (tema escuro com tons grafite, tipografia moderna e destaques em verde/azul/âmbar sem excessos):

### 4.1. Aba de Ações de Roteamento no Painel de Lote

Quando um lote é processado (ou ao carregar um lote existente), um novo card surge abaixo dos contadores de viabilidade:

```
┌────────────────────────────────────────────────────────┐
│ 🚗 Roteirização Inteligente de Visitas                 │
├────────────────────────────────────────────────────────┤
│ Pontos para Rota:                                      │
│ [x] Em Análise (12 vistorias)  [ ] Viáveis (45 inst.)  │
│                                                        │
│ Equipe & Parâmetros:                                   │
│ Técnicos Disponíveis:  [ 2  ▼ ]                        │
│ Visitas Máx. / Técnico: [ 8 ]                          │
│ Raio Máximo de Alerta: [ 40 km ]                       │
│ Ponto de Saída:        [ POP Mais Próximo ▼ ]          │
│                                                        │
│ [ 🚀 Otimizar e Gerar Roteiros de Visita ]             │
└────────────────────────────────────────────────────────┘
```

### 4.2. Visualização no Mapa Leaflet

1. **Marcadores Numerados com Pins Customizados:**
   - Cada técnico recebe uma paleta de alta legibilidade:
     - **Técnico 1:** Ciano `#06b6d4`
     - **Técnico 2:** Laranja Âmbar `#f97316`
     - **Técnico 3:** Esmeralda `#10b981`
     - **Técnico 4:** Violeta Claro `#8b5cf6`
   - O ícone no mapa exibe o número sequencial: `1`, `2`, `3` dentro de um círculo colorido.
2. **Polylines de Rota:**
   - Linhas coloridas correspondentes ao técnico conectando ordenadamente da base/POP para a Parada 1 → Parada 2 → Parada 3...
   - Efeito tracejado suave ou linha sólida semi-translúcida.
3. **Painel Flutuante do Roteiro (Route Drawer):**
   - Lista colapsável com as paradas de cada técnico em ordem.
   - Ao clicar em uma parada na lista, o mapa dá zoom suave no ponto.
   - Cada parada possui atalho:
     - 🗺️ **Abrir rota completa no Google Maps** (com todos os waypoints já inseridos na URL).
     - 🚗 **Ir até aqui com Waze**.
     - 📥 **Baixar Roteiro KMZ / CSV**.

---

## 5. Decisões Homologadas pelo Usuário (Alinhamento Concluído)

As três diretrizes fundamentais do projeto foram definidas e aprovadas:

### ✅ Decisão 1: Ponto de Partida Flexível
- **Definição:** A interface oferecerá um seletor no painel de roteirização com três opções:
  1. **POP Mais Próximo (Padrão):** O algoritmo identifica automaticamente o POP cadastrado mais perto do centróide das visitas daquele técnico.
  2. **Sede / Base Fixa:** Utiliza coordenadas configuradas da empresa/matriz.
  3. **Primeiro Ponto da Lista:** Inicia diretamente no primeiro endereço do arquivo, útil caso o técnico já vá direto de casa ao primeiro cliente.

### ✅ Decisão 2: Tratamento de Distâncias Proibitivas e Jornada de Trabalho
- **Definição:** O algoritmo calculará a jornada de trabalho acumulada (tempo de deslocamento + 25 minutos estimados por visita).
- Se a rota de uma região exceder a jornada máxima diária (ex: 8 horas ou 60 km), o sistema:
  1. Primeiro tenta alocar os pontos adicionais para outro técnico livre na mesma área de atendimento.
  2. Caso todos os técnicos atinjam sua capacidade, o sistema automaticamente desdobra o roteiro em **dias subsequentes** (ex: *Técnico 1 - Dia 1* e *Técnico 1 - Dia 2*), permitindo que o gestor planeje o cronograma semanal de campo.

### ✅ Decisão 3: Motor Híbrido de Trajeto e Navegação Mobile
- **Definição:**
  1. **Processamento Inicial Ultrarrápido:** Cálculo instantâneo no backend via matriz de Haversine ajustada por fator urbano (1.35x), garantindo resposta em milissegundos sem sobrecarregar a rede.
  2. **Traçado Real pelas Ruas (OSRM Gratuito):** Opção com um clique para desenhar a geometria curva-a-curva perfeitamente encaixada nas ruas no mapa Leaflet.
  3. **Integração Prática de Campo:** Cada parada gerará URLs diretas com deep links para **Google Maps** (rota multiparadas completa) e **Waze** (navegação ponto a ponto no smartphone do técnico).

---

## 6. Plano de Fases para Implementação Futura

1. **Fase 1 (Backend Core):** Criação do `routing_engine.py` com o algoritmo de clusterização espacial, solver 2-opt, estimativa de deslocamento e testes unitários automatizados com planilhas de teste.
2. **Fase 2 (Endpoints FastAPI):** Implementação das rotas `/api/routing/plan`, `/api/routing/export-kmz` e `/api/routing/export-csv`.
3. **Fase 3 (Frontend & Map Visualizer):** Adição do formulário de roteirização no painel de lote ([app.js](file:///c:/Dev/Viabilidade/frontend/js/app.js)), renderizador de polylines e pins sequenciais numerados no Leaflet ([map.js](file:///c:/Dev/Viabilidade/frontend/js/map.js)).
4. **Fase 4 (Exportadores & Mobile Deep Links):** Montagem dinâmica dos links do Google Maps/Waze e download de relatórios.
5. **Fase 5 (Testes de Carga & Validação de Campo):** Testar com lotes de 20 a 500 registros, avaliando tempo de resposta e coerência geográfica das rotas geradas.

---
*Documento gerado automaticamente pelo time de especialistas do Antigravity Kit.*

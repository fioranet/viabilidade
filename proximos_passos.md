# Planejamento Técnico e Próximos Passos | Sistema de Viabilidade Técnica Geográfica

Este documento consolida o planejamento de melhorias no processamento em lote e a estratégia de engenharia geoespacial para integração dos ativos de rede e condomínios da IHS.

---

## 1. Ajustes no Processamento em Lote

### 1.1 Fim do Disparo Automático (Upload com Confirmação)
* **Comportamento Atual:** Ao selecionar ou arrastar o arquivo `.csv` ou `.xlsx`, a rotina de envio e processamento é disparada imediatamente.
* **Novo Fluxo:**
  1. O usuário seleciona ou arrasta o arquivo.
  2. O sistema realiza apenas a **leitura prévia e validação** do arquivo, exibindo:
     * Nome do arquivo e tamanho formatado.
     * Total estimado de linhas / registros detectados.
     * Indicador de colunas identificadas (CEP, Endereço, Número, Lat, Long).
  3. O usuário revisa os parâmetros e clica no botão explícito **"Iniciar Análise de Viabilidade"** para começar a execução.

### 1.2 Painel de Parâmetros de Distância Dinâmicos
Permitir personalizar os limites de cálculo diretamente na interface antes de rodar o lote, enviando esses parâmetros para a API:
* **Tolerância de Borda (m):** Campo numérico configurável (padrão: `5.0` metros). Classifica como **Viável** pontos localizados imediatamente fora do polígono devido a imprecisões de geocodificação ou satélite.
* **Distância Máxima para "Em Análise" (m):** Campo numérico configurável (padrão: `100.0` metros). Classifica como **Em Análise** pontos situados dentro do raio de atendimento para viabilidade mediante extensão de rede ou lançamento de cabo drop.
* **Seletor de Mapa Alvo:** Opção de executar a checagem do lote contra todas as manchas ativas ou restringir a uma camada/rede específica (ex: Rede Própria vs. Rede Neutra).

---

## 2. Estratégia de Uso dos Arquivos da Rede IHS

A inclusão desses dados transforma a análise de uma simples checagem de "mancha teórica" em uma **análise física de engenharia de telecomunicações**:

---

### A. Edifícios e Condomínios Já Abordados (*On-Net Buildings*)
* **Conceito Técnico:** Prédios comerciais, condomínios residenciais e shoppings já interligados internamente com fibra IHS representam a oportunidade de maior valor: **ativação imediata, custo marginal de implantação quase zero e sem necessidade de licenciamento de obra externa**.
* **Modelagem e Uso no Sistema:**
  1. **Status Prioritário "Viável (On-Net / Edifício Abordado)":**
     * Durante a consulta (unitária ou em lote), o sistema cruza primeiramente o endereço/CEP + Número ou a coordenada geocodificada contra a base de edifícios (raio de 15m a 20m).
     * Havendo correspondência, o status é definido como **Viável On-Net**, retornando o nome do condomínio, tipo (Residencial/Comercial/Misto) e facilidade de atendimento.
  2. **Camada Visual Exclusiva no Mapa:**
     * Exibição de ícones diferenciados de prédios (ex: tonalidade Dourada/Roxa ou ícone de edifício).
     * Popup detalhado ao clicar no ponto com informações cadastrais do condomínio e quantidade de blocos/andares (se disponível).

---

### B. CDOEs e Caixas de Atendimento da Rede IHS
* **Conceito Técnico:** As Caixas de Distribuição Óptica (CDOEs) representam o ponto físico exato onde o cabo *drop* do cliente é conectorizado.
* **Modelagem e Uso no Sistema:**
  1. **Identificação da CDOE Mais Próxima:**
     * Para cada cliente consultado, o motor espacial consulta via R-Tree/k-d tree a CDOE mais próxima, calculando a menor distância métrica real.
     * Retorno no resultado: *"Viável a 42m da CDOE-IHS-SP-0412 (Poste X)"*.
  2. **Geração Automática de Manchas Reais (Buffers de Atendimento):**
     * A partir da localização das caixas, é possível gerar polígonos automáticos de cobertura técnica baseados no raio máximo de drop homologado (ex: 80m ou 100m ao redor de cada caixa).
  3. **Traçado de Rota de Drop no KMZ (Google Earth):**
     * Na exportação do `.kmz`, desenhar uma linha guia vetorial entre a coordenada do cliente e a CDOE mais próxima identificada, facilitando a vistoria em campo pela equipe técnica e comercial.
  4. **Camada Seletiva e Clusterização no Mapa:**
     * Renderização em camada dedicada no Leaflet com clusterização de alta performance, permitindo ligar e desligar a visualização das caixas para estudos de expansão de rede.

---

## 3. Roteiro de Execução

1. **Fase 1 (Interface e API de Lote):**
   * Adicionar no frontend o botão de disparo manual do lote e os campos de tolerância e distância máxima.
   * Ajustar o endpoint `/api/batch/upload` no backend para receber `tolerancia_borda` e `max_distancia_analise`.
2. **Fase 2 (Ingestão de Dados IHS):**
   * Identificar o formato dos arquivos fornecidos (Excel/CSV, KML/KMZ ou Shapefile).
   * Desenvolver scripts de normalização e carga para os edifícios abordados e para o parque de CDOEs.
3. **Fase 3 (Enriquecimento dos Resultados e KMZ):**
   * Integrar a busca por proximidade de CDOE e detecção de On-Net no motor espacial.
   * Incluir os dados detalhados no relatório `.csv` e nas camadas do `.kmz`.

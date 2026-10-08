# Mercado imobiliário da Serra Gaúcha

Quanto se pede pelo m² em nove cidades da Serra Gaúcha, como o preço evoluiu frente à inflação e ao custo de construir, para onde tende a ir e quanto se pede por um imóvel com determinadas características.

**Painel com mapa de calor:** https://fabi3105.github.io/mercado-imobiliario-serra-gaucha/
**Painel em Power BI:** [ver em PDF](painel_power_bi.pdf), sem precisar abrir o Power BI; projeto na pasta `Imoveis_Serra_PBIP` (formato .pbip)

> Os preços são **pedidos em anúncios**, coletados em 07/10/2026, e não preços de venda. O valor fechado costuma ser menor.

## Principais resultados

| Cidade | Apartamento (R$/m²) | Casa (R$/m²) | Terreno (R$/m²) |
|---|---|---|---|
| Gramado | 16.134 | 10.949 | 1.183 |
| Canela | 12.631 | 8.772 | 1.020 |
| Bento Gonçalves | 8.654 | 5.960 | 718 |
| Nova Petrópolis | 8.380 | 6.613 | 615 |
| Garibaldi | 7.112 | 5.556 | 595 |
| Flores da Cunha | 7.033 | 4.391* | 441 |
| Carlos Barbosa | 6.713 | 5.702 | 720* |
| Farroupilha | 6.528 | 5.017 | 528 |
| Caxias do Sul | 6.127 | 4.658 | 774 |

Mediana do preço pedido por m², 22.022 imóveis. *Amostra pequena (14 casas em Flores da Cunha, 48 terrenos em Carlos Barbosa).

- **Validação:** a mediana dos apartamentos de Caxias do Sul (R$ 6.127/m²) ficou 5% abaixo do Índice FipeZap da cidade em agosto/2026 (R$ 6.463/m²).
- **Preço x inflação x custo de construir:** de jan/2018 a ago/2026 o imóvel em Caxias subiu 63,6% (FipeZap), acima do IPCA (54,8%) e abaixo do INCC-DI (80,0%). Ganhou 5,7% em termos reais e perdeu 9,1% frente ao custo de construir. Porto Alegre subiu 25,9% no mesmo período.
- **Projeção de 5 anos:** das quatro regras testadas contra o passado, a que menos errou foi "o preço acompanha a inflação" (erro médio de 8,1% em 3 anos, quase sempre para baixo). Com IPCA de 5,2% ao ano, o m² de apartamento em Caxias iria de R$ 6.127 para cerca de R$ 7.900 em 2031. Fora de Caxias não há série histórica; a projeção supõe o mesmo ritmo.
- **Construção (Censos 2010 e 2022):** os apartamentos cresceram de 6% a 8% ao ano na maioria das cidades, e as casas menos de 2,6%. Em Bento Gonçalves passaram de 7,0 mil para 18,4 mil.
- **Oferta anunciada frente ao estoque:** Flores da Cunha, Carlos Barbosa, Farroupilha e Garibaldi têm poucos anúncios em relação aos domicílios existentes. O indicador mede oferta, não demanda, e fica inflado em Gramado, Canela e Nova Petrópolis, onde muitos imóveis são de uso ocasional.
- **Estimativa de valor:** regressão com área, vagas, banheiros, condomínio, cidade e bairro. Erro mediano em validação cruzada: 17% para apartamento, 23% para casa e 27% para terreno. O painel mostra o valor e uma faixa que contém 8 de cada 10 casos.

## Fontes

| Dado | Fonte |
|---|---|
| Anúncios de venda (apartamento, casa, terreno) | Portal Chaves na Mão, pelo canal público que o site oferece a agentes de IA ([llms.txt](https://www.chavesnamao.com.br/llms.txt)), uma consulta a cada 2 segundos |
| Série histórica de preços (Caxias do Sul, Porto Alegre, Brasil) | Índice FipeZap, Fipe |
| IPCA (série 433) e INCC-DI (série 192) | Banco Central, SGS |
| Domicílios por tipo, 2010 e 2022 | IBGE, SIDRA, tabelas 3152, 6326 e 4712 |

## Como foi feito

| Script | O que faz |
|---|---|
| `scripts/01_coletar_anuncios.py` | Coleta os anúncios; guarda só características do imóvel (sem anunciante, telefone, texto, foto ou link) |
| `scripts/02_tratar_anuncios.py` | Mantém só a cidade pesquisada, tira comerciais, valores implausíveis, os 1% extremos de R$/m² e repetidos: 40.244 → 22.022 |
| `scripts/03_baixar_fontes.py` | Baixa IPCA, INCC, Censos e FipeZap |
| `scripts/04_modelo_valor.py` | Modelo de estimativa do preço pedido, com validação cruzada em 5 partes |
| `scripts/05_tendencia_projecao.py` | Índices em base 100, teste das regras de projeção, projeção, construção e oferta relativa |
| `scripts/06_preparar_publicacao.py` | Gera a página publicada sem grupos com menos de 5 anúncios |

Ferramentas: Python e Pandas, Power BI (DAX, modelo semântico em formato .pbip), HTML e JavaScript com Leaflet, e agentes de IA (Claude) como copiloto. O roteiro usado para montar o Power BI está em `ROTEIRO_POWER_BI.md`.

## Dados publicados

A pasta `dados/publicar` traz só estatísticas agregadas (cidade, tipo, bairro com 10 ou mais imóveis), o modelo e as séries públicas tratadas. **A base anúncio por anúncio não é publicada.** Para reproduzir, rode os scripts 01 a 05 na ordem; o Power BI lê a base tratada local pelo parâmetro `PastaDados`.

## Limites

- Preço pedido, não preço de venda.
- A coleta trouxe de 66% a 100% do que o portal informava em cada cidade e tipo (`cobertura.csv`); Veranópolis ficou de fora por não ter anúncios no portal.
- Uma única data de coleta: não há série própria de preços, só a do FipeZap para Caxias.
- O modelo não considera idade, acabamento, vista nem andar.

## Autor

Fabian Aliatti Mayer. Estudo independente com dados públicos. Não usa dados internos de nenhuma empresa.

Outros estudos: [preço do gás de cozinha no RS](https://github.com/Fabi3105/preco-gas-p13-rs), [mercado de gás por município](https://github.com/Fabi3105/potencial-mercado-glp-rs) e [roteirizador de entregas](https://github.com/Fabi3105/roteirizador-entregas-glp).

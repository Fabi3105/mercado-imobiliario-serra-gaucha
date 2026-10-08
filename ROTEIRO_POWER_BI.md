# Roteiro do painel em Power BI: mercado imobiliário da Serra Gaúcha

Este roteiro é para você montar o painel com as próprias mãos no Power BI Desktop. Os dados já estão prontos; o trabalho aqui é modelar, escrever as medidas e desenhar as páginas. Tempo estimado: 6 a 10 horas, em 3 ou 4 sessões.

## 1. O que o painel responde

1. Quanto custa o m² anunciado em cada cidade, bairro e tipo de imóvel?
2. O preço dos imóveis subiu mais ou menos que a inflação (IPCA) e que o custo de construir (INCC)?
3. Para onde o preço tende a ir nos próximos 5 anos?
4. Que tipo de moradia cresceu mais e onde a oferta anunciada é grande ou pequena frente ao que já existe?
5. Quanto se pede, em média, por um imóvel com determinadas características?

## 2. Avisos que precisam aparecer no painel

- Os preços são **pedidos em anúncios**, coletados em 07/10/2026 no portal Chaves na Mão. Não são preços de venda; o valor fechado costuma ser menor.
- A coleta trouxe de 66% a 100% do que o portal informava ter em cada cidade e tipo (arquivo `cobertura.csv`).
- A série histórica só existe para **Caxias do Sul** (Índice FipeZap). Para as outras cidades a projeção usa a hipótese de que seguem o mesmo ritmo.
- A "oferta relativa" compara anúncios com domicílios ocupados do Censo 2022. Em **Gramado, Canela e Nova Petrópolis** ela fica inflada, porque muitos imóveis são de uso ocasional e o Censo não os conta como ocupados.
- Estudo independente. Não usa dados internos de nenhuma empresa.

## 3. Arquivos a importar

Todos em `dados\publicar`, exceto o primeiro. Separador ponto e vírgula, decimal com vírgula (o Power BI em português lê direto).

| Tabela no Power BI | Arquivo | Uma linha é |
|---|---|---|
| fAnuncios | `dados\anuncios_tratados.csv` | um imóvel anunciado (22.022 linhas) |
| dCidade | `domicilios_censo.csv` | uma cidade, com casas e apartamentos em 2010 e 2022 |
| fIndices | `indices_mensais.csv` | um mês, com IPCA, INCC e FipeZap em base 100 |
| fProjecao | `projecao_precos.csv` | cidade e ano projetado |
| fOferta | `oferta_relativa.csv` | cidade e tipo |
| fTipologia | `oferta_por_tipologia.csv` | cidade e tipologia |
| ModeloCoef | `modelo_coeficientes.csv` | tipo e variável do modelo |
| ModeloLocal | `modelo_efeito_local.csv` | tipo, cidade e bairro |
| ModeloErro | `modelo_erro.csv` | tipo, com o erro do modelo |
| Cobertura, Backtest | `cobertura.csv`, `backtest_projecao.csv` | apoio para a página de método |

Atenção: `anuncios_tratados.csv` não vai para o GitHub. Se publicar o `.pbix`, ele carrega essa base dentro; publique só imagens ou vídeo do painel, ou troque a fonte por `resumo_bairro.csv`.

## 4. Modelo de dados

- **Relacionamentos (1 para muitos, filtro único):** `dCidade[cidade]` → `fAnuncios[cidade]`, `fProjecao[cidade]`, `fOferta[cidade]`, `fTipologia[cidade]`.
- **Calendário:** crie `dCalendario = CALENDAR(DATE(2018,1,1), DATE(2026,12,1))`, marque como tabela de datas e relacione com `fIndices[data]`.
- **Tabelas do modelo (ModeloCoef, ModeloLocal, ModeloErro):** deixe **sem relacionamento**. Elas alimentam só a página de estimativa.
- **Coluna em dCidade:** `Perfil = IF(dCidade[cidade] IN {"Gramado","Canela","Nova Petrópolis"}, "Turística", "Vale dos Vinhedos e Caxias")`.
- **Ordenação:** em `fAnuncios`, ordene `faixa_preco` por uma coluna numérica auxiliar (1 a 7), senão as faixas saem em ordem alfabética.

## 5. Medidas DAX

Crie uma tabela vazia chamada `Medidas` e guarde tudo nela.

```dax
Imóveis = COUNTROWS(fAnuncios)

Preço m² mediano = MEDIAN(fAnuncios[preco_m2])

Preço m² P25 = PERCENTILE.INC(fAnuncios[preco_m2], 0.25)

Preço m² P75 = PERCENTILE.INC(fAnuncios[preco_m2], 0.75)

Preço mediano = MEDIAN(fAnuncios[preco_pedido])

Área mediana = MEDIAN(fAnuncios[area_m2])

% dos anúncios = DIVIDE([Imóveis], CALCULATE([Imóveis], ALLSELECTED(fAnuncios[tipologia])))

Amostra pequena = IF([Imóveis] < 30, "Amostra pequena (" & [Imóveis] & ")", BLANK())
```

Índices (use com `dCalendario[Date]` no eixo):

```dax
IPCA = MAX(fIndices[ipca])
INCC = MAX(fIndices[incc_di])
FipeZap Caxias = MAX(fIndices[fipezap_caxias])
FipeZap Porto Alegre = MAX(fIndices[fipezap_porto_alegre])
FipeZap Brasil = MAX(fIndices[fipezap_brasil])
Caxias real (IPCA) = MAX(fIndices[caxias_real_ipca])
Caxias sobre INCC = MAX(fIndices[caxias_sobre_incc])

Variação no período =
VAR fim = CALCULATE(MAX(fIndices[fipezap_caxias]), LASTDATE(dCalendario[Date]))
VAR ini = CALCULATE(MAX(fIndices[fipezap_caxias]), FIRSTDATE(dCalendario[Date]))
RETURN DIVIDE(fim, ini) - 1
```

Estimativa de valor. Antes, crie três parâmetros numéricos (Modelagem > Novo parâmetro > Intervalo numérico): `Área` (20 a 500, passo 5, padrão 80), `Vagas` (0 a 4, padrão 1), `Banheiros` (1 a 5, padrão 2). Crie também a tabela `Condominio = DATATABLE("Em condomínio", STRING, "valor", INTEGER, {{"Não", 0}, {"Sim", 1}})`.

```dax
Coef =
VAR cat = SELECTEDVALUE(ModeloErro[categoria], "Apartamento")
VAR v = SELECTEDVALUE(ModeloCoef[variavel])
RETURN CALCULATE(SUM(ModeloCoef[coeficiente]), ModeloCoef[categoria] = cat, ModeloCoef[variavel] = v)

Valor estimado =
VAR cat = SELECTEDVALUE(ModeloErro[categoria], "Apartamento")
VAR cid = SELECTEDVALUE(ModeloLocal[cidade], "(Serra inteira)")
VAR bai = SELECTEDVALUE(ModeloLocal[bairro], "(cidade inteira)")
VAR k   = CALCULATE(SUM(ModeloCoef[coeficiente]), ModeloCoef[categoria] = cat, ModeloCoef[variavel] = "constante")
VAR a   = CALCULATE(SUM(ModeloCoef[coeficiente]), ModeloCoef[categoria] = cat, ModeloCoef[variavel] = "ln_area")
VAR v   = CALCULATE(SUM(ModeloCoef[coeficiente]), ModeloCoef[categoria] = cat, ModeloCoef[variavel] = "vagas")
VAR b   = CALCULATE(SUM(ModeloCoef[coeficiente]), ModeloCoef[categoria] = cat, ModeloCoef[variavel] = "banheiros")
VAR c   = CALCULATE(SUM(ModeloCoef[coeficiente]), ModeloCoef[categoria] = cat, ModeloCoef[variavel] = "cond")
VAR ef  = CALCULATE(SUM(ModeloLocal[efeito_local]),
              ModeloLocal[categoria] = cat, ModeloLocal[cidade] = cid, ModeloLocal[bairro] = bai)
VAR cond = SELECTEDVALUE(Condominio[valor], 0)
RETURN
    EXP(k + a * LN([Valor Área]) + COALESCE(v, 0) * [Valor Vagas] + COALESCE(b, 0) * [Valor Banheiros] + c * cond + ef)

Valor estimado mínimo = [Valor estimado] * CALCULATE(MAX(ModeloErro[faixa80_inferior]), ModeloErro[categoria] = SELECTEDVALUE(ModeloErro[categoria], "Apartamento"))

Valor estimado máximo = [Valor estimado] * CALCULATE(MAX(ModeloErro[faixa80_superior]), ModeloErro[categoria] = SELECTEDVALUE(ModeloErro[categoria], "Apartamento"))

Estimado por m² = DIVIDE([Valor estimado], [Valor Área])
```

Os segmentadores dessa página são: `ModeloErro[categoria]`, `ModeloLocal[cidade]` e `ModeloLocal[bairro]` (seleção única nos três), `Condominio[Em condomínio]` e os três parâmetros. Para o bairro só mostrar os da cidade e do tipo escolhidos, aplique no segmentador de bairro um filtro visual com a medida:

```dax
Bairro do tipo escolhido = IF(MAX(ModeloLocal[categoria]) = SELECTEDVALUE(ModeloErro[categoria], "Apartamento"), 1)
```

### Conferência das medidas

Se as medidas estiverem certas, você deve ver:

- `Imóveis` sem filtro: **22.022**.
- `Preço m² mediano`, apartamento: Caxias do Sul **6.127**, Garibaldi **7.112**, Bento Gonçalves **8.654**, Gramado **16.134**.
- `Valor estimado` para apartamento, 80 m², 1 vaga, 2 banheiros, fora de condomínio, bairro "(cidade inteira)":

| Cidade | Valor estimado |
|---|---|
| Caxias do Sul | R$ 490.256 |
| Farroupilha | R$ 527.011 |
| Flores da Cunha | R$ 562.111 |
| Carlos Barbosa | R$ 565.220 |
| Garibaldi | R$ 583.190 |
| Bento Gonçalves | R$ 659.196 |
| Nova Petrópolis | R$ 660.604 |
| Canela | R$ 972.885 |
| Gramado | R$ 1.271.863 |
| (Serra inteira) | R$ 688.606 |

Diferença de poucos reais é arredondamento dos coeficientes. Diferença grande indica filtro errado em `ModeloLocal`.

## 6. Páginas

### Página 1: Visão geral
- **Mensagem:** o m² anunciado vai de cerca de R$ 6 mil em Caxias a R$ 16 mil em Gramado.
- Cartões: `Imóveis`, `Preço m² mediano`, `Preço mediano`, `Área mediana`.
- Barras horizontais: `Preço m² mediano` por cidade, ordenado; segmentador de `categoria`.
- Matriz: cidade nas linhas, categoria nas colunas, `Preço m² mediano` e `Imóveis`.
- Tabela dos 15 bairros mais caros e mais baratos (filtro `Imóveis >= 30`).
- Rodapé com o aviso de preço pedido e a data da coleta.

### Página 2: Preço, inflação e custo de construir
- **Mensagem:** de jan/2018 a ago/2026 o imóvel em Caxias subiu 63,6%, acima do IPCA (54,8%) e abaixo do INCC (80,0%). Em termos reais, ganhou 5,7%; frente ao custo de construir, perdeu 9,1%.
- Linhas: `FipeZap Caxias`, `IPCA`, `INCC` (base 100 em jan/2018).
- Segunda linha: `Caxias real (IPCA)` e `Caxias sobre INCC`, com linha de referência em 100.
- Barras por ano: variação anual de cada um. Destaque: o imóvel perdeu para a inflação até 2021 e ganhou de 2022 em diante (em 2024 subiu 10,7% contra 4,8% do IPCA).
- Comparação: `FipeZap Porto Alegre` (+25,9%) e `FipeZap Brasil` (+44,3%). Caxias valorizou bem mais que a capital.

### Página 3: Projeção de 5 anos
- **Mensagem:** a regra que menos errou no teste com o passado foi "o preço acompanha a inflação". Ela errou 8,1% em média em 3 anos, quase sempre para baixo: em mais de 9 de cada 10 testes o preço real ficou acima do previsto.
- Linha com faixa: `preco_m2_real` (centro), `preco_m2_real_min` e `preco_m2_real_max` por ano, de `fProjecao`; segmentador de cidade.
- Cartão: preço nominal em 2031 com a hipótese de IPCA de 5,22% ao ano (a média de 2018 a 2026). Em Caxias: de R$ 6.127 para cerca de R$ 7.900.
- Tabela `Backtest` com as quatro regras testadas.
- Texto fixo: "Projeção em reais de hoje. Fora de Caxias, supõe o mesmo ritmo de Caxias. O teste cobre um único ciclo (2021 a 2026)."

### Página 4: Construção e oferta
- **Mensagem:** entre 2010 e 2022 o número de apartamentos cresceu de 6% a 8% ao ano na maioria das cidades, e o de casas menos de 2,6%. Em Bento Gonçalves os apartamentos passaram de 7 mil para 18,4 mil.
- Barras agrupadas: `casas_cresc_aa_pct` e `apartamentos_cresc_aa_pct` por cidade (de `dCidade`).
- Colunas: `apartamentos_novos_por_ano` por cidade (Caxias 2.720, Bento 950, Farroupilha 314, Garibaldi 198).
- Cartão ou tabela: `apartamentos_2031_se_ritmo_mantido`, com o rótulo "extrapolação simples de dois censos".
- Barras: `anuncios_por_mil_domicilios` por cidade e tipo (de `fOferta`), com cor pela coluna `leitura` e as cidades turísticas marcadas.
- Barras 100% empilhadas: `pct_da_cidade` por tipologia (de `fTipologia`). Mostra, por exemplo, que apartamento de 1 quarto é 16% a 17% dos anúncios em Gramado e Canela e 3% em Caxias e Garibaldi.
- Texto fixo: "Oferta anunciada, não demanda. Sem dados de vendas, não dá para afirmar falta ou excesso; o indicador mostra onde há muito ou pouco imóvel anunciado frente ao que já existe."

### Página 5: Estime o valor
- Segmentadores à esquerda: tipo, cidade, bairro, condomínio, área, vagas, banheiros.
- Cartões grandes: `Valor estimado`, `Valor estimado mínimo` a `Valor estimado máximo`, `Estimado por m²`.
- Barras: `Valor estimado` por cidade para as mesmas características (use `ModeloLocal[cidade]` no eixo com o bairro fixo em "(cidade inteira)").
- Cartão com o erro do modelo para o tipo escolhido (`erro_mediano_pct` e `dentro_de_20_pct`).
- Texto fixo: "Estimativa do preço pedido. Não considera idade, acabamento, vista nem andar. Em 8 de cada 10 anúncios parecidos o preço ficou dentro da faixa."

### Página 6: Método e limites
- Funil da limpeza (`tratamento_log.csv`): de 40.244 anúncios para 22.022 imóveis.
- Tabela `Cobertura`.
- Erro do modelo por tipo (`ModeloErro`): apartamento 17%, casa 23%, terreno 27%.
- Fontes: Chaves na Mão (anúncios), Fipe (FipeZap), Banco Central (IPCA e INCC-DI), IBGE (Censos 2010 e 2022).

## 7. Acabamento

- Uma cor por série e a mesma em todas as páginas (por exemplo: imóvel em azul-escuro, IPCA em cinza, INCC em laranja).
- Título de cada visual como frase com a conclusão, não com o nome do campo.
- Formato: R$ sem centavos; índices com uma casa; percentuais com uma casa.
- Tooltips com `Imóveis` em todo visual de preço, para o leitor ver o tamanho da amostra.
- Teste final: selecione Flores da Cunha e casa. Deve aparecer o aviso de amostra pequena (14 imóveis).

## 8. Ordem sugerida de trabalho

1. Importar as tabelas e montar os relacionamentos (1 h).
2. Medidas básicas e página 1; conferir com os números da seção 5 (1 a 2 h).
3. Páginas 2 e 3 (2 h).
4. Página 4 (1 a 2 h).
5. Página 5, com os parâmetros e a conferência da tabela de estimativas (2 h).
6. Página 6 e acabamento (1 h).

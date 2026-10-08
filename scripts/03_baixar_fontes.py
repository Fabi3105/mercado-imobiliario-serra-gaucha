# -*- coding: utf-8 -*-
"""
Baixa as fontes públicas do estudo para dados/fontes (só biblioteca padrão do Python):
- Banco Central (SGS): IPCA mensal (série 433) e INCC-DI mensal (série 192)
- IBGE (SIDRA): domicílios por tipo no Censo 2010 (tabela 3152) e no Censo 2022 (tabela 6326),
  domicílios ocupados e moradores em 2022 (tabela 4712), municípios do RS
- Fipe: planilha de séries históricas do Índice FipeZap (venda residencial; inclui Caxias do Sul)

Uso: python scripts/03_baixar_fontes.py
"""
import os, sys, time, urllib.request

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados", "fontes")
os.makedirs(PASTA, exist_ok=True)
FONTES = [
    ("bcb_433_ipca.json", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2008&dataFinal=31/12/2026"),
    ("bcb_192_incc_di.json", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.192/dados?formato=json&dataInicial=01/01/2008&dataFinal=31/12/2026"),
    ("sidra_3152_domicilios_tipo_2010.json", "https://apisidra.ibge.gov.br/values/t/3152/n6/in%20n3%2043/v/96/p/all/c125/all/c68/9902"),
    ("sidra_6326_domicilios_tipo_2022.json", "https://apisidra.ibge.gov.br/values/t/6326/n6/in%20n3%2043/v/381/p/all/c125/all"),
    ("sidra_4712_domicilios_moradores_2022.json", "https://apisidra.ibge.gov.br/values/t/4712/n6/in%20n3%2043/v/all/p/all"),
    ("fipezap_series_historicas.xlsx", "https://downloads.fipe.org.br/indices/fipezap/fipezap-serieshistoricas.xlsx"),
]
falhas = 0
for nome, url in FONTES:
    destino = os.path.join(PASTA, nome)
    for tentativa in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (estudo-imoveis-serra)"})
            with urllib.request.urlopen(req, timeout=120) as r:
                dados = r.read()
            if len(dados) < 200:
                raise RuntimeError("resposta vazia")
            with open(destino, "wb") as f:
                f.write(dados)
            print(f"ok     {nome}  ({len(dados) // 1024} KB)")
            break
        except Exception as e:
            if tentativa == 2:
                falhas += 1
                print(f"FALHA  {nome}: {e}")
            else:
                time.sleep(5)
print("\nPronto." if not falhas else f"\nTerminou com {falhas} falha(s). Copie esta tela para o Claude.")

# -*- coding: utf-8 -*-
"""
Trata a base bruta de anúncios e gera:
- dados/anuncios_tratados.csv        : um imóvel por linha, limpo (fica só no computador; não publicar)
- dados/publicar/resumo_cidade_tipo.csv, resumo_bairro.csv, cobertura.csv, tratamento_log.csv : agregados publicáveis

Regras (todas registradas em tratamento_log.csv):
1. Mantém só anúncios cuja cidade é a cidade pesquisada (o portal devolve cidades de nome parecido).
2. Mantém apartamento, casa e terreno residenciais; tira os comerciais.
3. Tira anúncios sem área ou com preço/área fora de limites plausíveis.
4. Tira os 1% mais baratos e os 1% mais caros por m² em cada cidade e tipo.
5. Junta anúncios repetidos (mesma cidade, bairro, tipo, preço, área e quartos) em uma linha.

Uso: python scripts/02_tratar_anuncios.py
"""
import os, glob
import pandas as pd, numpy as np

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DADOS = os.path.join(RAIZ, "dados"); PUB = os.path.join(DADOS, "publicar"); os.makedirs(PUB, exist_ok=True)
LIMITES = {  # categoria: (preço mínimo, área mínima, área máxima, R$/m² mínimo, R$/m² máximo)
    "Apartamento": (60000, 20, 600, 1500, 45000),
    "Casa": (60000, 30, 1500, 800, 45000),
    "Terreno": (20000, 100, 20000, 30, 12000),
}
CATEGORIA = {"Apartamento": "Apartamento", "Casa / Sobrado": "Casa", "Casa / Sobrado em Condomínio": "Casa",
             "Terreno / Lote": "Terreno", "Terreno em Condomínio": "Terreno"}

log = []
def passo(nome, df):
    log.append({"etapa": nome, "linhas": len(df)}); print(f"{nome}: {len(df)}"); return df

b = pd.read_csv(os.path.join(DADOS, "anuncios_brutos.csv"), sep=";", encoding="utf-8-sig", dtype={"id": str})
passo("0. base bruta", b)
bruto_por = b.groupby(["cidade_busca", "tipo_busca"]).size().rename("coletados")

d = passo("1. cidade igual à pesquisada", b[b["cidade"] == b["cidade_busca"]].copy())
d["categoria"] = d["tipo"].map(CATEGORIA)
d["em_condominio"] = d["tipo"].str.contains("Condomínio", na=False)
d = passo("2. só residenciais (apto, casa, terreno)", d[d["categoria"].notna()].copy())
for c in ["preco_pedido", "area_m2", "quartos", "banheiros", "vagas"]:
    d[c] = pd.to_numeric(d[c], errors="coerce")
d = passo("3a. com preço e área", d[(d["preco_pedido"] > 0) & (d["area_m2"] > 0)].copy())
d["preco_m2"] = d["preco_pedido"] / d["area_m2"]
lim = d["categoria"].map(LIMITES)
ok = [(p >= l[0]) and (l[1] <= a <= l[2]) and (l[3] <= m <= l[4]) for p, a, m, l in zip(d["preco_pedido"], d["area_m2"], d["preco_m2"], lim)]
d = passo("3b. dentro dos limites plausíveis", d[ok].copy())
g = d.groupby(["cidade", "categoria"])["preco_m2"]
d = passo("4. sem os 1% extremos de R$/m² por cidade e tipo", d[(d["preco_m2"] >= g.transform(lambda s: s.quantile(0.01))) & (d["preco_m2"] <= g.transform(lambda s: s.quantile(0.99)))].copy())

d["bairro"] = d["bairro"].fillna("Não informado").str.strip()
terreno = d["categoria"] == "Terreno"
for c, mx in [("quartos", 6), ("banheiros", 8), ("vagas", 6)]:
    d.loc[terreno | (d[c] > mx) | (d[c] < 0), c] = np.nan
d.loc[~terreno & (d["quartos"] == 0), "quartos"] = np.nan
chave = ["cidade", "bairro", "categoria", "preco_pedido", "area_m2", "quartos"]
d["n_anuncios"] = d.groupby(chave, dropna=False)["id"].transform("size")
d = passo("5. sem anúncios repetidos", d.drop_duplicates(chave).copy())

d["faixa_preco"] = pd.cut(d["preco_pedido"], [0, 300000, 500000, 750000, 1000000, 1500000, 2500000, 1e12],
                          labels=["até 300 mil", "300 a 500 mil", "500 a 750 mil", "750 mil a 1 mi", "1 a 1,5 mi", "1,5 a 2,5 mi", "acima de 2,5 mi"])
rotulo_q = d["quartos"].map({1: "1 quarto", 2: "2 quartos", 3: "3 quartos"})
rotulo_q = rotulo_q.where(rotulo_q.notna(), np.where(d["quartos"] >= 4, "4+ quartos", "quartos não informados"))
d["tipologia"] = np.where(d["categoria"] == "Terreno", "Terreno", d["categoria"] + " " + rotulo_q)
col = ["id", "data_coleta", "cidade", "bairro", "categoria", "em_condominio", "tipologia", "preco_pedido", "area_m2",
       "preco_m2", "quartos", "banheiros", "vagas", "faixa_preco", "n_anuncios"]
d["preco_m2"] = d["preco_m2"].round(0)
d[col].to_csv(os.path.join(DADOS, "anuncios_tratados.csv"), sep=";", decimal=",", index=False, encoding="utf-8-sig")

def resumo(df, por):
    r = df.groupby(por, observed=True).agg(imoveis=("id", "size"), preco_m2_mediana=("preco_m2", "median"),
            preco_m2_p25=("preco_m2", lambda s: s.quantile(.25)), preco_m2_p75=("preco_m2", lambda s: s.quantile(.75)),
            preco_mediano=("preco_pedido", "median"), area_mediana=("area_m2", "median")).reset_index()
    return r.round(0)
rc = resumo(d, ["cidade", "categoria"]); rc.to_csv(os.path.join(PUB, "resumo_cidade_tipo.csv"), sep=";", decimal=",", index=False, encoding="utf-8-sig")
rt = resumo(d, ["cidade", "tipologia"]); rt = rt[rt["imoveis"] >= 5]; rt.to_csv(os.path.join(PUB, "resumo_cidade_tipologia.csv"), sep=";", decimal=",", index=False, encoding="utf-8-sig")
rb = resumo(d, ["cidade", "bairro", "categoria"]); rb = rb[rb["imoveis"] >= 10]
rb.to_csv(os.path.join(PUB, "resumo_bairro.csv"), sep=";", decimal=",", index=False, encoding="utf-8-sig")

# cobertura: anunciado pelo portal x coletado x aproveitado
tot = []
arqs = sorted(glob.glob(os.path.join(DADOS, "coleta_resumo_2*.csv")))
if arqs:
    r = pd.read_csv(arqs[-1], sep=";", encoding="utf-8-sig")
    tot = r[r["filtro"] == "TOTAL ANUNCIADO"][["cidade", "tipo", "anunciados"]]
    tot = tot.merge(bruto_por.reset_index().rename(columns={"cidade_busca": "cidade", "tipo_busca": "tipo"}), how="left")
    da_cidade = b[b["cidade"] == b["cidade_busca"]].groupby(["cidade_busca", "tipo_busca"]).size().rename("da_propria_cidade").reset_index().rename(columns={"cidade_busca": "cidade", "tipo_busca": "tipo"})
    tot = tot.merge(da_cidade, how="left").fillna(0)
    final = d.assign(tipo=d["categoria"].str.lower()).groupby(["cidade", "tipo"]).size().rename("na_base_tratada").reset_index()
    tot = tot.merge(final, how="left").fillna(0)
    tot.to_csv(os.path.join(PUB, "cobertura.csv"), sep=";", index=False, encoding="utf-8-sig")
    print("\nCobertura:\n", tot.to_string(index=False))
pd.DataFrame(log).to_csv(os.path.join(PUB, "tratamento_log.csv"), sep=";", index=False, encoding="utf-8-sig")
print("\nResumo por cidade e tipo:\n", rc.to_string(index=False))
print("\nPreenchimento na base tratada (apto e casa): quartos %.0f%%, vagas %.0f%%, banheiros %.0f%%" % tuple(
    100 * d.loc[~(d["categoria"] == "Terreno"), c].notna().mean() for c in ["quartos", "vagas", "banheiros"]))

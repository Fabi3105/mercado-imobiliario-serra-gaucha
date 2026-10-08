# -*- coding: utf-8 -*-
"""
Modelo de estimativa do preço pedido a partir das características do imóvel (regressão hedônica).

ln(preço) = constante + a*ln(área) + b*vagas + c*banheiros + d*em_condomínio + efeito do local (cidade e bairro)

- Um modelo por categoria (apartamento, casa, terreno). Terreno usa só área, condomínio e local.
- Bairros com menos de 15 imóveis entram como "Outros bairros" da cidade.
- O número de quartos fica de fora: com a área na conta, ele não melhora a estimativa (ver teste impresso).
- Erro medido por validação cruzada (5 partes): estima cada imóvel com um modelo que não o viu.

Saídas em dados/publicar (não contêm anúncios individuais):
  modelo_coeficientes.csv, modelo_efeito_local.csv, modelo_erro.csv
Uso: python scripts/04_modelo_valor.py
"""
import os
import numpy as np, pandas as pd

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PUB = os.path.join(RAIZ, "dados", "publicar")
d = pd.read_csv(os.path.join(RAIZ, "dados", "anuncios_tratados.csv"), sep=";", decimal=",", encoding="utf-8-sig")
MIN_BAIRRO = 15
coefs, locais, erros = [], [], []

def matriz(x, feats, niveis):
    X = np.column_stack([np.ones(len(x))] + [x[f].values.astype(float) for f in feats] +
                        [(x["local"].values == n).astype(float) for n in niveis[1:]])
    return X

for cat in ["Apartamento", "Casa", "Terreno"]:
    x = d[d["categoria"] == cat].copy()
    x["ln_preco"] = np.log(x["preco_pedido"]); x["ln_area"] = np.log(x["area_m2"]); x["cond"] = x["em_condominio"].astype(float)
    feats = ["ln_area", "cond"]
    if cat != "Terreno":
        for c in ["vagas", "banheiros", "quartos"]:
            x[c] = x[c].fillna(x[c].median())
        feats = ["ln_area", "vagas", "banheiros", "cond"]
    n_bairro = x.groupby(["cidade", "bairro"])["id"].transform("size")
    x["bairro_modelo"] = np.where(n_bairro >= MIN_BAIRRO, x["bairro"], "Outros bairros")
    x["local"] = x["cidade"] + " | " + x["bairro_modelo"]
    niveis = sorted(x["local"].unique())

    def ajusta(tr, fs):
        return np.linalg.lstsq(matriz(tr, fs, niveis), tr["ln_preco"].values, rcond=None)[0]

    # validação cruzada
    rng = np.random.default_rng(7); parte = rng.integers(0, 5, len(x))
    def cv(fs):
        res = np.zeros(len(x))
        for k in range(5):
            b = ajusta(x[parte != k], fs)
            res[parte == k] = x["ln_preco"].values[parte == k] - matriz(x[parte == k], fs, niveis) @ b
        return res
    res = cv(feats)
    erro_pct = np.abs(np.exp(-res) - 1)          # |estimado/real - 1|
    r2 = 1 - (res ** 2).sum() / ((x["ln_preco"] - x["ln_preco"].mean()) ** 2).sum()
    linha = {"categoria": cat, "imoveis": len(x), "r2_validacao": round(r2, 3),
             "erro_mediano_pct": round(100 * np.median(erro_pct), 1),
             "dentro_de_10_pct": round(100 * (erro_pct <= .10).mean(), 1), "dentro_de_20_pct": round(100 * (erro_pct <= .20).mean(), 1),
             "faixa80_inferior": round(float(np.exp(np.quantile(res, .10))), 3), "faixa80_superior": round(float(np.exp(np.quantile(res, .90))), 3)}
    if cat != "Terreno":
        res_q = cv(feats + ["quartos"]); linha["erro_mediano_com_quartos_pct"] = round(100 * np.median(np.abs(np.exp(-res_q) - 1)), 1)
    erros.append(linha); print(linha)

    b = ajusta(x, feats)                           # modelo final com toda a base
    coefs.append({"categoria": cat, "variavel": "constante", "coeficiente": b[0]})
    for f, v in zip(feats, b[1:1 + len(feats)]):
        coefs.append({"categoria": cat, "variavel": f, "coeficiente": v})
    efeito = dict(zip(niveis, np.concatenate([[0.0], b[1 + len(feats):]])))
    cont = x.groupby("local").size()
    for loc in niveis:
        cid, bai = loc.split(" | ")
        locais.append({"categoria": cat, "cidade": cid, "bairro": bai, "efeito_local": efeito[loc], "imoveis": int(cont[loc])})
    # linhas de média: cidade inteira e Serra inteira (média dos efeitos ponderada pelo nº de imóveis)
    x["ef"] = x["local"].map(efeito)
    for cid, g in x.groupby("cidade"):
        locais.append({"categoria": cat, "cidade": cid, "bairro": "(cidade inteira)", "efeito_local": g["ef"].mean(), "imoveis": len(g)})
    locais.append({"categoria": cat, "cidade": "(Serra inteira)", "bairro": "(cidade inteira)", "efeito_local": x["ef"].mean(), "imoveis": len(x)})

L = pd.DataFrame(locais); L["local_chave"] = L["categoria"] + " | " + L["cidade"] + " | " + L["bairro"]
fmt = dict(sep=";", decimal=",", index=False, encoding="utf-8-sig")
pd.DataFrame(coefs).round(5).to_csv(os.path.join(PUB, "modelo_coeficientes.csv"), **fmt)
L.round(5).to_csv(os.path.join(PUB, "modelo_efeito_local.csv"), **fmt)
pd.DataFrame(erros).to_csv(os.path.join(PUB, "modelo_erro.csv"), **fmt)
C = pd.DataFrame(coefs).pivot(index="variavel", columns="categoria", values="coeficiente").round(4)
print("\nCoeficientes:\n", C.to_string())

# exemplo de conferência: apartamento de 80 m², 1 vaga, 2 banheiros
def estima(cat, cidade, bairro, area, vagas=1, banh=2, cond=0):
    c = {r["variavel"]: r["coeficiente"] for r in coefs if r["categoria"] == cat}
    e = L[(L.categoria == cat) & (L.cidade == cidade) & (L.bairro == bairro)]["efeito_local"].iloc[0]
    return np.exp(c["constante"] + c["ln_area"] * np.log(area) + c.get("vagas", 0) * vagas + c.get("banheiros", 0) * banh + c["cond"] * cond + e)
print("\nExemplo, apartamento 80 m², 1 vaga, 2 banheiros (preço pedido estimado):")
for cid in sorted(d["cidade"].unique()) + ["(Serra inteira)"]:
    print(f"  {cid:18s} R$ {estima('Apartamento', cid, '(cidade inteira)', 80):,.0f}".replace(",", "."))

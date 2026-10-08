# -*- coding: utf-8 -*-
"""
Tendência, projeção e oferta relativa, a partir das fontes públicas em dados/fontes e da base tratada.

Saídas em dados/publicar:
  indices_mensais.csv      IPCA, INCC-DI e FipeZap (Caxias do Sul, Porto Alegre, Brasil) em número-índice, base jan/2018 = 100
  backtest_projecao.csv    teste das regras de projeção contra o passado
  projecao_precos.csv      projeção anual do preço por m² até 5 anos à frente (valores reais e nominais, com faixa)
  domicilios_censo.csv     casas e apartamentos em 2010 e 2022 (IBGE) e extrapolação
  oferta_relativa.csv      anúncios por mil domicílios existentes, por cidade e tipo
Uso: python scripts/05_tendencia_projecao.py
"""
import os, json
import numpy as np, pandas as pd, openpyxl

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
F = os.path.join(RAIZ, "dados", "fontes"); PUB = os.path.join(RAIZ, "dados", "publicar")
fmt = dict(sep=";", decimal=",", index=False, encoding="utf-8-sig")
CIDADES = ["Bento Gonçalves", "Canela", "Carlos Barbosa", "Caxias do Sul", "Farroupilha", "Flores da Cunha",
           "Garibaldi", "Gramado", "Nova Petrópolis"]

# ---------- 1. índices mensais ----------
def bcb(arq):
    a = pd.DataFrame(json.load(open(os.path.join(F, arq), encoding="utf-8")))
    return pd.Series(a["valor"].astype(float).values, index=pd.to_datetime(a["data"], format="%d/%m/%Y"))
def fipezap(aba):
    ws = openpyxl.load_workbook(os.path.join(F, "fipezap_series_historicas.xlsx"), read_only=True, data_only=True)[aba]
    linhas = [(r[1], r[2], r[17]) for r in ws.iter_rows(values_only=True) if hasattr(r[1], "year") and isinstance(r[2], (int, float))]
    t = pd.DataFrame(linhas, columns=["data", "indice", "preco_m2"]).set_index("data")
    t["preco_m2"] = pd.to_numeric(t["preco_m2"], errors="coerce")
    return t
ipca, incc = bcb("bcb_433_ipca.json"), bcb("bcb_192_incc_di.json")
cx, poa, br = fipezap("Caxias do Sul"), fipezap("Porto Alegre"), fipezap("Índice FipeZAP")
ini = cx.index.min(); fim = min(cx.index.max(), ipca.index.max(), incc.index.max())
m = pd.DataFrame(index=pd.date_range(ini, fim, freq="MS"))
for nome, s in [("ipca", ipca), ("incc_di", incc)]:
    v = s.reindex(m.index); v.iloc[0] = 0.0              # o mês-base vale 100
    m[nome] = 100 * (1 + v / 100).cumprod()
for nome, t in [("fipezap_caxias", cx), ("fipezap_porto_alegre", poa), ("fipezap_brasil", br)]:
    s = t["indice"].reindex(m.index); m[nome] = 100 * s / s.iloc[0]
m["caxias_preco_m2"] = cx["preco_m2"].reindex(m.index)
m["caxias_real_ipca"] = 100 * m["fipezap_caxias"] / m["ipca"]        # acima de 100 = subiu mais que a inflação
m["caxias_sobre_incc"] = 100 * m["fipezap_caxias"] / m["incc_di"]    # abaixo de 100 = subiu menos que o custo de construir
m.round(3).rename_axis("data").reset_index().to_csv(os.path.join(PUB, "indices_mensais.csv"), **fmt)
u = m.iloc[-1]; anos = (len(m) - 1) / 12
print(f"Período: {ini:%m/%Y} a {fim:%m/%Y} ({anos:.1f} anos)")
for c in ["ipca", "incc_di", "fipezap_caxias", "fipezap_porto_alegre", "fipezap_brasil"]:
    print(f"  {c:22s} acumulado {u[c]-100:6.1f}%   ao ano {100*((u[c]/100)**(1/anos)-1):5.2f}%")
print(f"  Caxias em termos reais (IPCA): {u['caxias_real_ipca']-100:+.1f}%   frente ao INCC: {u['caxias_sobre_incc']-100:+.1f}%")
print(f"  Caxias R$/m²: {m['caxias_preco_m2'].iloc[0]:.0f} -> {u['caxias_preco_m2']:.0f}")
for a in sorted(set(m.index.year)):
    x = m[m.index.year == a]
    if len(x) == 12 or a == fim.year:
        ant = m[m.index.year == a - 1]
        if len(ant):
            b = ant.iloc[-1]; print(f"   {a}{'*' if len(x)<12 else ' '} Caxias {100*(x['fipezap_caxias'].iloc[-1]/b['fipezap_caxias']-1):5.1f}%  IPCA {100*(x['ipca'].iloc[-1]/b['ipca']-1):5.1f}%  INCC {100*(x['incc_di'].iloc[-1]/b['incc_di']-1):5.1f}%")

# ---------- 2. regra de projeção, testada contra o passado ----------
real = np.log(m["caxias_real_ipca"])                     # log do índice real
REGRAS = {"real constante (acompanha o IPCA)": lambda h: 0.0,
          "ritmo real dos últimos 12 meses": lambda h: h.iloc[-1] - h.iloc[-13],
          "ritmo real dos últimos 36 meses": lambda h: (h.iloc[-1] - h.iloc[-37]) / 3,
          "ritmo real desde 2018": lambda h: (h.iloc[-1] - h.iloc[0]) / ((len(h) - 1) / 12)}
bt = []
for hz in (24, 36):
    for nome, regra in REGRAS.items():
        erros = []
        for o in range(36, len(real) - hz):              # origem precisa de 36 meses de história
            h = real.iloc[:o + 1]; prev = h.iloc[-1] + regra(h) * hz / 12
            erros.append(np.exp(prev - real.iloc[o + hz]) - 1)
        e = np.array(erros)
        bt.append({"horizonte_meses": hz, "regra": nome, "testes": len(e), "erro_medio_abs_pct": round(100 * np.abs(e).mean(), 1),
                   "vies_pct": round(100 * e.mean(), 1), "erro_p10_pct": round(100 * np.quantile(e, .1), 1), "erro_p90_pct": round(100 * np.quantile(e, .9), 1)})
B = pd.DataFrame(bt); B.to_csv(os.path.join(PUB, "backtest_projecao.csv"), **fmt); print("\n", B.to_string(index=False))
melhor = B[B.horizonte_meses == 36].sort_values("erro_medio_abs_pct").iloc[0]
print("\nRegra escolhida:", melhor["regra"], "| erro médio em 36 meses:", melhor["erro_medio_abs_pct"], "%")
g_real = REGRAS[melhor["regra"]](real)                   # crescimento real anual (log)
erro36 = melhor["erro_medio_abs_pct"] / 100
alta36 = 1 / (1 + melhor["erro_p10_pct"] / 100) - 1     # no teste, o preço real ficou até este tanto ACIMA do previsto
ipca_hip = (u["ipca"] / 100) ** (1 / anos) - 1           # hipótese: IPCA médio do período observado
trat = pd.read_csv(os.path.join(RAIZ, "dados", "anuncios_tratados.csv"), sep=";", decimal=",", encoding="utf-8-sig")
base = trat[trat.categoria == "Apartamento"].groupby("cidade")["preco_m2"].median()
proj = []
for cid in CIDADES:
    for k in range(0, 6):
        fr = float(np.exp(g_real * k)); esc = min(k, 3) / 3 * (1 if k <= 3 else (k / 3) ** 0.5)   # a faixa abre com o prazo
        proj.append({"cidade": cid, "ano": fim.year + k, "anos_a_frente": k, "tipo": "Apartamento",
                     "preco_m2_real": round(base[cid] * fr), "preco_m2_real_min": round(base[cid] * fr * (1 - erro36 * esc)), "preco_m2_real_max": round(base[cid] * fr * (1 + alta36 * esc)),
                     "preco_m2_nominal": round(base[cid] * fr * (1 + ipca_hip) ** k),
                     "base": "histórico próprio (FipeZap)" if cid == "Caxias do Sul" else "hipótese: mesmo ritmo de Caxias do Sul"})
pd.DataFrame(proj).to_csv(os.path.join(PUB, "projecao_precos.csv"), **fmt)
print(f"Crescimento real projetado: {100*(np.exp(g_real)-1):.2f}% ao ano | hipótese de IPCA: {100*ipca_hip:.2f}% ao ano | em 5 anos: real {100*(np.exp(5*g_real)-1):+.1f}%, nominal {100*(np.exp(5*g_real)*(1+ipca_hip)**5-1):+.1f}%")

# ---------- 3. domicílios nos censos (construção acumulada) ----------
def sidra(arq, ano):
    a = pd.DataFrame(json.load(open(os.path.join(F, arq), encoding="utf-8"))[1:])
    a["cidade"] = a["D1N"].str.replace(" - RS", "", regex=False); a["v"] = pd.to_numeric(a["V"], errors="coerce")
    a = a[a["cidade"].isin(CIDADES)]
    t = a.pivot_table(index="cidade", columns="D4N", values="v", aggfunc="sum")
    r = pd.DataFrame({"casas": t.get("Casa", 0).fillna(0) + t.get("Casa de vila ou em condomínio", 0).fillna(0), "apartamentos": t["Apartamento"], "total": t["Total"]})
    return r.add_suffix(f"_{ano}")
c = sidra("sidra_3152_domicilios_tipo_2010.json", 2010).join(sidra("sidra_6326_domicilios_tipo_2022.json", 2022))
mor = pd.DataFrame(json.load(open(os.path.join(F, "sidra_4712_domicilios_moradores_2022.json"), encoding="utf-8"))[1:])
mor["cidade"] = mor["D1N"].str.replace(" - RS", "", regex=False)
c["moradores_por_domicilio_2022"] = pd.to_numeric(mor[mor["D2C"] == "5930"].set_index("cidade")["V"], errors="coerce").reindex(c.index)
for t in ["casas", "apartamentos", "total"]:
    c[f"{t}_novos_por_ano"] = ((c[f"{t}_2022"] - c[f"{t}_2010"]) / 12).round(0)
    c[f"{t}_cresc_aa_pct"] = (100 * ((c[f"{t}_2022"] / c[f"{t}_2010"]) ** (1 / 12) - 1)).round(2)
    c[f"{t}_2031_se_ritmo_mantido"] = (c[f"{t}_2022"] * (c[f"{t}_2022"] / c[f"{t}_2010"]) ** (9 / 12)).round(0)
c["pct_apartamentos_2010"] = (100 * c["apartamentos_2010"] / c["total_2010"]).round(1)
c["pct_apartamentos_2022"] = (100 * c["apartamentos_2022"] / c["total_2022"]).round(1)
c.reset_index().to_csv(os.path.join(PUB, "domicilios_censo.csv"), **fmt)
print("\n", c[["casas_2010", "casas_2022", "apartamentos_2010", "apartamentos_2022", "casas_cresc_aa_pct", "apartamentos_cresc_aa_pct", "apartamentos_novos_por_ano", "pct_apartamentos_2022", "moradores_por_domicilio_2022"]].to_string())

# ---------- 4. oferta relativa: anúncios por mil domicílios existentes ----------
of = trat[trat.categoria != "Terreno"].groupby(["cidade", "categoria"]).agg(anuncios=("id", "size"), preco_m2_mediana=("preco_m2", "median")).reset_index()
est = pd.concat([c["casas_2022"].rename("estoque").reset_index().assign(categoria="Casa"), c["apartamentos_2022"].rename("estoque").reset_index().assign(categoria="Apartamento")])
of = of.merge(est, on=["cidade", "categoria"]); of["anuncios_por_mil_domicilios"] = (1000 * of["anuncios"] / of["estoque"]).round(1)
ref = (1000 * of.groupby("categoria")["anuncios"].sum() / of.groupby("categoria")["estoque"].sum()).rename("media_serra")
of = of.merge(ref.reset_index(), on="categoria"); of["indice_oferta"] = (100 * of["anuncios_por_mil_domicilios"] / of["media_serra"]).round(0)
of["mercado_turistico"] = of["cidade"].isin(["Gramado", "Canela", "Nova Petrópolis"])   # muitos imóveis de uso ocasional, que o Censo não conta como domicílio ocupado
of["leitura"] = pd.cut(of["indice_oferta"], [-1, 60, 140, 1e9], labels=["oferta escassa", "oferta na média", "oferta abundante"])
of.round(1).to_csv(os.path.join(PUB, "oferta_relativa.csv"), **fmt)
print("\n", of.sort_values(["categoria", "indice_oferta"]).to_string(index=False))
tp = trat[trat.categoria != "Terreno"].groupby(["cidade", "tipologia"]).size().rename("anuncios").reset_index()
tp["pct_da_cidade"] = (100 * tp["anuncios"] / tp.groupby("cidade")["anuncios"].transform("sum")).round(1)
tp.to_csv(os.path.join(PUB, "oferta_por_tipologia.csv"), **fmt)
print("\n", tp.pivot(index="cidade", columns="tipologia", values="pct_da_cidade").round(0).to_string())

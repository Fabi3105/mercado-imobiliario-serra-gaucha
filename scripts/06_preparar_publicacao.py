# -*- coding: utf-8 -*-
"""
Gera o index.html publicado a partir de painel_imoveis_serra_mapa.html:
1. Tira os grupos com menos de 5 anúncios (bairro, ou cidade + tipologia), para que nenhum número publicado
   corresponda a um anúncio individual.
2. Se existir coordenadas_bairros_serra.csv (botão "Baixar coordenadas (CSV)" do painel), embute as coordenadas
   e desliga a busca de bairros no Nominatim; assim quem abre a página não faz centenas de consultas ao serviço.
Uso: python scripts/06_preparar_publicacao.py
"""
import csv, glob, json, os, re, sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MIN_N = 5
ORIGEM, DESTINO = os.path.join(RAIZ, "painel_imoveis_serra_mapa.html"), os.path.join(RAIZ, "index.html")

s = open(ORIGEM, encoding="utf-8").read()
m = re.search(r"window\.__DATA__\s*=\s*", s)
D, fim = json.JSONDecoder().raw_decode(s[m.end():])
antes = (len(D["K"]), sum(len(v) for v in D["B"].values()), sum(len(v) for v in D["M"].values()))
D["K"] = {k: v for k, v in D["K"].items() if v["n"] >= MIN_N}
D["B"] = {k: [r for r in v if r[2] >= MIN_N] for k, v in D["B"].items()}
D["M"] = {k: [r for r in v if r[1] >= MIN_N] for k, v in D["M"].items()}
depois = (len(D["K"]), sum(len(v) for v in D["B"].values()), sum(len(v) for v in D["M"].values()))
print(f"Grupos com menos de {MIN_N} anúncios retirados: combinações {antes[0]}->{depois[0]}, linhas de bairro {antes[1]}->{depois[1]}, pontos do mapa {antes[2]}->{depois[2]}")
s = s[:m.end()] + json.dumps(D, ensure_ascii=False, separators=(",", ":")) + s[m.end() + fim:]

arqs = glob.glob(os.path.join(RAIZ, "coordenadas_bairros_serra*.csv")) + glob.glob(os.path.join(RAIZ, "dados", "coordenadas_bairros_serra*.csv"))
if arqs:
    arq = max(arqs, key=os.path.getmtime)
    geo = {}
    with open(arq, encoding="utf-8-sig", newline="") as f:
        for l in csv.DictReader(f, delimiter=";"):
            ok = l["localizado"].strip().lower() == "sim"
            geo[f'{l["cidade"]}|{l["bairro"]}'] = {"ok": True, "lat": float(l["latitude"]), "lon": float(l["longitude"])} if ok else {"ok": False}
    n_ok = sum(1 for g in geo.values() if g["ok"])
    print(f"Coordenadas embutidas de {os.path.basename(arq)}: {n_ok} de {len(geo)} bairros localizados")
    trocas = [
        ("let geo={};try{geo=JSON.parse(localStorage.getItem(GEOKEY)||'{}')}catch(e){geo={}}",
         "let geo=window.__GEO__||{};"),
        ("const fila=D.bairros.map((_,i)=>i).filter(i=>!geo[bkey(i)]);",
         "const fila=[]; // coordenadas já embutidas na página: não consulta o Nominatim"),
        ("<script>window.__DATA__=", "<script>window.__GEO__=" + json.dumps(geo, ensure_ascii=False, separators=(",", ":")) + ";</script>\n<script>window.__DATA__="),
        ("bairros localizados pelo nome via Nominatim (posição aproximada)", "bairros localizados pelo nome via Nominatim, uma única vez (posição aproximada)"),
    ]
    for a, b in trocas:
        if s.count(a) != 1:
            sys.exit(f"Não encontrei no painel o trecho: {a[:60]}... (o HTML mudou?)")
        s = s.replace(a, b)
else:
    print("Aviso: coordenadas_bairros_serra.csv não encontrado; a página publicada vai localizar os bairros no navegador de quem abrir.")
open(DESTINO, "w", encoding="utf-8").write(s)
print("Gerado:", os.path.relpath(DESTINO, RAIZ))

# -*- coding: utf-8 -*-
"""
Coleta anúncios de imóveis à venda pelo canal público para agentes do portal Chaves na Mão
(servidor MCP descrito em https://www.chavesnamao.com.br/llms.txt, sem senha).

O que este script faz
- Consulta a ferramenta "search_realty_listings" por cidade e tipo de imóvel (10 cidades da Serra; apartamento, casa e terreno).
- Guarda só as características do imóvel: tipo, cidade, bairro, preço pedido, área, quartos, banheiros e vagas.
  Não guarda anunciante, telefone, texto, foto nem link do anúncio.
- Faz uma consulta a cada 2 segundos (o limite declarado pelo portal é de 60 por minuto).
- Grava dados/anuncios_brutos.csv e um dados/coleta_resumo_<data>.csv por execução.

Atenção: são preços PEDIDOS em anúncios, não preços de venda. A base bruta é para uso no estudo e não deve
ser publicada; o estudo publica só estatísticas agregadas, citando a fonte.

Uso:  python scripts/01_coletar_anuncios.py
      python scripts/01_coletar_anuncios.py --cidades "Garibaldi;Bento Gonçalves" --tipos "apartamento;casa"
"""
import argparse, csv, json, os, sys, time, urllib.request, urllib.error
from datetime import date

ENDERECO = os.environ.get("CNM_MCP", "https://www.chavesnamao.com.br/api/mcp/")
PAUSA = 2.0            # segundos entre consultas
POR_PAGINA = 15        # o servidor só aceita 15
MAX_PAGINAS = 20       # o servidor devolve no máximo 20 páginas por filtro (300 anúncios)
PRECO_MAX = 100000000
CIDADES = ["Garibaldi", "Bento Gonçalves", "Carlos Barbosa", "Farroupilha", "Caxias do Sul", "Flores da Cunha",
           "Veranópolis", "Nova Petrópolis", "Gramado", "Canela"]
TIPOS = ["apartamento", "casa", "terreno"]
UF = "RS"

sessao = {"id": None, "n": 0, "consultas": 0}


def chamar(metodo, parametros):
    """Envia uma mensagem JSON-RPC ao servidor e devolve o campo result."""
    sessao["n"] += 1
    corpo = json.dumps({"jsonrpc": "2.0", "id": sessao["n"], "method": metodo, "params": parametros}).encode("utf-8")
    cab = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
           "User-Agent": "estudo-imoveis-serra/0.1 (estudo de portfolio; coleta lenta; github.com/Fabi3105)"}
    if sessao["id"]:
        cab["Mcp-Session-Id"] = sessao["id"]
    for tentativa in range(4):
        try:
            req = urllib.request.Request(ENDERECO, data=corpo, headers=cab, method="POST")
            with urllib.request.urlopen(req, timeout=40) as r:
                if r.headers.get("Mcp-Session-Id"):
                    sessao["id"] = r.headers.get("Mcp-Session-Id")
                texto = r.read().decode("utf-8", "replace")
            # a resposta pode vir como JSON puro ou como evento ("data: {...}")
            if not texto.lstrip().startswith("{"):
                linhas = [l[5:].strip() for l in texto.splitlines() if l.startswith("data:")]
                texto = linhas[-1] if linhas else "{}"
            resp = json.loads(texto)
            if "error" in resp:
                raise RuntimeError("servidor recusou: " + json.dumps(resp["error"], ensure_ascii=False)[:300])
            return resp.get("result", {})
        except urllib.error.HTTPError as e:
            espera = 60 if e.code == 429 else 10 * (tentativa + 1)
            print(f"   HTTP {e.code}; nova tentativa em {espera}s")
            time.sleep(espera)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"   falha de rede ({e}); nova tentativa em {10 * (tentativa + 1)}s")
            time.sleep(10 * (tentativa + 1))
    return None


def pagina(filtros, numero):
    time.sleep(PAUSA)
    sessao["consultas"] += 1
    r = chamar("tools/call", {"name": "search_realty_listings",
                              "arguments": {"filters": filtros, "page": numero, "pageSize": POR_PAGINA}})
    if not r:
        return None
    sc = r.get("structuredContent")
    if sc is None and r.get("content"):           # alguns servidores mandam só o texto
        try:
            sc = json.loads(r["content"][0]["text"])
        except Exception:
            sc = None
    return sc


def guardar(sc, cidade, tipo, base):
    for a in sc.get("results", []):
        loc = a.get("location") or {}
        base[str(a.get("id"))] = {
            "id": a.get("id"), "data_coleta": date.today().isoformat(), "fonte": "Chaves na Mão (anúncio)",
            "cidade_busca": cidade, "tipo_busca": tipo, "tipo": a.get("propertyType"),
            "cidade": loc.get("city"), "bairro": loc.get("neighborhood"),
            "preco_pedido": a.get("priceBRL"), "area_m2": a.get("areaM2"),
            "quartos": a.get("bedrooms"), "banheiros": a.get("bathrooms"), "vagas": a.get("parkingSpots"),
        }


def varrer(filtros, cidade, tipo, base, resumo, pmin=0, pmax=PRECO_MAX, raiz=True):
    """Lê todas as páginas de um filtro; se passar de 300 anúncios, parte a faixa de preço ao meio e repete.
    (O filtro de quartos do portal significa "N ou mais", por isso a divisão é só por preço.)"""
    f = dict(filtros) if raiz else dict(filtros, minPrice=pmin, maxPrice=pmax)
    p1 = pagina(f, 1)
    if p1 is None:
        resumo.append([cidade, tipo, f"{pmin}-{pmax}", "", "", "FALHA"])
        return
    pag = p1.get("pagination") or {}
    total, paginas = pag.get("totalResults", 0), pag.get("totalPages", 1)
    if raiz:
        resumo.append([cidade, tipo, "TOTAL ANUNCIADO", total, "", ""])
        print(f"   {cidade} / {tipo}: {total} anunciados")
    if paginas > MAX_PAGINAS and pmax - pmin > 5000:
        if pmax >= PRECO_MAX:
            meio = 1000000 if pmin < 1000000 else pmin * 2
        else:
            meio = (pmin + pmax) // 2
        varrer(filtros, cidade, tipo, base, resumo, pmin, meio, False)
        varrer(filtros, cidade, tipo, base, resumo, meio + 1, pmax, False)
        return
    antes = len(base)
    guardar(p1, cidade, tipo, base)
    for n in range(2, min(paginas, MAX_PAGINAS) + 1):
        sc = pagina(f, n)
        if sc:
            guardar(sc, cidade, tipo, base)
        else:
            resumo.append([cidade, tipo, f"{pmin}-{pmax} página {n}", "", "", "FALHA"])
    situacao = "CORTADO em 300" if paginas > MAX_PAGINAS else "ok"
    rotulo = "todos" if raiz else f"R$ {pmin} a {pmax}"
    resumo.append([cidade, tipo, rotulo, total, len(base) - antes, situacao])
    print(f"      {rotulo}: {total} na faixa, {len(base) - antes} novos na base ({situacao})")


CAMPOS = ["id", "data_coleta", "fonte", "cidade_busca", "tipo_busca", "tipo", "cidade", "bairro",
          "preco_pedido", "area_m2", "quartos", "banheiros", "vagas"]


def gravar(base, antigos, arq):
    with open(arq, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for k, v in base.items():
            if antigos.get(k):
                v = dict(v, data_coleta=antigos[k])   # mantém a data em que o anúncio foi visto pela primeira vez
            w.writerow(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cidades", default=";".join(CIDADES))
    ap.add_argument("--tipos", default=";".join(TIPOS))
    ap.add_argument("--saida", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dados"))
    a = ap.parse_args()
    cidades = [c.strip() for c in a.cidades.split(";") if c.strip()]
    tipos = [t.strip() for t in a.tipos.split(";") if t.strip()]
    os.makedirs(a.saida, exist_ok=True)

    print("Conectando a", ENDERECO)
    if chamar("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                             "clientInfo": {"name": "estudo-imoveis-serra", "version": "0.1"}}) is None:
        sys.exit("Não foi possível conectar. Confira a internet e tente de novo.")

    base, resumo, inicio = {}, [], time.time()
    arq = os.path.join(a.saida, "anuncios_brutos.csv")
    if os.path.exists(arq):                       # aproveita o que já foi coletado antes
        with open(arq, encoding="utf-8-sig", newline="") as f:
            for linha in csv.DictReader(f, delimiter=";"):
                base[str(linha["id"])] = linha
        print(f"Base existente: {len(base)} anúncios (serão mantidos; os novos entram junto).")
    antigos = {k: v.get("data_coleta") for k, v in base.items()}
    for c in cidades:
        for t in tipos:
            varrer({"transaction": "venda", "propertyType": t, "city": c, "state": UF}, c, t, base, resumo)
            gravar(base, antigos, arq)            # grava a cada cidade/tipo, para não perder nada se a janela fechar

    with open(os.path.join(a.saida, time.strftime("coleta_resumo_%Y%m%d_%H%M.csv")), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["cidade", "tipo", "filtro", "anunciados", "novos_na_base", "situacao"])
        w.writerows(resumo)
    print(f"\nPronto: {len(base)} anúncios em dados/anuncios_brutos.csv "
          f"({sessao['consultas']} consultas, {round((time.time() - inicio) / 60, 1)} min).")
    falhas = [r for r in resumo if "FALHA" in str(r[-1]) or "CORTADO" in str(r[-1])]
    if falhas:
        print(f"Atenção: {len(falhas)} trecho(s) com falha ou corte; veja o arquivo coleta_resumo mais recente na pasta dados.")


if __name__ == "__main__":
    main()

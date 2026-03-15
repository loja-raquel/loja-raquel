from http.server import BaseHTTPRequestHandler
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from db import sb_get


class handler(BaseHTTPRequestHandler):

    def _send(self, status, data):
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {})

    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            qs  = parse_qs(urlparse(self.path).query)
            de  = qs.get("de",  [None])[0]
            ate = qs.get("ate", [None])[0]

            if not de or not ate:
                self._send(400, {"sucesso": False, "erro": "Parâmetros 'de' e 'ate' são obrigatórios"})
                return

            vendas   = sb_get("vendas",   f"?data=gte.{de}&data=lte.{ate}")
            entradas = sb_get("entradas", f"?data=gte.{de}&data=lte.{ate}&order=data.desc")
            despesas = sb_get("despesas", f"?data=gte.{de}&data=lte.{ate}&categoria=neq.CMV&order=data.desc")

            faturamento   = sum(float(v.get("total", 0)) for v in vendas)
            cmv           = sum(float(v.get("custo", 0)) for v in vendas)
            lucro_bruto   = faturamento - cmv
            total_desp    = sum(float(d.get("valor", 0)) for d in despesas)
            lucro_liq     = lucro_bruto - total_desp
            margem        = round((lucro_bruto / faturamento * 100), 1) if faturamento > 0 else 0
            ticket_medio  = round(faturamento / len(vendas), 2) if vendas else 0
            total_compras = sum(float(e.get("total_pago", 0)) for e in entradas)

            por_produto = {}
            for v in vendas:
                for item in (v.get("itens") or []):
                    nome    = item.get("nome", "Desconhecido")
                    qtd     = int(item.get("qtd", 0))
                    receita = float(item.get("preco", 0)) * qtd
                    custo   = float(item.get("custo", 0)) * qtd
                    if nome not in por_produto:
                        por_produto[nome] = {"qtd": 0, "receita": 0, "custo": 0}
                    por_produto[nome]["qtd"]     += qtd
                    por_produto[nome]["receita"] += receita
                    por_produto[nome]["custo"]   += custo

            produtos_lista = []
            for nome, d in sorted(por_produto.items(), key=lambda x: -x[1]["receita"]):
                lucro_prod = d["receita"] - d["custo"]
                mg_prod    = round(lucro_prod / d["receita"] * 100, 1) if d["receita"] > 0 else 0
                produtos_lista.append({
                    "nome":    nome,
                    "qtd":     d["qtd"],
                    "receita": round(d["receita"], 2),
                    "custo":   round(d["custo"], 2),
                    "lucro":   round(lucro_prod, 2),
                    "margem":  mg_prod,
                })

            self._send(200, {
                "sucesso": True,
                "periodo": {"de": de, "ate": ate},
                "resumo": {
                    "faturamento":    round(faturamento, 2),
                    "cmv":            round(cmv, 2),
                    "lucro_bruto":    round(lucro_bruto, 2),
                    "lucro_liquido":  round(lucro_liq, 2),
                    "total_despesas": round(total_desp, 2),
                    "total_compras":  round(total_compras, 2),
                    "margem":         margem,
                    "ticket_medio":   ticket_medio,
                    "qtd_vendas":     len(vendas),
                    "qtd_entradas":   len(entradas),
                },
                "por_produto": produtos_lista,
                "entradas":    entradas,
                "despesas":    despesas,
            })

        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

from http.server import BaseHTTPRequestHandler
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from db import sb_get, sb_post, sb_patch


class handler(BaseHTTPRequestHandler):

    def _send(self, status, data):
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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

            params = "?order=data.desc,hora.desc"
            if de:  params += f"&data=gte.{de}"
            if ate: params += f"&data=lte.{ate}"
            if not de and not ate: params += "&limit=50"

            dados = sb_get("vendas", params)
            self._send(200, {"sucesso": True, "dados": dados})
        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))

            itens = body.get("itens", [])
            if not itens:
                self._send(400, {"sucesso": False, "erro": "Venda sem itens"})
                return

            # 1. Registrar venda
            venda = {
                "data":     body.get("data"),
                "hora":     body.get("hora"),
                "itens":    itens,
                "subtotal": float(body.get("subtotal", 0)),
                "desconto": float(body.get("desconto", 0)),
                "total":    float(body.get("total", 0)),
                "custo":    float(body.get("custo", 0)),
                "lucro":    float(body.get("lucro", 0)),
                "pgto":     body.get("pgto", "Dinheiro"),
            }
            res_venda = sb_post("vendas", venda)
            venda_id  = res_venda[0]["id"] if isinstance(res_venda, list) and res_venda else "?"

            # 2. Descontar estoque
            erros = []
            for item in itens:
                pid = item.get("id")
                qtd = int(item.get("qtd", 1))
                if not pid: continue
                try:
                    prods     = sb_get("produtos", f"?id=eq.{pid}&select=qtd")
                    qtd_atual = prods[0]["qtd"] if prods else 0
                    nova_qtd  = max(0, qtd_atual - qtd)
                    sb_patch("produtos", {"qtd": nova_qtd}, f"id=eq.{pid}")
                except Exception as ex:
                    erros.append(str(ex))

            # 3. Lançar CMV
            custo = float(body.get("custo", 0))
            if custo > 0:
                sb_post("despesas", {
                    "data":      body.get("data"),
                    "descricao": f"CMV — venda #{venda_id}",
                    "valor":     custo,
                    "categoria": "CMV",
                    "tipo":      "saida",
                })

            self._send(201, {"sucesso": True, "venda_id": venda_id, "erros_estoque": erros})
        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

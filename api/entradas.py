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

            params = "?order=data.desc"
            if de:  params += f"&data=gte.{de}"
            if ate: params += f"&data=lte.{ate}"
            if not de and not ate: params += "&limit=50"

            dados = sb_get("entradas", params)
            self._send(200, {"sucesso": True, "dados": dados})
        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))

            produto_id   = body.get("produto_id")
            produto_nome = body.get("produto_nome", "")
            qtd          = int(body.get("qtd", 0))
            custo        = float(body.get("custo", 0))
            validade     = body.get("validade") or None
            fornecedor   = body.get("fornecedor", "")
            data         = body.get("data")

            if not produto_id or qtd <= 0:
                self._send(400, {"sucesso": False, "erro": "produto_id e qtd são obrigatórios"})
                return

            # Busca estoque atual
            prods = sb_get("produtos", f"?id=eq.{produto_id}&select=qtd,custo")
            if not prods:
                self._send(404, {"sucesso": False, "erro": "Produto não encontrado"})
                return

            qtd_anterior = prods[0]["qtd"]
            qtd_nova     = qtd_anterior + qtd
            total_pago   = custo * qtd

            # Atualiza produto
            update = {"qtd": qtd_nova}
            if custo > 0:  update["custo"]    = custo
            if validade:   update["validade"] = validade
            sb_patch("produtos", update, f"id=eq.{produto_id}")

            # Registra entrada
            entrada = {
                "data":         data,
                "produto_id":   produto_id,
                "produto_nome": produto_nome,
                "qtd":          qtd,
                "custo":        custo,
                "total_pago":   total_pago,
                "fornecedor":   fornecedor,
                "qtd_anterior": qtd_anterior,
                "qtd_nova":     qtd_nova,
            }
            res = sb_post("entradas", entrada)

            # Lança despesa
            if total_pago > 0:
                desc = f"Compra de mercadoria — {produto_nome} ({qtd} un)"
                if fornecedor: desc += f" — {fornecedor}"
                sb_post("despesas", {
                    "data":      data,
                    "descricao": desc,
                    "valor":     total_pago,
                    "categoria": "Compra de mercadoria",
                    "tipo":      "saida",
                })

            self._send(201, {
                "sucesso":      True,
                "dados":        res,
                "qtd_anterior": qtd_anterior,
                "qtd_nova":     qtd_nova,
                "total_pago":   total_pago,
            })
        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

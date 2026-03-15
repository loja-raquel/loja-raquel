from http.server import BaseHTTPRequestHandler
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from db import sb_get, sb_post, sb_delete

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def _send(self, status, data):
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_OPTIONS(self):
        self._send(200, {})

    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            qs  = parse_qs(urlparse(self.path).query)
            de  = qs.get("de",  [None])[0]
            ate = qs.get("ate", [None])[0]

            params = "?categoria=neq.CMV&order=data.desc"
            if de:  params += f"&data=gte.{de}"
            if ate: params += f"&data=lte.{ate}"
            if not de and not ate: params += "&limit=50"

            dados = sb_get("despesas", params)
            self._send(200, {"sucesso": True, "dados": dados})
        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))
            acao   = body.get("acao", "criar")

            if acao == "criar":
                descricao = body.get("descricao", "").strip()
                valor     = float(body.get("valor", 0))
                categoria = body.get("categoria", "Outros")
                data      = body.get("data")

                if not descricao or valor <= 0:
                    self._send(400, {"sucesso": False, "erro": "Descrição e valor são obrigatórios"})
                    return
                if categoria == "CMV":
                    self._send(400, {"sucesso": False, "erro": "Categoria CMV é gerada automaticamente"})
                    return

                res = sb_post("despesas", {
                    "data":      data,
                    "descricao": descricao,
                    "valor":     valor,
                    "categoria": categoria,
                    "tipo":      "saida",
                })
                self._send(201, {"sucesso": True, "dados": res})

            elif acao == "excluir":
                did = body.get("id")
                if not did:
                    self._send(400, {"sucesso": False, "erro": "ID obrigatório"})
                    return
                sb_delete("despesas", f"id=eq.{did}")
                self._send(200, {"sucesso": True})

            else:
                self._send(400, {"sucesso": False, "erro": f"Ação desconhecida: {acao}"})

        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

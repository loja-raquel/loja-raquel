from http.server import BaseHTTPRequestHandler
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from db import sb_get, sb_post, sb_patch, sb_delete


class handler(BaseHTTPRequestHandler):

    def _send(self, status, data):
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {})

    def do_GET(self):
        try:
            dados = sb_get("produtos", "?order=nome")
            self._send(200, {"sucesso": True, "dados": dados})
        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))
            acao   = body.get("acao", "criar")

            if acao == "criar":
                dados = {
                    "nome":      body.get("nome"),
                    "codigo":    body.get("codigo", ""),
                    "categoria": body.get("categoria", ""),
                    "custo":     float(body.get("custo", 0)),
                    "venda":     float(body.get("venda", 0)),
                    "qtd":       int(body.get("qtd", 0)),
                    "min":       int(body.get("min", 5)),
                    "validade":  body.get("validade") or None,
                    "unidade":   body.get("unidade", "un"),
                }
                if not dados["nome"]:
                    self._send(400, {"sucesso": False, "erro": "Nome obrigatório"})
                    return
                res = sb_post("produtos", dados)
                self._send(201, {"sucesso": True, "dados": res if isinstance(res, list) else [res]})

            elif acao == "atualizar_qtd":
                pid = body.get("id")
                qtd = body.get("qtd")
                if pid is None or qtd is None:
                    self._send(400, {"sucesso": False, "erro": "ID e qtd obrigatórios"})
                    return
                res = sb_patch("produtos", {"qtd": int(qtd)}, f"id=eq.{pid}")
                self._send(200, {"sucesso": True, "dados": res})

            elif acao == "excluir":
                pid = body.get("id")
                if not pid:
                    self._send(400, {"sucesso": False, "erro": "ID obrigatório"})
                    return
                sb_delete("produtos", f"id=eq.{pid}")
                self._send(200, {"sucesso": True})

            else:
                self._send(400, {"sucesso": False, "erro": f"Ação desconhecida: {acao}"})

        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

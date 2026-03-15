from http.server import BaseHTTPRequestHandler
import json
import os
from supabase import create_client

def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    return create_client(url, key)


class handler(BaseHTTPRequestHandler):

    def _send(self, status, data):
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {})

    # ----------------------------------------------------------
    # GET /api/produtos
    # Retorna todos os produtos ordenados por nome
    # ----------------------------------------------------------
    def do_GET(self):
        try:
            sb = get_supabase()
            res = sb.table("produtos").select("*").order("nome").execute()
            self._send(200, {"sucesso": True, "dados": res.data})
        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

    # ----------------------------------------------------------
    # POST /api/produtos
    # Body pode ser:
    #   { "acao": "criar", ...campos }
    #   { "acao": "atualizar", "id": X, ...campos }
    #   { "acao": "excluir", "id": X }
    #   { "acao": "atualizar_qtd", "id": X, "qtd": N }
    # ----------------------------------------------------------
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            acao = body.get("acao", "criar")
            sb = get_supabase()

            if acao == "criar":
                dados = {
                    "nome":       body.get("nome"),
                    "codigo":     body.get("codigo", ""),
                    "categoria":  body.get("categoria", ""),
                    "custo":      float(body.get("custo", 0)),
                    "venda":      float(body.get("venda", 0)),
                    "qtd":        int(body.get("qtd", 0)),
                    "min":        int(body.get("min", 5)),
                    "validade":   body.get("validade") or None,
                    "unidade":    body.get("unidade", "un"),
                }
                if not dados["nome"]:
                    self._send(400, {"sucesso": False, "erro": "Nome obrigatório"})
                    return
                res = sb.table("produtos").insert(dados).execute()
                self._send(201, {"sucesso": True, "dados": res.data})

            elif acao == "atualizar":
                pid = body.get("id")
                if not pid:
                    self._send(400, {"sucesso": False, "erro": "ID obrigatório"})
                    return
                campos = {}
                for f in ["nome", "codigo", "categoria", "unidade"]:
                    if f in body:
                        campos[f] = body[f]
                for f in ["custo", "venda"]:
                    if f in body:
                        campos[f] = float(body[f])
                for f in ["qtd", "min"]:
                    if f in body:
                        campos[f] = int(body[f])
                if "validade" in body:
                    campos["validade"] = body["validade"] or None
                campos["updated_at"] = "NOW()"
                res = sb.table("produtos").update(campos).eq("id", pid).execute()
                self._send(200, {"sucesso": True, "dados": res.data})

            elif acao == "atualizar_qtd":
                pid = body.get("id")
                qtd = body.get("qtd")
                if pid is None or qtd is None:
                    self._send(400, {"sucesso": False, "erro": "ID e qtd obrigatórios"})
                    return
                res = sb.table("produtos").update({"qtd": int(qtd)}).eq("id", pid).execute()
                self._send(200, {"sucesso": True, "dados": res.data})

            elif acao == "excluir":
                pid = body.get("id")
                if not pid:
                    self._send(400, {"sucesso": False, "erro": "ID obrigatório"})
                    return
                sb.table("produtos").delete().eq("id", pid).execute()
                self._send(200, {"sucesso": True})

            else:
                self._send(400, {"sucesso": False, "erro": f"Ação desconhecida: {acao}"})

        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

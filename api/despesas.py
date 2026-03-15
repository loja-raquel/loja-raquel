from http.server import BaseHTTPRequestHandler
import json
import os
from supabase import create_client


def get_supabase():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    return create_client(url, key)


class handler(BaseHTTPRequestHandler):

    def _send(self, status, data):
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
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

            sb    = get_supabase()
            query = sb.table("despesas").select("*").neq("categoria", "CMV").order("data", desc=True)
            if de:  query = query.gte("data", de)
            if ate: query = query.lte("data", ate)
            if not de and not ate: query = query.limit(50)

            res = query.execute()
            self._send(200, {"sucesso": True, "dados": res.data})
        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))
            acao   = body.get("acao", "criar")
            sb     = get_supabase()

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

                res = sb.table("despesas").insert({
                    "data":      data,
                    "descricao": descricao,
                    "valor":     valor,
                    "categoria": categoria,
                    "tipo":      "saida",
                }).execute()
                self._send(201, {"sucesso": True, "dados": res.data})

            elif acao == "excluir":
                did = body.get("id")
                if not did:
                    self._send(400, {"sucesso": False, "erro": "ID obrigatório"})
                    return
                sb.table("despesas").delete().eq("id", did).execute()
                self._send(200, {"sucesso": True})

            else:
                self._send(400, {"sucesso": False, "erro": f"Ação desconhecida: {acao}"})

        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

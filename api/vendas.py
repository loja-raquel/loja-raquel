from http.server import BaseHTTPRequestHandler
import json
import os
from supabase import create_client


def get_supabase():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    from supabase.client import ClientOptions
    return create_client(url, key, options=ClientOptions(postgrest_client_timeout=10))


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

    # ----------------------------------------------------------
    # GET /api/vendas?de=2026-01-01&ate=2026-12-31
    # Retorna vendas no período. Sem parâmetros = últimas 50.
    # ----------------------------------------------------------
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            de  = qs.get("de",  [None])[0]
            ate = qs.get("ate", [None])[0]

            sb = get_supabase()
            query = sb.table("vendas").select("*").order("data", desc=True).order("hora", desc=True)

            if de:
                query = query.gte("data", de)
            if ate:
                query = query.lte("data", ate)
            if not de and not ate:
                query = query.limit(50)

            res = query.execute()
            self._send(200, {"sucesso": True, "dados": res.data})
        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

    # ----------------------------------------------------------
    # POST /api/vendas
    # Registra uma venda e desconta o estoque de cada item.
    # Body:
    # {
    #   "itens": [{ "id": 1, "nome": "X", "preco": 5.0, "qtd": 2, "custo": 3.0 }],
    #   "subtotal": 10.0,
    #   "desconto": 0.0,
    #   "total": 10.0,
    #   "custo": 6.0,
    #   "lucro": 4.0,
    #   "pgto": "PIX",
    #   "data": "2026-03-15",
    #   "hora": "14:32"
    # }
    # ----------------------------------------------------------
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))
            sb     = get_supabase()

            itens = body.get("itens", [])
            if not itens:
                self._send(400, {"sucesso": False, "erro": "Venda sem itens"})
                return

            # 1. Registrar a venda
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
            res_venda = sb.table("vendas").insert(venda).execute()
            venda_id  = res_venda.data[0]["id"] if res_venda.data else "?"

            # 2. Descontar estoque de cada item
            erros_estoque = []
            for item in itens:
                pid  = item.get("id")
                qtd  = int(item.get("qtd", 1))
                if not pid:
                    continue
                try:
                    prod = sb.table("produtos").select("qtd").eq("id", pid).single().execute()
                    qtd_atual = prod.data["qtd"] if prod.data else 0
                    nova_qtd  = max(0, qtd_atual - qtd)
                    sb.table("produtos").update({"qtd": nova_qtd}).eq("id", pid).execute()
                except Exception as e:
                    erros_estoque.append(f"Produto {pid}: {str(e)}")

            # 3. Registrar CMV como despesa
            custo = float(body.get("custo", 0))
            if custo > 0:
                sb.table("despesas").insert({
                    "data":      body.get("data"),
                    "descricao": f"CMV — venda #{venda_id}",
                    "valor":     custo,
                    "categoria": "CMV",
                    "tipo":      "saida",
                }).execute()

            self._send(201, {
                "sucesso": True,
                "venda_id": venda_id,
                "erros_estoque": erros_estoque
            })

        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

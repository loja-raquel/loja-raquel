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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {})

    # ----------------------------------------------------------
    # GET /api/entradas?de=2026-01-01&ate=2026-12-31
    # Retorna entradas no período. Sem parâmetros = últimas 50.
    # ----------------------------------------------------------
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            qs  = parse_qs(urlparse(self.path).query)
            de  = qs.get("de",  [None])[0]
            ate = qs.get("ate", [None])[0]

            sb    = get_supabase()
            query = sb.table("entradas").select("*").order("data", desc=True)

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
    # POST /api/entradas
    # Registra entrada de mercadoria, soma estoque do produto
    # e lança despesa de compra automaticamente.
    # Body:
    # {
    #   "produto_id":   1,
    #   "produto_nome": "Coca-Cola 2L",
    #   "qtd":          24,
    #   "custo":        3.50,
    #   "validade":     "2026-12-31",   (opcional)
    #   "fornecedor":   "Distribuidora X",  (opcional)
    #   "data":         "2026-03-15"
    # }
    # ----------------------------------------------------------
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))
            sb     = get_supabase()

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

            # 1. Buscar estoque atual do produto
            prod = sb.table("produtos").select("qtd, custo").eq("id", produto_id).single().execute()
            if not prod.data:
                self._send(404, {"sucesso": False, "erro": "Produto não encontrado"})
                return

            qtd_anterior = prod.data["qtd"]
            qtd_nova     = qtd_anterior + qtd
            total_pago   = custo * qtd

            # 2. Atualizar estoque (e custo e validade se informados)
            update_campos = {"qtd": qtd_nova}
            if custo > 0:
                update_campos["custo"] = custo
            if validade:
                update_campos["validade"] = validade
            sb.table("produtos").update(update_campos).eq("id", produto_id).execute()

            # 3. Registrar a entrada
            entrada = {
                "data":          data,
                "produto_id":    produto_id,
                "produto_nome":  produto_nome,
                "qtd":           qtd,
                "custo":         custo,
                "total_pago":    total_pago,
                "fornecedor":    fornecedor,
                "qtd_anterior":  qtd_anterior,
                "qtd_nova":      qtd_nova,
            }
            res = sb.table("entradas").insert(entrada).execute()

            # 4. Lançar despesa de compra automaticamente
            if total_pago > 0:
                desc = f"Compra de mercadoria — {produto_nome} ({qtd} un)"
                if fornecedor:
                    desc += f" — {fornecedor}"
                sb.table("despesas").insert({
                    "data":      data,
                    "descricao": desc,
                    "valor":     total_pago,
                    "categoria": "Compra de mercadoria",
                    "tipo":      "saida",
                }).execute()

            self._send(201, {
                "sucesso":      True,
                "dados":        res.data,
                "qtd_anterior": qtd_anterior,
                "qtd_nova":     qtd_nova,
                "total_pago":   total_pago,
            })

        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

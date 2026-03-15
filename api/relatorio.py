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
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {})

    # ----------------------------------------------------------
    # GET /api/relatorio?de=2026-01-01&ate=2026-01-07
    # Retorna relatório completo do período:
    # - Resumo financeiro (faturamento, CMV, lucro bruto/líquido)
    # - Margem por produto
    # - Entradas de mercadoria
    # - Despesas (exceto CMV)
    # - Total comprado no período
    # ----------------------------------------------------------
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            qs  = parse_qs(urlparse(self.path).query)
            de  = qs.get("de",  [None])[0]
            ate = qs.get("ate", [None])[0]

            if not de or not ate:
                self._send(400, {"sucesso": False, "erro": "Parâmetros 'de' e 'ate' são obrigatórios"})
                return

            sb = get_supabase()

            # 1. Vendas do período
            vendas = (
                sb.table("vendas")
                .select("*")
                .gte("data", de)
                .lte("data", ate)
                .execute()
            ).data or []

            # 2. Entradas do período
            entradas = (
                sb.table("entradas")
                .select("*")
                .gte("data", de)
                .lte("data", ate)
                .order("data", desc=True)
                .execute()
            ).data or []

            # 3. Despesas do período (exceto CMV)
            despesas = (
                sb.table("despesas")
                .select("*")
                .gte("data", de)
                .lte("data", ate)
                .neq("categoria", "CMV")
                .order("data", desc=True)
                .execute()
            ).data or []

            # 4. Calcular resumo financeiro
            faturamento  = sum(float(v.get("total", 0))  for v in vendas)
            cmv          = sum(float(v.get("custo", 0))  for v in vendas)
            lucro_bruto  = faturamento - cmv
            total_desp   = sum(float(d.get("valor", 0))  for d in despesas)
            lucro_liq    = lucro_bruto - total_desp
            margem       = round((lucro_bruto / faturamento * 100), 1) if faturamento > 0 else 0
            ticket_medio = round(faturamento / len(vendas), 2) if vendas else 0
            total_compras = sum(float(e.get("total_pago", 0)) for e in entradas)

            # 5. Margem por produto
            por_produto = {}
            for v in vendas:
                for item in v.get("itens", []):
                    nome   = item.get("nome", "Desconhecido")
                    qtd    = int(item.get("qtd", 0))
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
                    "faturamento":   round(faturamento, 2),
                    "cmv":           round(cmv, 2),
                    "lucro_bruto":   round(lucro_bruto, 2),
                    "lucro_liquido": round(lucro_liq, 2),
                    "total_despesas":round(total_desp, 2),
                    "total_compras": round(total_compras, 2),
                    "margem":        margem,
                    "ticket_medio":  ticket_medio,
                    "qtd_vendas":    len(vendas),
                    "qtd_entradas":  len(entradas),
                },
                "por_produto": produtos_lista,
                "entradas":    entradas,
                "despesas":    despesas,
            })

        except Exception as e:
            self._send(500, {"sucesso": False, "erro": str(e)})

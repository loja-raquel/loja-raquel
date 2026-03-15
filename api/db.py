import os
import json
import ssl
from urllib.request import Request, urlopen

# Cria contexto SSL explícito — necessário no ambiente Vercel serverless
_ssl_ctx = ssl.create_default_context()

def supabase_headers():
    key = os.environ.get("SUPABASE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def supabase_url(table, params=""):
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    return f"{base}/rest/v1/{table}{params}"

def sb_get(table, params=""):
    req = Request(supabase_url(table, params), headers=supabase_headers(), method="GET")
    with urlopen(req, timeout=15, context=_ssl_ctx) as r:
        return json.loads(r.read().decode("utf-8"))

def sb_post(table, data):
    body = json.dumps(data).encode("utf-8")
    req = Request(supabase_url(table), data=body, headers=supabase_headers(), method="POST")
    with urlopen(req, timeout=15, context=_ssl_ctx) as r:
        return json.loads(r.read().decode("utf-8"))

def sb_patch(table, data, filter_param):
    body = json.dumps(data).encode("utf-8")
    req = Request(supabase_url(table, f"?{filter_param}"), data=body, headers=supabase_headers(), method="PATCH")
    with urlopen(req, timeout=15, context=_ssl_ctx) as r:
        return json.loads(r.read().decode("utf-8"))

def sb_delete(table, filter_param):
    req = Request(supabase_url(table, f"?{filter_param}"), headers=supabase_headers(), method="DELETE")
    with urlopen(req, timeout=15, context=_ssl_ctx) as r:
        return True

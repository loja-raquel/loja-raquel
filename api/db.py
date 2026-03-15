import os
import httpx

def supabase_headers():
    key = os.environ.get("SUPABASE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def supabase_url(table, params=""):
    base = os.environ.get("SUPABASE_URL", "")
    return f"{base}/rest/v1/{table}{params}"

def sb_get(table, params=""):
    r = httpx.get(supabase_url(table, params), headers=supabase_headers(), timeout=15)
    r.raise_for_status()
    return r.json()

def sb_post(table, data):
    r = httpx.post(supabase_url(table), headers=supabase_headers(), json=data, timeout=15)
    r.raise_for_status()
    return r.json()

def sb_patch(table, data, filter_param):
    url = supabase_url(table, f"?{filter_param}")
    r = httpx.patch(url, headers=supabase_headers(), json=data, timeout=15)
    r.raise_for_status()
    return r.json()

def sb_delete(table, filter_param):
    url = supabase_url(table, f"?{filter_param}")
    r = httpx.delete(url, headers=supabase_headers(), timeout=15)
    r.raise_for_status()
    return True

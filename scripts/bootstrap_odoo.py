#!/usr/bin/env python3
"""Create the local synthetic Odoo database and install Purchase.

This talks only to the local Odoo database manager and the self-hosted XML-RPC
interface. It is intentionally separate from the ChangeShield runner: recovery
jobs never receive database-administrator capability.
"""
import os
import time
import xmlrpc.client
import requests

BASE = os.getenv("ODOO_BASE_URL", "http://localhost:8069").rstrip("/")
DATABASE = os.getenv("ODOO_DATABASE", "changeshield")
LOGIN = os.getenv("ODOO_USERNAME", "requester@example.test")
PASSWORD = os.getenv("ODOO_PASSWORD", "demo-only-password")
MASTER_PASSWORD = os.getenv("ODOO_MASTER_PASSWORD", "admin")


def wait_ready():
    for _ in range(60):
        try:
            if requests.get(f"{BASE}/web/database/list", timeout=3).status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise RuntimeError("Odoo did not become ready")


def create_database():
    response = requests.post(f"{BASE}/web/database/create", data={"master_pwd": MASTER_PASSWORD, "name": DATABASE, "login": LOGIN, "password": PASSWORD, "lang": "en_US", "country_code": "IN", "phone": "", "demo": "true"}, timeout=120)
    if response.status_code >= 400 and "already exists" not in response.text.lower():
        raise RuntimeError(f"Odoo database creation failed: HTTP {response.status_code}")


def install_purchase():
    common = xmlrpc.client.ServerProxy(f"{BASE}/xmlrpc/2/common")
    uid = common.authenticate(DATABASE, LOGIN, PASSWORD, {})
    if not uid:
        raise RuntimeError("Could not authenticate to the synthetic Odoo database")
    models = xmlrpc.client.ServerProxy(f"{BASE}/xmlrpc/2/object")
    module_ids = models.execute_kw(DATABASE, uid, PASSWORD, "ir.module.module", "search", [[("name", "=", "purchase")]], {"limit": 1})
    if not module_ids:
        raise RuntimeError("Odoo Purchase module was not found")
    state = models.execute_kw(DATABASE, uid, PASSWORD, "ir.module.module", "read", [module_ids], {"fields": ["state"]})[0]["state"]
    if state != "installed":
        models.execute_kw(DATABASE, uid, PASSWORD, "ir.module.module", "button_immediate_install", [module_ids])


if __name__ == "__main__":
    wait_ready()
    try:
        create_database()
    except RuntimeError as exc:
        if "already exists" not in str(exc).lower():
            raise
    install_purchase()
    reset_url = os.getenv("SANDBOX_SNAPSHOT_URL", "http://localhost:8080/snapshot")
    reset_token = os.getenv("SANDBOX_RESET_TOKEN", "local-reset-token-change-me")
    try:
        response = requests.post(reset_url, headers={"Authorization": f"Bearer {reset_token}"}, timeout=150)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("Odoo was initialized, but the clean validation snapshot could not be captured") from exc
    print(f"Odoo sandbox ready at {BASE} with database {DATABASE}")

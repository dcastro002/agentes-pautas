#!/usr/bin/env python3
"""Genera el refresh token de Google (Google Ads, y opcionalmente GA4) para el servidor.

Se corre UNA vez en tu computadora, con tu cuenta de Freelan. No guarda nada en archivos:
imprime el refresh token para que lo pegues directo en las variables de Railway.

Requisitos:
- Un cliente OAuth de tipo "App de escritorio" (Desktop app) en el proyecto de Google Cloud,
  con la pantalla de consentimiento en modo Interno.
- Python 3.9+ (no necesita instalar nada).

Uso:
    python3 scripts/google_refresh_token.py            # solo Google Ads
    python3 scripts/google_refresh_token.py --ga4      # Google Ads + lectura de GA4
"""
import argparse
import base64
import getpass
import hashlib
import http.server
import json
import os
import secrets
import socket
import sys
import urllib.parse
import urllib.request
import webbrowser

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE_ADS = "https://www.googleapis.com/auth/adwords"
SCOPE_GA4 = "https://www.googleapis.com/auth/analytics.readonly"


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ga4", action="store_true", help="incluye permiso de solo lectura de Google Analytics")
    args = p.parse_args()

    client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID") or input("Client ID del cliente OAuth: ").strip()
    client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET") or getpass.getpass("Client secret (no se muestra): ").strip()
    if not client_id or not client_secret:
        sys.exit("Faltan el client ID o el client secret.")

    scopes = [SCOPE_ADS] + ([SCOPE_GA4] if args.ga4 else [])
    verificador = secrets.token_urlsafe(64)
    reto = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    estado = secrets.token_urlsafe(24)
    puerto = puerto_libre()
    redirect = f"http://127.0.0.1:{puerto}"
    resultado: dict = {}

    class Manejador(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            resultado.update({k: v[0] for k, v in q.items()})
            ok = "code" in q and q.get("state", [""])[0] == estado
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(("<h2>Listo, ya puedes cerrar esta pestaña y volver a la terminal.</h2>" if ok else
                              "<h2>No se completó la autorización. Revisa la terminal.</h2>").encode())

        def log_message(self, *a):
            pass

    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": " ".join(scopes),
        "access_type": "offline", "prompt": "consent", "state": estado,
        "code_challenge": reto, "code_challenge_method": "S256"})
    print("\nAbriendo el navegador para que autorices con tu cuenta de Freelan…")
    print("Si no se abre solo, copia esta URL en el navegador:\n" + url + "\n")
    webbrowser.open(url)
    with http.server.HTTPServer(("127.0.0.1", puerto), Manejador) as servidor:
        while "code" not in resultado and "error" not in resultado:
            servidor.handle_request()

    if resultado.get("error"):
        sys.exit(f"Google devolvió un error: {resultado['error']}")
    if resultado.get("state") != estado:
        sys.exit("El parámetro state no coincide; por seguridad no continúo. Vuelve a correr el script.")

    datos = urllib.parse.urlencode({"code": resultado["code"], "client_id": client_id, "client_secret": client_secret,
                                    "redirect_uri": redirect, "grant_type": "authorization_code",
                                    "code_verifier": verificador}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=datos), timeout=30) as r:
            token = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"No pude canjear el código: {e.read().decode()[:300]}")

    refresh = token.get("refresh_token")
    if not refresh:
        sys.exit("Google no devolvió refresh token. Quita el acceso de la app en myaccount.google.com/permissions "
                 "y vuelve a correr el script.")
    print("Permisos otorgados:", token.get("scope", ""))
    print("\nCopia este valor en Railway como GOOGLE_ADS_REFRESH_TOKEN (y no lo guardes en ningún archivo):\n")
    print(refresh)
    print("\nDespués de guardarlo en Railway, cierra esta terminal o límpiala (comando: clear).")


if __name__ == "__main__":
    main()

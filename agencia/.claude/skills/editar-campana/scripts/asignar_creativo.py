#!/usr/bin/env python3
"""Asigna un creativo nuevo a un anuncio EXISTENTE de Meta (mismo ID de anuncio).

Uso:
  python3 asignar_creativo.py --ad <ID_ANUNCIO> --creative <ID_CREATIVO> [--dry-run]

- Usa la API de Marketing de Meta directamente. El token se lee de la
  variable de entorno META_ACCESS_TOKEN (nunca de un archivo ni del chat).
- Versión de la API: variable META_API_VERSION (por defecto v23.0).
- Solo cambia el creativo. Nunca envía estatus: el anuncio conserva el que tenía.
- Verifica después: el creativo nuevo quedó asignado y el estatus no cambió.
"""
import argparse, json, os, sys, urllib.parse, urllib.request, urllib.error

VER = os.environ.get("META_API_VERSION", "v23.0")
BASE = f"https://graph.facebook.com/{VER}"
CAMPOS = "id,name,status,effective_status,adset_id,creative{id,name}"


def llamar(metodo, ruta, params):
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        sys.exit("Falta la variable META_ACCESS_TOKEN. Defínela en la terminal antes de abrir Claude Code.")
    params = dict(params, access_token=token)
    datos = urllib.parse.urlencode(params).encode()
    if metodo == "GET":
        req = urllib.request.Request(f"{BASE}/{ruta}?{datos.decode()}")
    else:
        req = urllib.request.Request(f"{BASE}/{ruta}", data=datos, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode()).get("error", {})
        except Exception:
            err = {"message": str(e)}
        print("ERROR DE META:", json.dumps({k: err.get(k) for k in
              ("message", "type", "code", "error_subcode", "error_user_title", "error_user_msg")},
              ensure_ascii=False, indent=1))
        sys.exit(1)


def resumen(ad):
    c = ad.get("creative") or {}
    return {"anuncio": ad.get("id"), "nombre": ad.get("name"), "estatus": ad.get("status"),
            "estatus_efectivo": ad.get("effective_status"), "creativo": c.get("id")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ad", required=True)
    p.add_argument("--creative", required=True)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    antes = llamar("GET", a.ad, {"fields": CAMPOS})
    print("ANTES:", json.dumps(resumen(antes), ensure_ascii=False))
    if (antes.get("creative") or {}).get("id") == a.creative:
        print("El anuncio ya usa ese creativo. No hay nada que cambiar.")
        return
    if a.dry_run:
        print(f"SIMULACIÓN: se asignaría el creativo {a.creative} al anuncio {a.ad}. No se cambió nada.")
        return

    r = llamar("POST", a.ad, {"creative": json.dumps({"creative_id": a.creative})})
    if not r.get("success", False):
        print("Respuesta inesperada de Meta:", r)
        sys.exit(1)

    despues = llamar("GET", a.ad, {"fields": CAMPOS})
    print("DESPUÉS:", json.dumps(resumen(despues), ensure_ascii=False))
    ok_creativo = (despues.get("creative") or {}).get("id") == a.creative
    ok_estatus = despues.get("status") == antes.get("status")
    if not ok_creativo:
        print("ATENCIÓN: Meta respondió éxito pero el anuncio no muestra el creativo nuevo.")
        sys.exit(1)
    if not ok_estatus:
        print(f"ATENCIÓN: el estatus cambió de {antes.get('status')} a {despues.get('status')}. Revísalo en Ads Manager.")
        sys.exit(1)
    print("LISTO: mismo anuncio, creativo nuevo, estatus sin cambios. Meta lo volverá a revisar.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Valida el JSON del analista y arma el dashboard HTML.

Uso:
  python3 armar_dashboard.py <datos.json> <salida.html>

Toma la plantilla assets/dashboard.html (junto a esta carpeta), reemplaza
solo el bloque <script id="report-data"> y guarda el resultado.
Si el JSON no cumple lo mínimo, no genera nada y sale con código 1.
"""
import json, os, re, sys
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
PLANTILLA = os.path.join(AQUI, "..", "assets", "dashboard.html")
OBLIGATORIAS = ["meta", "estado", "meses", "hechos", "calidad", "definiciones"]
NUM = ["inversion", "impresiones", "clics", "resultados"]


def main(datos_p, salida_p):
    d = json.load(open(datos_p, encoding="utf-8"))
    errores, avisos = [], []

    for k in OBLIGATORIAS:
        if k not in d:
            errores.append(f"Falta la llave '{k}'")
    meses = set(d.get("meses", []))
    for i, h in enumerate(d.get("hechos", [])):
        for k in ["mes", "campana", "anuncio"] + NUM:
            if k not in h:
                errores.append(f"hechos[{i}] sin '{k}'")
        for k in NUM:
            if k in h and not isinstance(h[k], (int, float)):
                errores.append(f"hechos[{i}].{k} debe ser número, no {h[k]!r}")
        if h.get("mes") and h["mes"] not in meses:
            errores.append(f"hechos[{i}].mes {h['mes']} no está en 'meses'")
    for m in meses:
        if not re.fullmatch(r"\d{4}-\d{2}", m):
            errores.append(f"Mes con formato inválido: {m} (debe ser AAAA-MM)")
    if d.get("meta", {}).get("datos_ficticios"):
        avisos.append("meta.datos_ficticios está en true: el dashboard dirá que son datos de prueba")

    if errores:
        print("NO SE GENERÓ EL DASHBOARD:")
        for e in errores:
            print(" -", e)
        sys.exit(1)

    # Totales para que el analista los compare contra la plataforma
    tot = defaultdict(float)
    por_mes = defaultdict(lambda: defaultdict(float))
    for h in d["hechos"]:
        for k in NUM:
            tot[k] += h[k]
            por_mes[h["mes"]][k] += h[k]

    html = open(PLANTILLA, encoding="utf-8").read()
    datos = json.dumps(d, ensure_ascii=False, indent=1).replace("</", "<\\/")
    nuevo, n = re.subn(r'(<script id="report-data" type="application/json">)(.*?)(</script>)',
                       lambda m: m.group(1) + "\n" + datos + "\n" + m.group(3), html, count=1, flags=re.S)
    if n != 1:
        sys.exit("No encontré el bloque report-data en la plantilla.")
    os.makedirs(os.path.dirname(os.path.abspath(salida_p)), exist_ok=True)
    open(salida_p, "w", encoding="utf-8").write(nuevo)

    print("Dashboard generado:", salida_p)
    print(f"Totales de 'hechos': inversión {tot['inversion']:,.2f} · impresiones {tot['impresiones']:,.0f} · "
          f"clics {tot['clics']:,.0f} · resultados {tot['resultados']:,.0f}")
    for m in sorted(meses):
        v = por_mes.get(m, {})
        print(f"  {m}: inversión {v.get('inversion', 0):,.2f} · impresiones {v.get('impresiones', 0):,.0f}")
    for a in avisos:
        print("AVISO:", a)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])

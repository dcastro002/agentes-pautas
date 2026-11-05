#!/usr/bin/env python3
"""Valida una campaña de Google Search (JSON) y genera su brief en Excel para revisión humana.

Uso:
    python3 .claude/skills/campana-google/scripts/brief_google.py <campana.json> <salida.xlsx>

Sale con código 1 y la lista de errores si algo no cumple los límites de Google.
El JSON es el mismo que después recibe la herramienta de montaje, así que lo que se revisa
en Monday es exactamente lo que se sube.
"""
import json
import re
import sys
from datetime import date

TITULOS = (3, 15, 30)        # mínimo, máximo, caracteres
DESCRIPCIONES = (2, 4, 90)
RUTA = 15
PALABRA = (80, 10)           # caracteres, palabras
CONCORDANCIAS = {"EXACTA", "FRASE", "AMPLIA", "EXACT", "PHRASE", "BROAD"}


def validar(spec: dict) -> list[str]:
    e = []
    for campo in ("cuenta", "nombre", "presupuesto_diario_mxn", "inicio", "grupos"):
        if not spec.get(campo):
            e.append(f"Falta «{campo}»")
    try:
        if float(spec.get("presupuesto_diario_mxn") or 0) <= 0:
            e.append("presupuesto_diario_mxn debe ser mayor a 0")
    except ValueError:
        e.append("presupuesto_diario_mxn no es un número")
    try:
        inicio = date.fromisoformat(str(spec.get("inicio")))
        if inicio < date.today():
            e.append("inicio: la fecha ya pasó")
        if spec.get("fin") and date.fromisoformat(str(spec["fin"])) <= inicio:
            e.append("fin: debe ser posterior al inicio")
    except ValueError:
        e.append("Fechas en formato AAAA-MM-DD")
    estrategia = str(spec.get("estrategia") or "MAXIMIZAR_CLICS").upper()
    if estrategia not in ("MAXIMIZAR_CLICS", "CPC_MANUAL"):
        e.append("estrategia: MAXIMIZAR_CLICS o CPC_MANUAL")
    if estrategia == "CPC_MANUAL" and not spec.get("cpc_max_mxn"):
        e.append("Con CPC_MANUAL hace falta cpc_max_mxn")
    for u in spec.get("ubicaciones") or []:
        if not re.fullmatch(r"geoTargetConstants/\d+", str(u)):
            e.append(f"Ubicación «{u}»: usa geoTargetConstants/<id>")
    for g_i, g in enumerate(spec.get("grupos") or [], 1):
        donde = f"Grupo {g_i} «{g.get('nombre', '')}»"
        palabras = g.get("palabras_clave") or []
        if not palabras:
            e.append(f"{donde}: sin palabras clave")
        for p in palabras + [{"texto": n, "concordancia": "AMPLIA"} if isinstance(n, str) else n
                             for n in (g.get("negativas") or [])]:
            p = p if isinstance(p, dict) else {"texto": p, "concordancia": "FRASE"}
            texto = str(p.get("texto", ""))
            if str(p.get("concordancia", "FRASE")).upper() not in CONCORDANCIAS:
                e.append(f"{donde}: concordancia no válida en «{texto}»")
            if len(texto) > PALABRA[0] or len(texto.split()) > PALABRA[1]:
                e.append(f"{donde}: palabra demasiado larga «{texto}»")
        anuncios = g.get("anuncios") or []
        if not 1 <= len(anuncios) <= 3:
            e.append(f"{donde}: de 1 a 3 anuncios")
        for a_i, a in enumerate(anuncios, 1):
            d = f"{donde}, anuncio {a_i}"
            t, ds = a.get("titulos") or [], a.get("descripciones") or []
            if not TITULOS[0] <= len(t) <= TITULOS[1]:
                e.append(f"{d}: {len(t)} títulos (de {TITULOS[0]} a {TITULOS[1]})")
            if not DESCRIPCIONES[0] <= len(ds) <= DESCRIPCIONES[1]:
                e.append(f"{d}: {len(ds)} descripciones (de {DESCRIPCIONES[0]} a {DESCRIPCIONES[1]})")
            e += [f"{d}: título de {len(x)} caracteres (máx. {TITULOS[2]}): «{x}»" for x in t if len(x) > TITULOS[2]]
            e += [f"{d}: descripción de {len(x)} caracteres (máx. {DESCRIPCIONES[2]}): «{x}»"
                  for x in ds if len(x) > DESCRIPCIONES[2]]
            if len({x.lower() for x in t}) != len(t):
                e.append(f"{d}: títulos repetidos")
            if not str(a.get("url_final", "")).startswith("https://"):
                e.append(f"{d}: url_final debe empezar con https://")
            for r in ("ruta1", "ruta2"):
                if len(str(a.get(r) or "")) > RUTA:
                    e.append(f"{d}: {r} de más de {RUTA} caracteres")
    return e


def excel(spec: dict, salida: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    negrita, encabezado = Font(bold=True), PatternFill("solid", fgColor="DDE3F0")
    wb = Workbook()
    ws = wb.active
    ws.title = "Campaña"
    filas = [("Plataforma", "Google Ads · Red de Búsqueda"), ("Cuenta", spec.get("cuenta")),
             ("Nombre", spec.get("nombre")), ("Presupuesto diario (MXN)", spec.get("presupuesto_diario_mxn")),
             ("Inicio", spec.get("inicio")), ("Fin", spec.get("fin") or "Sin fecha de fin"),
             ("Estrategia de puja", spec.get("estrategia") or "MAXIMIZAR_CLICS"),
             ("CPC máximo (MXN)", spec.get("cpc_max_mxn") or "—"),
             ("Ubicaciones", ", ".join(spec.get("ubicaciones") or ["México (geoTargetConstants/2484)"])),
             ("Idiomas", ", ".join(spec.get("idiomas") or ["Español (languageConstants/1003)"])),
             ("Socios de búsqueda", "Sí" if spec.get("red_de_socios_de_busqueda") else "No"),
             ("Red de Display", "Sí" if spec.get("red_display") else "No"),
             ("Negativas de campaña", ", ".join(str(n if isinstance(n, str) else n.get("texto"))
                                                for n in spec.get("negativas_campana") or []) or "—"),
             ("Estatus al montar", "EN PAUSA (una persona la activa en Google Ads)")]
    for f in filas:
        ws.append(list(f))
    for c in ws["A"]:
        c.font = negrita
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 28, 80

    wk = wb.create_sheet("Palabras clave")
    wk.append(["Grupo", "Palabra clave", "Concordancia", "Tipo"])
    for g in spec.get("grupos") or []:
        for p in g.get("palabras_clave") or []:
            p = p if isinstance(p, dict) else {"texto": p, "concordancia": "FRASE"}
            wk.append([g.get("nombre"), p.get("texto"), p.get("concordancia", "FRASE"), "Positiva"])
        for n in g.get("negativas") or []:
            n = n if isinstance(n, dict) else {"texto": n, "concordancia": "AMPLIA"}
            wk.append([g.get("nombre"), n.get("texto"), n.get("concordancia", "AMPLIA"), "Negativa"])

    wa = wb.create_sheet("Anuncios")
    wa.append(["Grupo", "Anuncio", "Tipo", "Texto", "Caracteres", "Límite"])
    for g in spec.get("grupos") or []:
        for a_i, a in enumerate(g.get("anuncios") or [], 1):
            for t in a.get("titulos") or []:
                wa.append([g.get("nombre"), a_i, "Título", t, len(t), TITULOS[2]])
            for t in a.get("descripciones") or []:
                wa.append([g.get("nombre"), a_i, "Descripción", t, len(t), DESCRIPCIONES[2]])
            wa.append([g.get("nombre"), a_i, "URL final", a.get("url_final"), "", ""])
            ruta = "/".join(x for x in (a.get("ruta1"), a.get("ruta2")) if x)
            if ruta:
                wa.append([g.get("nombre"), a_i, "Ruta visible", ruta, len(ruta), RUTA * 2])
    for hoja, anchos in ((wk, (28, 45, 16, 12)), (wa, (28, 9, 14, 95, 12, 8))):
        for celda in hoja[1]:
            celda.font, celda.fill = negrita, encabezado
        for i, ancho in enumerate(anchos):
            hoja.column_dimensions["ABCDEF"[i]].width = ancho
        for fila in hoja.iter_rows(min_row=2):
            for celda in fila:
                celda.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(salida)


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        spec = json.load(f)
    errores = validar(spec)
    if errores:
        print("ERRORES:\n- " + "\n- ".join(errores))
        sys.exit(1)
    excel(spec, sys.argv[2])
    anuncios = sum(len(g.get("anuncios") or []) for g in spec["grupos"])
    palabras = sum(len(g.get("palabras_clave") or []) for g in spec["grupos"])
    print(f"OK · {len(spec['grupos'])} grupos · {palabras} palabras clave · {anuncios} anuncios · "
          f"${float(spec['presupuesto_diario_mxn']):,.2f} MXN diarios → {sys.argv[2]}")


if __name__ == "__main__":
    main()

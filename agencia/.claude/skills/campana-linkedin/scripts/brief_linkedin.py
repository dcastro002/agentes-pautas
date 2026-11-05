#!/usr/bin/env python3
"""Valida una campaña de LinkedIn (JSON) y genera su brief en Excel para revisión humana.

Uso:
    python3 .claude/skills/campana-linkedin/scripts/brief_linkedin.py <campana.json> <salida.xlsx>

Sale con código 1 y la lista de errores si algo no cumple. Los avisos (texto o título más largos
de lo recomendado) no detienen. El JSON es el mismo que recibe la herramienta de montaje.
"""
import json
import sys
from datetime import date

OBJETIVOS = {"VISITAS_SITIO", "INTERACCION", "RECONOCIMIENTO"}
CTAS = {"LEARN_MORE", "SIGN_UP", "REGISTER", "DOWNLOAD", "SUBSCRIBE", "REQUEST_DEMO", "SEE_MORE", "APPLY",
        "JOIN", "ATTEND", "VIEW_QUOTE"}
FACETAS = {"ubicaciones", "cargos", "funciones", "seniority", "industrias", "tamano_empresa", "habilidades",
           "empresas", "idiomas_interfaz"}
TEXTO = (600, 150)    # máximo, recomendado
TITULO = (200, 70)
CTA_ES = {"LEARN_MORE": "Más información", "SIGN_UP": "Registrarse", "REGISTER": "Inscribirse",
          "DOWNLOAD": "Descargar", "SUBSCRIBE": "Suscribirse", "REQUEST_DEMO": "Solicitar demo",
          "SEE_MORE": "Ver más", "APPLY": "Postularse", "JOIN": "Unirse", "ATTEND": "Asistir", "VIEW_QUOTE": "Ver cotización"}


def validar(spec: dict) -> tuple[list[str], list[str]]:
    e, avisos = [], []
    for campo in ("cuenta", "nombre", "presupuesto_diario", "inicio", "anuncios"):
        if not spec.get(campo):
            e.append(f"Falta «{campo}»")
    if str(spec.get("objetivo") or "VISITAS_SITIO").upper() not in OBJETIVOS:
        e.append("objetivo: VISITAS_SITIO, INTERACCION o RECONOCIMIENTO")
    try:
        if float(spec.get("presupuesto_diario") or 0) <= 0:
            e.append("presupuesto_diario debe ser mayor a 0")
        if float((spec.get("puja") or {}).get("monto") or 0) <= 0:
            e.append("puja.monto: falta la puja")
    except ValueError:
        e.append("presupuesto o puja no son números")
    if str((spec.get("puja") or {}).get("tipo") or "CPC").upper() not in ("CPC", "CPM"):
        e.append("puja.tipo: CPC o CPM")
    try:
        inicio = date.fromisoformat(str(spec.get("inicio")))
        if inicio < date.today():
            e.append("inicio: la fecha ya pasó")
        if spec.get("fin") and date.fromisoformat(str(spec["fin"])) <= inicio:
            e.append("fin: debe ser posterior al inicio")
    except ValueError:
        e.append("Fechas en formato AAAA-MM-DD")
    seg = spec.get("segmentacion") or {}
    if not seg.get("ubicaciones"):
        e.append("segmentación: falta al menos una ubicación (urn:li:geo:…)")
    for bloque, donde in ((seg, "incluir"), (seg.get("excluir") or {}, "excluir")):
        for clave, valores in bloque.items():
            if clave == "excluir":
                continue
            if clave not in FACETAS:
                e.append(f"segmentación {donde}: «{clave}» no soportada")
            for v in valores or []:
                if not str(v).startswith("urn:li:"):
                    e.append(f"segmentación {donde}, {clave}: «{v}» no es un URN de LinkedIn")
    for i, a in enumerate(spec.get("anuncios") or [], 1):
        d = f"Anuncio {i}"
        texto, titulo = str(a.get("texto") or ""), str(a.get("titulo") or "")
        if not texto or len(texto) > TEXTO[0]:
            e.append(f"{d}: texto vacío o de más de {TEXTO[0]} caracteres")
        elif len(texto) > TEXTO[1]:
            avisos.append(f"{d}: texto de {len(texto)} caracteres; LinkedIn corta en ~{TEXTO[1]} con «ver más»")
        if not titulo or len(titulo) > TITULO[0]:
            e.append(f"{d}: título vacío o de más de {TITULO[0]} caracteres")
        elif len(titulo) > TITULO[1]:
            avisos.append(f"{d}: título de {len(titulo)} caracteres (recomendado hasta {TITULO[1]})")
        if not str(a.get("url") or "").startswith("https://"):
            e.append(f"{d}: url debe empezar con https://")
        if str(a.get("cta") or "LEARN_MORE").upper() not in CTAS:
            e.append(f"{d}: CTA no válido")
        if not (a.get("archivo") or a.get("imagen")):
            e.append(f"{d}: falta «archivo» (nombre exacto del PNG adjunto en Artes)")
    return e, avisos


def excel(spec: dict, salida: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    negrita, encabezado = Font(bold=True), PatternFill("solid", fgColor="DDE3F0")
    wb = Workbook()
    ws = wb.active
    ws.title = "Campaña"
    seg = spec.get("segmentacion") or {}
    filas = [("Plataforma", "LinkedIn Ads · Contenido patrocinado (imagen única)"), ("Cuenta", spec.get("cuenta")),
             ("Nombre", spec.get("nombre")), ("Objetivo", spec.get("objetivo") or "VISITAS_SITIO"),
             ("Presupuesto diario", spec.get("presupuesto_diario")),
             ("Puja", f"{(spec.get('puja') or {}).get('tipo', 'CPC')} {(spec.get('puja') or {}).get('monto', '')}"),
             ("Inicio", spec.get("inicio")), ("Fin", spec.get("fin") or "Sin fecha de fin"),
             ("Red de audiencia de LinkedIn", "Sí" if spec.get("red_de_audiencia") else "No"),
             ("Estatus al montar", "BORRADOR (una persona la lanza en Campaign Manager)")]
    for f in filas:
        ws.append(list(f))
    ws.append([])
    ws.append(["Segmentación", "Incluye (URN · nombre)"])
    nombres = spec.get("segmentacion_nombres") or {}
    for clave, valores in seg.items():
        if clave != "excluir":
            ws.append([clave, "\n".join(f"{v} · {nombres.get(v, '')}".rstrip(" ·") for v in valores or [])])
    for clave, valores in (seg.get("excluir") or {}).items():
        ws.append([f"excluir: {clave}", "\n".join(f"{v} · {nombres.get(v, '')}".rstrip(" ·") for v in valores or [])])
    for c in ws["A"]:
        c.font = negrita
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 30, 80

    wa = wb.create_sheet("Anuncios")
    wa.append(["#", "Texto introductorio", "Caracteres", "Título", "Caracteres", "Botón", "URL", "Arte"])
    for i, a in enumerate(spec.get("anuncios") or [], 1):
        cta = str(a.get("cta") or "LEARN_MORE").upper()
        wa.append([i, a.get("texto"), len(a.get("texto") or ""), a.get("titulo"), len(a.get("titulo") or ""),
                   CTA_ES.get(cta, cta), a.get("url"), a.get("archivo") or a.get("imagen")])
    for celda in wa[1]:
        celda.font, celda.fill = negrita, encabezado
    for i, ancho in enumerate((5, 70, 11, 40, 11, 18, 45, 30)):
        wa.column_dimensions["ABCDEFGH"[i]].width = ancho
    for fila in list(ws.iter_rows()) + list(wa.iter_rows(min_row=2)):
        for celda in fila:
            celda.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(salida)


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        spec = json.load(f)
    errores, avisos = validar(spec)
    for a in avisos:
        print("AVISO:", a)
    if errores:
        print("ERRORES:\n- " + "\n- ".join(errores))
        sys.exit(1)
    excel(spec, sys.argv[2])
    print(f"OK · {len(spec['anuncios'])} anuncios · {spec['presupuesto_diario']} diarios → {sys.argv[2]}")


if __name__ == "__main__":
    main()

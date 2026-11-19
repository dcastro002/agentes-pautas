#!/usr/bin/env python3
"""Llena la plantilla de brief de Meta (Excel) a partir de un JSON.

Uso:
  python3 llenar_brief.py <datos.json> <plantilla.xlsx> <salida.xlsx>

Plantilla: pestaña "Meta", formulario vertical (columna A = campo, B = valor).
- Escribe solo la columna B de las filas de CELDAS; borra antes los valores de ejemplo.
- Valida las listas desplegables leyendo las validaciones de la propia plantilla,
  así el script sigue funcionando si alguien agrega opciones en el Excel.
- La cuenta (B14) se elige de la lista de la plantilla buscando el ID de "cuenta".
- Los textos, títulos y descripciones (3 variantes) van numerados, uno por línea.
- La sección 7 (salida del agente) queda vacía: la llena el montaje.
- Si algo no es válido, no escribe nada y sale con código 1.
"""
import datetime
import json
import sys

try:
    import openpyxl
    from openpyxl.styles import Alignment
except ImportError:
    sys.exit("Falta openpyxl. Instálalo con: pip3 install --user openpyxl")

HOJA = "Meta"
CELDAS = {
    "cuenta": "B14", "nombre": "B17", "plataformas": "B18", "objetivo": "B19", "fin": "B20",
    "destino": "B23", "evento": "B24", "formulario_o_whatsapp": "B25", "conjuntos": "B26",
    "presupuesto_conjunto": "B27", "geo": "B28", "edad": "B29", "pistas_segmentacion": "B30",
    "ubicaciones": "B31", "segmentacion_final": "B32",
    "formato": "B35", "carpeta_assets": "B36", "instrucciones_artes": "B37", "texto_imagen": "B38",
    "variantes": "B39", "artes": "B40",
    "instrucciones_copy": "B43", "textos": "B44", "titulos": "B45", "descripciones": "B46",
    "cta": "B47", "url": "B48", "kpi": "B51",
}
SALIDA = ["B54", "B55", "B56", "B57", "B58"]  # las llena el montaje
LISTAS = ("textos", "titulos", "descripciones", "artes")
OBLIGATORIOS = ["cuenta", "nombre", "plataformas", "objetivo", "destino", "presupuesto_conjunto", "geo", "edad",
                "ubicaciones", "segmentacion_final", "formato", "artes", "textos", "titulos", "cta", "url"]
MAX_TITULO, MAX_DESCRIPCION, TEXTO_VISIBLE = 40, 30, 125


def opciones_de(ws) -> dict[str, list[str]]:
    """Opciones de cada lista desplegable de la plantilla: {"B19": [...], ...}."""
    salida = {}
    for dv in ws.data_validations.dataValidation:
        if dv.type != "list" or not dv.formula1:
            continue
        formula = dv.formula1.strip()
        if formula.startswith("="):
            continue  # rangos con nombre: no se validan aquí
        texto = "".join(p.strip('"') for p in formula.split('"&"'))
        valores = [v.strip() for v in texto.strip('"').split(",") if v.strip()]
        for rango in str(dv.sqref).split():
            salida[rango.split(":")[0]] = valores
    return salida


def numerada(valores: list[str]) -> str:
    return "\n".join(f"{i}. {v}" for i, v in enumerate(valores, 1)) if len(valores) > 1 else valores[0]


def main(datos_p, plantilla_p, salida_p):
    d = json.load(open(datos_p, encoding="utf-8"))
    wb = openpyxl.load_workbook(plantilla_p)
    if HOJA not in wb.sheetnames:
        sys.exit(f'La plantilla no tiene la pestaña "{HOJA}".')
    ws = wb[HOJA]
    opciones = opciones_de(ws)
    errores, avisos = [], []

    for k in OBLIGATORIOS:
        v = d.get(k)
        if v in (None, "", 0, []):
            errores.append(f"Falta {k} ({CELDAS[k]})")

    # Cuenta: se toma la opción de la plantilla que contiene el ID
    cuenta = str(d.get("cuenta") or "").replace("act_", "").strip()
    valor_cuenta = None
    if cuenta:
        coincide = [o for o in opciones.get("B14", []) if cuenta in o.split()]
        if len(coincide) == 1:
            valor_cuenta = coincide[0]
        else:
            errores.append(f"La cuenta {cuenta} no está en la lista de la plantilla (B14). "
                           "Agrégala a la plantilla antes de registrar.")

    for k, celda in CELDAS.items():
        v = d.get(k)
        if k == "cuenta" or v in (None, "", []) or celda not in opciones:
            continue
        if v not in opciones[celda]:
            errores.append(f"{k} ({celda}) = {v!r} no es válido. Opciones: {opciones[celda]}")

    if d.get("objetivo") == "Conversiones" and not d.get("evento"):
        errores.append("El objetivo es Conversiones: falta el evento (B24)")
    if d.get("destino") in ("WhatsApp", "Formulario instantáneo") and not d.get("formulario_o_whatsapp"):
        errores.append("El destino es WhatsApp o formulario: falta el ID o número (B25)")
    try:
        if d.get("presupuesto_conjunto") not in (None, "") and float(d["presupuesto_conjunto"]) <= 0:
            errores.append("presupuesto_conjunto debe ser mayor a 0 (B27)")
    except (TypeError, ValueError):
        errores.append("presupuesto_conjunto debe ser un número (B27)")
    fin = None
    if d.get("fin"):
        for formato in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                fin = datetime.datetime.strptime(d["fin"], formato)
                break
            except ValueError:
                pass
        if not fin:
            errores.append("fin debe tener formato AAAA-MM-DD o AAAA-MM-DD HH:MM (B20)")
    if d.get("url") and not str(d["url"]).startswith("https://"):
        errores.append("La URL de destino debe empezar con https:// (B48)")

    for k in LISTAS:
        v = d.get(k)
        if v not in (None, "", []) and not (isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)):
            errores.append(f"{k} ({CELDAS[k]}) debe ser una lista de textos")
    for t in d.get("titulos") or []:
        if isinstance(t, str) and len(t) > MAX_TITULO:
            errores.append(f"Título de {len(t)} caracteres (máximo {MAX_TITULO}): {t!r}")
    for t in d.get("descripciones") or []:
        if isinstance(t, str) and len(t) > MAX_DESCRIPCION:
            errores.append(f"Descripción de {len(t)} caracteres (máximo {MAX_DESCRIPCION}): {t!r}")
    for t in d.get("textos") or []:
        if isinstance(t, str) and len(t) > TEXTO_VISIBLE:
            avisos.append(f"Texto principal de {len(t)} caracteres: después de ~{TEXTO_VISIBLE} se corta en 'Ver más'")

    if errores:
        print("NO SE GENERÓ EL BRIEF:")
        for e in errores:
            print(" -", e)
        sys.exit(1)

    for celda in list(CELDAS.values()) + SALIDA:
        ws[celda].value = None
    for k, celda in CELDAS.items():
        v = d.get(k)
        if v in (None, "", []):
            continue
        if k == "cuenta":
            v = valor_cuenta
        elif k == "fin":
            v = fin
            ws[celda].number_format = "yyyy-mm-dd hh:mm" if fin.hour or fin.minute else "yyyy-mm-dd"
        elif k in LISTAS:
            v = numerada(v)
            ws[celda].alignment = Alignment(wrap_text=True, vertical="top")
        elif k == "presupuesto_conjunto":
            v = float(v)
        ws[celda].value = v
    wb.save(salida_p)

    # Verificar leyendo como lo hará el agente de pautas
    chk = openpyxl.load_workbook(salida_p, data_only=True)[HOJA]
    print("Brief generado:", salida_p)
    for k, celda in CELDAS.items():
        if chk[celda].value not in (None, ""):
            print(f"  {celda} {k}: {str(chk[celda].value).replace(chr(10), ' | ')}")
    for a in avisos:
        print("  AVISO:", a)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])

#!/usr/bin/env python3
"""Renderiza un HTML a PNG con medidas exactas usando Chrome sin ventana.

Uso:
  python3 render_png.py <pieza.html> <salida.png> <ancho> <alto>

Chrome en modo headless recorta la parte baja de la página (deja una franja
blanca), así que se renderiza más alto y luego se recorta al tamaño exacto.
Ruta de Chrome: variable CHROME o la de macOS por defecto.
"""
import os, subprocess, sys, tempfile

try:
    from PIL import Image
except ImportError:
    sys.exit("Falta Pillow. Instálalo con: pip3 install --user Pillow")

CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def main(html, png, w, h):
    w, h = int(w), int(h)
    html = os.path.abspath(html)
    if not os.path.exists(CHROME):
        sys.exit(f"No encontré Chrome en {CHROME}. Define la variable CHROME con la ruta correcta.")
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=1", f"--window-size={w},{h + 400}",
           "--virtual-time-budget=5000", f"--screenshot={tmp}", "file://" + html]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        cmd.insert(1, "--no-sandbox")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    if not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
        sys.exit("Chrome no generó la imagen.")
    im = Image.open(tmp)
    if im.width < w or im.height < h:
        sys.exit(f"La captura salió de {im.size}, menor a {w}x{h}.")
    im.crop((0, 0, w, h)).convert("RGB").save(png, "PNG")
    os.remove(tmp)
    print(f"PNG generado: {png} ({w}x{h})")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])

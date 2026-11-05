#!/usr/bin/env python3
"""Busca tokens y llaves en los archivos que git tiene registrados. Sale con 1 si encuentra algo.

Se corre en GitHub Actions en cada push y PR, y se puede correr a mano antes de un commit:
    python3 scripts/revisar_secretos.py
Para revisar también todo el historial de commits (una vez, al configurar el repo):
    python3 scripts/revisar_secretos.py --historial
No imprime el valor encontrado completo, solo el archivo, la línea y el tipo.
"""
import re
import subprocess
import sys

PATRONES = {
    "Token de Meta": r"\bEAA[A-Za-z0-9]{40,}",
    "Token de Slack": r"\bxox[abprs]-[0-9A-Za-z-]{20,}|\bxapp-[0-9]-[0-9A-Za-z-]{20,}",
    "API key de Anthropic": r"\bsk-ant-[A-Za-z0-9_-]{20,}",
    "Secreto OAuth de Google": r"\bGOCSPX-[A-Za-z0-9_-]{20,}",
    "Refresh token de Google": r"\b1//0[0-9A-Za-z_-]{30,}",
    "Access token de Google": r"\bya29\.[0-9A-Za-z_-]{30,}",
    "Token de LinkedIn": r"\bAQ[VWX][A-Za-z0-9_-]{100,}",
    "Token de Monday (JWT)": r"\beyJhbGciOi[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}",
    "Llave privada": r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----",
    "Token de GitHub": r"\bgh[pousr]_[A-Za-z0-9]{36,}|\bgithub_pat_[A-Za-z0-9_]{40,}",
    "Llave de AWS": r"\bAKIA[0-9A-Z]{16}\b",
}
ASIGNACION = re.compile(r"^\s*(?:export\s+)?([A-Z0-9_]*(?:TOKEN|SECRET|KEY|PASSWORD))\s*=\s*['\"]?([^'\"\s#]{12,})")
PERMITIDOS = {"xoxb-sin-configurar"}


def archivos() -> list[str]:
    salida = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    return [f for f in salida.decode().split("\0") if f]


def revisar_historial(compilados: dict) -> list[str]:
    texto = subprocess.run(["git", "log", "-p", "--all", "--no-color"], capture_output=True).stdout.decode(errors="ignore")
    hallazgos, commit = [], ""
    for linea in texto.splitlines():
        if linea.startswith("commit "):
            commit = linea.split()[1][:8]
        if not linea.startswith("+") or linea.startswith("+++"):
            continue
        for tipo, patron in compilados.items():
            m = patron.search(linea)
            if m and m.group(0) not in PERMITIDOS:
                hallazgos.append(f"commit {commit} · {tipo} ({m.group(0)[:6]}…)")
    return hallazgos


def main() -> None:
    hallazgos = []
    compilados = {k: re.compile(v) for k, v in PATRONES.items()}
    if "--historial" in sys.argv:
        hallazgos = revisar_historial(compilados)
        if hallazgos:
            print("Hay secretos en el historial de git. ROTA esos valores (generar nuevos y revocar los viejos):")
            print("\n".join(f"- {h}" for h in sorted(set(hallazgos))))
            sys.exit(1)
        print("Sin secretos en el historial.")
        return
    for ruta in archivos():
        if ruta.endswith((".png", ".jpg", ".jpeg", ".gif", ".xlsx", ".pdf", ".zip", ".ico")):
            continue
        try:
            lineas = open(ruta, encoding="utf-8", errors="ignore").read().splitlines()
        except (IsADirectoryError, FileNotFoundError):
            continue
        for n, linea in enumerate(lineas, 1):
            for tipo, patron in compilados.items():
                m = patron.search(linea)
                if m and m.group(0) not in PERMITIDOS:
                    hallazgos.append(f"{ruta}:{n} · {tipo} ({m.group(0)[:6]}…)")
            a = ASIGNACION.search(linea)
            if a and ruta != ".env.example" and not ruta.startswith("tests/"):
                hallazgos.append(f"{ruta}:{n} · posible secreto asignado a {a.group(1)}")
    if hallazgos:
        print("Se encontraron posibles secretos. Quítalos del repo y ROTA esos valores (ya quedaron en el historial):")
        print("\n".join(f"- {h}" for h in hallazgos))
        sys.exit(1)
    print(f"Sin secretos en {len(archivos())} archivos.")


if __name__ == "__main__":
    main()

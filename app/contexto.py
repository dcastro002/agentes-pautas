"""Contexto de una ejecución del agente: quién la pidió y si hay aprobación humana vigente."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Contexto:
    conv_id: str
    canal: str
    thread_ts: str
    usuario: str                 # ID de Slack de quien pidió, o "monday:<id>"
    aprobado: bool = False       # True solo en la ejecución que sigue a un "Aprobar" (o a un disparo de Monday)
    aprobado_por: str = ""
    item_monday: str = ""
    slack: Any = None            # cliente de Slack (AsyncWebClient) o None en pruebas
    escrituras: list[str] = field(default_factory=list)  # registro de lo que se escribió

    def puede_escribir(self) -> tuple[bool, str]:
        if not self.aprobado:
            return False, ("BLOQUEADO: esta acción necesita aprobación humana. Presenta el plan, "
                           "termina tu mensaje con [[APROBACION]] y espera a que la persona apruebe.")
        return True, ""

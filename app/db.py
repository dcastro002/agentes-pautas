"""Bitácora: conversaciones, ejecuciones (con tokens y costo) y eventos por agente."""
import datetime as dt
import json

from sqlalchemy import (Boolean, Column, DateTime, Float, Integer, MetaData, String, Table, Text,
                        create_engine, desc, func, insert, select, update)

from . import config

metadata = MetaData()

conversaciones = Table(
    "conversaciones", metadata,
    Column("id", String(80), primary_key=True),        # "<canal>:<thread_ts>"
    Column("canal", String(40)),
    Column("thread_ts", String(40)),
    Column("usuario", String(80)),                      # ID de Slack, o "monday:<id>"
    Column("session_id", String(80)),
    Column("estado", String(30), default="nuevo"),      # trabajando | esperando_aprobacion | terminado | error
    Column("aprobacion_vigente", Boolean, default=False),
    Column("aprobado_por", String(80)),
    Column("titulo", Text),
    Column("item_monday", String(40)),
    Column("creado", DateTime),
    Column("actualizado", DateTime),
)

ejecuciones = Table(
    "ejecuciones", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversacion_id", String(80)),
    Column("inicio", DateTime),
    Column("fin", DateTime),
    Column("estado", String(30)),
    Column("costo_usd", Float, default=0.0),
    Column("input_tokens", Integer, default=0),
    Column("output_tokens", Integer, default=0),
    Column("cache_read_tokens", Integer, default=0),
    Column("cache_write_tokens", Integer, default=0),
    Column("turnos", Integer, default=0),
    Column("uso_por_modelo", Text),
    Column("error", Text),
)

eventos = Table(
    "eventos", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ts", DateTime),
    Column("conversacion_id", String(80)),
    Column("agente", String(60)),
    Column("tipo", String(40)),
    Column("detalle", Text),
)

_engine = None


def ahora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(config.DATABASE_URL, future=True, pool_pre_ping=True)
        metadata.create_all(_engine)
    return _engine


def obtener_conversacion(conv_id: str) -> dict | None:
    with engine().connect() as c:
        fila = c.execute(select(conversaciones).where(conversaciones.c.id == conv_id)).mappings().first()
        return dict(fila) if fila else None


def guardar_conversacion(conv_id: str, **campos) -> dict:
    campos["actualizado"] = ahora()
    with engine().begin() as c:
        existe = c.execute(select(conversaciones.c.id).where(conversaciones.c.id == conv_id)).first()
        if existe:
            c.execute(update(conversaciones).where(conversaciones.c.id == conv_id).values(**campos))
        else:
            campos.setdefault("creado", ahora())
            c.execute(insert(conversaciones).values(id=conv_id, **campos))
    return obtener_conversacion(conv_id)


def iniciar_ejecucion(conv_id: str) -> int:
    with engine().begin() as c:
        r = c.execute(insert(ejecuciones).values(conversacion_id=conv_id, inicio=ahora(), estado="trabajando"))
        return r.inserted_primary_key[0]


def cerrar_ejecucion(ejec_id: int, estado: str, costo: float | None, uso: dict | None,
                     turnos: int | None, uso_modelo: dict | None, error: str | None = None) -> None:
    uso = uso or {}
    with engine().begin() as c:
        c.execute(update(ejecuciones).where(ejecuciones.c.id == ejec_id).values(
            fin=ahora(), estado=estado, costo_usd=costo or 0.0,
            input_tokens=int(uso.get("input_tokens") or 0),
            output_tokens=int(uso.get("output_tokens") or 0),
            cache_read_tokens=int(uso.get("cache_read_input_tokens") or 0),
            cache_write_tokens=int(uso.get("cache_creation_input_tokens") or 0),
            turnos=turnos or 0,
            uso_por_modelo=json.dumps(uso_modelo or {}, default=str),
            error=(error or "")[:4000],
        ))


def evento(conv_id: str, agente: str, tipo: str, detalle: str = "") -> None:
    with engine().begin() as c:
        c.execute(insert(eventos).values(ts=ahora(), conversacion_id=conv_id, agente=agente,
                                         tipo=tipo, detalle=(detalle or "")[:1000]))


def estado_oficina() -> dict:
    """Datos para el panel de la oficina."""
    hoy = ahora().replace(hour=0, minute=0, second=0, microsecond=0)
    mes = hoy.replace(day=1)
    with engine().connect() as c:
        def costo_desde(desde):
            return float(c.execute(select(func.coalesce(func.sum(ejecuciones.c.costo_usd), 0.0))
                                   .where(ejecuciones.c.inicio >= desde)).scalar() or 0.0)

        def tokens_desde(desde):
            fila = c.execute(select(
                func.coalesce(func.sum(ejecuciones.c.input_tokens), 0),
                func.coalesce(func.sum(ejecuciones.c.output_tokens), 0),
                func.coalesce(func.sum(ejecuciones.c.cache_read_tokens), 0),
                func.coalesce(func.sum(ejecuciones.c.cache_write_tokens), 0),
            ).where(ejecuciones.c.inicio >= desde)).first()
            return {"entrada": int(fila[0]), "salida": int(fila[1]), "cache_lectura": int(fila[2]),
                    "cache_escritura": int(fila[3])}

        convs = [dict(r) for r in c.execute(select(conversaciones).order_by(desc(conversaciones.c.actualizado))
                                            .limit(30)).mappings()]
        evs = [dict(r) for r in c.execute(select(eventos).order_by(desc(eventos.c.id)).limit(60)).mappings()]
        ejs = [dict(r) for r in c.execute(select(ejecuciones).order_by(desc(ejecuciones.c.id)).limit(30)).mappings()]
        return {
            "generado": ahora().isoformat() + "Z",
            "modo_prueba": config.MODO_PRUEBA,
            "costo_hoy_usd": round(costo_desde(hoy), 4),
            "costo_mes_usd": round(costo_desde(mes), 4),
            "tokens_hoy": tokens_desde(hoy),
            "tokens_mes": tokens_desde(mes),
            "conversaciones": convs,
            "eventos": evs,
            "ejecuciones": ejs,
        }

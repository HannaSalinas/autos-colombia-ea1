"""Datos de demostración (ficticios) para el historial y el reporte de ocupación.

NO se ejecuta al arrancar. Requiere las semillas (python -m app.seed) y una base sin estancias.
Uso:  docker compose exec backend python -m app.demo
Para volver a la base limpia:  docker compose down -v && docker compose up -d

Crea estancias cerradas de los últimos 7 días (varias por placa, con correcciones y novedades)
y unas 5 estancias abiertas. Un vehículo solo tiene estancias en días con mensualidad vigente.
"""

import random
import sys
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_engine
from app.domain.reglas import ZONA_BOGOTA, mensualidad_vigente, orden_de_asignacion, tipo_celda_para
from app.models import Celda, CorreccionCelda, Estancia, Mensualidad, Novedad, Operador, Vehiculo

DIAS_DE_HISTORIAL = 7
ABIERTAS = ["ABC123", "KLM45D", "GHI789", "JKL321", "STU852"]   # todas con mensualidad vigente hoy
MOTIVOS = ["El conductor parqueó en la celda de al lado.", "La celda asignada tenía un obstáculo.",
           "El vehículo no cabía bien y se movió.", "Error del conductor al leer el número de la celda."]
NOVEDADES = {
    "RAYON": ["Rayón en la puerta del conductor.", "Rayón leve en el bómper trasero."],
    "GOLPE": ["Golpe pequeño en el guardabarros.", "Abolladura en la tapa del baúl."],
    "OBJETO_OLVIDADO": ["Llaves olvidadas en la portería.", "Celular encontrado junto a la celda."],
    "OTRO": ["Llanta baja al ingresar.", "Luces encendidas: se avisó al cliente."],
}


def _en_bogota(dia: date, hora: int, minuto: int) -> datetime:
    return datetime.combine(dia, time(hora, minuto), ZONA_BOGOTA)


def generar(session: Session, ahora: datetime, semilla: int = 20261025) -> dict[str, int]:
    if session.scalar(select(func.count()).select_from(Estancia)):
        raise RuntimeError("La base ya tiene estancias. Para repetir la demostración vuelve a la base "
                           "limpia: docker compose down -v && docker compose up -d")
    vehiculos = list(session.scalars(select(Vehiculo).order_by(Vehiculo.placa)))
    operadores = list(session.scalars(select(Operador).order_by(Operador.id)))
    if not set(ABIERTAS) <= {v.placa for v in vehiculos} or len(operadores) < 2:
        raise RuntimeError("Faltan las semillas. Ejecuta primero: python -m app.seed")
    celdas = {tipo: list(session.scalars(select(Celda).where(Celda.tipo == tipo).order_by(Celda.codigo)))
              for tipo in ("CARRO", "MOTO")}
    mensualidades: dict[int, list[Mensualidad]] = {}
    for m in session.scalars(select(Mensualidad)):
        mensualidades.setdefault(m.vehiculo_id, []).append(m)

    def vigente(vehiculo: Vehiculo, dia: date) -> bool:
        return any(mensualidad_vigente(m.fecha_inicio, m.fecha_fin, dia) for m in mensualidades.get(vehiculo.id, []))

    rnd = random.Random(semilla)
    hoy = ahora.astimezone(ZONA_BOGOTA).date()
    creados = {"estancias_cerradas": 0, "estancias_abiertas": 0, "correcciones": 0, "novedades": 0}

    def liberar(celda: Celda, momento: datetime) -> None:
        """La celda queda libre desde 'momento' (se guarda el más reciente)."""
        if celda.disponible_desde is None or momento > celda.disponible_desde:
            celda.disponible_desde = momento

    def novedad(estancia: Estancia, desde: datetime, hasta: datetime) -> None:
        tipo = rnd.choice(list(NOVEDADES))
        momento = desde + (hasta - desde) * rnd.random()
        session.add(Novedad(estancia_id=estancia.id, operador_id=rnd.choice(operadores).id, fecha=momento,
                            tipo=tipo, descripcion=rnd.choice(NOVEDADES[tipo])))
        creados["novedades"] += 1

    def corregir(estancia: Estancia, anterior: Celda, nueva: Celda, momento: datetime) -> None:
        session.add(CorreccionCelda(estancia_id=estancia.id, celda_anterior_id=anterior.id, celda_nueva_id=nueva.id,
                                    operador_id=rnd.choice(operadores).id, fecha=momento, motivo=rnd.choice(MOTIVOS)))
        estancia.celda_id = nueva.id
        liberar(anterior, momento)
        creados["correcciones"] += 1

    # 1) Historial: estancias cerradas de los últimos días. Cada vehículo, como máximo una por día,
    #    y cada día con celdas distintas para que nunca coincidan dos vehículos en la misma celda.
    for atras in range(DIAS_DE_HISTORIAL, 0, -1):
        dia = hoy - timedelta(days=atras)
        usadas = {"CARRO": 0, "MOTO": 0}
        for vehiculo in vehiculos:
            if not vigente(vehiculo, dia) or rnd.random() > 0.75:
                continue
            tipo = tipo_celda_para(vehiculo.tipo)
            lista = celdas[tipo]
            inicio = (atras * 3 + usadas[tipo]) % len(lista)   # reparte el uso entre todas las celdas
            usadas[tipo] += 2                                  # deja una libre por si hay corrección
            celda = lista[inicio]
            entrada = _en_bogota(dia, rnd.randint(6, 15), rnd.choice([0, 10, 25, 40, 55]))
            salida = min(entrada + timedelta(minutes=rnd.randint(45, 9 * 60)), _en_bogota(dia, 21, 30))
            estancia = Estancia(vehiculo_id=vehiculo.id, celda_id=celda.id, entrada=entrada, salida=salida,
                                operador_entrada_id=rnd.choice(operadores).id,
                                operador_salida_id=rnd.choice(operadores).id)
            session.add(estancia)
            session.flush()
            creados["estancias_cerradas"] += 1
            final = celda
            if rnd.random() < 0.25:
                final = lista[(inicio + 1) % len(lista)]
                corregir(estancia, celda, final, entrada + timedelta(minutes=rnd.randint(5, 20)))
            if rnd.random() < 0.3:
                novedad(estancia, entrada, salida)
            liberar(final, salida)
    session.flush()

    # 2) Vehículos dentro ahora: la celda se elige con el mismo orden del sistema
    #    (libre, del tipo correcto y la que lleva más tiempo libre). Las entradas se
    #    generan en orden cronológico, como ocurrirían en las porterías.
    ocupadas: set[int] = set()
    por_placa = {v.placa: v for v in vehiculos}
    entradas = sorted(ahora - timedelta(minutes=rnd.randint(20, 300)) for _ in ABIERTAS)
    for n, (placa, entrada) in enumerate(zip(ABIERTAS, entradas)):
        vehiculo = por_placa[placa]
        tipo = tipo_celda_para(vehiculo.tipo)
        libres = [c for c in celdas[tipo] if c.id not in ocupadas]
        celda = min(libres, key=lambda c: orden_de_asignacion(c.disponible_desde, c.codigo))
        ocupadas.add(celda.id)
        estancia = Estancia(vehiculo_id=vehiculo.id, celda_id=celda.id, entrada=entrada,
                            operador_entrada_id=operadores[n % 2].id)
        session.add(estancia)
        session.flush()
        creados["estancias_abiertas"] += 1
        if n == 1:   # una novedad y una corrección también en estancias abiertas
            novedad(estancia, entrada, ahora)
        if n == 3:
            nueva = next(c for c in celdas[tipo] if c.id not in ocupadas and c.disponible_desde is None)
            # La corrección ocurre antes de la siguiente entrada, que ya puede usar la celda liberada.
            momento = min(entrada + timedelta(minutes=10), entradas[n + 1] - timedelta(minutes=1))
            corregir(estancia, celda, nueva, momento)
            ocupadas.add(nueva.id)
            ocupadas.discard(celda.id)
    session.flush()
    return creados


def main() -> int:
    try:
        with Session(get_engine()) as session, session.begin():
            creados = generar(session, datetime.now(timezone.utc))
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print("Datos de demostración creados: " + ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in creados.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

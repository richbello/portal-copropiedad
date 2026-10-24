"""Días hábiles en Colombia (festivos según Ley 51 de 1983 - 'Ley Emiliani')."""
from datetime import date, timedelta
from functools import lru_cache


def _pascua(anio: int) -> date:
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)


def _al_lunes(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday()) % 7)


@lru_cache(maxsize=32)
def festivos(anio: int) -> frozenset[date]:
    fijos = [date(anio, 1, 1), date(anio, 5, 1), date(anio, 7, 20),
             date(anio, 8, 7), date(anio, 12, 8), date(anio, 12, 25)]
    trasladables = [date(anio, 1, 6), date(anio, 3, 19), date(anio, 6, 29), date(anio, 8, 15),
                    date(anio, 10, 12), date(anio, 11, 1), date(anio, 11, 11)]
    p = _pascua(anio)
    semana_santa = [p - timedelta(days=3), p - timedelta(days=2)]
    religiosos = [p + timedelta(days=39), p + timedelta(days=60), p + timedelta(days=68)]
    todos = fijos + semana_santa + [_al_lunes(d) for d in trasladables + religiosos]
    return frozenset(todos)


def es_habil(d: date) -> bool:
    return d.weekday() < 5 and d not in festivos(d.year)


def sumar_dias_habiles(inicio: date, dias: int) -> date:
    d = inicio
    contados = 0
    while contados < dias:
        d += timedelta(days=1)
        if es_habil(d):
            contados += 1
    return d


def dias_habiles_entre(inicio: date, fin: date) -> int:
    """Días hábiles transcurridos desde inicio (exclusive) hasta fin (inclusive). Negativo si fin < inicio."""
    if fin < inicio:
        return -dias_habiles_entre(fin, inicio)
    n, d = 0, inicio
    while d < fin:
        d += timedelta(days=1)
        if es_habil(d):
            n += 1
    return n

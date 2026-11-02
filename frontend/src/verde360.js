// Integración con Verde360 (la app de Ciudad Verde).
// El portal se sigue abriendo igual por su enlace directo; cuando alguien llega
// desde Verde360 (?origen=verde360) se muestra el camino de regreso.
export const URL_VERDE360 = 'https://richbello.github.io/Ciudad_verde_360/'

export function vieneDeVerde360() {
  try {
    const q = new URLSearchParams(window.location.search)
    if (q.get('origen') === 'verde360') sessionStorage.setItem('origen', 'verde360')
    return sessionStorage.getItem('origen') === 'verde360' || /ciudad_verde_360/i.test(document.referrer)
  } catch { return false }
}

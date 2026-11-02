// Licencias de prueba (solo en el portal de demostración).
const CLAVE = 'portal_licencia'

export function licenciaGuardada() {
  try { return JSON.parse(localStorage.getItem(CLAVE) || 'null') } catch { return null }
}
export function guardarLicencia(l) {
  try { l ? localStorage.setItem(CLAVE, JSON.stringify(l)) : localStorage.removeItem(CLAVE) } catch { /* sin storage */ }
}

// Código que llega en el enlace (?licencia=...). Se quita de la barra de direcciones después de leerlo.
export function licenciaDelEnlace() {
  try {
    const q = new URLSearchParams(window.location.search)
    const c = q.get('licencia')
    if (c) {
      q.delete('licencia')
      const resto = q.toString()
      window.history.replaceState(null, '', window.location.pathname + (resto ? '?' + resto : ''))
    }
    return c
  } catch { return null }
}

// Lee (sin validar: eso lo hace el servidor) el conjunto y la fecha que trae el código, para mostrarlos
export function leerCodigo(codigo) {
  try {
    const b = codigo.split('.')[0].replace(/-/g, '+').replace(/_/g, '/')
    const txt = new TextDecoder().decode(Uint8Array.from(atob(b + '='.repeat((4 - b.length % 4) % 4)), ch => ch.charCodeAt(0)))
    const d = JSON.parse(txt)
    return { conjunto: d.c, vence: d.v }
  } catch { return null }
}

export function fechaCorta(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' })
}

export function diasRestantes(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  const hoy = new Date(); hoy.setHours(0, 0, 0, 0)
  return Math.round((new Date(y, m - 1, d) - hoy) / 86400000)
}

export function enlaceWhatsApp(numero, texto) {
  return `https://wa.me/${numero}?text=${encodeURIComponent(texto)}`
}

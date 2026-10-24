// Cliente de la API con token JWT
const TOKEN_KEY = 'portal_token'

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(t) {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch { /* sin storage */ }
}

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status }
}

async function request(method, path, body) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (body instanceof FormData) payload = body
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  const res = await fetch(path, { method, headers, body: payload })
  if (res.status === 401 && token) {
    setToken(null)
    window.dispatchEvent(new Event('sesion-expirada'))
  }
  if (!res.ok) {
    let msg = `Error ${res.status}`
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail : Array.isArray(j.detail) ? j.detail.map(d => d.msg).join('. ') : msg
    } catch { /* respuesta sin JSON */ }
    throw new ApiError(res.status, msg)
  }
  const tipo = res.headers.get('content-type') || ''
  return tipo.includes('application/json') ? res.json() : res
}

export const api = {
  get: p => request('GET', p),
  post: (p, b) => request('POST', p, b),
  put: (p, b) => request('PUT', p, b),
  patch: (p, b) => request('PATCH', p, b),
  del: p => request('DELETE', p),
}

// Descarga un archivo protegido (PDF, adjunto, plantilla)
export async function descargar(path, nombrePorDefecto = 'archivo') {
  const res = await request('GET', path)
  const blob = await res.blob()
  const cd = res.headers.get('content-disposition') || ''
  const m = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i)
  const nombre = m ? decodeURIComponent(m[1]) : nombrePorDefecto
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = nombre
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

// Formatos colombianos
const fmtPesos = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
export const pesos = v => fmtPesos.format(Number(v || 0))
export const fecha = v => v ? new Date(v.length === 10 ? v + 'T12:00:00' : v)
  .toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'
export const fechaHora = v => v ? new Date(v).toLocaleString('es-CO', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'

export const NOMBRES = {
  tipos: {
    dano_locativo: 'Daño locativo', reserva_zona_comun: 'Reserva de zona común', certificado: 'Certificado',
    queja: 'Queja o reclamo', derecho_peticion: 'Derecho de petición', solicitud_documentos: 'Solicitud de documentos',
    consulta: 'Consulta', otro: 'Otro',
  },
  estados: { radicada: 'Radicada', en_tramite: 'En trámite', respondida: 'Respondida', cerrada: 'Cerrada' },
  roles: {
    propietario: 'Propietario', residente: 'Residente', administrador: 'Administración', contador: 'Contador',
    consejo: 'Consejo de administración', revisor_fiscal: 'Revisor fiscal',
  },
  cargos: {
    administracion: 'Administración', extraordinaria: 'Extraordinaria', multa: 'Multa',
    interes_mora: 'Intereses de mora', parqueadero: 'Parqueadero', otro: 'Otro',
  },
  categorias: {
    acta_asamblea: 'Actas de asamblea', acta_consejo: 'Actas de consejo', presupuesto: 'Presupuesto',
    estados_financieros: 'Estados financieros', reglamento: 'Reglamento', circular: 'Circulares',
    contrato: 'Contratos', otro: 'Otros',
  },
}

export const esGestion = u => ['administrador', 'contador'].includes(u?.rol)
export const esLecturaGlobal = u => ['administrador', 'contador', 'consejo', 'revisor_fiscal'].includes(u?.rol)

// Fecha local (no UTC): en Bogotá, después de las 7 p.m. toISOString ya da el día siguiente
export const hoyLocal = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
export const mesLocal = () => hoyLocal().slice(0, 7)
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
export const nombrePeriodo = p => p ? `${MESES[Number(p.slice(5, 7)) - 1]} de ${p.slice(0, 4)}` : ''

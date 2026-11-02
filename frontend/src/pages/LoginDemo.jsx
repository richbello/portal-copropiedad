import { useState } from 'react'
import { api } from '../api'
import { diasRestantes, enlaceWhatsApp, fechaCorta, guardarLicencia, leerCodigo, licenciaDelEnlace, licenciaGuardada } from '../licencia'

// Ingreso del portal de demostración: con un código de licencia de prueba, como administración o como propietario.
export default function LoginDemo({ onIngreso, salud, conjunto, onUsuarioClave }) {
  const [codigo, setCodigo] = useState(() => licenciaDelEnlace() || licenciaGuardada()?.codigo || '')
  const [editar, setEditar] = useState(false)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState('')
  const info = codigo ? leerCodigo(codigo.trim()) : null
  const whatsapp = salud?.whatsapp || '573208303847'

  async function entrar(perfil) {
    setError(''); setEnviando(perfil)
    try {
      const r = await api.post('/api/auth/licencia', { codigo: codigo.trim(), perfil })
      guardarLicencia({ codigo: codigo.trim(), ...r.licencia, activa: true })
      onIngreso(r.access_token, r.usuario)
    } catch (err) { setError(err.message) }
    setEnviando('')
  }

  const dias = info?.vence ? diasRestantes(info.vence) : null
  const mostrarCampo = !info || editar

  return (
    <div className="ingreso">
      <section className="ingreso-arte">
        <div style={{ position: 'relative', fontFamily: 'var(--display)', fontSize: '1.15rem', opacity: 0.9 }}>{salud.demo ? 'Portal de copropiedad · Verde360' : `${conjunto} · red Verde360`}</div>
        <h1>Conozca por dentro el portal de su conjunto</h1>
        <p>Recórralo como administración y como propietario: cartera, paz y salvos, solicitudes con plazos de ley, censo, parqueaderos, presupuesto y comunicados.</p>
      </section>
      <section className="ingreso-form">
        <div className="panel formulario">
          <span className="sello-demo">Licencia de prueba</span>
          <h2 style={{ margin: 0 }}>{info ? `Bienvenido, ${info.conjunto}` : 'Ingresar a la demostración'}</h2>

          {info && !editar && (
            <p className="peq suave" style={{ margin: 0 }}>
              Su licencia {dias >= 0 ? <>es válida hasta el <strong>{fechaCorta(info.vence)}</strong> ({dias === 0 ? 'vence hoy' : `${dias} día${dias === 1 ? '' : 's'}`}).</> : <>venció el {fechaCorta(info.vence)}.</>}{' '}
              <button type="button" className="texto" onClick={() => setEditar(true)}>Usar otro código</button>
            </p>
          )}
          {mostrarCampo && (
            <label>Código de licencia
              <input value={codigo} onChange={e => setCodigo(e.target.value)} placeholder="Pegue aquí el código que le enviamos" autoComplete="off" spellCheck="false" />
            </label>
          )}

          <p className="peq suave" style={{ margin: 0 }}>¿Cómo quiere ver el portal?</p>
          <div className="perfiles-demo">
            <button type="button" disabled={!codigo.trim() || !!enviando} onClick={() => entrar('administrador')}>
              <strong>{enviando === 'administrador' ? 'Ingresando…' : 'Como administración'}</strong>
              <small>Tablero, cartera, facturación, censo y respuestas</small>
            </button>
            <button type="button" className="secundario" disabled={!codigo.trim() || !!enviando} onClick={() => entrar('propietario')}>
              <strong>{enviando === 'propietario' ? 'Ingresando…' : 'Como propietario'}</strong>
              <small>Estado de cuenta, paz y salvo y solicitudes</small>
            </button>
          </div>
          {error && <div className="aviso error" role="alert">{error}</div>}
          <div className="aviso info peq">{salud.solo_consulta
            ? 'Licencia de solo consulta: puede abrir todas las pantallas y descargar los documentos de ejemplo, pero no guardar cambios.'
            : 'Todos los nombres, apartamentos y valores son ficticios. Puede crear, editar y probar sin miedo: la demostración se restablece sola.'}</div>
          {salud.verde360 && <p className="peq suave" style={{ margin: 0 }}>Este portal hace parte de <a href={salud.verde360} target="_blank" rel="noopener">Verde360 · Ciudad Verde</a>, la plataforma de la ciudadela.</p>}
          <p className="peq suave" style={{ margin: 0 }}>
            {onUsuarioClave && <><button type="button" className="texto" onClick={onUsuarioClave}>Ingresar con usuario y clave</button> · </>}
            ¿No tiene código? <a href={enlaceWhatsApp(whatsapp, 'Hola, administro un conjunto y quiero una licencia de prueba del portal de copropiedad de Verde360.')} target="_blank" rel="noopener">Pídalo por WhatsApp</a>
          </p>
        </div>
      </section>
    </div>
  )
}

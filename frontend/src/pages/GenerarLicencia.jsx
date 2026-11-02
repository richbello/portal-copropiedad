import { useState } from 'react'
import { api } from '../api'
import { enlaceWhatsApp, fechaCorta } from '../licencia'

// Página interna para crear licencias de prueba (protegida con la CLAVE_MAESTRA del servidor).
export default function GenerarLicencia({ salud }) {
  const [clave, setClave] = useState(() => { try { return sessionStorage.getItem('clave_maestra') || '' } catch { return '' } })
  const [conjunto, setConjunto] = useState('')
  const [contacto, setContacto] = useState('')
  const [telefono, setTelefono] = useState('')
  const [dias, setDias] = useState(salud?.dias_licencia || 15)
  const [lic, setLic] = useState(null)
  const [error, setError] = useState('')
  const [copiado, setCopiado] = useState(false)

  async function generar(e) {
    e.preventDefault()
    setError(''); setLic(null); setCopiado(false)
    try {
      const r = await api.post('/api/auth/licencia/generar', { clave_maestra: clave, conjunto, contacto, dias: Number(dias) })
      try { sessionStorage.setItem('clave_maestra', clave) } catch { /* sin storage */ }
      setLic(r)
    } catch (err) { setError(err.message) }
  }

  const mensaje = lic && `Hola${contacto ? ' ' + contacto.split(' ')[0] : ''}, le comparto su licencia de prueba del portal de copropiedad de Verde360 para ${lic.conjunto}. ` +
    `Puede entrar como administración y como propietario hasta el ${fechaCorta(lic.vence)}:\n${lic.enlace}\n\nLos datos son ficticios; pruebe con confianza. Quedo atento a sus preguntas.`

  async function copiar() {
    try { await navigator.clipboard.writeText(mensaje); setCopiado(true) } catch { setCopiado(false) }
  }

  const tel = telefono.replace(/\D/g, '')
  const telCompleto = tel.length === 10 ? '57' + tel : tel

  return (
    <div className="ingreso">
      <section className="ingreso-arte">
        <div style={{ position: 'relative', fontFamily: 'var(--display)', fontSize: '1.15rem', opacity: 0.9 }}>Verde360 · uso interno</div>
        <h1>Licencias de prueba para administradores</h1>
        <p>Cada licencia da acceso al portal de demostración como administración y como propietario hasta la fecha que elija. Vence sola; no hay que borrar nada.</p>
      </section>
      <section className="ingreso-form">
        <form className="panel formulario" onSubmit={generar}>
          <h2 style={{ margin: 0 }}>Nueva licencia</h2>
          <label>Clave maestra
            <input type="password" required value={clave} onChange={e => setClave(e.target.value)} autoComplete="off" />
          </label>
          <label>Conjunto
            <input required value={conjunto} onChange={e => setConjunto(e.target.value)} placeholder="Ej.: Conjunto Azalea Ciudad Verde" />
          </label>
          <label>Nombre del administrador (opcional)
            <input value={contacto} onChange={e => setContacto(e.target.value)} />
          </label>
          <label>Celular para enviarla por WhatsApp (opcional)
            <input inputMode="tel" value={telefono} onChange={e => setTelefono(e.target.value)} placeholder="3001234567" />
          </label>
          <label>Días de prueba
            <select value={dias} onChange={e => setDias(e.target.value)}>
              {[7, 15, 30, 45, 60].map(d => <option key={d} value={d}>{d} días</option>)}
            </select>
          </label>
          {error && <div className="aviso error" role="alert">{error}</div>}
          <button>Generar licencia</button>

          {lic && (
            <div className="aviso ok" role="status">
              <strong>Licencia para {lic.conjunto}</strong><br />
              <span className="peq">Válida hasta el {fechaCorta(lic.vence)}</span>
              <textarea readOnly value={mensaje} rows={7} style={{ width: '100%', marginTop: 8 }} onFocus={e => e.target.select()} />
              <div className="fila" style={{ marginTop: 8 }}>
                <button type="button" onClick={copiar}>{copiado ? 'Copiado ✓' : 'Copiar mensaje'}</button>
                {telCompleto.length >= 11 && <a className="boton" href={enlaceWhatsApp(telCompleto, mensaje)} target="_blank" rel="noopener">Enviar por WhatsApp</a>}
              </div>
            </div>
          )}
        </form>
      </section>
    </div>
  )
}

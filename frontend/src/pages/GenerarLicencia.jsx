import { useState } from 'react'
import { api } from '../api'
import { enlaceWhatsApp, fechaCorta } from '../licencia'

// Página interna para crear licencias de prueba (protegida con la CLAVE_MAESTRA del servidor).
export default function GenerarLicencia({ salud, conjunto: portal }) {
  const [clave, setClave] = useState(() => { try { return sessionStorage.getItem('clave_maestra') || '' } catch { return '' } })
  const [conjunto, setConjunto] = useState('')
  const [contacto, setContacto] = useState('')
  const [telefono, setTelefono] = useState('')
  const [vence, setVence] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() + (salud?.dias_licencia || 15))
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  })
  const [lic, setLic] = useState(null)
  const [error, setError] = useState('')
  const [copiado, setCopiado] = useState(false)

  async function generar(e) {
    e.preventDefault()
    setError(''); setLic(null); setCopiado(false)
    try {
      const r = await api.post('/api/auth/licencia/generar', { clave_maestra: clave, conjunto, contacto, vence })
      try { sessionStorage.setItem('clave_maestra', clave) } catch { /* sin storage */ }
      setLic(r)
    } catch (err) { setError(err.message) }
  }

  const mensaje = lic && `Hola${contacto ? ' ' + contacto.split(' ')[0] : ''}, le comparto su licencia de prueba del portal de copropiedad de Verde360 (${lic.conjunto}).\n\n` +
    `1) Portal del conjunto (${portal}): puede entrar como administración y como propietario hasta el ${fechaCorta(lic.vence)}:\n${lic.enlace}\n\n` +
    (salud?.verde360 ? `2) Verde360, la plataforma de Ciudad Verde:\n${salud.verde360}\n\n` : '') +
    (salud?.solo_consulta ? 'La licencia es de solo consulta y los datos son de ejemplo. ' : 'Los datos son ficticios; pruebe con confianza. ') + 'Quedo atento a sus preguntas.'


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
        <p>Cada licencia da acceso a {portal} como administración y como propietario hasta la fecha que elija{salud?.solo_consulta ? ', en solo consulta' : ''}. Vence sola; no hay que borrar nada.</p>
      </section>
      <section className="ingreso-form">
        <form className="panel formulario" onSubmit={generar}>
          <h2 style={{ margin: 0 }}>Nueva licencia</h2>
          <label>Clave maestra
            <input type="password" required value={clave} onChange={e => setClave(e.target.value)} autoComplete="off" />
          </label>
          <label>Para quién (conjunto o grupo)
            <input required value={conjunto} onChange={e => setConjunto(e.target.value)} placeholder="Ej.: Conjunto Azalea Ciudad Verde" />
          </label>
          <label>Nombre del administrador (opcional)
            <input value={contacto} onChange={e => setContacto(e.target.value)} />
          </label>
          <label>Celular para enviarla por WhatsApp (opcional)
            <input inputMode="tel" value={telefono} onChange={e => setTelefono(e.target.value)} placeholder="3001234567" />
          </label>
          <label>Vence el (incluido, hasta las 11:59 p. m.)
            <input type="date" required value={vence} onChange={e => setVence(e.target.value)} />
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

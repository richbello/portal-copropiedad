import { useState } from 'react'
import { api } from '../api'
import { URL_VERDE360, vieneDeVerde360 } from '../verde360'

export default function Login({ onIngreso, conjunto, onLicencia }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [desdeVerde] = useState(vieneDeVerde360)

  async function enviar(e) {
    e.preventDefault()
    setError(''); setEnviando(true)
    try {
      const r = await api.post('/api/auth/login', { email, password })
      onIngreso(r.access_token, r.usuario)
    } catch (err) { setError(err.message) }
    setEnviando(false)
  }

  return (
    <div className="ingreso">
      <section className="ingreso-arte">
        <svg viewBox="0 0 400 300" aria-hidden="true" fill="#eef5f1">
          {[0, 1, 2].map(t => (
            <g key={t} transform={`translate(${t * 125} ${t === 1 ? 20 : 60})`}>
              <rect width="105" height={t === 1 ? 280 : 240} />
              {Array.from({ length: t === 1 ? 9 : 8 }).map((_, p) =>
                [0, 1, 2].map(v => <rect key={`${p}-${v}`} x={14 + v * 30} y={16 + p * 29} width="18" height="16" fill="#1f4d3a" />))}
            </g>
          ))}
        </svg>
        <div style={{ position: 'relative', fontFamily: 'var(--display)', fontSize: '1.15rem', opacity: 0.9 }}>{conjunto}</div>
        <h1>Su apartamento, sus cuentas y sus solicitudes en un solo lugar</h1>
        <p>Consulte su estado de cuenta, descargue su paz y salvo, radique solicitudes a la administración y revise en qué se gasta el presupuesto del conjunto.</p>
      </section>
      <section className="ingreso-form">
        <form className="panel formulario" onSubmit={enviar}>
          {desdeVerde && <a className="volver-verde" href={URL_VERDE360}>← Volver a Verde360</a>}
          <h2>Ingresar</h2>
          {desdeVerde && <p className="peq suave" style={{ marginTop: 0 }}>Propietarios, residentes y administración ingresan con el mismo formulario. Cada quien ve lo que le corresponde según su usuario.</p>}
          <label>Correo electrónico
            <input type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} />
          </label>
          <label>Contraseña
            <input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} />
          </label>
          {error && <div className="aviso error" role="alert">{error}</div>}
          <button disabled={enviando}>{enviando ? 'Ingresando…' : 'Ingresar'}</button>
          <p className="peq suave">¿No tiene usuario o olvidó su contraseña? Solicítelo en la administración; le entregarán una clave temporal.</p>
          {onLicencia && <p className="peq suave" style={{ margin: 0 }}>¿Le enviamos una licencia de prueba? <button type="button" className="texto" onClick={onLicencia}>Ingresar con el código</button></p>}
          <p className="peq suave red-verde">Parte de la red <a href={URL_VERDE360} target="_blank" rel="noopener">Verde360 · Ciudad Verde</a></p>
        </form>
      </section>
    </div>
  )
}

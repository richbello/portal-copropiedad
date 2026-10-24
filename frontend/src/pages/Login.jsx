import { useState } from 'react'
import { api } from '../api'

export default function Login({ onIngreso }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

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
        <h1>Su apartamento, sus cuentas y sus solicitudes en un solo lugar</h1>
        <p>Consulte su estado de cuenta, descargue su paz y salvo, radique solicitudes a la administración y revise en qué se gasta el presupuesto del conjunto.</p>
      </section>
      <section className="ingreso-form">
        <form className="panel formulario" onSubmit={enviar}>
          <h2>Ingresar</h2>
          <label>Correo electrónico
            <input type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} />
          </label>
          <label>Contraseña
            <input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} />
          </label>
          {error && <div className="aviso error" role="alert">{error}</div>}
          <button disabled={enviando}>{enviando ? 'Ingresando…' : 'Ingresar'}</button>
          <p className="peq suave">¿No tiene usuario o olvidó su contraseña? Solicítelo en la administración; le entregarán una clave temporal.</p>
        </form>
      </section>
    </div>
  )
}

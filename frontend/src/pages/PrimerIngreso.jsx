import { useState } from 'react'
import { api } from '../api'

export default function PrimerIngreso({ usuario, onListo, onSalir }) {
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [confirma, setConfirma] = useState('')
  const [acepta, setAcepta] = useState(false)
  const [error, setError] = useState('')

  async function enviar(e) {
    e.preventDefault()
    setError('')
    try {
      if (usuario.debe_cambiar_password) {
        if (nueva !== confirma) throw new Error('Las contraseñas nuevas no coinciden')
        await api.post('/api/auth/cambiar-password', { actual, nueva })
      }
      if (!usuario.acepto_tratamiento_datos) {
        if (!acepta) throw new Error('Debe aceptar la política de tratamiento de datos para continuar')
        await api.post('/api/auth/aceptar-tratamiento-datos')
      }
      onListo()
    } catch (err) { setError(err.message) }
  }

  return (
    <div className="ingreso-form" style={{ minHeight: '100vh' }}>
      <form className="panel formulario" style={{ maxWidth: 520 }} onSubmit={enviar}>
        <h2>Bienvenido, {usuario.nombre.split(' ')[0]}</h2>
        <p className="suave">Antes de continuar complete estos pasos. Solo se piden una vez.</p>
        {usuario.debe_cambiar_password && <>
          <h3>Cree su contraseña personal</h3>
          <label>Clave temporal que le entregó la administración
            <input type="password" required value={actual} onChange={e => setActual(e.target.value)} autoComplete="current-password" />
          </label>
          <label>Nueva contraseña<span className="ayuda">Mínimo 8 caracteres, con letras y números</span>
            <input type="password" required minLength={8} value={nueva} onChange={e => setNueva(e.target.value)} autoComplete="new-password" />
          </label>
          <label>Repita la nueva contraseña
            <input type="password" required value={confirma} onChange={e => setConfirma(e.target.value)} autoComplete="new-password" />
          </label>
        </>}
        {!usuario.acepto_tratamiento_datos && <>
          <h3>Tratamiento de datos personales</h3>
          <div className="aviso info peq">
            La copropiedad, como responsable del tratamiento, usará sus datos (nombre, documento, contacto, unidad y
            estado de cuenta) para administrar la propiedad horizontal, informarle sobre cuotas y responder sus
            solicitudes, conforme a la Ley 1581 de 2012. Usted puede conocer, actualizar, rectificar y suprimir sus
            datos radicando una solicitud en este portal. Sus datos de cartera no son visibles para otros propietarios.
          </div>
          <label style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, fontWeight: 400 }}>
            <input type="checkbox" style={{ width: 20, marginTop: 3 }} checked={acepta} onChange={e => setAcepta(e.target.checked)} />
            Autorizo el tratamiento de mis datos personales en los términos descritos.
          </label>
        </>}
        {error && <div className="aviso error" role="alert">{error}</div>}
        <div className="fila">
          <button>Continuar</button>
          <button type="button" className="secundario" onClick={onSalir}>Salir</button>
        </div>
      </form>
    </div>
  )
}

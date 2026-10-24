import { useState } from 'react'
import { api, fechaHora } from '../api'
import { Aviso, Encabezado, useDatos, useSesion } from '../App'

export default function AdminConfiguracion() {
  const { usuario } = useSesion()
  const { datos: params, recargar } = useDatos('/api/admin/parametros')
  const puedeAuditar = ['administrador', 'revisor_fiscal'].includes(usuario.rol)
  const { datos: aud } = useDatos(puedeAuditar ? '/api/admin/auditoria?limite=150' : null)

  return (
    <>
      <Encabezado titulo="Configuración y auditoría" />
      <section className="panel">
        <h2>Parámetros financieros</h2>
        <div className="pila">{(params || []).map(p => <Parametro key={p.clave} p={p} editable={usuario.rol === 'administrador'} onGuardado={recargar} />)}</div>
      </section>
      {puedeAuditar && <section className="panel">
        <h2>Registro de auditoría</h2>
        <p className="suave peq" style={{ marginBottom: 10 }}>Quién hizo qué y cuándo. Este registro no se puede editar desde el portal.</p>
        <div className="tabla-scroll"><table>
          <thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Detalle</th></tr></thead>
          <tbody>{(aud || []).map((a, i) => <tr key={i}>
            <td className="peq" style={{ whiteSpace: 'nowrap' }}>{fechaHora(a.fecha)}</td><td className="peq">{a.usuario || '—'}</td>
            <td className="peq">{a.accion.replaceAll('_', ' ')}</td><td className="peq">{a.detalle}</td></tr>)}
          </tbody>
        </table></div>
      </section>}
    </>
  )
}

function Parametro({ p, editable, onGuardado }) {
  const [valor, setValor] = useState(p.valor)
  const [msg, setMsg] = useState(null)
  async function guardar(e) {
    e.preventDefault()
    try { await api.put(`/api/admin/parametros/${p.clave}`, { valor }); setMsg({ tipo: 'ok', t: 'Guardado' }); onGuardado() }
    catch (err) { setMsg({ tipo: 'error', t: err.message }) }
  }
  return (
    <form onSubmit={guardar} className="formulario" style={{ paddingBottom: 12, borderBottom: '1px solid var(--linea)' }}>
      <label>{p.clave.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase())}<span className="ayuda">{p.descripcion}</span>
        <div className="fila" style={{ flexWrap: 'nowrap' }}>
          <input value={valor} onChange={e => setValor(e.target.value)} disabled={!editable} />
          {editable && <button disabled={valor === p.valor}>Guardar</button>}
        </div>
      </label>
      {msg && <Aviso tipo={msg.tipo}>{msg.t}</Aviso>}
    </form>
  )
}

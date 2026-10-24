import { useState } from 'react'
import { fecha, NOMBRES, pesos } from '../api'
import { Aviso, Encabezado, useDatos, useSesion } from '../App'
import Recibo from './Recibo'

export default function EstadoCuenta() {
  const { usuario } = useSesion()
  const [unidad, setUnidad] = useState(usuario.unidades[0]?.id)
  const { datos: ec, error } = useDatos(unidad ? `/api/unidades/${unidad}/estado-cuenta` : null)
  const [filtro, setFiltro] = useState('todos')

  if (!unidad) return <><Encabezado titulo="Estado de cuenta" /><p className="vacio">No tiene unidades asignadas.</p></>

  const movs = (ec?.movimientos || []).filter(m => filtro === 'todos' || m.tipo === filtro).slice().reverse()

  return (
    <>
      <Encabezado titulo="Estado de cuenta" descripcion="Cargos, pagos y saldo acumulado, del más reciente al más antiguo.">
        {usuario.unidades.length > 1 &&
          <select value={unidad} onChange={e => setUnidad(Number(e.target.value))} aria-label="Unidad">
            {usuario.unidades.map(u => <option key={u.id} value={u.id}>{u.etiqueta}</option>)}
          </select>}
      </Encabezado>
      <Aviso>{error}</Aviso>
      {ec && <>
        <Recibo ec={ec} />
        {ec.pendientes.length > 0 && (
          <section className="panel" style={{ marginTop: 16 }}>
            <h2>Qué está pendiente</h2>
            <p className="suave peq" style={{ marginBottom: 10 }}>Los pagos se aplican primero a lo más antiguo y, dentro de cada mes, primero a intereses.</p>
            <div className="tabla-scroll"><table>
              <thead><tr><th>Concepto</th><th>Venció</th><th className="derecha">Pendiente</th></tr></thead>
              <tbody>{ec.pendientes.map(p => (
                <tr key={p.cargo_id}><td>{p.concepto}</td><td>{fecha(p.vencimiento)}</td><td className="derecha">{pesos(p.pendiente)}</td></tr>))}
              </tbody>
            </table></div>
          </section>)}
        <section className="panel" style={{ marginTop: 16 }}>
          <div className="fila" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
            <h2 style={{ margin: 0 }}>Movimientos</h2>
            <div className="pestanas" style={{ margin: 0, border: 'none' }}>
              {[['todos', 'Todos'], ['cargo', 'Cargos'], ['pago', 'Pagos']].map(([k, n]) =>
                <button key={k} className={filtro === k ? 'activa' : ''} onClick={() => setFiltro(k)}>{n}</button>)}
            </div>
          </div>
          <div className="tabla-scroll"><table>
            <thead><tr><th>Fecha</th><th>Concepto</th><th className="derecha">Cargo</th><th className="derecha">Pago</th><th className="derecha">Saldo</th></tr></thead>
            <tbody>{movs.map(m => (
              <tr key={`${m.tipo}-${m.id}`}>
                <td style={{ whiteSpace: 'nowrap' }}>{fecha(m.fecha)}</td>
                <td>{m.concepto}{m.tipo === 'cargo' && <div className="peq suave">{NOMBRES.cargos[m.categoria]} · {m.periodo}</div>}</td>
                <td className="derecha">{m.debito ? pesos(m.debito) : ''}</td>
                <td className="derecha" style={{ color: 'var(--verde)' }}>{m.credito ? pesos(m.credito) : ''}</td>
                <td className="derecha"><strong>{pesos(m.saldo)}</strong></td>
              </tr>))}
            </tbody>
          </table></div>
        </section>
      </>}
    </>
  )
}

import { useState } from 'react'
import { api, esGestion, fecha, hoyLocal, pesos } from '../api'
import { Aviso, Encabezado, Modal, useDatos, useSesion } from '../App'

export default function Presupuesto() {
  const { usuario } = useSesion()
  const anio = new Date().getFullYear()
  const [vigencia, setVigencia] = useState(anio)
  const { datos: p, error, recargar } = useDatos(`/api/presupuesto?vigencia=${vigencia}`)
  const [rubro, setRubro] = useState(null)
  const [nuevoGasto, setNuevoGasto] = useState(false)

  return (
    <>
      <Encabezado titulo="Presupuesto y gastos"
        descripcion="Lo que aprobó la asamblea frente a lo que la administración ha pagado. La línea marca lo que debería llevarse gastado a la fecha.">
        <select value={vigencia} onChange={e => setVigencia(Number(e.target.value))} aria-label="Vigencia">
          {[anio, anio - 1, anio - 2].map(a => <option key={a}>{a}</option>)}
        </select>
        {esGestion(usuario) && <button onClick={() => setNuevoGasto(true)}>Registrar gasto</button>}
      </Encabezado>
      <Aviso>{error}</Aviso>
      {p && <>
        <div className="rejilla rejilla-4" style={{ marginBottom: 16 }}>
          <div className="panel indicador"><div className="suave">Presupuesto aprobado</div><div className="valor">{pesos(p.total_aprobado)}</div></div>
          <div className="panel indicador"><div className="suave">Ejecutado</div><div className="valor">{pesos(p.total_ejecutado)}</div>
            <div className="detalle">{p.porcentaje_total}% del total</div></div>
          <div className="panel indicador"><div className="suave">Esperado a la fecha</div><div className="valor">{Math.round(p.meses_transcurridos / 12 * 100)}%</div>
            <div className="detalle">{p.meses_transcurridos} de 12 meses</div></div>
        </div>
        <div className="panel">
          {p.rubros.length === 0 ? <p className="vacio">No hay presupuesto cargado para {vigencia}.</p> :
            <div className="tabla-scroll"><table>
              <thead><tr><th>Rubro</th><th style={{ width: '32%' }}>Ejecución</th><th className="derecha">Aprobado</th><th className="derecha">Ejecutado</th><th className="derecha">Disponible</th></tr></thead>
              <tbody>{p.rubros.map(r => (
                <tr key={r.id} className="clic" onClick={() => setRubro(r)}>
                  <td><strong>{r.nombre}</strong><div className="peq suave">{r.codigo}</div>
                    {r.alerta && <div className="peq" style={{ color: r.alerta === 'sobreejecucion' ? 'var(--rojo)' : 'var(--ocre)' }}>
                      {r.alerta === 'sobreejecucion' ? 'Supera lo aprobado' : 'Gasto por encima del ritmo esperado'}</div>}</td>
                  <td>
                    <div className="barra" title={`${r.porcentaje}%`}>
                      <span className={r.alerta === 'sobreejecucion' ? 'sobre' : r.alerta ? 'alto' : ''} style={{ width: `${Math.min(r.porcentaje, 100)}%` }} />
                      <i className="esperado" style={{ left: `${Math.min(r.esperado_a_la_fecha / r.aprobado * 100, 100)}%` }} />
                    </div>
                    <div className="peq suave num" style={{ marginTop: 4 }}>{r.porcentaje}%</div>
                  </td>
                  <td className="derecha">{pesos(r.aprobado)}</td>
                  <td className="derecha">{pesos(r.ejecutado)}</td>
                  <td className="derecha" style={{ color: r.disponible < 0 ? 'var(--rojo)' : undefined }}>{pesos(r.disponible)}</td>
                </tr>))}
              </tbody>
            </table></div>}
        </div>
      </>}
      {rubro && <GastosRubro rubro={rubro} onCerrar={() => setRubro(null)} />}
      {nuevoGasto && p && <NuevoGasto rubros={p.rubros} onCerrar={() => setNuevoGasto(false)} onListo={() => { setNuevoGasto(false); recargar() }} />}
    </>
  )
}

function GastosRubro({ rubro, onCerrar }) {
  const { datos } = useDatos(`/api/presupuesto/rubros/${rubro.id}/gastos`)
  return (
    <Modal titulo={rubro.nombre} onCerrar={onCerrar}>
      {!datos ? <p>Cargando…</p> : datos.length === 0 ? <p className="vacio">Sin gastos registrados.</p> :
        <table><thead><tr><th>Fecha</th><th>Proveedor y concepto</th><th className="derecha">Valor</th></tr></thead>
          <tbody>{datos.map(g => <tr key={g.id}>
            <td style={{ whiteSpace: 'nowrap' }}>{fecha(g.fecha)}</td>
            <td>{g.proveedor}<div className="peq suave">{g.concepto}{g.soporte && `, soporte ${g.soporte}`}</div></td>
            <td className="derecha">{pesos(g.valor)}</td></tr>)}
          </tbody></table>}
    </Modal>
  )
}

function NuevoGasto({ rubros, onCerrar, onListo }) {
  const [f, setF] = useState({ rubro_id: rubros[0]?.id, fecha: hoyLocal(), proveedor: '', concepto: '', valor: '', soporte: '' })
  const [error, setError] = useState('')
  const set = k => e => setF({ ...f, [k]: e.target.value })
  async function enviar(e) {
    e.preventDefault()
    try { await api.post('/api/presupuesto/gastos', { ...f, rubro_id: Number(f.rubro_id) }); onListo() } catch (err) { setError(err.message) }
  }
  return (
    <Modal titulo="Registrar gasto" onCerrar={onCerrar}>
      <form className="formulario" onSubmit={enviar}>
        <label>Rubro<select value={f.rubro_id} onChange={set('rubro_id')}>{rubros.map(r => <option key={r.id} value={r.id}>{r.codigo} {r.nombre}</option>)}</select></label>
        <div className="formulario-2">
          <label>Fecha de pago<input type="date" required value={f.fecha} onChange={set('fecha')} /></label>
          <label>Valor<input type="number" min="1" required value={f.valor} onChange={set('valor')} /></label>
        </div>
        <label>Proveedor<input required value={f.proveedor} onChange={set('proveedor')} /></label>
        <label>Concepto<input required value={f.concepto} onChange={set('concepto')} /></label>
        <label>No. factura o comprobante<input value={f.soporte} onChange={set('soporte')} /></label>
        <Aviso>{error}</Aviso>
        <div><button>Registrar gasto</button></div>
      </form>
    </Modal>
  )
}

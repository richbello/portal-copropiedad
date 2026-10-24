import { useState } from 'react'
import { fecha, hoyLocal, pesos } from '../api'
import { Aviso, Encabezado, Modal, useDatos } from '../App'
import Recibo from './Recibo'

export default function AdminCartera() {
  const { datos: d, error } = useDatos('/api/admin/cartera')
  const [torre, setTorre] = useState('')
  const [soloMora, setSoloMora] = useState(false)
  const [unidad, setUnidad] = useState(null)

  const filas = (d?.unidades || []).filter(u => (!torre || u.torre === torre) && (!soloMora || u.vencido > 0))
  const torres = [...new Set((d?.unidades || []).map(u => u.torre))]

  function exportar() {
    const enc = ['Unidad', 'Propietario', 'Saldo', 'Vencido', 'Por vencer', '1-30', '31-60', '61-90', '>90']
    const lineas = filas.map(f => [f.unidad, f.propietario, f.saldo, f.vencido, f.al_dia, f['1_30'], f['31_60'], f['61_90'], f.mas_90]
      .map(v => `"${String(v).replace(/"/g, '""')}"`).join(';'))
    const blob = new Blob(['﻿' + [enc.join(';'), ...lineas].join('\n')], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob); a.download = `cartera_${hoyLocal()}.csv`; a.click()
  }

  return (
    <>
      <Encabezado titulo="Cartera por unidad" descripcion={d && `Corte al ${fecha(d.fecha_corte)}. Haga clic en una unidad para ver su estado de cuenta.`}>
        <button className="secundario" onClick={exportar} disabled={!d}>Exportar a Excel (CSV)</button>
      </Encabezado>
      <Aviso>{error}</Aviso>
      <div className="panel">
        <div className="fila" style={{ marginBottom: 12 }}>
          <select value={torre} onChange={e => setTorre(e.target.value)} style={{ width: 'auto' }} aria-label="Torre">
            <option value="">Todas las torres</option>{torres.map(t => <option key={t} value={t}>Torre {t}</option>)}
          </select>
          <label style={{ flexDirection: 'row', gap: 8, fontWeight: 400 }}>
            <input type="checkbox" style={{ width: 18 }} checked={soloMora} onChange={e => setSoloMora(e.target.checked)} /> Solo unidades en mora
          </label>
        </div>
        <div className="tabla-scroll"><table>
          <thead><tr><th>Unidad</th><th>Propietario</th><th className="derecha">Saldo</th><th className="derecha">1-30</th><th className="derecha">31-60</th><th className="derecha">61-90</th><th className="derecha">Más de 90</th></tr></thead>
          <tbody>{filas.map(f => (
            <tr key={f.unidad_id} className="clic" onClick={() => setUnidad(f.unidad_id)}>
              <td style={{ whiteSpace: 'nowrap' }}><strong>{f.unidad}</strong></td>
              <td>{f.propietario}</td>
              <td className="derecha" style={{ color: f.vencido > 0 ? 'var(--rojo)' : f.saldo <= 0 ? 'var(--verde)' : undefined }}><strong>{pesos(f.saldo)}</strong></td>
              {['1_30', '31_60', '61_90', 'mas_90'].map(k => <td key={k} className="derecha">{f[k] ? pesos(f[k]) : ''}</td>)}
            </tr>))}
          </tbody>
          {d && <tfoot><tr>
            <td colSpan={2}><strong>Total</strong></td>
            <td className="derecha"><strong>{pesos(filas.reduce((s, f) => s + f.saldo, 0))}</strong></td>
            {['1_30', '31_60', '61_90', 'mas_90'].map(k => <td key={k} className="derecha"><strong>{pesos(filas.reduce((s, f) => s + f[k], 0))}</strong></td>)}
          </tr></tfoot>}
        </table></div>
      </div>
      {unidad && <DetalleUnidad id={unidad} onCerrar={() => setUnidad(null)} />}
    </>
  )
}

function DetalleUnidad({ id, onCerrar }) {
  const { datos: ec } = useDatos(`/api/unidades/${id}/estado-cuenta`)
  return (
    <Modal titulo={ec ? ec.unidad : 'Estado de cuenta'} onCerrar={onCerrar}>
      {!ec ? <p>Cargando…</p> : <>
        <p className="suave" style={{ marginBottom: 12 }}>{ec.propietarios}</p>
        <Recibo ec={ec} />
        <table style={{ marginTop: 16 }}><tbody>
          {ec.movimientos.slice().reverse().slice(0, 15).map(m => (
            <tr key={`${m.tipo}-${m.id}`}><td className="peq" style={{ whiteSpace: 'nowrap' }}>{fecha(m.fecha)}</td><td className="peq">{m.concepto}</td>
              <td className="derecha peq" style={{ color: m.credito ? 'var(--verde)' : undefined }}>{m.credito ? `− ${pesos(m.credito)}` : pesos(m.debito)}</td></tr>))}
        </tbody></table>
      </>}
    </Modal>
  )
}

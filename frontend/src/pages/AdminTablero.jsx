import { Link, useNavigate } from 'react-router-dom'
import { fecha, hoyLocal, nombrePeriodo, NOMBRES, pesos } from '../api'
import { Aviso, Encabezado, useDatos } from '../App'

const EDADES = [['1_30', '1 a 30 días'], ['31_60', '31 a 60'], ['61_90', '61 a 90'], ['mas_90', 'Más de 90']]

export default function AdminTablero() {
  const { datos: d, error } = useDatos('/api/admin/dashboard')
  const nav = useNavigate()
  if (error) return <Aviso>{error}</Aviso>
  if (!d) return <p className="vacio">Cargando…</p>
  const c = d.cartera
  const maxEdad = Math.max(...EDADES.map(([k]) => c.edades[k]), 1)
  const recaudoPct = d.mes.facturado ? Math.round(d.mes.recaudado / d.mes.facturado * 100) : 0

  return (
    <>
      <Encabezado titulo="Tablero de la copropiedad" descripcion={`Corte al ${fecha(hoyLocal())}`} />

      <section className="recibo" style={{ marginBottom: 16 }}>
        <div className="recibo-cuerpo">
          <div>
            <div className="recibo-unidad">Cartera vencida</div>
            <div className="recibo-saldo en-mora">{pesos(c.vencido_total)}</div>
            <p className="recibo-leyenda">{c.unidades_morosas} de {c.unidades_total} unidades tienen saldo vencido.</p>
          </div>
          <Link className="boton secundario" to="/admin/cartera" style={{ background: 'transparent', color: 'var(--verde)' }}>Ver detalle de cartera</Link>
        </div>
        <div style={{ padding: '0 24px 20px', display: 'grid', gap: 8 }}>
          {EDADES.map(([k, n]) => (
            <div key={k} className="fila" style={{ flexWrap: 'nowrap' }}>
              <span className="peq" style={{ width: 90, flexShrink: 0 }}>{n}</span>
              <div style={{ flex: 1, height: 14 }}>
                <span className={`edad-${k}`} style={{ display: 'block', height: '100%', borderRadius: 3, width: `${c.edades[k] / maxEdad * 100}%`, minWidth: c.edades[k] ? 3 : 0 }} />
              </div>
              <span className="peq num" style={{ width: 110, textAlign: 'right' }}>{pesos(c.edades[k])}</span>
            </div>))}
        </div>
      </section>

      <div className="rejilla rejilla-4" style={{ marginBottom: 16 }}>
        <div className="panel indicador"><div className="suave">Recaudo de {nombrePeriodo(d.mes.periodo)}</div><div className="valor">{recaudoPct}%</div>
          <div className="detalle">{pesos(d.mes.recaudado)} de {pesos(d.mes.facturado)} facturados</div></div>
        <div className="panel indicador"><div className="suave">Solicitudes abiertas</div><div className="valor">{d.solicitudes.abiertas}</div>
          <div className="detalle">{d.solicitudes.total} radicadas en total</div></div>
        <div className="panel indicador"><div className="suave">Respondidas a tiempo</div>
          <div className="valor">{d.solicitudes.cumplimiento_pct ?? '—'}{d.solicitudes.cumplimiento_pct != null && '%'}</div>
          <div className="detalle">Dentro del plazo en días hábiles</div></div>
        <div className="panel indicador"><div className="suave">Sin autorización de datos</div><div className="valor">{d.usuarios.sin_autorizacion_datos}</div>
          <div className="detalle">de {d.usuarios.total} usuarios</div></div>
      </div>

      <div className="rejilla rejilla-2">
        <section className="panel">
          <h2>Solicitudes vencidas</h2>
          {d.solicitudes.vencidas_detalle.length === 0 ? <p className="vacio">Ninguna solicitud ha superado su plazo.</p> :
            <table><tbody>{d.solicitudes.vencidas_detalle.map(s => (
              <tr key={s.id} className="clic" onClick={() => nav(`/solicitudes/${s.id}`)}>
                <td><strong>{s.asunto}</strong><div className="peq suave">{s.radicado}</div></td>
                <td className="derecha" style={{ color: 'var(--rojo)', whiteSpace: 'nowrap' }}>Venció {fecha(s.fecha_limite)}</td>
              </tr>))}</tbody></table>}
        </section>
        <section className="panel">
          <h2>Mayores saldos vencidos</h2>
          {c.top_morosos.length === 0 ? <p className="vacio">No hay unidades en mora.</p> :
            <table><tbody>{c.top_morosos.map(m => (
              <tr key={m.unidad_id}><td><strong>{m.unidad}</strong><div className="peq suave">{m.propietario}</div></td>
                <td className="derecha">{pesos(m.vencido)}</td></tr>))}</tbody></table>}
          <h3 style={{ marginTop: 16, marginBottom: 6 }}>Por tipo de solicitud</h3>
          <div className="fila peq">
            {Object.entries(d.solicitudes.por_tipo).map(([k, v]) => <span key={k} className="estado cerrada">{NOMBRES.tipos[k]}: {v}</span>)}
          </div>
        </section>
      </div>
    </>
  )
}

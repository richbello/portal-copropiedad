import { useState } from 'react'
import { api, descargar, fecha, hoyLocal, mesLocal, NOMBRES, pesos } from '../api'
import { Aviso, Encabezado, useDatos } from '../App'

const hoy = hoyLocal
const mesActual = mesLocal

export default function AdminFacturacion() {
  const [tab, setTab] = useState('pago')
  const { datos: unidades } = useDatos('/api/admin/unidades')
  const pestanas = [['pago', 'Registrar pago'], ['facturar', 'Facturar el mes'], ['cargo', 'Cargo individual'],
    ['intereses', 'Intereses de mora'], ['importar', 'Importar desde Excel']]
  return (
    <>
      <Encabezado titulo="Facturación y pagos" descripcion="Cada operación queda registrada en la auditoría y notifica al propietario cuando corresponde." />
      <div className="pestanas">
        {pestanas.map(([k, n]) => <button key={k} className={tab === k ? 'activa' : ''} onClick={() => setTab(k)}>{n}</button>)}
      </div>
      <div className="panel" style={{ maxWidth: 820 }}>
        {tab === 'pago' && <Pago unidades={unidades} />}
        {tab === 'facturar' && <Facturar />}
        {tab === 'cargo' && <Cargo unidades={unidades} />}
        {tab === 'intereses' && <Intereses />}
        {tab === 'importar' && <Importar />}
      </div>
    </>
  )
}

function SelectorUnidad({ unidades, value, onChange }) {
  return (
    <label>Unidad
      <select required value={value} onChange={onChange}>
        <option value="">Seleccione…</option>
        {(unidades || []).map(u => <option key={u.id} value={u.id}>{u.etiqueta} — {u.usuarios.filter(x => x.relacion === 'propietario').map(x => x.nombre).join(', ') || 'sin propietario'}</option>)}
      </select>
    </label>
  )
}

function useFormulario(inicial) {
  const [f, setF] = useState(inicial)
  const [msg, setMsg] = useState(null)
  return { f, setF, msg, setMsg, set: k => e => setF({ ...f, [k]: e.target.value }) }
}

function Pago({ unidades }) {
  const { f, setF, set, msg, setMsg } = useFormulario({ unidad_id: '', fecha: hoy(), valor: '', medio: 'consignacion', referencia: '', observacion: '' })
  const [saldo, setSaldo] = useState(null)
  async function elegir(e) {
    setF({ ...f, unidad_id: e.target.value }); setSaldo(null)
    if (e.target.value) setSaldo((await api.get(`/api/unidades/${e.target.value}/estado-cuenta`)).saldo)
  }
  async function enviar(e) {
    e.preventDefault(); setMsg(null)
    try {
      await api.post('/api/admin/pagos', { ...f, unidad_id: Number(f.unidad_id), referencia: f.referencia || null })
      setMsg({ tipo: 'ok', texto: `Pago de ${pesos(f.valor)} registrado. El propietario fue notificado.` })
      setF({ ...f, valor: '', referencia: '', observacion: '' }); setSaldo(saldo - Number(f.valor))
    } catch (err) { setMsg({ tipo: 'error', texto: err.message }) }
  }
  return (
    <form className="formulario" onSubmit={enviar}>
      <SelectorUnidad unidades={unidades} value={f.unidad_id} onChange={elegir} />
      {saldo !== null && <p className="aviso info">Saldo actual de la unidad: <strong>{pesos(saldo)}</strong></p>}
      <div className="formulario-2">
        <label>Fecha del pago<input type="date" required value={f.fecha} onChange={set('fecha')} /></label>
        <label>Valor<input type="number" min="1" required value={f.valor} onChange={set('valor')} /></label>
        <label>Medio
          <select value={f.medio} onChange={set('medio')}>
            {['consignacion', 'transferencia', 'pse', 'efectivo', 'cheque'].map(m => <option key={m}>{m}</option>)}
          </select>
        </label>
        <label>Referencia bancaria<span className="ayuda">Evita registrar dos veces el mismo pago</span><input value={f.referencia} onChange={set('referencia')} /></label>
      </div>
      <label>Observación<input value={f.observacion} onChange={set('observacion')} /></label>
      {msg && <Aviso tipo={msg.tipo}>{msg.texto}</Aviso>}
      <div><button>Registrar pago</button></div>
    </form>
  )
}

function Facturar() {
  const { datos: params } = useDatos('/api/admin/parametros')
  const { f, set, msg, setMsg } = useFormulario({ periodo: mesActual() })
  const pres = params?.find(p => p.clave === 'presupuesto_mensual')?.valor
  async function enviar(e) {
    e.preventDefault(); setMsg(null)
    if (!confirm(`¿Generar las cuotas de administración de ${f.periodo} para todas las unidades?`)) return
    try {
      const r = await api.post('/api/admin/facturar', { periodo: f.periodo })
      setMsg({ tipo: 'ok', texto: `Se generaron ${r.creados} cuotas con vencimiento ${fecha(r.vencimiento)}.` +
        (r.omitidos_ya_facturados ? ` ${r.omitidos_ya_facturados} unidades ya estaban facturadas y se omitieron.` : '') })
    } catch (err) { setMsg({ tipo: 'error', texto: err.message }) }
  }
  return (
    <form className="formulario" onSubmit={enviar}>
      <p>Genera la cuota de administración de cada unidad multiplicando el presupuesto mensual por su coeficiente de copropiedad (art. 29, Ley 675 de 2001). Si el mes ya fue facturado para una unidad, no se duplica.</p>
      {pres && <p className="aviso info">Presupuesto mensual a distribuir: <strong>{pesos(pres)}</strong>. Se cambia en Configuración.</p>}
      <label style={{ maxWidth: 240 }}>Periodo<input type="month" required value={f.periodo} onChange={set('periodo')} /></label>
      {msg && <Aviso tipo={msg.tipo}>{msg.texto}</Aviso>}
      <div><button>Generar cuotas del mes</button></div>
    </form>
  )
}

function Cargo({ unidades }) {
  const { f, setF, set, msg, setMsg } = useFormulario({ unidad_id: '', periodo: mesActual(), tipo: 'multa', concepto: '', valor: '', fecha_vencimiento: hoy() })
  async function enviar(e) {
    e.preventDefault(); setMsg(null)
    try {
      await api.post('/api/admin/cargos', { ...f, unidad_id: Number(f.unidad_id) })
      setMsg({ tipo: 'ok', texto: 'Cargo registrado.' }); setF({ ...f, concepto: '', valor: '' })
    } catch (err) { setMsg({ tipo: 'error', texto: err.message }) }
  }
  return (
    <form className="formulario" onSubmit={enviar}>
      <SelectorUnidad unidades={unidades} value={f.unidad_id} onChange={set('unidad_id')} />
      <div className="formulario-2">
        <label>Tipo<select value={f.tipo} onChange={set('tipo')}>{Object.entries(NOMBRES.cargos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label>Periodo<input type="month" required value={f.periodo} onChange={set('periodo')} /></label>
        <label>Valor<input type="number" min="1" required value={f.valor} onChange={set('valor')} /></label>
        <label>Vence<input type="date" required value={f.fecha_vencimiento} onChange={set('fecha_vencimiento')} /></label>
      </div>
      <label>Concepto<span className="ayuda">Para multas, cite el artículo del reglamento y el acta que la impuso</span>
        <input required value={f.concepto} onChange={set('concepto')} /></label>
      {msg && <Aviso tipo={msg.tipo}>{msg.texto}</Aviso>}
      <div><button>Registrar cargo</button></div>
    </form>
  )
}

function Intereses() {
  const { datos: params } = useDatos('/api/admin/parametros')
  const { f, set, msg, setMsg } = useFormulario({ periodo: mesActual(), fecha_corte: hoy() })
  const tasa = params?.find(p => p.clave === 'tasa_mora_mensual')?.valor
  const tope = params?.find(p => p.clave === 'tope_mora_mensual')?.valor
  async function enviar(e) {
    e.preventDefault(); setMsg(null)
    try {
      const r = await api.post('/api/admin/liquidar-intereses', f)
      setMsg({ tipo: 'ok', texto: r.unidades ? `Se liquidaron intereses a ${r.unidades} unidades por ${pesos(r.total_intereses)} (tasa ${r.tasa}% mensual).` : 'No hay unidades con capital vencido para liquidar en ese periodo, o ya fueron liquidadas.' })
    } catch (err) { setMsg({ tipo: 'error', texto: err.message }) }
  }
  return (
    <form className="formulario" onSubmit={enviar}>
      <p>Calcula intereses solo sobre el capital vencido a la fecha de corte (no sobre intereses anteriores). Cada unidad se liquida una sola vez por periodo.</p>
      {tasa && <p className="aviso alerta">Tasa configurada: <strong>{tasa}% mensual</strong>. Tope legal configurado: <strong>{tope}%</strong>.
        Verifique cada mes el interés bancario corriente certificado por la Superintendencia Financiera; el máximo es 1,5 veces ese valor (art. 30, Ley 675 de 2001).</p>}
      <div className="formulario-2">
        <label>Periodo<input type="month" required value={f.periodo} onChange={set('periodo')} /></label>
        <label>Fecha de corte<input type="date" required value={f.fecha_corte} onChange={set('fecha_corte')} /></label>
      </div>
      {msg && <Aviso tipo={msg.tipo}>{msg.texto}</Aviso>}
      <div><button>Liquidar intereses</button></div>
    </form>
  )
}

function Importar() {
  const [tipo, setTipo] = useState('pagos')
  const [archivo, setArchivo] = useState(null)
  const [vista, setVista] = useState(null)
  const [msg, setMsg] = useState(null)

  async function enviar(confirmar) {
    setMsg(null)
    const fd = new FormData()
    fd.append('tipo', tipo); fd.append('confirmar', confirmar ? 'true' : 'false'); fd.append('archivo', archivo)
    try {
      const r = await api.post('/api/admin/importar', fd)
      if (confirmar) { setMsg({ tipo: 'ok', texto: `Se importaron ${r.importados} registros por ${pesos(r.total)}.` }); setVista(null) }
      else setVista(r)
    } catch (err) { setMsg({ tipo: 'error', texto: err.message }) }
  }

  return (
    <div className="formulario">
      <p>Cargue los pagos del extracto bancario o los cargos exportados de su programa contable. Primero verá una vista previa; nada se guarda hasta que confirme.</p>
      <div className="formulario-2">
        <label>Qué va a importar
          <select value={tipo} onChange={e => { setTipo(e.target.value); setVista(null) }}>
            <option value="pagos">Pagos</option><option value="cargos">Cargos</option>
          </select>
        </label>
        <label>Archivo Excel o CSV<input type="file" accept=".xlsx,.xls,.csv" onChange={e => { setArchivo(e.target.files[0]); setVista(null) }} /></label>
      </div>
      <div className="fila">
        <button disabled={!archivo} onClick={() => enviar(false)}>Revisar archivo</button>
        <button className="texto" onClick={() => descargar(`/api/admin/plantilla/${tipo}.xlsx`)}>Descargar plantilla de {tipo}</button>
      </div>
      {vista && <>
        <p className={`aviso ${vista.errores.length ? 'alerta' : 'ok'}`}>
          {vista.filas_validas} filas válidas por {pesos(vista.total)}.{vista.errores.length > 0 && ` ${vista.errores.length} filas con errores: corríjalas en el archivo y vuelva a revisarlo.`}
        </p>
        {vista.errores.length > 0 && <table><thead><tr><th>Fila</th><th>Error</th></tr></thead>
          <tbody>{vista.errores.map(e => <tr key={e.fila}><td>{e.fila}</td><td>{e.error}</td></tr>)}</tbody></table>}
        {vista.vista_previa.length > 0 && <div className="tabla-scroll"><table>
          <thead><tr><th>Unidad</th><th>{tipo === 'pagos' ? 'Fecha' : 'Concepto'}</th><th className="derecha">Valor</th></tr></thead>
          <tbody>{vista.vista_previa.slice(0, 10).map((v, i) => <tr key={i}><td>{v._unidad}</td>
            <td>{tipo === 'pagos' ? `${fecha(v.fecha)} ${v.referencia || ''}` : v.concepto}</td><td className="derecha">{pesos(v.valor)}</td></tr>)}</tbody>
        </table></div>}
        <div><button disabled={vista.errores.length > 0 || !vista.filas_validas} onClick={() => enviar(true)}>Importar {vista.filas_validas} registros</button></div>
      </>}
      {msg && <Aviso tipo={msg.tipo}>{msg.texto}</Aviso>}
    </div>
  )
}

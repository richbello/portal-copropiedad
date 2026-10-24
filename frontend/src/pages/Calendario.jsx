import { useMemo, useState } from 'react'
import { api, NOMBRES } from '../api'
import { Aviso, Encabezado, Modal, useDatos, useSesion } from '../App'

const DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const hora = d => d.toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' })

export function textoCuando(e) {
  const ini = new Date(e.inicio)
  const dia = ini.toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' })
  if (e.todo_el_dia) return `${dia}, todo el día`
  return `${dia}, ${hora(ini)}${e.fin ? ` a ${hora(new Date(e.fin))}` : ''}`
}

export default function Calendario() {
  const { usuario } = useSesion()
  const esAdmin = usuario.rol === 'administrador'
  const hoy = new Date()
  const [mes, setMes] = useState(new Date(hoy.getFullYear(), hoy.getMonth(), 1))
  const [diaSel, setDiaSel] = useState(iso(hoy))
  const [editar, setEditar] = useState(null)

  const primero = new Date(mes)
  const inicioGrid = new Date(primero)
  inicioGrid.setDate(1 - ((primero.getDay() + 6) % 7))
  const celdas = Array.from({ length: 42 }, (_, i) => { const d = new Date(inicioGrid); d.setDate(d.getDate() + i); return d })
  const finGrid = celdas[41]
  const { datos: eventos, error, recargar } = useDatos(`/api/eventos?desde=${iso(inicioGrid)}&hasta=${iso(finGrid)}`)
  const { datos: proximos, recargar: recargarProx } = useDatos('/api/eventos')

  const porDia = useMemo(() => {
    const m = {}
    for (const e of eventos || []) (m[e.inicio.slice(0, 10)] ||= []).push(e)
    return m
  }, [eventos])
  const futuros = (proximos || []).filter(e => new Date(e.fin || e.inicio) >= new Date(iso(hoy) + 'T00:00')).slice(0, 8)
  const delDia = porDia[diaSel] || []
  const cambiarMes = n => setMes(new Date(mes.getFullYear(), mes.getMonth() + n, 1))
  const listo = () => { setEditar(null); recargar(); recargarProx() }

  return (
    <>
      <Encabezado titulo="Calendario" descripcion="Asambleas, mantenimientos, cortes de servicio y actividades del conjunto.">
        {esAdmin && <button onClick={() => setEditar({ fecha: diaSel })}>Programar evento</button>}
      </Encabezado>
      <Aviso>{error}</Aviso>
      <div className="rejilla calendario-rejilla">
        <section className="panel">
          <div className="fila" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
            <button className="secundario" onClick={() => cambiarMes(-1)} aria-label="Mes anterior">‹</button>
            <h2 style={{ margin: 0 }}>{MESES[mes.getMonth()]} {mes.getFullYear()}</h2>
            <button className="secundario" onClick={() => cambiarMes(1)} aria-label="Mes siguiente">›</button>
          </div>
          <div className="mes" role="grid">
            {DIAS.map(d => <div key={d} className="mes-cab">{d}</div>)}
            {celdas.map(d => {
              const k = iso(d), evs = porDia[k] || []
              const clases = ['mes-dia', d.getMonth() !== mes.getMonth() && 'fuera', k === iso(hoy) && 'hoy', k === diaSel && 'sel'].filter(Boolean).join(' ')
              return (
                <button key={k} className={clases} onClick={() => setDiaSel(k)} aria-label={`${d.getDate()} ${evs.length ? `, ${evs.length} eventos` : ''}`}>
                  <span className="mes-num">{d.getDate()}</span>
                  {evs.slice(0, 2).map(e => <span key={e.id} className={`chip-evento cat-${e.categoria}`}>{e.titulo}</span>)}
                  {evs.length > 2 && <span className="peq suave">+{evs.length - 2} más</span>}
                </button>
              )
            })}
          </div>
          <div style={{ marginTop: 16 }}>
            <h3 style={{ marginBottom: 8 }}>{new Date(diaSel + 'T12:00').toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' })}</h3>
            {delDia.length === 0 ? <p className="suave">No hay eventos programados este día.</p> :
              delDia.map(e => <Evento key={e.id} e={e} onEditar={esAdmin ? () => setEditar(e) : null} />)}
          </div>
        </section>
        <aside className="panel">
          <h2>Próximos eventos</h2>
          {futuros.length === 0 ? <p className="vacio">No hay eventos programados.</p> :
            futuros.map(e => <Evento key={e.id} e={e} compacto onEditar={esAdmin ? () => setEditar(e) : null}
              onClick={() => { const d = new Date(e.inicio); setMes(new Date(d.getFullYear(), d.getMonth(), 1)); setDiaSel(iso(d)) }} />)}
        </aside>
      </div>
      {editar && <FormEvento ev={editar} onCerrar={() => setEditar(null)} onListo={listo} />}
    </>
  )
}

function Evento({ e, compacto, onEditar, onClick }) {
  return (
    <div className={`evento cat-borde-${e.categoria}`} onClick={onClick} style={{ cursor: onClick ? 'pointer' : undefined }}>
      <div className="fila" style={{ justifyContent: 'space-between', flexWrap: 'nowrap' }}>
        <strong>{e.titulo}</strong>
        {onEditar && <button className="texto" onClick={ev => { ev.stopPropagation(); onEditar() }}>Editar</button>}
      </div>
      <div className="peq">{textoCuando(e)}{e.lugar && `, ${e.lugar}`}</div>
      <div className="peq suave">{NOMBRES.eventos[e.categoria]}</div>
      {!compacto && e.descripcion && <p style={{ marginTop: 6 }}>{e.descripcion}</p>}
    </div>
  )
}

function FormEvento({ ev, onCerrar, onListo }) {
  const nuevo = !ev.id
  const local = s => s ? s.slice(0, 16) : ''
  const [f, setF] = useState({
    titulo: ev.titulo || '', categoria: ev.categoria || 'otro', lugar: ev.lugar || '', descripcion: ev.descripcion || '',
    inicio: local(ev.inicio) || `${ev.fecha}T08:00`, fin: local(ev.fin), todo_el_dia: !!ev.todo_el_dia, notificar_todos: nuevo,
  })
  const [error, setError] = useState('')
  const set = k => e => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  async function guardar(e) {
    e.preventDefault(); setError('')
    const datos = { ...f, fin: f.fin || null, lugar: f.lugar || null, descripcion: f.descripcion || null }
    try {
      if (nuevo) await api.post('/api/eventos', datos); else await api.put(`/api/eventos/${ev.id}`, datos)
      onListo()
    } catch (err) { setError(err.message) }
  }
  async function borrar() {
    if (!confirm(`¿Eliminar "${ev.titulo}" del calendario?`)) return
    await api.del(`/api/eventos/${ev.id}`); onListo()
  }
  return (
    <Modal titulo={nuevo ? 'Programar evento' : 'Editar evento'} onCerrar={onCerrar}>
      <form className="formulario" onSubmit={guardar}>
        <label>Título<input required minLength={3} value={f.titulo} onChange={set('titulo')} /></label>
        <div className="formulario-2">
          <label>Tipo<select value={f.categoria} onChange={set('categoria')}>
            {Object.entries(NOMBRES.eventos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label>Lugar<input value={f.lugar} onChange={set('lugar')} placeholder="Salón comunal" /></label>
          <label>Inicio<input type="datetime-local" required value={f.inicio} onChange={set('inicio')} /></label>
          <label>Fin<input type="datetime-local" value={f.fin} onChange={set('fin')} /></label>
        </div>
        <label>Descripción<textarea value={f.descripcion} onChange={set('descripcion')} style={{ minHeight: 80 }} /></label>
        <label className="casilla"><input type="checkbox" checked={f.todo_el_dia} onChange={set('todo_el_dia')} /> Dura todo el día</label>
        {nuevo && <label className="casilla"><input type="checkbox" checked={f.notificar_todos} onChange={set('notificar_todos')} /> Avisar a todos los residentes</label>}
        <Aviso>{error}</Aviso>
        <div className="fila">
          <button>{nuevo ? 'Programar evento' : 'Guardar cambios'}</button>
          {!nuevo && <button type="button" className="peligro" onClick={borrar}>Eliminar</button>}
        </div>
      </form>
    </Modal>
  )
}

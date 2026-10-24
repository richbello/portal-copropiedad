import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api, descargar, esGestion, fecha, fechaHora, NOMBRES } from '../api'
import { Aviso, Encabezado, useDatos, useSesion } from '../App'
import { Semaforo } from './Solicitudes'

export default function SolicitudDetalle() {
  const { id } = useParams()
  const { usuario } = useSesion()
  const loc = useLocation()
  const { datos: s, error, setDatos } = useDatos(`/api/solicitudes/${id}`)
  const [texto, setTexto] = useState('')
  const [estado, setEstado] = useState('')
  const [archivos, setArchivos] = useState([])
  const [errorEnvio, setErrorEnvio] = useState('')
  const gestion = esGestion(usuario)
  const soloLectura = ['consejo', 'revisor_fiscal'].includes(usuario.rol)

  async function enviar(e) {
    e.preventDefault()
    setErrorEnvio('')
    const fd = new FormData()
    fd.append('texto', texto)
    if (estado) fd.append('estado', estado)
    archivos.forEach(a => fd.append('archivos', a))
    try {
      setDatos(await api.post(`/api/solicitudes/${id}/mensajes`, fd))
      setTexto(''); setEstado(''); setArchivos([]); e.target.reset()
    } catch (err) { setErrorEnvio(err.message) }
  }

  if (error) return <Aviso>{error}</Aviso>
  if (!s) return <p className="vacio">Cargando…</p>

  return (
    <>
      <p style={{ marginBottom: 12 }}><Link to="/solicitudes">Volver a solicitudes</Link></p>
      {loc.state?.nueva && <div className="aviso ok" style={{ marginBottom: 16 }}>
        Su solicitud quedó radicada con el número <strong>{s.radicado}</strong>. Le avisaremos cuando la administración responda.</div>}
      <Encabezado titulo={s.asunto} descripcion={`${s.radicado} · ${NOMBRES.tipos[s.tipo]}`}>
        <button className="secundario" onClick={() => descargar(`/api/solicitudes/${s.id}/constancia.pdf`)}>Descargar constancia</button>
      </Encabezado>

      <div className="rejilla detalle-rejilla">
        <div className="pila">
          <section className="panel">
            <div className="autor peq suave">{s.solicitante}{s.unidad && `, ${s.unidad}`}, {fechaHora(s.fecha_radicado)}</div>
            <p style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>{s.descripcion}</p>
            {s.zona_comun && <p className="aviso info" style={{ marginTop: 12 }}>Reserva de {s.zona_comun} para el {fecha(s.fecha_reserva)}</p>}
          </section>

          {s.mensajes.length > 0 && <section className="hilo">
            {s.mensajes.map(m => <div key={m.id}>
              {m.estado_nuevo && <div className="cambio-estado">Estado cambiado a {NOMBRES.estados[m.estado_nuevo].toLowerCase()}</div>}
              <div className={`mensaje ${['administrador', 'contador'].includes(m.rol) ? 'admin' : 'propio'}`}
                style={{ marginLeft: ['administrador', 'contador'].includes(m.rol) ? 0 : 'auto' }}>
                <div className="autor">{m.autor}, {fechaHora(m.fecha)}</div>
                <div style={{ whiteSpace: 'pre-wrap' }}>{m.texto}</div>
              </div>
            </div>)}
          </section>}

          {!soloLectura && (s.estado !== 'cerrada' || gestion) &&
            <form className="panel formulario" onSubmit={enviar}>
              <label>{gestion ? 'Respuesta de la administración' : 'Agregar un mensaje'}
                <textarea required value={texto} onChange={e => setTexto(e.target.value)} style={{ minHeight: 90 }} />
              </label>
              <div className="formulario-2">
                {gestion && <label>Cambiar estado
                  <select value={estado} onChange={e => setEstado(e.target.value)}>
                    <option value="">Mantener ({NOMBRES.estados[s.estado]})</option>
                    {Object.entries(NOMBRES.estados).filter(([k]) => k !== s.estado).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </label>}
                <label>Adjuntos<input type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.docx,.xlsx" onChange={e => setArchivos([...e.target.files])} /></label>
              </div>
              <Aviso>{errorEnvio}</Aviso>
              <div><button>{gestion ? 'Enviar respuesta' : 'Enviar mensaje'}</button></div>
            </form>}
        </div>

        <aside className="panel pila">
          <div><div className="peq suave">Estado</div><span className={`estado ${s.estado}`}>{NOMBRES.estados[s.estado]}</span></div>
          <div><div className="peq suave">Fecha límite de respuesta</div><strong>{fecha(s.fecha_limite)}</strong><div><Semaforo s={s} /></div></div>
          {s.fecha_cierre && <div><div className="peq suave">Atendida</div>{fechaHora(s.fecha_cierre)}</div>}
          <div>
            <div className="peq suave">Adjuntos</div>
            {s.adjuntos.length === 0 ? <span className="peq">Ninguno</span> :
              s.adjuntos.map(a => <div key={a.id}>
                <button className="texto" onClick={() => descargar(`/api/solicitudes/${s.id}/adjuntos/${a.id}`, a.nombre)}>{a.nombre}</button>
              </div>)}
          </div>
        </aside>
      </div>
    </>
  )
}

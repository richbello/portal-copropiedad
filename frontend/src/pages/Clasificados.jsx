import { useEffect, useState } from 'react'
import { api, fecha, pesos, urlProtegida } from '../api'
import { Aviso, Encabezado, Modal, useDatos, useSesion } from '../App'

const CATEGORIAS = {
  negocio: 'Negocios y emprendimientos', servicio: 'Servicios', venta: 'Se vende',
  compra: 'Se compra o se busca', arriendo: 'Se arrienda',
}
const CORTO = { negocio: 'Negocio', servicio: 'Servicio', venta: 'Venta', compra: 'Se busca', arriendo: 'Arriendo' }
const VIGENCIA = { negocio: 90, servicio: 90, venta: 30, compra: 30, arriendo: 45 }

function whatsapp(tel, titulo) {
  let n = (tel || '').replace(/\D/g, '')
  if (n.length === 10 && n.startsWith('3')) n = '57' + n
  return `https://wa.me/${n}?text=${encodeURIComponent(`Hola, vi su anuncio "${titulo}" en el portal del conjunto.`)}`
}

export default function Clasificados() {
  const { usuario } = useSesion()
  const esAdmin = usuario.rol === 'administrador'
  const puedePublicar = !['consejo', 'revisor_fiscal', 'contador'].includes(usuario.rol)
  const [vista, setVista] = useState('')
  const [q, setQ] = useState('')
  const ruta = vista === 'mios' ? '/api/clasificados/mios' : vista === 'reportados' ? '/api/clasificados/reportados'
    : `/api/clasificados?${new URLSearchParams({ ...(vista && { categoria: vista }), ...(q.length > 2 && { q }) })}`
  const { datos, error, recargar } = useDatos(ruta)
  const [form, setForm] = useState(null)
  const [reportar, setReportar] = useState(null)
  const [retirar, setRetirar] = useState(null)
  const [msg, setMsg] = useState('')

  async function accion(a, que) {
    setMsg('')
    if (que === 'eliminar' && !confirm(`¿Eliminar "${a.titulo}"? No se puede deshacer.`)) return
    if (que === 'eliminar') await api.del(`/api/clasificados/${a.id}`)
    else await api.post(`/api/clasificados/${a.id}/${que}`)
    setMsg({ renovar: 'Anuncio renovado.', cerrar: 'Anuncio cerrado. Ya no aparece en la cartelera.', eliminar: 'Anuncio eliminado.' }[que])
    recargar()
  }

  return (
    <>
      <Encabezado titulo="Negocios y clasificados"
        descripcion="Emprendimientos, servicios, ventas, compras y arriendos entre vecinos del conjunto.">
        {puedePublicar && <button onClick={() => setForm({})}>Publicar anuncio</button>}
      </Encabezado>
      <div className="pestanas">
        <button className={vista === '' ? 'activa' : ''} onClick={() => setVista('')}>Todos</button>
        {Object.entries(CORTO).map(([k, v]) => <button key={k} className={vista === k ? 'activa' : ''} onClick={() => setVista(k)}>{v}</button>)}
        {puedePublicar && <button className={vista === 'mios' ? 'activa' : ''} onClick={() => setVista('mios')}>Mis anuncios</button>}
        {esAdmin && <button className={vista === 'reportados' ? 'activa' : ''} onClick={() => setVista('reportados')}>Reportados</button>}
      </div>
      {!['mios', 'reportados'].includes(vista) &&
        <input placeholder="Buscar: tortas, plomero, bicicleta…" value={q} onChange={e => setQ(e.target.value)} style={{ maxWidth: 380, marginBottom: 16 }} />}
      <Aviso>{error}</Aviso>
      {msg && <div className="aviso ok" style={{ marginBottom: 12 }}>{msg}</div>}
      {datos?.length === 0 && <div className="panel vacio">
        {vista === 'mios' ? 'Todavía no ha publicado anuncios.' : vista === 'reportados' ? 'No hay anuncios reportados.'
          : 'No hay anuncios en esta categoría. ¿Tiene un negocio o algo para ofrecer? Publíquelo gratis para sus vecinos.'}
      </div>}
      <div className="cartelera">
        {(datos || []).map(a => (
          <article key={a.id} className={`anuncio${a.vigente ? '' : ' inactivo'}`}>
            <Foto a={a} />
            <div className="anuncio-cuerpo">
              <div className="fila" style={{ justifyContent: 'space-between' }}>
                <span className={`cat-anuncio cat-a-${a.categoria}`}>{CORTO[a.categoria]}</span>
                {!a.vigente && <span className="estado cerrada">{a.estado === 'retirado' ? 'Retirado' : a.estado === 'cerrado' ? 'Cerrado' : 'Vencido'}</span>}
              </div>
              <h3>{a.titulo}</h3>
              {a.precio != null && <div className="precio">{a.precio > 0 ? pesos(a.precio) : 'Gratis'}{a.precio_negociable && <span className="peq suave"> negociable</span>}</div>}
              <p className="descripcion">{a.descripcion}</p>
              <div className="peq suave">{a.publicado_por}{a.torre && `, torre ${a.torre}`}. Publicado el {fecha(a.creado)}</div>
              {a.motivo_retiro && <p className="peq" style={{ color: 'var(--rojo)' }}>Retirado: {a.motivo_retiro}</p>}
              {esAdmin && a.reportes?.length > 0 && <div className="aviso alerta peq">
                {a.reportes.length} reporte(s): {a.reportes.map(r => r.motivo).join(' | ')}{a.unidad && `. Publicado desde ${a.unidad}`}</div>}
              <div className="fila" style={{ marginTop: 'auto', paddingTop: 10 }}>
                {!a.es_mio && a.telefono && a.vigente && <>
                  {a.whatsapp && <a className="boton" href={whatsapp(a.telefono, a.titulo)} target="_blank" rel="noopener noreferrer">WhatsApp</a>}
                  <a className="boton secundario" style={{ background: 'transparent', color: 'var(--verde)' }} href={`tel:${a.telefono}`}>Llamar</a>
                </>}
                {!a.es_mio && a.vigente && <button className="texto" onClick={() => setReportar(a)}>Reportar</button>}
                {a.es_mio && a.estado !== 'retirado' && <>
                  <button className="texto" onClick={() => setForm(a)}>Editar</button>
                  {a.vigente ? <button className="texto" onClick={() => accion(a, 'cerrar')}>Cerrar</button>
                    : <button className="texto" onClick={() => accion(a, 'renovar')}>Volver a publicar</button>}
                  {a.vigente && <span className="peq suave">Visible hasta {fecha(a.vence)}</span>}
                </>}
                {a.es_mio && <button className="texto" onClick={() => accion(a, 'eliminar')}>Eliminar</button>}
                {esAdmin && !a.es_mio && a.estado === 'activo' && <button className="texto" onClick={() => setRetirar(a)}>Retirar</button>}
              </div>
            </div>
          </article>))}
      </div>
      <p className="peq suave" style={{ marginTop: 16 }}>Los acuerdos son directamente entre vecinos; la administración no interviene ni responde por ellos.
        No se permiten anuncios que contraríen la ley o el manual de convivencia.</p>
      {form && <FormAnuncio a={form.id ? form : null} onCerrar={() => setForm(null)}
        onListo={t => { setForm(null); setMsg(t); setVista(form.id ? vista : 'mios'); recargar() }} />}
      {reportar && <Motivo titulo="Reportar anuncio" ayuda="La administración revisará el anuncio. Quien lo publicó no sabrá quién lo reportó."
        boton="Enviar reporte" ruta={`/api/clasificados/${reportar.id}/reportar`} onCerrar={() => setReportar(null)}
        onListo={() => { setReportar(null); setMsg('Gracias. La administración revisará el anuncio.') }} />}
      {retirar && <Motivo titulo={`Retirar "${retirar.titulo}"`} ayuda="El motivo se le informará a quien lo publicó."
        boton="Retirar anuncio" ruta={`/api/clasificados/${retirar.id}/retirar`} onCerrar={() => setRetirar(null)}
        onListo={() => { setRetirar(null); setMsg('Anuncio retirado y notificado.'); recargar() }} />}
    </>
  )
}

function Foto({ a }) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    if (!a.fotos.length) return
    let u
    urlProtegida(`/api/clasificados/${a.id}/fotos/${a.fotos[0]}`).then(x => { u = x; setUrl(x) }).catch(() => {})
    return () => u && URL.revokeObjectURL(u)
  }, [a.id, a.fotos])
  if (!a.fotos.length) return <div className={`anuncio-foto sin-foto cat-a-${a.categoria}`} aria-hidden="true">{CORTO[a.categoria]}</div>
  return <div className="anuncio-foto">{url && <img src={url} alt={a.titulo} />}{a.fotos.length > 1 && <span className="mas-fotos">+{a.fotos.length - 1}</span>}</div>
}

function FormAnuncio({ a, onCerrar, onListo }) {
  const [f, setF] = useState({
    categoria: a?.categoria || 'negocio', titulo: a?.titulo || '', descripcion: a?.descripcion || '',
    precio: a?.precio != null ? String(Math.round(a.precio)) : '', precio_negociable: a?.precio_negociable || false,
    telefono: a?.telefono || '', whatsapp: a ? a.whatsapp : true,
  })
  const [fotos, setFotos] = useState([])
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const set = k => e => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  async function guardar(e) {
    e.preventDefault(); setError(''); setEnviando(true)
    try {
      if (a) await api.put(`/api/clasificados/${a.id}`, f)
      else {
        const fd = new FormData()
        Object.entries(f).forEach(([k, v]) => fd.append(k, v))
        fotos.forEach(x => fd.append('fotos', x))
        await api.post('/api/clasificados', fd)
      }
      onListo(a ? 'Cambios guardados.' : 'Anuncio publicado. Ya lo pueden ver sus vecinos.')
    } catch (err) { setError(err.message); setEnviando(false) }
  }
  return (
    <Modal titulo={a ? 'Editar anuncio' : 'Publicar anuncio'} onCerrar={onCerrar}>
      <form className="formulario" onSubmit={guardar}>
        <label>¿Qué quiere publicar?<select value={f.categoria} onChange={set('categoria')}>
          {Object.entries(CATEGORIAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          <span className="ayuda">Se mostrará durante {VIGENCIA[f.categoria]} días; luego puede volver a publicarlo con un clic.</span></label>
        <label>Título<input required minLength={5} maxLength={120} value={f.titulo} onChange={set('titulo')}
          placeholder={{ negocio: 'Tortas y postres por encargo', servicio: 'Clases de inglés', venta: 'Vendo nevera de 300 litros', compra: 'Busco coche para bebé', arriendo: 'Arriendo parqueadero cubierto' }[f.categoria]} /></label>
        <label>Descripción<textarea required minLength={15} value={f.descripcion} onChange={set('descripcion')} style={{ minHeight: 100 }}
          placeholder="Qué ofrece, estado, horarios, cómo entrega…" /></label>
        <div className="formulario-2">
          <label>Precio<span className="ayuda">Opcional. Solo números</span><input inputMode="numeric" value={f.precio} onChange={set('precio')} placeholder="150000" /></label>
          <label>Celular de contacto<input value={f.telefono} onChange={set('telefono')} placeholder="3001234567" /></label>
        </div>
        <label className="casilla"><input type="checkbox" checked={f.precio_negociable} onChange={set('precio_negociable')} /> Precio negociable</label>
        <label className="casilla"><input type="checkbox" checked={f.whatsapp} onChange={set('whatsapp')} /> Pueden escribirme por WhatsApp</label>
        {!a && <label>Fotos<span className="ayuda">Hasta 3, en JPG o PNG</span>
          <input type="file" accept=".jpg,.jpeg,.png" multiple onChange={e => setFotos([...e.target.files].slice(0, 3))} /></label>}
        <p className="peq suave">Su anuncio mostrará su nombre con la inicial del apellido y su torre, no su apartamento.</p>
        <Aviso>{error}</Aviso>
        <div><button disabled={enviando}>{a ? 'Guardar cambios' : enviando ? 'Publicando…' : 'Publicar anuncio'}</button></div>
      </form>
    </Modal>
  )
}

function Motivo({ titulo, ayuda, boton, ruta, onCerrar, onListo }) {
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState('')
  async function enviar(e) {
    e.preventDefault(); setError('')
    try { await api.post(ruta, { motivo }); onListo() } catch (err) { setError(err.message) }
  }
  return (
    <Modal titulo={titulo} onCerrar={onCerrar}>
      <form className="formulario" onSubmit={enviar}>
        <label>Motivo<span className="ayuda">{ayuda}</span><textarea required minLength={5} value={motivo} onChange={e => setMotivo(e.target.value)} style={{ minHeight: 80 }} /></label>
        <Aviso>{error}</Aviso>
        <div><button>{boton}</button></div>
      </form>
    </Modal>
  )
}

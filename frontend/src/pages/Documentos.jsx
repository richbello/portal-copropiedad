import { useState } from 'react'
import { api, descargar, esGestion, fecha, NOMBRES } from '../api'
import { Aviso, Encabezado, Modal, useDatos, useSesion } from '../App'

export default function Documentos() {
  const { usuario } = useSesion()
  const [categoria, setCategoria] = useState('')
  const { datos, error, recargar } = useDatos(`/api/documentos${categoria ? `?categoria=${categoria}` : ''}`)
  const [subir, setSubir] = useState(false)

  async function eliminar(d) {
    if (!confirm(`¿Eliminar "${d.titulo}"? Esta acción no se puede deshacer.`)) return
    await api.del(`/api/documentos/${d.id}`)
    recargar()
  }

  return (
    <>
      <Encabezado titulo="Documentos" descripcion="Actas, presupuesto, estados financieros, reglamento y circulares de la copropiedad.">
        {esGestion(usuario) && <button onClick={() => setSubir(true)}>Publicar documento</button>}
      </Encabezado>
      <div className="pestanas">
        <button className={!categoria ? 'activa' : ''} onClick={() => setCategoria('')}>Todos</button>
        {Object.entries(NOMBRES.categorias).map(([k, v]) =>
          <button key={k} className={categoria === k ? 'activa' : ''} onClick={() => setCategoria(k)}>{v}</button>)}
      </div>
      <Aviso>{error}</Aviso>
      <div className="panel">
        {datos?.length === 0 && <p className="vacio">No hay documentos publicados en esta categoría.</p>}
        {datos?.length > 0 && <table><tbody>
          {datos.map(d => <tr key={d.id}>
            <td><strong>{d.titulo}</strong>
              <div className="peq suave">{NOMBRES.categorias[d.categoria]}, publicado el {fecha(d.publicado)}</div>
              {d.descripcion && <div className="peq">{d.descripcion}</div>}</td>
            <td className="derecha" style={{ whiteSpace: 'nowrap' }}>
              <button className="secundario" onClick={() => descargar(`/api/documentos/${d.id}/archivo`, d.nombre_archivo)}>Descargar</button>
              {usuario.rol === 'administrador' && <button className="texto" onClick={() => eliminar(d)}>Eliminar</button>}
            </td>
          </tr>)}
        </tbody></table>}
      </div>
      {subir && <PublicarDocumento onCerrar={() => setSubir(false)} onListo={() => { setSubir(false); recargar() }} />}
    </>
  )
}

function PublicarDocumento({ onCerrar, onListo }) {
  const [error, setError] = useState('')
  async function enviar(e) {
    e.preventDefault()
    try { await api.post('/api/documentos', new FormData(e.target)); onListo() } catch (err) { setError(err.message) }
  }
  return (
    <Modal titulo="Publicar documento" onCerrar={onCerrar}>
      <form className="formulario" onSubmit={enviar}>
        <label>Título<input name="titulo" required /></label>
        <label>Categoría
          <select name="categoria">{Object.entries(NOMBRES.categorias).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        </label>
        <label>Descripción<input name="descripcion" /></label>
        <label>Archivo<input name="archivo" type="file" required accept=".pdf,.jpg,.png,.docx,.xlsx" /></label>
        <label style={{ flexDirection: 'row', gap: 10, fontWeight: 400 }}>
          <input type="checkbox" name="notificar_todos" value="true" style={{ width: 20 }} /> Avisar a todos los propietarios
        </label>
        <Aviso>{error}</Aviso>
        <div><button>Publicar</button></div>
      </form>
    </Modal>
  )
}

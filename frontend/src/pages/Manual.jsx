import { useEffect, useState } from 'react'
import { descargar, esGestion, fecha, urlProtegida } from '../api'
import { Aviso, Encabezado, useDatos, useSesion } from '../App'

export default function Manual() {
  const { usuario } = useSesion()
  const { datos, error } = useDatos('/api/manual-convivencia')
  const [url, setUrl] = useState(null)
  const [errorVista, setErrorVista] = useState('')
  const v = datos?.vigente

  useEffect(() => {
    if (!v) return
    let actual
    urlProtegida(`/api/documentos/${v.id}/ver`).then(u => { actual = u; setUrl(u) }).catch(e => setErrorVista(e.message))
    return () => actual && URL.revokeObjectURL(actual)
  }, [v])

  return (
    <>
      <Encabezado titulo="Manual de convivencia"
        descripcion={v ? `Versión vigente publicada el ${fecha(v.publicado)}.` : 'Normas para vivir en comunidad.'}>
        {v && <button className="secundario" onClick={() => descargar(`/api/documentos/${v.id}/archivo`, v.nombre_archivo)}>Descargar PDF</button>}
      </Encabezado>
      <Aviso>{error || errorVista}</Aviso>
      {datos && !v && <div className="panel vacio">
        Todavía no se ha publicado el manual de convivencia.
        {esGestion(usuario) && ' Publíquelo en Documentos eligiendo la categoría "Manual de convivencia".'}
      </div>}
      {v && <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
        {url ? <iframe title="Manual de convivencia" src={url} className="visor-pdf" /> : <p className="vacio">Cargando…</p>}
      </div>}
      {datos?.anteriores.length > 0 && <section className="panel">
        <h2>Versiones anteriores</h2>
        {datos.anteriores.map(d => <div key={d.id} className="fila" style={{ justifyContent: 'space-between', padding: '6px 0' }}>
          <span>{d.titulo}, publicado el {fecha(d.publicado)}</span>
          <button className="texto" onClick={() => descargar(`/api/documentos/${d.id}/archivo`, d.nombre_archivo)}>Descargar</button>
        </div>)}
      </section>}
      <p className="peq suave" style={{ marginTop: 12 }}>Si no puede ver el documento en su celular, use el botón Descargar PDF.</p>
    </>
  )
}

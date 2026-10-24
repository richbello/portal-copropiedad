import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api, fechaHora } from '../api'
import { Encabezado, useDatos } from '../App'

export default function Notificaciones() {
  const { datos } = useDatos('/api/auth/notificaciones')
  useEffect(() => {
    if (datos?.some(n => !n.leida)) api.post('/api/auth/notificaciones/leer-todas').catch(() => {})
  }, [datos])

  return (
    <>
      <Encabezado titulo="Notificaciones" />
      <div className="panel">
        {datos?.length === 0 && <p className="vacio">No tiene notificaciones.</p>}
        {datos?.map(n => (
          <div key={n.id} style={{ padding: '12px 0', borderBottom: '1px solid var(--linea)' }}>
            <div className="fila" style={{ justifyContent: 'space-between' }}>
              <strong>{!n.leida && <span className="punto" style={{ marginRight: 8 }}>nueva</span>}{n.titulo}</strong>
              <span className="peq suave">{fechaHora(n.fecha)}</span>
            </div>
            <p className="suave">{n.texto}</p>
            {n.enlace && <Link to={n.enlace}>Ver</Link>}
          </div>))}
      </div>
    </>
  )
}

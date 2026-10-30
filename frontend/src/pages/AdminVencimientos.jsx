import { useState } from 'react'
import { api, fecha } from '../api'
import { Encabezado, useDatos } from '../App'

const NOMBRE_DOC = { soat: 'SOAT', tecnomecanica: 'Tecnomecánica', vacuna: 'Vacuna antirrábica' }

export default function AdminVencimientos() {
  const { datos: vencen, recargar } = useDatos('/api/vencimientos')
  const [tipo, setTipo] = useState('vehiculos')
  const [avisos, setAvisos] = useState(null)
  async function enviarAvisos() {
    const r = await api.post('/api/vencimientos/revisar')
    setAvisos(r.avisos_enviados ? `Se enviaron ${r.avisos_enviados} avisos.` : 'No había avisos pendientes; los vencimientos ya fueron notificados.')
    recargar()
  }
  const visibles = (vencen || []).filter(d => tipo === 'todos' || (tipo === 'vehiculos' ? d.documento !== 'vacuna' : d.documento === 'vacuna'))
  return (
    <>
      <Encabezado titulo="Vencimientos" descripcion="SOAT y tecnomecánica de los vehículos, y vacunas de las mascotas, vencidos o por vencer en los próximos 30 días.">
        <button className="secundario" onClick={enviarAvisos}>Enviar avisos ahora</button>
      </Encabezado>
      <section className="panel">
        <div className="pestanas" style={{ marginTop: 0 }}>
          {[['vehiculos', 'SOAT y tecnomecánica'], ['mascotas', 'Vacunas'], ['todos', 'Todos']].map(([k, n]) =>
            <button key={k} className={tipo === k ? 'activa' : ''} onClick={() => setTipo(k)}>{n}</button>)}
        </div>
        <p className="peq suave" style={{ marginBottom: 8 }}>El portal avisa solo a cada unidad 30 días antes, 7 días antes y al vencer. El botón fuerza la revisión de inmediato.</p>
        {avisos && <p className="aviso ok" style={{ marginBottom: 8 }}>{avisos}</p>}
        {vencen && (visibles.length === 0 ? <p className="suave">No hay documentos vencidos ni por vencer en los próximos 30 días.</p> :
          <div className="tabla-scroll"><table>
            <thead><tr><th>Unidad</th><th>Documento</th><th>Estado</th></tr></thead>
            <tbody>{visibles.map(d => <tr key={d.objeto + d.documento}>
              <td style={{ whiteSpace: 'nowrap' }}>{d.unidad}</td><td>{NOMBRE_DOC[d.documento]}, {d.que}</td>
              <td style={{ color: d.estado === 'vencido' ? 'var(--rojo)' : 'var(--ocre)' }}>
                {d.estado === 'vencido' ? `Vencido desde ${fecha(d.vence)}` : `Vence ${fecha(d.vence)} (${d.dias} días)`}</td>
            </tr>)}</tbody>
          </table></div>)}
      </section>
    </>
  )
}

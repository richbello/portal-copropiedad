import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, hoyLocal, NOMBRES } from '../api'
import { Aviso, Encabezado, useDatos, useSesion } from '../App'

const AYUDAS = {
  dano_locativo: 'Indique el lugar exacto y desde cuándo ocurre. Adjunte fotos si puede.',
  reserva_zona_comun: 'Indique la hora de inicio y fin, y cuántas personas asistirán.',
  certificado: 'Indique para qué entidad o trámite necesita el certificado.',
  queja: 'Describa los hechos, fechas y, si aplica, la torre o zona donde ocurren.',
  derecho_peticion: 'Exprese con claridad lo que solicita y los fundamentos. La administración tiene 15 días hábiles para responder (Ley 1755 de 2015).',
  solicitud_documentos: 'Indique qué documentos necesita (actas, contratos, estados financieros) y el periodo.',
  consulta: 'Escriba su pregunta. El plazo de respuesta es de 30 días hábiles.',
  otro: 'Describa su solicitud con el mayor detalle posible.',
}

export default function NuevaSolicitud() {
  const { usuario } = useSesion()
  const nav = useNavigate()
  const { datos: cat } = useDatos('/api/solicitudes/catalogo')
  const [f, setF] = useState({ tipo: 'dano_locativo', asunto: '', descripcion: '', unidad_id: usuario.unidades[0]?.id || '', zona_comun: '', fecha_reserva: '' })
  const [archivos, setArchivos] = useState([])
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const dias = cat?.tipos.find(t => t.valor === f.tipo)?.dias_habiles

  async function enviar(e) {
    e.preventDefault()
    setError(''); setEnviando(true)
    const fd = new FormData()
    Object.entries(f).forEach(([k, v]) => v !== '' && fd.append(k, v))
    archivos.forEach(a => fd.append('archivos', a))
    try {
      const s = await api.post('/api/solicitudes', fd)
      nav(`/solicitudes/${s.id}`, { state: { nueva: true } })
    } catch (err) { setError(err.message); setEnviando(false) }
  }

  return (
    <>
      <Encabezado titulo="Radicar una solicitud" />
      <form className="panel formulario" style={{ maxWidth: 720 }} onSubmit={enviar}>
        <div className="formulario-2">
          <label>Tipo de solicitud
            <select value={f.tipo} onChange={set('tipo')}>
              {Object.entries(NOMBRES.tipos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          {usuario.unidades.length > 1 &&
            <label>Unidad
              <select value={f.unidad_id} onChange={set('unidad_id')}>
                {usuario.unidades.map(u => <option key={u.id} value={u.id}>{u.etiqueta}</option>)}
              </select>
            </label>}
        </div>
        <div className="aviso info peq">{AYUDAS[f.tipo]}{dias && ` Plazo de respuesta: ${dias} días hábiles.`}</div>
        {f.tipo === 'reserva_zona_comun' && cat &&
          <div className="formulario-2">
            <label>Zona común
              <select required value={f.zona_comun} onChange={set('zona_comun')}>
                <option value="">Seleccione…</option>
                {cat.zonas_comunes.map(z => <option key={z}>{z}</option>)}
              </select>
            </label>
            <label>Fecha
              <input type="date" required value={f.fecha_reserva} min={hoyLocal()} onChange={set('fecha_reserva')} />
            </label>
          </div>}
        <label>Asunto<input required minLength={5} maxLength={200} value={f.asunto} onChange={set('asunto')} /></label>
        <label>Descripción<textarea required minLength={10} value={f.descripcion} onChange={set('descripcion')} /></label>
        <label>Adjuntos<span className="ayuda">Fotos o documentos: PDF, JPG, PNG, Word o Excel, hasta 10 MB cada uno</span>
          <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.docx,.xlsx" onChange={e => setArchivos([...e.target.files])} />
        </label>
        <Aviso>{error}</Aviso>
        <div className="fila">
          <button disabled={enviando}>{enviando ? 'Radicando…' : 'Radicar solicitud'}</button>
          <button type="button" className="secundario" onClick={() => nav(-1)}>Cancelar</button>
        </div>
      </form>
    </>
  )
}

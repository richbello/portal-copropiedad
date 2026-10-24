import { useState } from 'react'
import { api, fecha, fechaHora, NOMBRES } from '../api'
import { Aviso, Encabezado, Modal, useDatos, useSesion } from '../App'

// Censo de una unidad. Lo usa el propietario o residente (su unidad) y la administración (cualquiera).
export function CensoUnidad({ unidadId, onCambio }) {
  const { datos: c, error, recargar } = useDatos(`/api/censo/unidades/${unidadId}`)
  const [form, setForm] = useState(null)
  const [msg, setMsg] = useState('')
  const listo = () => { setForm(null); recargar(); onCambio?.() }

  async function confirmar() {
    setMsg('')
    await api.post(`/api/censo/unidades/${unidadId}/confirmar`)
    setMsg('Gracias. Quedó registrado que el censo de su unidad está al día.')
    recargar(); onCambio?.()
  }
  async function quitar(tipo, item, nombre) {
    if (!confirm(`¿Quitar a ${nombre} del censo?`)) return
    await api.del(`/api/censo/unidades/${unidadId}/${tipo}/${item.id}`); listo()
  }

  if (error) return <Aviso>{error}</Aviso>
  if (!c) return <p className="vacio">Cargando…</p>
  const parqPorVehiculo = Object.fromEntries(c.parqueaderos.filter(p => p.vehiculo).map(p => [p.vehiculo.id, p]))

  return (
    <div className="pila">
      <div className={`aviso ${c.vigente ? 'ok' : 'alerta'}`}>
        <div className="fila" style={{ justifyContent: 'space-between' }}>
          <span>{c.vigente
            ? `Censo confirmado el ${fechaHora(c.confirmado)}`
            : c.confirmado ? `El censo se confirmó el ${fechaHora(c.confirmado)} y ya pasaron más de ${c.meses_vigencia} meses. Revíselo y confírmelo de nuevo.`
              : 'El censo de esta unidad no se ha confirmado. Revise las personas, mascotas y vehículos y confírmelo.'}</span>
          <button onClick={confirmar}>Confirmar que está al día</button>
        </div>
      </div>
      {msg && <Aviso tipo="ok">{msg}</Aviso>}

      <section className="panel">
        <div className="fila" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Personas que viven aquí</h2>
          <button className="secundario" onClick={() => setForm({ tipo: 'personas' })}>Agregar persona</button>
        </div>
        {c.personas.length === 0 ? <p className="suave">Nadie registrado todavía.</p> :
          <table><tbody>{c.personas.map(p => (
            <tr key={p.id}>
              <td><strong>{p.nombre}</strong>
                <div className="peq suave">{NOMBRES.relaciones[p.relacion]}{p.menor_de_edad && ', menor de edad'}{p.contacto_emergencia && ', contacto de emergencia'}</div></td>
              <td className="peq">{p.telefono}</td>
              <td className="derecha" style={{ whiteSpace: 'nowrap' }}>
                <button className="texto" onClick={() => setForm({ tipo: 'personas', item: p })}>Editar</button>
                <button className="texto" onClick={() => quitar('personas', p, p.nombre)}>Quitar</button></td>
            </tr>))}</tbody></table>}
      </section>

      <section className="panel">
        <div className="fila" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Mascotas</h2>
          <button className="secundario" onClick={() => setForm({ tipo: 'mascotas' })}>Agregar mascota</button>
        </div>
        {c.mascotas.length === 0 ? <p className="suave">No hay mascotas registradas.</p> :
          <table><tbody>{c.mascotas.map(m => (
            <tr key={m.id}>
              <td><strong>{m.nombre}</strong>
                <div className="peq suave">{NOMBRES.especies[m.especie]}{m.raza && `, ${m.raza}`}{m.color && `, ${m.color}`}</div>
                {m.falta_poliza && <div className="peq" style={{ color: 'var(--rojo)' }}>Raza potencialmente peligrosa: falta registrar la póliza de responsabilidad civil</div>}
                {m.vacuna_vencida && <div className="peq" style={{ color: 'var(--ocre)' }}>La vacuna antirrábica venció el {fecha(m.vacuna_antirrabica_vence)}</div>}</td>
              <td className="peq">{m.vacuna_antirrabica_vence && !m.vacuna_vencida && `Vacuna hasta ${fecha(m.vacuna_antirrabica_vence)}`}</td>
              <td className="derecha" style={{ whiteSpace: 'nowrap' }}>
                <button className="texto" onClick={() => setForm({ tipo: 'mascotas', item: m })}>Editar</button>
                <button className="texto" onClick={() => quitar('mascotas', m, m.nombre)}>Quitar</button></td>
            </tr>))}</tbody></table>}
      </section>

      <section className="panel">
        <div className="fila" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
          <h2 style={{ margin: 0 }}>Vehículos y parqueaderos</h2>
          <button className="secundario" onClick={() => setForm({ tipo: 'vehiculos' })}>Agregar vehículo</button>
        </div>
        <p className="peq suave" style={{ marginBottom: 8 }}>Registrar su vehículo lo inscribe en la lista de espera para el próximo sorteo de parqueaderos.</p>
        {c.vehiculos.length === 0 ? <p className="suave">No hay vehículos registrados.</p> :
          <table><tbody>{c.vehiculos.map(v => {
            const p = parqPorVehiculo[v.id]
            return (
              <tr key={v.id}>
                <td><strong>{NOMBRES.vehiculos[v.tipo]}{v.placa && ` ${v.placa}`}</strong>
                  <div className="peq suave">{[v.marca, v.color].filter(Boolean).join(', ')}</div>
                  {v.tipo !== 'bicicleta' && <div className="fila" style={{ gap: 6, marginTop: 6 }}>
                    <Documento nombre="SOAT" fecha={v.soat_vence} est={v.soat} />
                    <Documento nombre="Tecnomecánica" fecha={v.tecnomecanica_vence} est={v.tecnomecanica} sinDato="Tecnomecánica: no registrada" />
                  </div>}</td>
                <td>{p ? <span className="estado respondida">Parqueadero {p.codigo}</span>
                  : <span className="estado en_tramite">En espera de parqueadero</span>}</td>
                <td className="derecha" style={{ whiteSpace: 'nowrap' }}>
                  <button className="texto" onClick={() => setForm({ tipo: 'vehiculos', item: v })}>Editar</button>
                  <button className="texto" onClick={() => quitar('vehiculos', v, `${NOMBRES.vehiculos[v.tipo].toLowerCase()} ${v.placa || ''}`)}>Quitar</button></td>
              </tr>)
          })}</tbody></table>}
        {c.parqueaderos.filter(p => !p.vehiculo).map(p =>
          <p key={p.id} className="peq" style={{ marginTop: 8 }}>También tiene asignado el parqueadero {p.codigo} ({p.tipo}).</p>)}
      </section>
      {form && <FormCenso unidadId={unidadId} {...form} onCerrar={() => setForm(null)} onListo={listo} />}
    </div>
  )
}

// Estado de un documento con fecha de vencimiento (SOAT, tecnomecánica)
export function Documento({ nombre, fecha: vence, est, sinDato }) {
  if (!est || est.estado === 'sin_dato') return <span className="doc doc-sin">{sinDato || `${nombre}: sin fecha`}</span>
  const txt = est.estado === 'vencido' ? `${nombre} vencido desde ${fecha(vence)}`
    : est.estado === 'por_vencer' ? (est.dias === 0 ? `${nombre} vence hoy` : `${nombre} vence en ${est.dias} días`)
    : `${nombre} hasta ${fecha(vence)}`
  return <span className={`doc doc-${est.estado}`}>{txt}</span>
}

const VACIOS = {
  personas: { nombre: '', relacion: 'familiar', documento: '', telefono: '', menor_de_edad: false, contacto_emergencia: false },
  mascotas: { nombre: '', especie: 'perro', raza: '', color: '', vacuna_antirrabica_vence: '', potencialmente_peligrosa: false, poliza: '' },
  vehiculos: { tipo: 'carro', placa: '', marca: '', color: '', soat_vence: '', tecnomecanica_vence: '' },
}
const TITULOS = { personas: 'persona', mascotas: 'mascota', vehiculos: 'vehículo' }

function FormCenso({ unidadId, tipo, item, onCerrar, onListo }) {
  const [f, setF] = useState(() => {
    const base = { ...VACIOS[tipo] }
    if (item) for (const k of Object.keys(base)) base[k] = item[k] ?? base[k]
    return base
  })
  const [error, setError] = useState('')
  const set = k => e => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  async function guardar(e) {
    e.preventDefault(); setError('')
    const datos = { ...f }
    for (const k of ['vacuna_antirrabica_vence', 'soat_vence', 'tecnomecanica_vence']) if (k in datos && !datos[k]) datos[k] = null
    try {
      if (item) await api.put(`/api/censo/unidades/${unidadId}/${tipo}/${item.id}`, datos)
      else await api.post(`/api/censo/unidades/${unidadId}/${tipo}`, datos)
      onListo()
    } catch (err) { setError(err.message) }
  }
  return (
    <Modal titulo={`${item ? 'Editar' : 'Agregar'} ${TITULOS[tipo]}`} onCerrar={onCerrar}>
      <form className="formulario" onSubmit={guardar}>
        {tipo === 'personas' && <>
          <label>Nombre completo<input required minLength={3} value={f.nombre} onChange={set('nombre')} /></label>
          <label>Relación con la unidad<select value={f.relacion} onChange={set('relacion')}>
            {Object.entries(NOMBRES.relaciones).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label className="casilla"><input type="checkbox" checked={f.menor_de_edad} onChange={set('menor_de_edad')} /> Es menor de edad</label>
          {!f.menor_de_edad && <div className="formulario-2">
            <label>Documento<span className="ayuda">Opcional</span><input value={f.documento} onChange={set('documento')} /></label>
            <label>Celular<span className="ayuda">Opcional</span><input value={f.telefono} onChange={set('telefono')} /></label>
          </div>}
          {!f.menor_de_edad && <label className="casilla"><input type="checkbox" checked={f.contacto_emergencia} onChange={set('contacto_emergencia')} /> Contactar en caso de emergencia</label>}
          {f.menor_de_edad && <p className="peq suave">De los menores solo se guarda el nombre.</p>}
        </>}
        {tipo === 'mascotas' && <>
          <div className="formulario-2">
            <label>Nombre<input required value={f.nombre} onChange={set('nombre')} /></label>
            <label>Especie<select value={f.especie} onChange={set('especie')}>
              {Object.entries(NOMBRES.especies).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            <label>Raza<input value={f.raza} onChange={set('raza')} /></label>
            <label>Color<input value={f.color} onChange={set('color')} /></label>
            <label>Vacuna antirrábica vigente hasta<input type="date" value={f.vacuna_antirrabica_vence || ''} onChange={set('vacuna_antirrabica_vence')} /></label>
          </div>
          {f.especie === 'perro' && <>
            <label className="casilla"><input type="checkbox" checked={f.potencialmente_peligrosa} onChange={set('potencialmente_peligrosa')} /> Es de raza potencialmente peligrosa</label>
            {f.potencialmente_peligrosa && <label>Número de la póliza de responsabilidad civil
              <span className="ayuda">Obligatoria para estas razas (Ley 1801 de 2016)</span>
              <input value={f.poliza} onChange={set('poliza')} /></label>}
          </>}
        </>}
        {tipo === 'vehiculos' && <div className="formulario-2">
          <label>Tipo<select value={f.tipo} onChange={set('tipo')}>
            {Object.entries(NOMBRES.vehiculos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          {f.tipo !== 'bicicleta' && <label>Placa<input required value={f.placa} onChange={set('placa')} style={{ textTransform: 'uppercase' }} /></label>}
          <label>Marca y modelo<input value={f.marca} onChange={set('marca')} /></label>
          <label>Color<input value={f.color} onChange={set('color')} /></label>
          {f.tipo !== 'bicicleta' && <>
            <label>SOAT vigente hasta<input type="date" value={f.soat_vence || ''} onChange={set('soat_vence')} /></label>
            <label>Tecnomecánica vigente hasta
              <span className="ayuda">Déjela vacía si su vehículo aún no la requiere (los carros particulares nuevos desde el 5.º año y las motos desde el 2.º)</span>
              <input type="date" value={f.tecnomecanica_vence || ''} onChange={set('tecnomecanica_vence')} /></label>
          </>}
        </div>}
        {tipo === 'vehiculos' && f.tipo !== 'bicicleta' && <p className="peq suave">Le avisaremos 30 días antes, 7 días antes y el día del vencimiento.</p>}
        <Aviso>{error}</Aviso>
        <div><button>{item ? 'Guardar cambios' : `Agregar ${TITULOS[tipo]}`}</button></div>
      </form>
    </Modal>
  )
}

export default function MiUnidad() {
  const { usuario } = useSesion()
  const [unidad, setUnidad] = useState(usuario.unidades[0]?.id)
  return (
    <>
      <Encabezado titulo="Mi unidad"
        descripcion="Quién vive en su apartamento, sus mascotas y vehículos. Solo lo ven usted y la administración.">
        {usuario.unidades.length > 1 && <select value={unidad} onChange={e => setUnidad(Number(e.target.value))} aria-label="Unidad">
          {usuario.unidades.map(u => <option key={u.id} value={u.id}>{u.etiqueta}</option>)}</select>}
      </Encabezado>
      {unidad ? <CensoUnidad key={unidad} unidadId={unidad} /> : <p className="vacio">Su usuario no tiene unidades asignadas.</p>}
    </>
  )
}

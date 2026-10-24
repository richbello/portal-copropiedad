import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { api, esGestion, esLecturaGlobal, getToken, NOMBRES, setToken } from './api'
import Login from './pages/Login'
import PrimerIngreso from './pages/PrimerIngreso'
import Inicio from './pages/Inicio'
import EstadoCuenta from './pages/EstadoCuenta'
import Solicitudes from './pages/Solicitudes'
import SolicitudDetalle from './pages/SolicitudDetalle'
import NuevaSolicitud from './pages/NuevaSolicitud'
import Documentos from './pages/Documentos'
import Presupuesto from './pages/Presupuesto'
import Notificaciones from './pages/Notificaciones'
import AdminTablero from './pages/AdminTablero'
import AdminCartera from './pages/AdminCartera'
import AdminFacturacion from './pages/AdminFacturacion'
import AdminUsuarios from './pages/AdminUsuarios'
import AdminConfiguracion from './pages/AdminConfiguracion'

const SesionCtx = createContext(null)
export const useSesion = () => useContext(SesionCtx)

export default function App() {
  const [usuario, setUsuario] = useState(null)
  const [cargando, setCargando] = useState(!!getToken())

  const recargar = useCallback(async () => {
    if (!getToken()) { setUsuario(null); setCargando(false); return }
    try { setUsuario(await api.get('/api/auth/me')) } catch { setUsuario(null) }
    setCargando(false)
  }, [])

  useEffect(() => { recargar() }, [recargar])
  useEffect(() => {
    const salir = () => setUsuario(null)
    window.addEventListener('sesion-expirada', salir)
    return () => window.removeEventListener('sesion-expirada', salir)
  }, [])

  const ingresar = (token, u) => { setToken(token); setUsuario(u) }
  const salir = () => { setToken(null); setUsuario(null) }

  if (cargando) return <div className="vacio">Cargando…</div>
  if (!usuario) return <Login onIngreso={ingresar} />
  if (usuario.debe_cambiar_password || !usuario.acepto_tratamiento_datos)
    return <PrimerIngreso usuario={usuario} onListo={recargar} onSalir={salir} />

  return (
    <SesionCtx.Provider value={{ usuario, recargar, salir }}>
      <Marco>
        <Routes>
          <Route path="/" element={esLecturaGlobal(usuario) ? <AdminTablero /> : <Inicio />} />
          <Route path="/estado-cuenta" element={<EstadoCuenta />} />
          <Route path="/solicitudes" element={<Solicitudes />} />
          <Route path="/solicitudes/nueva" element={<NuevaSolicitud />} />
          <Route path="/solicitudes/:id" element={<SolicitudDetalle />} />
          <Route path="/documentos" element={<Documentos />} />
          <Route path="/presupuesto" element={<Presupuesto />} />
          <Route path="/notificaciones" element={<Notificaciones />} />
          {esLecturaGlobal(usuario) && <Route path="/admin/cartera" element={<AdminCartera />} />}
          {esGestion(usuario) && <Route path="/admin/facturacion" element={<AdminFacturacion />} />}
          {esGestion(usuario) && <Route path="/admin/usuarios" element={<AdminUsuarios />} />}
          {esLecturaGlobal(usuario) && <Route path="/admin/configuracion" element={<AdminConfiguracion />} />}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Marco>
    </SesionCtx.Provider>
  )
}

function Marco({ children }) {
  const { usuario, salir } = useSesion()
  const [abierto, setAbierto] = useState(false)
  const [sinLeer, setSinLeer] = useState(0)
  const loc = useLocation()

  useEffect(() => { setAbierto(false) }, [loc.pathname])
  useEffect(() => {
    api.get('/api/auth/notificaciones').then(n => setSinLeer(n.filter(x => !x.leida).length)).catch(() => {})
  }, [loc.pathname])

  const global = esLecturaGlobal(usuario)
  const gestion = esGestion(usuario)
  const unidades = usuario.unidades.map(u => u.etiqueta).join(', ')

  return (
    <div className="app">
      <div className="barra-movil">
        <strong style={{ fontFamily: 'var(--display)' }}>Portal del conjunto</strong>
        <button onClick={() => setAbierto(true)} aria-label="Abrir menú">Menú</button>
      </div>
      <aside className={'lateral' + (abierto ? ' abierto' : '')}>
        <div className="fila" style={{ justifyContent: 'space-between' }}>
          <div className="marca">Portal del conjunto<small>{global ? NOMBRES.roles[usuario.rol] : unidades}</small></div>
          {abierto && <button className="secundario" style={{ color: '#fff', borderColor: '#fff' }} onClick={() => setAbierto(false)}>Cerrar</button>}
        </div>
        <nav className="nav">
          <NavLink to="/" end>{global ? 'Tablero' : 'Inicio'}</NavLink>
          {!global && <NavLink to="/estado-cuenta">Estado de cuenta</NavLink>}
          <NavLink to="/solicitudes">Solicitudes</NavLink>
          <NavLink to="/documentos">Documentos</NavLink>
          <NavLink to="/presupuesto">Presupuesto y gastos</NavLink>
          <NavLink to="/notificaciones">Notificaciones {sinLeer > 0 && <span className="punto">{sinLeer}</span>}</NavLink>
          {global && <>
            <div className="nav-grupo">Administración</div>
            <NavLink to="/admin/cartera">Cartera</NavLink>
            {gestion && <NavLink to="/admin/facturacion">Facturación y pagos</NavLink>}
            {gestion && <NavLink to="/admin/usuarios">Propietarios y usuarios</NavLink>}
            <NavLink to="/admin/configuracion">Configuración y auditoría</NavLink>
          </>}
        </nav>
        <div className="usuario-lateral">
          <div><strong>{usuario.nombre}</strong></div>
          <div style={{ opacity: 0.75 }}>{usuario.email}</div>
          <button onClick={salir}>Cerrar sesión</button>
        </div>
      </aside>
      <main className="contenido">{children}</main>
    </div>
  )
}

export function Encabezado({ titulo, descripcion, children }) {
  return (
    <div className="encabezado">
      <div><h1>{titulo}</h1>{descripcion && <p>{descripcion}</p>}</div>
      {children && <div className="fila">{children}</div>}
    </div>
  )
}

export function Aviso({ tipo = 'error', children }) {
  if (!children) return null
  return <div className={`aviso ${tipo}`} role={tipo === 'error' ? 'alert' : 'status'}>{children}</div>
}

export function Modal({ titulo, onCerrar, children }) {
  useEffect(() => {
    const k = e => e.key === 'Escape' && onCerrar()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onCerrar])
  return (
    <div className="modal-fondo" onClick={onCerrar}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={titulo} onClick={e => e.stopPropagation()}>
        <div className="fila" style={{ justifyContent: 'space-between', marginBottom: 16 }}>
          <h2>{titulo}</h2>
          <button className="texto" onClick={onCerrar}>Cerrar</button>
        </div>
        {children}
      </div>
    </div>
  )
}

// Hook sencillo para cargar datos
export function useDatos(ruta, deps = []) {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const cargar = useCallback(() => {
    if (!ruta) return
    setError('')
    api.get(ruta).then(setDatos).catch(e => setError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ruta, ...deps])
  useEffect(() => { cargar() }, [cargar])
  return { datos, error, recargar: cargar, setDatos }
}

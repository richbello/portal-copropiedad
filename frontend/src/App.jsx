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
import Calendario from './pages/Calendario'
import MiUnidad from './pages/MiUnidad'
import Manual from './pages/Manual'
import AdminCenso from './pages/AdminCenso'
import AdminParqueaderos from './pages/AdminParqueaderos'
import AdminVencimientos from './pages/AdminVencimientos'
import Clasificados from './pages/Clasificados'

const SesionCtx = createContext(null)
export const useSesion = () => useContext(SesionCtx)

export default function App() {
  const [usuario, setUsuario] = useState(null)
  const [cargando, setCargando] = useState(!!getToken())
  const [conjunto, setConjunto] = useState('Conjunto Avellana Ciudad Verde')

  // El nombre viene del servidor (NOMBRE_CONJUNTO), para no repetirlo en el código
  useEffect(() => {
    api.get('/api/salud').then(r => { setConjunto(r.conjunto); document.title = r.conjunto }).catch(() => {})
  }, [])

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
  if (!usuario) return <Login onIngreso={ingresar} conjunto={conjunto} />
  if (usuario.debe_cambiar_password || !usuario.acepto_tratamiento_datos)
    return <PrimerIngreso usuario={usuario} onListo={recargar} onSalir={salir} />

  return (
    <SesionCtx.Provider value={{ usuario, recargar, salir, conjunto }}>
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
          <Route path="/calendario" element={<Calendario />} />
          <Route path="/mi-unidad" element={<MiUnidad />} />
          <Route path="/manual" element={<Manual />} />
          <Route path="/clasificados" element={<Clasificados />} />
          {esLecturaGlobal(usuario) && <Route path="/admin/censo" element={<AdminCenso />} />}
          {esLecturaGlobal(usuario) && <Route path="/admin/parqueaderos" element={<AdminParqueaderos />} />}
          {usuario.rol === 'administrador' && <Route path="/admin/vencimientos" element={<AdminVencimientos />} />}
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
  const { usuario, salir, conjunto } = useSesion()
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

  // Accesos de la barra inferior en el celular: lo que más se usa según el rol
  const atajos = global
    ? [['/', 'Tablero', 'inicio'], ['/solicitudes', 'Solicitudes', 'solicitudes'], ['/admin/censo', 'Censo', 'unidad'], ['/calendario', 'Calendario', 'calendario']]
    : [['/', 'Inicio', 'inicio'], ['/mi-unidad', 'Mi unidad', 'unidad'], ['/calendario', 'Calendario', 'calendario'], ['/solicitudes', 'Solicitudes', 'solicitudes']]

  return (
    <div className="app">
      <header className="barra-movil">
        <strong className="barra-movil-nombre">{conjunto}</strong>
        <NavLink to="/notificaciones" className="campana" aria-label={`Notificaciones${sinLeer ? `, ${sinLeer} sin leer` : ''}`}>
          <Icono n="campana" />{sinLeer > 0 && <span className="punto">{sinLeer}</span>}
        </NavLink>
      </header>
      <nav className="barra-inferior" aria-label="Navegación principal">
        {atajos.map(([to, txt, ic]) => <NavLink key={to} to={to} end={to === '/'}><Icono n={ic} /><span>{txt}</span></NavLink>)}
        <button className={abierto ? 'activa' : ''} onClick={() => setAbierto(true)} aria-label="Más opciones"><Icono n="menu" /><span>Más</span></button>
      </nav>
      {abierto && <div className="velo" onClick={() => setAbierto(false)} aria-hidden="true" />}
      <aside className={'lateral' + (abierto ? ' abierto' : '')}>
        <div className="fila" style={{ justifyContent: 'space-between', flexWrap: 'nowrap' }}>
          <div className="marca">{conjunto}<small>{global ? NOMBRES.roles[usuario.rol] : unidades}</small></div>
          {abierto && <button className="cerrar-menu" onClick={() => setAbierto(false)} aria-label="Cerrar menú"><Icono n="cerrar" /></button>}
        </div>
        <nav className="nav">
          <NavLink to="/" end>{global ? 'Tablero' : 'Inicio'}</NavLink>
          {!global && <NavLink to="/estado-cuenta">Estado de cuenta</NavLink>}
          {!global && <NavLink to="/mi-unidad">Mi unidad</NavLink>}
          <NavLink to="/calendario">Calendario</NavLink>
          <NavLink to="/solicitudes">Solicitudes</NavLink>
          <NavLink to="/clasificados">Negocios y clasificados</NavLink>
          <NavLink to="/manual">Manual de convivencia</NavLink>
          <NavLink to="/documentos">Documentos</NavLink>
          <NavLink to="/presupuesto">Presupuesto y gastos</NavLink>
          <NavLink to="/notificaciones">Notificaciones {sinLeer > 0 && <span className="punto">{sinLeer}</span>}</NavLink>
          {global && <>
            <div className="nav-grupo">Administración</div>
            <NavLink to="/admin/cartera">Cartera</NavLink>
            <NavLink to="/admin/censo">Censo</NavLink>
            <NavLink to="/admin/parqueaderos">Parqueaderos</NavLink>
            {usuario.rol === 'administrador' && <NavLink to="/admin/vencimientos">Vencimientos</NavLink>}
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

const TRAZOS = {
  inicio: 'M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
  unidad: 'M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16M15 9h4a1 1 0 0 1 1 1v11M2 21h20M8 8h3M8 12h3M8 16h3',
  calendario: 'M4 6a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1zM4 10h16M8 3v4M16 3v4',
  solicitudes: 'M4 5h16v11H9l-5 4z',
  menu: 'M4 7h16M4 12h16M4 17h16',
  campana: 'M6 16V11a6 6 0 1 1 12 0v5l2 2H4zM10 21h4',
  cerrar: 'M6 6l12 12M18 6L6 18',
}
export function Icono({ n }) {
  return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={TRAZOS[n]} /></svg>
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

import { useState } from 'react'
import { Outlet, NavLink, Link, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import {
  LayoutDashboard, Building2, BookOpen,
  Settings, LogOut, Phone, Menu, X,
} from 'lucide-react'
import AssistantChat from './AssistantChat'

const NAV = [
  { to: '/dashboard',            label: 'Dashboard',  icon: LayoutDashboard, exact: true },
  { to: '/dashboard/properties', label: 'Properties', icon: Building2 },
  { to: '/dashboard/knowledge',  label: 'Knowledge',  icon: BookOpen },
  { to: '/dashboard/settings',   label: 'Settings',   icon: Settings },
]

export default function Layout({ session }) {
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  async function handleSignOut() {
    if (!window.confirm('Sign out of NexaDesk?')) return
    await supabase.auth.signOut()
    navigate('/login')
  }

  const appName = import.meta.env.VITE_APP_NAME || 'NexaDesk'

  function closeSidebar() { setSidebarOpen(false) }

  return (
    <div className="flex h-screen overflow-hidden">

      {/* Mobile top bar */}
      <div className="fixed top-0 left-0 right-0 h-14 bg-navy-600 flex items-center justify-between px-4 z-30 md:hidden">
        <Link to="/dashboard" className="flex items-center gap-2">
          <Phone className="w-4 h-4 text-accent" />
          <span className="text-white font-semibold text-base">{appName}</span>
        </Link>
        <button onClick={() => setSidebarOpen(true)} className="text-gray-400 hover:text-white p-1">
          <Menu className="w-6 h-6" />
        </button>
      </div>

      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={closeSidebar} />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed md:static inset-y-0 left-0 z-50 w-64 bg-navy-600 flex flex-col flex-shrink-0
        transition-transform duration-200 md:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-6 border-b border-navy-700">
          <Link to="/dashboard" className="flex items-center gap-2">
            <Phone className="w-5 h-5 text-accent" />
            <span className="text-white font-semibold text-lg">{appName}</span>
          </Link>
          <button onClick={closeSidebar} className="text-gray-400 hover:text-white md:hidden">
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV.map(({ to, label, icon: Icon, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              onClick={closeSidebar}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-accent text-white' : 'text-gray-400 hover:bg-navy-700 hover:text-white'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-3 pb-4 border-t border-navy-700 pt-3 space-y-1">
          <div className="flex items-center gap-3 px-3 pt-2 pb-1">
            <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center text-white text-xs font-semibold flex-shrink-0">
              {session?.user?.email?.[0]?.toUpperCase() || '?'}
            </div>
            <p className="text-white text-xs font-medium truncate flex-1">{session?.user?.email}</p>
          </div>
          <button
            onClick={handleSignOut}
            className="flex items-center gap-2 text-gray-400 hover:text-white text-xs transition-colors w-full px-3 py-1.5 rounded-lg hover:bg-navy-700"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-gray-50 pt-14 md:pt-0">
        <Outlet />
      </main>

      <AssistantChat />
    </div>
  )
}

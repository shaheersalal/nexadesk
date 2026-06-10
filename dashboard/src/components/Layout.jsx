import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import {
  LayoutDashboard, Users, Building2, BookOpen,
  CalendarDays, Settings, LogOut, Phone, Bot
} from 'lucide-react'

const nav = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/dashboard/leads', label: 'Leads', icon: Users },
  { to: '/dashboard/properties', label: 'Properties', icon: Building2 },
  { to: '/dashboard/ai-agent', label: 'AI Agent', icon: Bot },
  { to: '/dashboard/knowledge', label: 'Knowledge', icon: BookOpen },
  { to: '/dashboard/appointments', label: 'Appointments', icon: CalendarDays },
  { to: '/dashboard/settings', label: 'Settings', icon: Settings },
]

export default function Layout({ session }) {
  const navigate = useNavigate()

  async function handleSignOut() {
    await supabase.auth.signOut()
    navigate('/login')
  }

  const appName = import.meta.env.VITE_APP_NAME || 'NexaDesk'

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-navy-600 flex flex-col flex-shrink-0">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-navy-700">
          <Phone className="w-5 h-5 text-accent mr-2" />
          <span className="text-white font-semibold text-lg">{appName}</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {nav.map(({ to, label, icon: Icon, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-accent text-white'
                    : 'text-gray-400 hover:bg-navy-700 hover:text-white'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User + Sign out */}
        <div className="p-4 border-t border-navy-700">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-white text-sm font-semibold">
              {session?.user?.email?.[0]?.toUpperCase() || '?'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-xs font-medium truncate">{session?.user?.email}</p>
            </div>
          </div>
          <button
            onClick={handleSignOut}
            className="flex items-center gap-2 text-gray-400 hover:text-white text-xs transition-colors w-full"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-gray-50">
        <Outlet />
      </main>
    </div>
  )
}

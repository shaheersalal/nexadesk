import { useState, useEffect } from 'react'
import { Outlet, NavLink, Link, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import {
  LayoutDashboard, Building2, BookOpen, Users, Calendar, Bot,
  Settings, LogOut, Phone, Menu, X, Sparkles, ShieldCheck, MessageSquare, LifeBuoy, BarChart3,
  ChevronsUpDown,
} from 'lucide-react'
import { getAccessibleCompanies, getSelectedCompanyId, setSelectedCompanyId } from '../lib/api'

const ADMIN_UID = '7227a933-56ef-45c4-8cbc-1c8331c74b21'
import AssistantChat from './AssistantChat'
import SupportChat from './SupportChat'

const NAV = [
  { to: '/dashboard',             label: 'Dashboard',    icon: LayoutDashboard, exact: true },
  { to: '/dashboard/analytics',   label: 'Analytics',    icon: BarChart3 },
  { to: '/dashboard/leads',       label: 'Leads',        icon: Users },
  { to: '/dashboard/properties',  label: 'Properties',   icon: Building2 },
  { to: '/dashboard/appointments',label: 'Appointments', icon: Calendar },
  { to: '/dashboard/knowledge',   label: 'Knowledge',    icon: BookOpen },
  { to: '/dashboard/ai-agent',    label: 'AI Agent',     icon: Bot },
  { to: '/dashboard/settings',    label: 'Settings',     icon: Settings },
]

export default function Layout({ session }) {
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [onboardingComplete, setOnboardingComplete] = useState(true) // default true to avoid flash
  const [supportOpen, setSupportOpen] = useState(false)
  const [accessibleCompanies, setAccessibleCompanies] = useState([])
  const [selectedId, setSelectedId] = useState(getSelectedCompanyId())
  const isAdmin = session?.user?.id === ADMIN_UID

  useEffect(() => {
    async function checkSetup() {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return
      const { data: userData } = await supabase.from('users').select('company_id').eq('id', user.id).single()
      if (!userData?.company_id) return
      const { data } = await supabase.from('companies').select('onboarding_complete').eq('id', userData.company_id).single()
      setOnboardingComplete(data?.onboarding_complete ?? false)
    }
    async function loadCompanies() {
      try {
        const companies = await getAccessibleCompanies()
        setAccessibleCompanies(companies)
      } catch {}
    }
    checkSetup()
    loadCompanies()
  }, [])

  function handleCompanySwitch(id) {
    setSelectedCompanyId(id || null)
    setSelectedId(id || null)
    window.location.reload()
  }

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

        {/* Company switcher — shown only for parent accounts with 2+ accessible companies */}
        {accessibleCompanies.length > 1 && (
          <div className="px-3 py-2 border-b border-navy-700">
            <div className="relative">
              <select
                value={selectedId || ''}
                onChange={(e) => handleCompanySwitch(e.target.value)}
                className="w-full appearance-none bg-navy-700 text-white text-xs rounded-lg px-3 py-2 pr-7 focus:outline-none focus:ring-1 focus:ring-accent cursor-pointer"
              >
                <option value="">All offices</option>
                {accessibleCompanies.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <ChevronsUpDown className="w-3.5 h-3.5 text-gray-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>
          </div>
        )}

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

        {isAdmin && (
          <div className="px-3 pb-2 space-y-1">
            <Link
              to="/dashboard/support"
              onClick={closeSidebar}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-amber-400 hover:bg-navy-700 hover:text-amber-300 transition-colors"
            >
              <MessageSquare className="w-4 h-4" />
              Support Inbox
            </Link>
            <Link
              to="/admin"
              onClick={closeSidebar}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-amber-400 hover:bg-navy-700 hover:text-amber-300 transition-colors"
            >
              <ShieldCheck className="w-4 h-4" />
              Admin Panel
            </Link>
          </div>
        )}

        <div className="px-3 pb-4 border-t border-navy-700 pt-3 space-y-1">
          <div className="flex items-center gap-3 px-3 pt-2 pb-1">
            <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center text-white text-xs font-semibold flex-shrink-0">
              {session?.user?.email?.[0]?.toUpperCase() || '?'}
            </div>
            <p className="text-white text-xs font-medium truncate flex-1">{session?.user?.email}</p>
          </div>
          {!isAdmin && (
            <button
              onClick={() => { setSupportOpen(true); closeSidebar() }}
              className="flex items-center gap-2 text-gray-400 hover:text-white text-xs transition-colors w-full px-3 py-1.5 rounded-lg hover:bg-navy-700"
            >
              <LifeBuoy className="w-3.5 h-3.5" />
              Support
            </button>
          )}
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
        {!onboardingComplete && (
          <div className="bg-amber-50 border-b border-amber-200 px-5 py-3 flex items-center justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <Sparkles className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <p className="text-sm text-amber-800">
                Your AI receptionist isn't configured yet — it won't answer calls until you complete setup.
              </p>
            </div>
            <Link
              to="/setup"
              className="text-sm font-semibold text-amber-900 hover:text-amber-700 whitespace-nowrap transition-colors"
            >
              Complete setup →
            </Link>
          </div>
        )}
        <Outlet />
      </main>

      <AssistantChat />
      {supportOpen && <SupportChat onClose={() => setSupportOpen(false)} />}
    </div>
  )
}

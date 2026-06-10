import { useState, useEffect } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import {
  LayoutDashboard, Users, Building2, BookOpen,
  CalendarDays, Settings, LogOut, Phone, Bot,
  Headset, Inbox,
} from 'lucide-react'
import SupportChat from './SupportChat'

const ADMIN_UID = '7227a933-56ef-45c4-8cbc-1c8331c74b21'

const USER_NAV = [
  { to: '/dashboard',              label: 'Dashboard',   icon: LayoutDashboard, exact: true },
  { to: '/dashboard/leads',        label: 'Leads',       icon: Users },
  { to: '/dashboard/properties',   label: 'Properties',  icon: Building2 },
  { to: '/dashboard/ai-agent',     label: 'AI Agent',    icon: Bot },
  { to: '/dashboard/knowledge',    label: 'Knowledge',   icon: BookOpen },
  { to: '/dashboard/appointments', label: 'Appointments',icon: CalendarDays },
  { to: '/dashboard/settings',     label: 'Settings',    icon: Settings },
]

const ADMIN_NAV = [
  ...USER_NAV,
  { to: '/dashboard/support', label: 'Support Inbox', icon: Inbox },
]

export default function Layout({ session }) {
  const navigate = useNavigate()
  const [showHelp, setShowHelp] = useState(false)
  const [unread, setUnread] = useState(0)
  const [companyId, setCompanyId] = useState(null)

  const isAdmin = session?.user?.id === ADMIN_UID
  const nav = isAdmin ? ADMIN_NAV : USER_NAV

  // Load unread count for non-admin users
  useEffect(() => {
    if (isAdmin) return
    async function init() {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return
      const { data: ud } = await supabase.from('users').select('company_id').eq('id', user.id).single()
      const cid = ud?.company_id
      if (!cid) return
      setCompanyId(cid)
      const { count } = await supabase.from('support_messages')
        .select('id', { count: 'exact', head: true })
        .eq('company_id', cid).eq('sender_role', 'admin').eq('read_by_user', false)
      setUnread(count || 0)
    }
    init()
  }, [isAdmin])

  // Realtime badge: increment when admin replies
  useEffect(() => {
    if (!companyId || isAdmin) return
    const channel = supabase.channel(`layout_unread_${companyId}`)
      .on('postgres_changes', {
        event: 'INSERT', schema: 'public', table: 'support_messages',
        filter: `company_id=eq.${companyId}`,
      }, payload => {
        if (payload.new.sender_role === 'admin') setUnread(prev => prev + 1)
      })
      .subscribe()
    return () => supabase.removeChannel(channel)
  }, [companyId, isAdmin])

  async function handleSignOut() {
    await supabase.auth.signOut()
    navigate('/login')
  }

  const appName = import.meta.env.VITE_APP_NAME || 'NexaDesk'

  return (
    <div className="flex h-screen overflow-hidden">

      {/* Sidebar */}
      <aside className="w-64 bg-navy-600 flex flex-col flex-shrink-0">
        <div className="h-16 flex items-center px-6 border-b border-navy-700">
          <Phone className="w-5 h-5 text-accent mr-2" />
          <span className="text-white font-semibold text-lg">{appName}</span>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {nav.map(({ to, label, icon: Icon, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
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

        {/* Bottom section */}
        <div className="px-3 pb-4 space-y-1 border-t border-navy-700 pt-3">

          {/* Help button — non-admin only */}
          {!isAdmin && (
            <button
              onClick={() => { setShowHelp(true); setUnread(0) }}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:bg-navy-700 hover:text-white transition-colors"
            >
              <div className="relative">
                <Headset className="w-4 h-4" />
                {unread > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 w-3.5 h-3.5 bg-accent text-white text-[9px] rounded-full flex items-center justify-center font-bold leading-none">
                    {unread > 9 ? '9+' : unread}
                  </span>
                )}
              </div>
              <span>Get Assistance</span>
              {unread > 0 && (
                <span className="ml-auto text-[10px] bg-accent text-white px-1.5 py-0.5 rounded-full font-semibold">
                  {unread} new
                </span>
              )}
            </button>
          )}

          {/* User + sign out */}
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
      <main className="flex-1 overflow-y-auto bg-gray-50">
        <Outlet />
      </main>

      {/* Support chat modal */}
      {showHelp && (
        <SupportChat
          onClose={() => setShowHelp(false)}
          onMessagesRead={() => setUnread(0)}
        />
      )}
    </div>
  )
}

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'

import Layout from './components/Layout'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Analytics from './pages/Analytics'
import Leads from './pages/Leads'
import LeadDetail from './pages/LeadDetail'
import Properties from './pages/Properties'
import Knowledge from './pages/Knowledge'
import Appointments from './pages/Appointments'
import Settings from './pages/Settings'
import AIAgent from './pages/AIAgent'
import SupportInbox from './pages/SupportInbox'
import Setup from './pages/Setup'
import AdminPanel from './pages/AdminPanel'
import Integrations from './pages/Integrations'

const ADMIN_UID = '7227a933-56ef-45c4-8cbc-1c8331c74b21'

function ProtectedRoute({ children, session }) {
  if (!session) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const [session, setSession] = useState(undefined) // undefined = loading

  useEffect(() => {
    // onAuthStateChange fires INITIAL_SESSION immediately with the correct session
    // (handles token refresh automatically — no race with getSession()).
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s)
    })
    return () => subscription.unsubscribe()
  }, [])

  if (session === undefined) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-navy-600">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={session ? <Navigate to="/dashboard" replace /> : <Landing />} />
        <Route path="/login" element={session ? <Navigate to="/dashboard" replace /> : <Login />} />

        {/* Onboarding — handles its own auth (invite token in URL hash) */}
        <Route path="/setup" element={<Setup />} />

        {/* Protected app — all under /dashboard */}
        <Route path="/dashboard" element={
          <ProtectedRoute session={session}>
            <Layout session={session} />
          </ProtectedRoute>
        }>
          <Route index element={<Dashboard />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="leads" element={<Leads />} />
          <Route path="leads/:id" element={<LeadDetail />} />
          <Route path="properties" element={<Properties />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="appointments" element={<Appointments />} />
          <Route path="ai-agent" element={<AIAgent />} />
          <Route path="integrations" element={<Integrations />} />
          <Route path="settings" element={<Settings />} />
          <Route path="support" element={
            session?.user?.id === ADMIN_UID
              ? <SupportInbox />
              : <Navigate to="/dashboard" replace />
          } />
        </Route>

        {/* Admin panel — restricted to Shaheer's UID; URL obscured */}
        <Route path="/nxd-c0ns0le" element={
          session?.user?.id === ADMIN_UID
            ? <AdminPanel />
            : <Navigate to="/" replace />
        } />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

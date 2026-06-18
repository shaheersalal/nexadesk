import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'

import Layout from './components/Layout'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Leads from './pages/Leads'
import LeadDetail from './pages/LeadDetail'
import Properties from './pages/Properties'
import Knowledge from './pages/Knowledge'
import Appointments from './pages/Appointments'
import Settings from './pages/Settings'
import AIAgent from './pages/AIAgent'
import SupportInbox from './pages/SupportInbox'
import Setup from './pages/Setup'

function ProtectedRoute({ children, session }) {
  if (!session) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  const [session, setSession] = useState(undefined) // undefined = loading

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => setSession(s))
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

        {/* Onboarding (protected, full-screen — no sidebar) */}
        <Route path="/setup" element={
          <ProtectedRoute session={session}>
            <Setup />
          </ProtectedRoute>
        } />

        {/* Protected app — all under /dashboard */}
        <Route path="/dashboard" element={
          <ProtectedRoute session={session}>
            <Layout session={session} />
          </ProtectedRoute>
        }>
          <Route index element={<Dashboard />} />
          <Route path="leads" element={<Leads />} />
          <Route path="leads/:id" element={<LeadDetail />} />
          <Route path="properties" element={<Properties />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="appointments" element={<Appointments />} />
          <Route path="ai-agent" element={<AIAgent />} />
          <Route path="settings" element={<Settings />} />
          <Route path="support" element={<SupportInbox />} />
        </Route>

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

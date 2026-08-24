import { useEffect, useState } from 'react'
import { API_BASE } from '../lib/apiBase'
import { supabase } from '../lib/supabase'
import { api, getAccessibleCompanies } from '../lib/api'
import { Save, Link as LinkIcon, Mail, Copy, Check, Building2, Plus, Send } from 'lucide-react'

const LISTINGS_INBOUND_DOMAIN = 'listings.nexadesk.site'

export default function Settings() {
  const [company, setCompany] = useState(null)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [emailCopied, setEmailCopied] = useState(false)
  const [childCompanies, setChildCompanies] = useState([])
  const [childForm, setChildForm] = useState({ name: '', invite_email: '', full_name: '' })
  const [inviting, setInviting] = useState(false)
  const [inviteResult, setInviteResult] = useState(null)

  useEffect(() => {
    loadCompany()
    loadChildCompanies()
  }, [])

  async function loadChildCompanies() {
    try {
      const all = await getAccessibleCompanies()
      // Only children have parent_company_id set; exclude own row
      setChildCompanies(all.filter((c) => c.parent_company_id !== null))
    } catch {}
  }

  async function handleInviteChild(e) {
    e.preventDefault()
    setInviting(true)
    setInviteResult(null)
    try {
      const result = await api.createChildCompany(childForm)
      setInviteResult({ ok: true, msg: `Invite sent to ${result.invite_sent_to}. "${result.name}" is now a branch office.` })
      setChildForm({ name: '', invite_email: '', full_name: '' })
      loadChildCompanies()
    } catch (err) {
      setInviteResult({ ok: false, msg: err.message || 'Failed to create branch office' })
    } finally {
      setInviting(false)
    }
  }

  async function loadCompany() {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return
    const { data: userData } = await supabase.from('users').select('company_id').eq('id', user.id).single()
    if (!userData?.company_id) return
    const { data } = await supabase.from('companies').select('*').eq('id', userData.company_id).single()
    setCompany(data)
    setForm({
      name: data?.name || '',
      phone: data?.phone || '',
      email: data?.email || '',
      address: data?.address || '',
      ai_persona: data?.ai_persona || 'a friendly and professional real estate receptionist',
    })
  }

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const updated = await api.updateCompany(form)
      setCompany(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setError(err.message || 'Failed to save changes')
    } finally {
      setSaving(false)
    }
  }

  const apiBase = API_BASE
  const widgetCode = company ? `<script>
  window.NexaDeskConfig = {
    companyId: "${company.id}",
    apiBase: "${apiBase}",
  };
</script>
<script src="${apiBase}/widget.js" defer></script>` : ''

  function copyWidget() {
    navigator.clipboard.writeText(widgetCode)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const listingsAddress = company ? `listings+${company.id}@${LISTINGS_INBOUND_DOMAIN}` : ''

  function copyListingsAddress() {
    navigator.clipboard.writeText(listingsAddress)
    setEmailCopied(true)
    setTimeout(() => setEmailCopied(false), 2000)
  }

  return (
    <div className="p-4 md:p-8 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Settings</h1>
        <p className="text-gray-500 text-sm mt-1">Configure your AI receptionist</p>
      </div>

      {/* Company info */}
      <form onSubmit={handleSave} className="card mb-6 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">Company Information</h2>
        {[
          { label: 'Company Name', key: 'name' },
          { label: 'Phone Number', key: 'phone', placeholder: '+1 (555) 000-0000' },
          { label: 'Email', key: 'email', placeholder: 'hello@yourcompany.com' },
          { label: 'Address', key: 'address' },
        ].map(({ label, key, placeholder }) => (
          <div key={key}>
            <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
            <input
              value={form[key] || ''}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              placeholder={placeholder}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
        ))}

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">AI Persona</label>
          <p className="text-xs text-gray-400 mb-2">Describe how you want the AI to sound and behave</p>
          <textarea
            value={form.ai_persona || ''}
            onChange={(e) => setForm({ ...form, ai_persona: e.target.value })}
            rows={3}
            placeholder="e.g. a warm and knowledgeable luxury real estate specialist who makes clients feel valued"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent resize-none"
          />
        </div>

        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}

        <div className="flex justify-end">
          <button type="submit" disabled={saving} className="btn-primary flex items-center gap-2">
            {saved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            {saved ? 'Saved!' : saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </form>

      {/* Chat widget embed code */}
      <div className="card">
        <div className="flex items-center gap-2 mb-3">
          <LinkIcon className="w-4 h-4 text-gray-400" />
          <h2 className="text-sm font-semibold text-gray-700">Embed Chat Widget</h2>
        </div>
        <p className="text-xs text-gray-400 mb-3">
          Copy this snippet and paste it before the closing &lt;/body&gt; tag on your website.
        </p>
        <div className="bg-gray-900 rounded-lg p-4 relative">
          <pre className="text-xs text-green-400 overflow-x-auto whitespace-pre-wrap">{widgetCode}</pre>
          <button
            onClick={copyWidget}
            className="absolute top-3 right-3 text-gray-500 hover:text-white transition-colors"
          >
            {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Email-forward listing ingestion */}
      <div className="card mt-6">
        <div className="flex items-center gap-2 mb-3">
          <Mail className="w-4 h-4 text-gray-400" />
          <h2 className="text-sm font-semibold text-gray-700">Forward Listings by Email</h2>
        </div>
        <p className="text-xs text-gray-400 mb-3">
          Forward or CC any email with a listing sheet, CSV/Excel export, or photo attached to this address — Nexa reads it automatically. No setup needed on your end.
        </p>
        <div className="bg-gray-900 rounded-lg p-4 relative">
          <pre className="text-xs text-green-400 overflow-x-auto whitespace-pre-wrap">{listingsAddress}</pre>
          <button
            onClick={copyListingsAddress}
            className="absolute top-3 right-3 text-gray-500 hover:text-white transition-colors"
          >
            {emailCopied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Branch offices / child accounts — visible only for top-level (parent) accounts */}
      {company && !company.parent_company_id && (
        <div className="card mt-6">
          <div className="flex items-center gap-2 mb-3">
            <Building2 className="w-4 h-4 text-gray-400" />
            <h2 className="text-sm font-semibold text-gray-700">Branch Offices</h2>
          </div>
          <p className="text-xs text-gray-400 mb-4">
            Invite a branch office or sub-team as a child account. They get their own login and data, while you see an aggregated view across all offices in your dashboard.
          </p>

          {childCompanies.length > 0 && (
            <ul className="mb-4 space-y-1">
              {childCompanies.map((c) => (
                <li key={c.id} className="flex items-center gap-2 text-sm text-gray-700 bg-gray-50 rounded-lg px-3 py-2">
                  <Building2 className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                  {c.name}
                </li>
              ))}
            </ul>
          )}

          <form onSubmit={handleInviteChild} className="space-y-3">
            <h3 className="text-xs font-semibold text-gray-600">Add a branch office</h3>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Branch name</label>
              <input
                required
                value={childForm.name}
                onChange={(e) => setChildForm({ ...childForm, name: e.target.value })}
                placeholder="e.g. Dubai Marina Branch"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Branch manager email</label>
              <input
                required
                type="email"
                value={childForm.invite_email}
                onChange={(e) => setChildForm({ ...childForm, invite_email: e.target.value })}
                placeholder="manager@branch.com"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Manager name (optional)</label>
              <input
                value={childForm.full_name}
                onChange={(e) => setChildForm({ ...childForm, full_name: e.target.value })}
                placeholder="Full name"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            {inviteResult && (
              <p className={`text-sm ${inviteResult.ok ? 'text-green-600' : 'text-red-600'}`}>
                {inviteResult.msg}
              </p>
            )}
            <div className="flex justify-end">
              <button type="submit" disabled={inviting} className="btn-primary flex items-center gap-2">
                <Send className="w-4 h-4" />
                {inviting ? 'Sending invite…' : 'Invite Branch'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

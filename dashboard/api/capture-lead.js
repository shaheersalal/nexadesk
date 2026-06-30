// Vercel serverless function — independent fallback for the demo/signup form.
//
// Deliberately has zero shared code or imports with the FastAPI backend (app/public/router.py
// book_demo): if the self-hosted Docker backend is down, this still runs, because Vercel's
// serverless functions are a completely separate deployment with their own uptime.
// Calls Resend directly. Requires RESEND_API_KEY to be set in this Vercel project's own
// environment variables (configured separately from the backend's .env — not shared).
export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' })
    return
  }

  const { name, email, agency, phone, country, monthly_calls } = req.body || {}
  if (!name || !email || !agency || !phone) {
    res.status(400).json({ error: 'Missing required fields' })
    return
  }

  const apiKey = process.env.RESEND_API_KEY
  if (!apiKey) {
    res.status(503).json({ error: 'Not configured' })
    return
  }

  try {
    const resendRes = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'NexaDesk <onboarding@resend.dev>',
        to: ['shaheersalal@gmail.com'],
        subject: `New Access Request (fallback) — ${agency} (${country || 'unknown'})`,
        html: `
<div style="font-family:sans-serif;max-width:580px;color:#1a1a1a">
  <h2 style="color:#1e3a5f;margin-bottom:4px">New Access Request 🎯</h2>
  <p style="color:#888;font-size:13px;margin-top:0">
    Submitted from nexadesk.site — captured via Vercel fallback (backend was unreachable)
  </p>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <tr><td style="padding:9px 0;color:#666;width:140px;border-bottom:1px solid #f0f0f0">Name</td>
        <td style="padding:9px 0;font-weight:600;border-bottom:1px solid #f0f0f0">${name}</td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Email</td>
        <td style="padding:9px 0;border-bottom:1px solid #f0f0f0">${email}</td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Agency</td>
        <td style="padding:9px 0;font-weight:600;border-bottom:1px solid #f0f0f0">${agency}</td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Phone</td>
        <td style="padding:9px 0;border-bottom:1px solid #f0f0f0">${phone}</td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Country</td>
        <td style="padding:9px 0;border-bottom:1px solid #f0f0f0">${country || ''}</td></tr>
    <tr><td style="padding:9px 0;color:#666">Monthly Calls</td>
        <td style="padding:9px 0">${monthly_calls || ''}</td></tr>
  </table>
  <p style="font-size:12px;color:#94a3b8;margin-top:16px">
    The backend was down when this came in — no demo_requests row exists yet. Follow up by email, then add them manually once the backend is back.
  </p>
</div>`,
      }),
    })

    if (!resendRes.ok) {
      const detail = await resendRes.text().catch(() => '')
      res.status(502).json({ error: 'Resend failed', detail })
      return
    }

    res.status(200).json({ status: 'ok' })
  } catch (err) {
    res.status(502).json({ error: 'Send failed', detail: String(err) })
  }
}

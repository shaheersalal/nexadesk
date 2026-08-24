/**
 * The one place the backend origin is defined.
 *
 * This used to be inlined in nine files with five different fallbacks —
 * 'https://api.nexadesk.site', '/api' and 'http://localhost:8000' — so which
 * backend a component talked to depended on which file it lived in. The custom
 * domain among those fallbacks had no valid TLS certificate, which meant the
 * components carrying it failed while their neighbours worked.
 *
 * VITE_API_URL is set in the Vercel project and is what production actually
 * uses; the fallback only matters for `vite dev` against a local backend.
 */
export const API_BASE =
  import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default API_BASE

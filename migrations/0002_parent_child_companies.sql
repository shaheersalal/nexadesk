-- Phase 6: multi-tenant parent/child accounts.
--
-- A company with parent_company_id IS NULL is top-level (current behavior,
-- unchanged for every existing company). A company with parent_company_id
-- set is a child under that parent. Nesting is exactly one level deep —
-- a company that already has a parent cannot itself become a parent
-- (enforced below via trigger, since a CHECK constraint can't query other
-- rows in Postgres).

ALTER TABLE public.companies ADD COLUMN IF NOT EXISTS parent_company_id uuid REFERENCES public.companies(id);
CREATE INDEX IF NOT EXISTS idx_companies_parent ON public.companies(parent_company_id);

-- ── One-level nesting enforcement ───────────────────────────────────────────

CREATE OR REPLACE FUNCTION enforce_one_level_company_nesting()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  grandparent_id uuid;
BEGIN
  IF NEW.parent_company_id IS NOT NULL THEN
    IF NEW.parent_company_id = NEW.id THEN
      RAISE EXCEPTION 'A company cannot be its own parent';
    END IF;
    SELECT parent_company_id INTO grandparent_id FROM companies WHERE id = NEW.parent_company_id;
    IF grandparent_id IS NOT NULL THEN
      RAISE EXCEPTION 'parent_company_id must point to a top-level company (one level of nesting only)';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enforce_one_level_company_nesting ON companies;
CREATE TRIGGER trg_enforce_one_level_company_nesting
  BEFORE INSERT OR UPDATE OF parent_company_id ON companies
  FOR EACH ROW EXECUTE FUNCTION enforce_one_level_company_nesting();

-- ── accessible_company_ids(): self + children (if parent), self only otherwise ─

CREATE OR REPLACE FUNCTION accessible_company_ids() RETURNS SETOF uuid AS $$
  SELECT id FROM companies WHERE id = current_company_id()
  UNION
  SELECT id FROM companies WHERE parent_company_id = current_company_id()
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

-- ── RLS: widen SELECT to accessible_company_ids(), keep writes strictly
--    scoped to the caller's own company_id (defense in depth — all current
--    writes go through the backend's service-role client anyway, which
--    bypasses RLS entirely, but direct-frontend writes should never be able
--    to touch a sibling/child company's rows even if added later).

DROP POLICY IF EXISTS "company_isolation_properties" ON properties;
CREATE POLICY "company_isolation_properties_select" ON properties FOR SELECT
  USING (company_id = ANY(SELECT accessible_company_ids()));
CREATE POLICY "company_isolation_properties_insert" ON properties FOR INSERT
  WITH CHECK (company_id = current_company_id());
CREATE POLICY "company_isolation_properties_update" ON properties FOR UPDATE
  USING (company_id = current_company_id()) WITH CHECK (company_id = current_company_id());
CREATE POLICY "company_isolation_properties_delete" ON properties FOR DELETE
  USING (company_id = current_company_id());

DROP POLICY IF EXISTS "company_isolation_leads" ON leads;
CREATE POLICY "company_isolation_leads_select" ON leads FOR SELECT
  USING (company_id = ANY(SELECT accessible_company_ids()));
CREATE POLICY "company_isolation_leads_insert" ON leads FOR INSERT
  WITH CHECK (company_id = current_company_id());
CREATE POLICY "company_isolation_leads_update" ON leads FOR UPDATE
  USING (company_id = current_company_id()) WITH CHECK (company_id = current_company_id());
CREATE POLICY "company_isolation_leads_delete" ON leads FOR DELETE
  USING (company_id = current_company_id());

DROP POLICY IF EXISTS "company_isolation_conversations" ON conversations;
CREATE POLICY "company_isolation_conversations_select" ON conversations FOR SELECT
  USING (company_id = ANY(SELECT accessible_company_ids()));
CREATE POLICY "company_isolation_conversations_insert" ON conversations FOR INSERT
  WITH CHECK (company_id = current_company_id());
CREATE POLICY "company_isolation_conversations_update" ON conversations FOR UPDATE
  USING (company_id = current_company_id()) WITH CHECK (company_id = current_company_id());
CREATE POLICY "company_isolation_conversations_delete" ON conversations FOR DELETE
  USING (company_id = current_company_id());

DROP POLICY IF EXISTS "company_isolation_appointments" ON appointments;
CREATE POLICY "company_isolation_appointments_select" ON appointments FOR SELECT
  USING (company_id = ANY(SELECT accessible_company_ids()));
CREATE POLICY "company_isolation_appointments_insert" ON appointments FOR INSERT
  WITH CHECK (company_id = current_company_id());
CREATE POLICY "company_isolation_appointments_update" ON appointments FOR UPDATE
  USING (company_id = current_company_id()) WITH CHECK (company_id = current_company_id());
CREATE POLICY "company_isolation_appointments_delete" ON appointments FOR DELETE
  USING (company_id = current_company_id());

DROP POLICY IF EXISTS "company_isolation_documents" ON documents;
CREATE POLICY "company_isolation_documents_select" ON documents FOR SELECT
  USING (company_id = ANY(SELECT accessible_company_ids()));
CREATE POLICY "company_isolation_documents_insert" ON documents FOR INSERT
  WITH CHECK (company_id = current_company_id());
CREATE POLICY "company_isolation_documents_update" ON documents FOR UPDATE
  USING (company_id = current_company_id()) WITH CHECK (company_id = current_company_id());
CREATE POLICY "company_isolation_documents_delete" ON documents FOR DELETE
  USING (company_id = current_company_id());

-- companies: a user can see their own company row plus, if they belong to a
-- parent account, their children's rows too (needed for the company-switcher
-- dropdown to show child company names). No write policy added — company
-- updates already go exclusively through the backend's service-role client
-- (PATCH /companies/me), which bypasses RLS.
DROP POLICY IF EXISTS "users_see_company" ON companies;
CREATE POLICY "users_see_company" ON companies FOR SELECT
  USING (id = ANY(SELECT accessible_company_ids()));

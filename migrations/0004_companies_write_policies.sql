-- Write policies for `companies`.
--
-- RLS is enabled on companies but only a SELECT policy exists
-- ("users_see_company"). Every write therefore has to go through the
-- service-role client, which bypasses row-level security entirely — so three
-- authenticated endpoints (onboarding_complete, update_my_company,
-- create_child_company) still run as the system rather than as their caller,
-- and their tenant boundary is a hand-written filter rather than the database.
--
-- With these policies in place those three can take `db: RlsDb` like every
-- other authenticated route, and the service-role allowlist in
-- tests/test_tenant_isolation.py shrinks to the admin surface alone.
--
-- Idempotent: safe to re-run.

-- A user may update their own company only.
DROP POLICY IF EXISTS "company_update_own" ON companies;
CREATE POLICY "company_update_own"
    ON companies
    FOR UPDATE
    USING      (id = current_company_id())
    WITH CHECK (id = current_company_id());

-- A user may create a child company under their own.
--
-- Deliberately not a blanket INSERT: without the parent_company_id predicate
-- any authenticated user could create a top-level company, which is an
-- account-creation path and does not belong on this table's policy.
DROP POLICY IF EXISTS "company_insert_child" ON companies;
CREATE POLICY "company_insert_child"
    ON companies
    FOR INSERT
    WITH CHECK (parent_company_id = current_company_id());

-- No DELETE policy on purpose. Deleting a company orphans its leads,
-- conversations, properties and documents; that is an operational action, not
-- something a dashboard session should be able to do.

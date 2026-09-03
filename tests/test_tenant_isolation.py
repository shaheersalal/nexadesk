"""
Tenant isolation on the paths where an identifier comes from the request.

The backend uses the Supabase service-role client everywhere and therefore
bypasses row-level security. Isolation is not enforced by the database; it rests
entirely on every query carrying a company_id filter. A missing filter is a
silent cross-tenant read or write rather than a permissions error.

The bug this file exists for: create_appointment took lead_id from the request
body and neither looked the lead up nor updated its status with a company
filter, so any authenticated user could read another agency's lead — name and
email, and that email then received the calendar invite — and write to it.

These assertions walk the actual call chain with the AST. An earlier version
searched the surrounding source text for "company_id" and passed happily on the
vulnerable code, because the string appears elsewhere in the same function.
Checking "is the filter present nearby" is not the same question as "is THIS
query filtered", and only the second one is worth asking.
"""
import ast
import inspect

import pytest

from app.leads import router as leads_router


def _chain_calls(node):
    """Every method name and its args in one attribute call chain."""
    calls = []
    cur = node
    while isinstance(cur, ast.Call):
        if isinstance(cur.func, ast.Attribute):
            calls.append((cur.func.attr, cur.args))
            cur = cur.func.value
        else:
            break
    return calls


def _queries_in(fn, table_name):
    """
    Yield (chain, source_segment) for each query in `fn` against `table_name`.

    A chain is the flat list of (method, args) making up one fluent expression,
    e.g. table("leads").update(...).eq("id", x).eq("company_id", y).execute().
    """
    src = inspect.getsource(fn)
    tree = ast.parse(inspect.cleandoc(src.replace("\n    ", "\n", 1)) if False else src.lstrip())
    for node in ast.walk(tree):
        # Anchor on the terminating .execute(): ast.walk yields every nested
        # Call, so an inner fragment of a fully-scoped chain would otherwise be
        # reported as its own unscoped query.
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute"):
            continue
        chain = _chain_calls(node)
        names = [c[0] for c in chain]
        if "table" not in names:
            continue
        # the table(...) call carries the table name as a literal
        for method, args in chain:
            if method == "table" and args and isinstance(args[0], ast.Constant):
                if args[0].value == table_name:
                    yield chain
                break


def _is_scoped(chain):
    """True when this chain filters on company_id."""
    for method, args in chain:
        if method in ("eq", "in_") and args and isinstance(args[0], ast.Constant):
            if args[0].value == "company_id":
                return True
    return False


def _addresses_a_row(chain):
    """True when the chain targets a specific row by id."""
    for method, args in chain:
        if method == "eq" and args and isinstance(args[0], ast.Constant):
            if args[0].value == "id":
                return True
    return False


# ── The specific queries that were exploitable ───────────────────────────────

def test_create_appointment_scopes_every_lead_query():
    """
    lead_id comes from the request body. Both the lookup and the status write
    must be scoped, or a foreign lead is readable and writable.
    """
    unscoped = [
        chain for chain in _queries_in(leads_router.create_appointment, "leads")
        if _addresses_a_row(chain) and not _is_scoped(chain)
    ]
    assert not unscoped, (
        f"{len(unscoped)} query on `leads` in create_appointment addresses a row "
        "by id without a company_id filter — a caller can pass another agency's "
        "lead_id and read or write it"
    )


def test_delete_appointment_scopes_the_calendar_lookup():
    """
    Unscoped, this both confirmed another tenant's appointment exists and handed
    its google_event_id to delete_event() under this company's credentials.
    """
    unscoped = [
        chain for chain in _queries_in(leads_router.delete_appointment, "appointments")
        if _addresses_a_row(chain) and not _is_scoped(chain)
    ]
    assert not unscoped, "delete_appointment reads an appointment by id unscoped"


@pytest.mark.parametrize("fn_name", [
    "get_lead", "update_lead", "update_lead_status", "delete_lead",
    "create_appointment", "update_appointment", "delete_appointment",
])
@pytest.mark.parametrize("table", ["leads", "appointments"])
def test_no_id_addressed_query_is_unscoped(fn_name, table):
    """Every row-addressed query on a tenant table carries the filter."""
    fn = getattr(leads_router, fn_name)
    offenders = [
        chain for chain in _queries_in(fn, table)
        if _addresses_a_row(chain) and not _is_scoped(chain)
    ]
    assert not offenders, f"{fn_name}: unscoped row-addressed query on `{table}`"


def test_the_check_can_actually_fail():
    """
    Guard against a vacuous test.

    The first version of this file searched the function source for the string
    "company_id" and passed on the vulnerable code, because the name appears
    elsewhere in the same function. This proves the AST walk distinguishes a
    scoped chain from an unscoped one.
    """
    scoped = ast.parse(
        'sb.table("leads").update(p).eq("id", x).eq("company_id", c).execute()'
    ).body[0].value
    unscoped = ast.parse(
        'sb.table("leads").update(p).eq("id", x).execute()'
    ).body[0].value
    assert _is_scoped(_chain_calls(scoped))
    assert not _is_scoped(_chain_calls(unscoped))
    assert _addresses_a_row(_chain_calls(unscoped))


# ── Whole-app enforcement ────────────────────────────────────────────────────

import pathlib  # noqa: E402

APP = pathlib.Path(__file__).resolve().parent.parent / "app"

# Rows that belong to a company through a company_id column.
CHILD_TABLES = {
    "leads", "appointments", "conversations", "properties", "documents",
    "api_keys", "webhook_endpoints", "webhook_logs", "crm_connections",
}

# Sites where the row key is not a tenant reference and a company filter would
# be meaningless. Each is listed with the reason, so adding to this set is a
# decision someone has to justify rather than a way to silence the test.
ALLOWED = {
    # webhook_logs row this process just inserted, updated with its delivery
    # result. The id never leaves the function.
    ("app/integrations/events.py", "webhook_logs"),
    # crm_router refreshes tokens on a row it already fetched under a company
    # filter, keyed by that row's own id.
    ("app/integrations/crm_router.py", "crm_connections"),
}


def _all_queries():
    for path in sorted(APP.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        rel = path.relative_to(APP.parent).as_posix()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "execute"):
                continue
            chain = _chain_calls(node)
            table = None
            for method, args in chain:
                if method == "table" and args and isinstance(args[0], ast.Constant):
                    table = args[0].value
                    break
            if table:
                yield rel, node.lineno, table, chain


def test_no_child_table_row_is_addressed_without_its_company():
    """
    Every query that picks a row out of a company-owned table by id must also
    filter on company_id.

    The backend runs as service-role and bypasses row-level security, so this
    filter is the entire tenant boundary. Without it, an id is authorisation —
    and ids travel in request bodies.
    """
    offenders = []
    for rel, line, table, chain in _all_queries():
        if table not in CHILD_TABLES:
            continue
        if not _addresses_a_row(chain) or _is_scoped(chain):
            continue
        if any(rel.startswith(p) and table == t for p, t in ALLOWED):
            continue
        offenders.append(f"{rel}:{line} -> {table}")
    assert not offenders, (
        "Row-addressed queries on company-owned tables with no company_id "
        "filter:\n  " + "\n  ".join(offenders)
    )


# ── Authenticated routes must run as the caller, not as the system ───────────

# Routes that legitimately act as the system rather than as their caller. Each
# needs a reason; the point of the list is that adding to it is a decision.
SERVICE_ROLE_ALLOWED = {
    # Calls auth.admin.invite_user_by_email, which a caller-scoped client cannot
    # do, and rolls back by deleting the company it just created — which
    # migration 0004 deliberately does not permit. The INSERT would pass RLS;
    # the rest of the function is what keeps it here.
    ("app/companies/router.py", "create_child_company"),
    # Cross-tenant by design, gated on a single admin uid: triage of inbound
    # access requests and issuing invites.
    ("app/admin/router.py", "list_requests"),
    ("app/admin/router.py", "invite_user"),
    ("app/admin/router.py", "invite_quick"),
    # site_visits has no RLS and no company_id at all — it's owner-only
    # first-party analytics for shaheer.dev/nexadesk.site, not tenant data,
    # gated purely by the same ADMIN_UID check as the routes above.
    ("app/analytics/router.py", "site_summary"),
    ("app/analytics/router.py", "site_session_detail"),
}


def _authenticated_handlers():
    """(file, function, source) for every route handler that requires a user."""
    for path in sorted(APP.rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        if "CurrentUser" not in src and "require_admin" not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        rel = path.relative_to(APP.parent).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorated = any(
                isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                and isinstance(d.func.value, ast.Name) and d.func.value.id == "router"
                for d in node.decorator_list
            )
            if not decorated:
                continue
            args = ast.unparse(node.args) if hasattr(ast, "unparse") else ""
            needs_user = "CurrentUser" in args or any(
                "require_admin" in ast.unparse(d) for d in node.decorator_list
            ) or "require_admin" in args
            if needs_user:
                yield rel, node.name, ast.get_source_segment(src, node) or ""


def test_authenticated_routes_do_not_use_the_service_role_client():
    """
    A signed-in caller's request must run under their own identity.

    get_supabase_admin() bypasses row-level security, so using it on a route
    that has a caller throws away the database's enforcement and puts the whole
    tenant boundary back on remembering a filter. Routes that genuinely act as
    the system are listed above with a reason.
    """
    offenders = []
    for rel, name, src in _authenticated_handlers():
        if (rel, name) in SERVICE_ROLE_ALLOWED:
            continue
        if "get_supabase_admin(" in src:
            offenders.append(f"{rel}::{name}")
    assert not offenders, (
        "Authenticated routes using the service-role client, which bypasses "
        "RLS:\n  " + "\n  ".join(offenders)
    )

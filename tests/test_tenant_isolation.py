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

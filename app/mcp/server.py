"""
NexaDesk MCP Server — Streamable HTTP transport (JSON-RPC 2.0).
POST /mcp/  ← all JSON-RPC requests
GET  /mcp/  ← server info + discovery

Auth: Authorization: Bearer nxd_live_...
Protocol version: 2024-11-05
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.dependencies import get_supabase_admin
from app.v1.router import _touch_last_used

logger = logging.getLogger("nexadesk.mcp")
router = APIRouter()

MCP_VERSION = "2024-11-05"
SERVER_INFO = {"name": "nexadesk", "version": "1.0.0"}

TOOLS = [
    {
        "name": "get_leads",
        "description": "List leads from the NexaDesk CRM. Filter by status or source channel.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["new", "contacted", "qualified", "appointment", "closed", "lost"],
                    "description": "Filter by lead status",
                },
                "source": {"type": "string", "description": "Filter by source channel (chat, voice, manual, api, mcp)"},
                "limit": {"type": "integer", "default": 20, "maximum": 100, "description": "Number of leads to return"},
            },
        },
    },
    {
        "name": "create_lead",
        "description": "Add a new lead to NexaDesk. Triggers webhooks and CRM sync automatically.",
        "inputSchema": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "description": "Lead's full name"},
                "email": {"type": "string", "description": "Email address"},
                "phone": {"type": "string", "description": "Phone number"},
                "source": {"type": "string", "default": "mcp", "description": "Source identifier"},
                "notes": {"type": "string", "description": "Additional notes"},
            },
        },
    },
    {
        "name": "get_appointments",
        "description": "List upcoming property viewing appointments with lead and property details.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10, "maximum": 50},
            },
        },
    },
    {
        "name": "get_properties",
        "description": "List property listings in the NexaDesk inventory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Filter by property type (apartment, villa, office, etc.)"},
                "limit": {"type": "integer", "default": 20, "maximum": 100},
            },
        },
    },
]


def _coerce_limit(raw: Any, default: int, cap: int) -> int:
    """
    JSON-RPC arguments are untyped — the advertised inputSchema is never
    enforced on the wire. `min("20", 100)` raises TypeError, which the generic
    handler then reported as "Internal server error", disguising a client
    mistake as a server fault (AUDIT.md M11).
    """
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"'limit' must be an integer, got {raw!r}")
    if value < 1:
        raise ValueError("'limit' must be at least 1")
    return min(value, cap)


def _ok(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


async def _auth(request: Request) -> tuple[str | None, list[str]]:
    """
    Validate API key; returns (company_id, scopes) or (None, []).

    Never raises: the caller invokes this outside its try block, so a raised
    exception became an unhandled HTTP 500 rather than a clean JSON-RPC
    unauthorized response (AUDIT.md H4).
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer nxd_"):
        return None, []
    raw_key = auth.removeprefix("Bearer ").strip()
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    try:
        sb = get_supabase_admin()
        result = sb.table("api_keys").select("company_id,scopes,revoked_at") \
            .eq("key_hash", key_hash).maybe_single().execute()
        if not result or not result.data or result.data.get("revoked_at"):
            return None, []
        _touch_last_used(sb, key_hash)
        return result.data["company_id"], (result.data.get("scopes") or [])
    except Exception as exc:
        logger.warning("MCP auth lookup failed: %s", exc)
        return None, []


async def _call(company_id: str, scopes: list[str], name: str, args: dict) -> Any:
    sb = get_supabase_admin()

    if name == "get_leads":
        if "leads:read" not in scopes:
            raise PermissionError("Scope 'leads:read' required")
        q = sb.table("leads").select("id,name,email,phone,status,source,score,created_at") \
            .eq("company_id", company_id)
        if args.get("status"):
            q = q.eq("status", args["status"])
        if args.get("source"):
            q = q.eq("source", args["source"])
        return q.order("created_at", desc=True).limit(_coerce_limit(args.get("limit"), 20, 100)).execute().data or []

    if name == "create_lead":
        if "leads:write" not in scopes:
            raise PermissionError("Scope 'leads:write' required")
        if not args.get("name"):
            raise ValueError("'name' is required")
        result = sb.table("leads").insert({
            "company_id": company_id,
            "name": args["name"],
            "email": args.get("email"),
            "phone": args.get("phone"),
            "source": args.get("source", "mcp"),
            "notes": args.get("notes"),
            "status": "new",
        }).execute()
        if not result.data:
            raise RuntimeError("Lead was not created")
        lead = result.data[0]
        from app.integrations.events import fire_event
        fire_event(company_id, "lead.created", lead)
        return lead

    if name == "get_appointments":
        if "appointments:read" not in scopes:
            raise PermissionError("Scope 'appointments:read' required")
        return sb.table("appointments") \
            .select("id,datetime,status,notes,leads(name,phone),properties(title,address)") \
            .eq("company_id", company_id) \
            .gte("datetime", datetime.now(timezone.utc).isoformat()) \
            .order("datetime").limit(_coerce_limit(args.get("limit"), 10, 50)).execute().data or []

    if name == "get_properties":
        if "properties:read" not in scopes:
            raise PermissionError("Scope 'properties:read' required")
        q = sb.table("properties").select("id,title,address,type,price,status,bedrooms,bathrooms") \
            .eq("company_id", company_id)
        if args.get("type"):
            q = q.eq("type", args["type"])
        return q.order("created_at", desc=True).limit(_coerce_limit(args.get("limit"), 20, 100)).execute().data or []

    raise ValueError(f"Unknown tool: {name}")


@router.get("/")
async def mcp_info():
    return {
        "name": "NexaDesk MCP Server",
        "version": "1.0.0",
        "protocol": MCP_VERSION,
        "transport": "streamable-http",
        "auth": "Authorization: Bearer <nxd_live_...>",
        "tools": [t["name"] for t in TOOLS],
        "claude_config": {
            "mcpServers": {
                "nexadesk": {
                    "type": "http",
                    "url": "https://api.nexadesk.site/mcp/",
                    "headers": {"Authorization": "Bearer YOUR_API_KEY"},
                }
            }
        },
    }


@router.post("/")
async def mcp_handler(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(_err(None, -32700, "Parse error"), status_code=200)

    method = body.get("method")
    id_ = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return JSONResponse(_ok(id_, {
            "protocolVersion": MCP_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }))

    if method in ("ping", "notifications/initialized"):
        return JSONResponse(_ok(id_, {}))

    if method == "tools/list":
        return JSONResponse(_ok(id_, {"tools": TOOLS}))

    if method == "tools/call":
        company_id, scopes = await _auth(request)
        if not company_id:
            return JSONResponse(_err(id_, -32001, "Unauthorized: provide a valid NexaDesk API key"), status_code=200)
        try:
            result = await _call(company_id, scopes, params.get("name"), params.get("arguments", {}))
            return JSONResponse(_ok(id_, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]
            }))
        except PermissionError as e:
            return JSONResponse(_err(id_, -32003, str(e)))
        except ValueError as e:
            return JSONResponse(_err(id_, -32601, str(e)))
        except Exception as e:
            logger.error("MCP tool error: %s", e, exc_info=True)
            return JSONResponse(_err(id_, -32603, "Internal server error"))

    return JSONResponse(_err(id_, -32601, f"Method not found: {method}"))

"""官方 MCP Streamable HTTP 接入；只监听回环，认证不依赖模型提示词。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import inspect
import socket
import threading
import time
from typing import Any
from urllib.parse import urlsplit

from .remote_mcp import MCP_TOOLS, READ_TOOLS, RemoteWorkbench
from .repair_tools import RepairTools

INSTRUCTIONS = """LALC Windows remote development workbench. Start with mcp_status; ask the local user to authorize if necessary.
Acquire once with mcp_acquire and retain control_token privately for subsequent tools and reconnection. Another chat must not take over.
Read list_skills and relevant Skill files (read scope=skills) before development; action_contracts is authoritative for APIs.
Use a fresh UUID operation_id for each new write/execution; reuse exactly the same UUID and parameters when retrying.
Writes return operation IDs: query mcp_query(operation_id=...) until finished or waiting_local. Do not duplicate an operation because a response was lost.
validate_and_publish precedes trial_run; query its returned run_id. Run polling returns status and at most five logs including Debug.
Local approval is completed in Windows LALC. Network loss does not stop tasks or release control. No remote pause/resume, Runtime Recheck, shell, or arbitrary filesystem access.
Release only when idle. If control_token is lost, ask the local user to revoke. Workflow Python is trusted code, not sandboxed.
"""


def parameter_schema(name, default, tool):
    """把现有服务签名映射为工具参数；实际服务继续执行内容和路径校验。"""
    integer = {"offset", "limit", "start_sequence", "render_sequence", "run_id", "start_run_id", "text_offset", "history_offset"}
    boolean = {"image", "unknown", "all_runs", "remove", "enabled", "use_saved_config", "auto_park_cursor", "explicit_user_request"}
    arrays = {"images", "tags", "levels", "round_numbers", "repositories"}
    objects = {"inputs", "run_state", "version_group"}
    value: dict[str, Any]
    if name == "region":
        value = {"type": "object", "properties": {key: {"type": "integer"} for key in ("x", "y", "width", "height")},
                 "required": ["x", "y", "width", "height"], "additionalProperties": False}
    elif name == "copy_from":
        value = {"type": "object" if tool == "page_resource" else "string"}
    elif name in integer or type(default) is int:
        value = {"type": "integer"}
    elif name in boolean or type(default) is bool:
        value = {"type": "boolean"}
    elif name in arrays:
        value = {"type": "array"}
    elif name in objects:
        value = {"type": "object"}
    elif name == "threshold" or type(default) is float:
        value = {"type": "number"}
    else:
        value = {"type": "string"}
    if default is None:
        value["type"] = [value["type"], "null"]
    elif default is not inspect.Parameter.empty:
        value["default"] = default
    return value


def tool_catalog():
    """复用服务方法签名，权限名单保持独立；不解析或执行 pi 的 TypeScript。"""
    from mcp import types
    from .agent_history import AgentHistory
    from .knowledge import KnowledgeLibrary
    from .page_drafts import PageDrafts
    special = {
        "read": RemoteWorkbench.read, "edit": RemoteWorkbench.edit, "list_skills": RemoteWorkbench.list_skills,
        "validate_and_publish": RepairTools.publish,
        "page_list": PageDrafts.list, "page_read": PageDrafts.read, "page_create": PageDrafts.create,
        "page_update": PageDrafts.update,
        "knowledge_list": KnowledgeLibrary.list, "knowledge_read": KnowledgeLibrary.read,
        "knowledge_search_literal": KnowledgeLibrary.search, "knowledge_search_hybrid": KnowledgeLibrary.search_hybrid,
        "knowledge_git": KnowledgeLibrary.git_operation,
        "list_game_versions": AgentHistory.versions, "search_agent_sessions": AgentHistory.search,
        "read_agent_session": AgentHistory.read,
    }
    management = {"mcp_status": None, "mcp_acquire": RemoteWorkbench.acquire,
                  "mcp_release": RemoteWorkbench.release, "mcp_query": RemoteWorkbench.query,
                  "mcp_stop": RemoteWorkbench.stop_run}
    result = []
    for name in (*management, *MCP_TOOLS, "list_skills"):
        function = management.get(name) if name in management else special.get(name, getattr(RepairTools, name, None))
        properties, required = {}, []
        if function:
            for parameter in inspect.signature(function).parameters.values():
                if parameter.name == "self" or parameter.kind in {parameter.VAR_KEYWORD, parameter.VAR_POSITIONAL}:
                    continue
                properties[parameter.name] = parameter_schema(parameter.name, parameter.default, name)
                if parameter.default is inspect.Parameter.empty:
                    required.append(parameter.name)
        if name == "page_read":
            properties["image"] = {"type": "boolean", "default": False}
        if name not in management:
            properties["control_token"] = {"type": "string", "description": "Private control credential from mcp_acquire."}
            required.append("control_token")
            if name not in READ_TOOLS:
                properties["operation_id"] = {"type": "string", "format": "uuid", "description": "Stable retry ID; fresh UUID for a NEW operation."}
                required.append("operation_id")
        description = inspect.getdoc(function) if function else "View service, authorization and workbench state; no control credentials are returned."
        if name not in READ_TOOLS and name not in management:
            description = (description or name) + " Returns an operation ID; use mcp_query for actual completion and local approval status."
        result.append(types.Tool(name=name, description=description or name,
            input_schema={"type": "object", "properties": properties, "required": required, "additionalProperties": False},
            annotations=types.ToolAnnotations(read_only_hint=name in READ_TOOLS or name in {"mcp_status", "mcp_query"})))
    return result


def make_app(remote):
    """认证覆盖初始化、调用及连接关闭；缺少或不可信 Origin 由 SDK 按规范处理。"""
    from mcp import types
    from mcp.server import Server
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from mcp.server.transport_security import TransportSecuritySettings
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from starlette.responses import JSONResponse
    import jsonschema

    catalog = tool_catalog()
    schemas = {tool.name: tool.input_schema for tool in catalog}

    async def list_tools(_context, _params):
        return types.ListToolsResult(tools=catalog)

    async def call_tool(_context, params):
        try:
            if params.name not in schemas:
                raise ValueError("Unknown LALC MCP tool")
            arguments = dict(params.arguments or {})
            try:
                jsonschema.validate(arguments, schemas[params.name])
            except jsonschema.ValidationError as error:
                raise ValueError("无效工具参数：" + ".".join(map(str, error.path))) from None
            name = params.name
            if name in {"mcp_status", "mcp_acquire", "mcp_release", "mcp_query", "mcp_stop"}:
                method = {"mcp_status": remote.snapshot, "mcp_acquire": remote.acquire, "mcp_release": remote.release,
                          "mcp_query": remote.query, "mcp_stop": remote.stop_run}[name]
                value = await asyncio.to_thread(method, **arguments)
                result = RepairTools.text(value)
            else:
                control = arguments.pop("control_token")
                identity = arguments.pop("operation_id", None)
                result = await asyncio.to_thread(remote.invoke, name, arguments, control, identity)
            return types.CallToolResult(content=result["content"], structured_content=result.get("details"),
                                        is_error=result.get("isError", False))
        except Exception as error:
            from .agent_diagnostics import redact
            return types.CallToolResult(content=[types.TextContent(type="text", text=str(redact(str(error))))], is_error=True)

    server = Server("LALC", instructions=INSTRUCTIONS, on_list_tools=list_tools, on_call_tool=call_tool)
    external = urlsplit(remote.config["url"])
    hosts = ["127.0.0.1:*", "localhost:*"]
    origins = [f"http://127.0.0.1:{remote.config['port']}"]
    if external.hostname:
        hosts.extend([external.hostname, external.netloc, external.hostname + ":443"])
        origins.append("https://" + external.netloc)
    manager = StreamableHTTPSessionManager(server, stateless=True, json_response=True,
        security_settings=TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins))

    @asynccontextmanager
    async def lifespan(_app):
        async with manager.run():
            yield

    async def endpoint(scope, receive, send):
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"").decode("latin1")
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() != "bearer" or not remote.authenticate(credential):
            await JSONResponse({"error": "LALC MCP authentication required"}, status_code=401,
                               headers={"WWW-Authenticate": "Bearer"})(scope, receive, send)
        elif scope["path"] != "/mcp":
            await JSONResponse({"error": "Not found"}, status_code=404)(scope, receive, send)
        else:
            await manager.handle_request(scope, receive, send)

    return Starlette(routes=[Mount("/", app=endpoint)], lifespan=lifespan)


def start_server(remote):
    """预先绑定端口后启动应用托管线程；启动失败不留下假开启状态。"""
    import uvicorn
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", remote.config["port"]))
        config = uvicorn.Config(make_app(remote), host="127.0.0.1", port=remote.config["port"],
                                log_level="warning", access_log=False, lifespan="on")
        server = uvicorn.Server(config)
        def run():
            try:
                server.run(sockets=[sock])
            finally:
                sock.close()
                if not server.should_exit:
                    with remote.service._condition:
                        remote.failure = "MCP 网络服务意外退出，已撤销授权并请求停止。"
                        remote.enabled = False
                        remote.revoke()
        thread = threading.Thread(target=run, name="lalc-mcp-http", daemon=True)
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        if not server.started:
            server.should_exit = True
            thread.join()
            raise RuntimeError("MCP 服务启动失败，请检查端口和依赖。")
        return server, thread
    except BaseException:
        sock.close()
        raise

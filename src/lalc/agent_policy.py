"""开发模式与入口的固定授权；历史消息不参与权限计算。"""

BASE_TOOLS = ("read", "edit", "validate", "asset_tree", "asset_directory", "asset_images",
              "action_contracts", "game_screenshot", "crop_asset", "add_component", "add_recovery_rule",
              "publish", "trial_run", "list_runs", "read_run_log", "search_run_logs", "preview_crop", "remove_asset",
              "list_manifests", "read_manifest", "read_manifest_source",
              "list_game_versions", "search_agent_sessions", "read_agent_session")
KNOWLEDGE_TOOLS = ("knowledge_list", "knowledge_read", "knowledge_search_literal", "knowledge_search_hybrid", "knowledge_git")
GUI_TOOLS = KNOWLEDGE_TOOLS + ("request_feedback",)
PAGE_TOOLS = ("page_list", "page_read", "page_create", "page_update", "page_resource", "page_preview", "page_set_enabled")
HISTORY_TOOLS = ("list_game_versions", "search_agent_sessions", "read_agent_session")
RUNTIME_TOOLS = tuple(name for name in BASE_TOOLS if name not in {"remove_asset", "trial_run"}) + (
    "knowledge_list", "knowledge_read", "knowledge_search_literal", "knowledge_search_hybrid",
    "request_feedback", "read_run_state", "recheck")
MODE_TOOLS = {"Construct": frozenset(BASE_TOOLS + GUI_TOOLS + PAGE_TOOLS),
              "Repair": frozenset(BASE_TOOLS + GUI_TOOLS)}
ENTRY_TOOLS = {"gui": frozenset(BASE_TOOLS + GUI_TOOLS + PAGE_TOOLS), "cli": frozenset(BASE_TOOLS),
               "runtime": frozenset(RUNTIME_TOOLS)}


def allowed_tools(mode, entry, *, history_enabled=True, runtime_feedback_enabled=False, knowledge_enabled=True):
    """入口与模式取交集；CLI 不因保存了 Construct 对话而取得其权限。"""
    if mode not in MODE_TOOLS or entry not in ENTRY_TOOLS or entry in {"cli", "runtime"} and mode != "Repair":
        raise ValueError("CLI 仅能使用 Repair；无效的开发模式或入口。")
    ordered = RUNTIME_TOOLS if entry == "runtime" else BASE_TOOLS + GUI_TOOLS + PAGE_TOOLS
    allowed = ENTRY_TOOLS[entry] if entry == "runtime" else MODE_TOOLS[mode] & ENTRY_TOOLS[entry]
    if not history_enabled:
        allowed = allowed - set(HISTORY_TOOLS)
    if not knowledge_enabled:
        allowed = allowed - set(KNOWLEDGE_TOOLS)
    if entry == "runtime" and not runtime_feedback_enabled:
        allowed = allowed - {"request_feedback"}
    return tuple(name for name in ordered if name in allowed)

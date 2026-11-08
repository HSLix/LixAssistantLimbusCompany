"""开发模式与入口的固定授权；历史消息不参与权限计算。"""

BASE_TOOLS = ("read", "edit", "validate", "asset_tree", "asset_directory", "asset_images",
              "action_contracts", "game_screenshot", "crop_asset", "add_component", "add_recovery_rule",
              "publish", "trial_run", "list_runs", "read_run_log", "preview_crop", "remove_asset",
              "list_manifests", "read_manifest", "read_manifest_source",
              "list_game_versions", "search_agent_sessions", "read_agent_session")
KNOWLEDGE_TOOLS = ("knowledge_list", "knowledge_read", "knowledge_search_literal", "knowledge_search_hybrid", "knowledge_git")
GUI_TOOLS = KNOWLEDGE_TOOLS + ("request_feedback",)
PAGE_TOOLS = ("page_list", "page_read", "page_create", "page_update", "page_resource", "page_preview", "page_set_enabled")
MODE_TOOLS = {"Construct": frozenset(BASE_TOOLS + GUI_TOOLS + PAGE_TOOLS),
              "Repair": frozenset(BASE_TOOLS + GUI_TOOLS)}
ENTRY_TOOLS = {"gui": frozenset(BASE_TOOLS + GUI_TOOLS + PAGE_TOOLS), "cli": frozenset(BASE_TOOLS)}


def allowed_tools(mode, entry):
    """入口与模式取交集；CLI 不因保存了 Construct 对话而取得其权限。"""
    if mode not in MODE_TOOLS or entry not in ENTRY_TOOLS or entry == "cli" and mode != "Repair":
        raise ValueError("CLI 仅能使用 Repair；无效的开发模式或入口。")
    allowed = MODE_TOOLS[mode] & ENTRY_TOOLS[entry]
    return tuple(name for name in BASE_TOOLS + GUI_TOOLS + PAGE_TOOLS if name in allowed)

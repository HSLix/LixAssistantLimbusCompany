"""Agent Repair 的分轮对话呈现；界面合并工具状态，原始事件不丢弃。"""

from html import escape
import json

from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtWidgets import QTextBrowser


class RepairChat(QTextBrowser):
    """用原生富文本区呈现角色与 Markdown，按调用 ID 合并可展开工具记录。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = []
        self.tools = {}
        self.setOpenLinks(False)
        self.anchorClicked.connect(self.open_link)

    def clear(self):
        self.entries.clear()
        self.tools.clear()
        super().clear()

    def add_message(self, role, text, round_number=0):
        self.entries.append({"role": role, "text": text, "round": round_number})
        self.render()

    def upsert_tool(self, round_number, call_id, name, kind, event):
        """同轮同 ID 更新一条记录；错误状态保留，宿主结果不冒充 pi 完成。"""
        key = (round_number, call_id)
        if key not in self.tools:
            entry = {"role": "工具", "round": round_number, "name": name, "events": {}, "expanded": False}
            self.tools[key] = entry
            self.entries.append(entry)
        entry = self.tools[key]
        entry["events"][kind] = event
        entry["failed"] = any(value.get("isError") or value.get("result", {}).get("isError")
                              or value.get("ok") is False for value in entry["events"].values())
        if entry["failed"]:
            entry["status"] = "失败"
        elif "tool_execution_end" in entry["events"] or str(call_id).startswith("manual-"):
            entry["status"] = "成功"
        elif "repair_tool" in entry["events"] or "validation" in entry["events"]:
            entry["status"] = "等待完成确认"
        else:
            entry["status"] = "执行中"
        self.render()
        return entry

    def open_link(self, url):
        if url.scheme() == "tool":
            index = int(url.path())
            self.entries[index]["expanded"] = not self.entries[index]["expanded"]
            self.render(follow=False)
        elif url.scheme() in {"http", "https"}:
            QDesktopServices.openUrl(url)

    def render(self, *, follow=True):
        """只在本来位于底部时跟随新内容；查看历史与展开详情时保留滚动位置。"""
        bar = self.verticalScrollBar()
        position = bar.value()
        at_bottom = position >= bar.maximum() - 2
        parts, previous_round = [], None
        for index, entry in enumerate(self.entries):
            number, role = entry["round"], entry["role"]
            if number and number != previous_round:
                parts.append(f"<hr><p><b>第 {number} 轮</b></p>")
                previous_round = number
            if role == "工具":
                color = "#9e1c1c" if entry["failed"] else "#333333"
                title = f"工具：{escape(entry['name'])} · {entry['status']}"
                toggle = "收起详情" if entry["expanded"] else "展开详情"
                body = f'<p style="color:{color}">{title}　<a href="tool:{index}">{toggle}</a></p>'
                if entry["expanded"]:
                    events = entry["events"]
                    host, end = events.get("repair_tool", {}), events.get("tool_execution_end", {})
                    result = host.get("result", end.get("result", {}))
                    if isinstance(result, dict):
                        result = result.get("details", result)
                    if "validation" in events:
                        value = events["validation"]
                        result = {"ok": value["ok"], "errors": value.get("errors", [])}
                    shown = {"arguments": host.get("arguments", events.get("tool_execution_start", {}).get("args", {})),
                             "result": result}
                    if host and end.get("isError") and not host.get("result", {}).get("isError"):
                        shown["pi_error"] = end.get("result")
                    body += "<pre>" + escape(json.dumps(shown, ensure_ascii=False, indent=2)) + "</pre>"
                parts.append(body)
                continue
            heading = escape(role) + (f" · 第 {number} 轮" if number else "")
            background = {"你": "#e8f2ff", "Agent": "#f2f4f6"}.get(role, "#fff6dd")
            if role == "Agent":
                document = QTextDocument()
                document.setMarkdown(entry["text"], QTextDocument.MarkdownFeature.MarkdownDialectGitHub
                                     | QTextDocument.MarkdownFeature.MarkdownNoHTML)
                body = document.toHtml().split("<body", 1)[1].split(">", 1)[1].rsplit("</body>", 1)[0]
            else:
                body = "<p>" + escape(entry["text"]).replace("\n", "<br>") + "</p>"
            parts.append(f'<table width="100%" cellspacing="0" cellpadding="10" bgcolor="{background}" '
                         f'style="color:#172b4d"><tr><td><b>{heading}</b>{body}</td></tr></table><p></p>')
        self.setHtml("".join(parts))
        bar.setValue(bar.maximum() if follow and at_bottom else position)

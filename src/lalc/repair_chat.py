"""Agent Repair 的分轮对话呈现；界面合并工具状态，原始事件不丢弃。"""

from html import escape
import json

from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtWidgets import QTextBrowser

from .i18n import tr
from .agent_prompts import user_message_text, chat_title


def raw_output_text(content):
    """同一格式呈现实时内容与已落盘的完整模型消息。"""
    parts = []
    for part in content:
        kind = part.get('type')
        if kind == 'text':
            parts.append(part.get('text', ''))
        elif kind == 'thinking':
            parts.append(part.get('thinking', ''))
        elif kind == 'toolCall':
            arguments = part.get('partialArgs')
            if arguments is None:
                arguments = json.dumps(part.get('arguments', {}), ensure_ascii=False)
            parts.append(part.get('name', '') + '\n' + arguments)
    return '\n\n'.join(part for part in parts if part)


class RepairChat(QTextBrowser):
    """用原生富文本区呈现角色与 Markdown，按调用 ID 合并可展开工具记录。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = []
        self.tools = {}
        self.activities = {}
        self.activity_round = 0
        self.setOpenLinks(False)
        self.anchorClicked.connect(self.open_link)

    def clear(self):
        self.entries.clear()
        self.tools.clear()
        self.activities.clear()
        self.activity_round = 0
        super().clear()

    def activity(self, number=None):
        """每轮独立保存生成过程和展开选择，避免续聊覆盖上一轮。"""
        number = self.activity_round if number is None else number
        return self.activities.setdefault(number, {'status': '', 'tooltip': '', 'messages': [],
                                                   'pending': '', 'expanded': False})

    def remember_message(self, number, content):
        """复用完整消息记录保留生成过程，不新增逐片持久化或迁移。"""
        self.activity_round = number
        activity = self.activity(number)
        text = raw_output_text(content)
        if text:
            activity['messages'].append(text)
        activity['pending'] = ''
        self.render()

    def set_activity(self, status, round_number, tooltip=""):
        """状态与生成过程位于对应轮次回复顶部。"""
        self.activity_round = round_number
        activity = self.activity()
        unchanged_empty = not status and not activity['status'] and not activity['messages'] and not activity['pending']
        activity.update(status=status, tooltip=tooltip)
        if not unchanged_empty:
            self.render()

    def activity_html(self, number):
        """真实状态作折叠标题；模型内容按纯文字转义。"""
        activity = self.activity(number)
        raw = '\n\n'.join([*activity['messages'], *([activity['pending']] if activity['pending'] else [])])
        title = escape(activity['status'] or tr('Raw output'))
        tooltip = escape(activity['tooltip'], quote=True)
        if raw:
            tooltip = escape(tr('Expand or collapse raw output'), quote=True) + (' · ' + tooltip if tooltip else '')
            arrow = '▾' if activity['expanded'] else '▸'
            title = f'<a href="raw:{number}" title="{tooltip}" style="color:#737980;text-decoration:none">{title} {arrow}</a>'
        elif not activity['status']:
            return ''
        body = f'<p style="color:#737980" title="{tooltip}">{title}</p>'
        if raw and activity['expanded']:
            body += '<pre>' + escape(raw) + '</pre>'
        return body

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

    def format_retry(self, round_number):
        """同轮格式纠正只占一条系统摘要；每次实际重试仍准确计数。"""
        entry = next((entry for entry in self.entries if 'format_retry' in entry and entry['round'] == round_number), None)
        if entry is None:
            entry = {'role': '系统', 'round': round_number, 'format_retry': 0}
            self.entries.append(entry)
        entry['format_retry'] += 1
        entry['text'] = tr('Response format did not match JSON; automatic retries: {0}.').format(entry['format_retry'])
        self.render()

    def open_link(self, url):
        if url.scheme() == "raw":
            if not url.path().isdigit() or int(url.path()) not in self.activities:
                return
            activity = self.activities[int(url.path())]
            activity['expanded'] = not activity['expanded']
            self.render(follow=False)
        elif url.scheme() == "tool":
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
        # 每轮折叠区跟随该轮用户消息，续聊仍保留旧轮次内容。
        activity_indices = {}
        for index, entry in enumerate(self.entries):
            if entry['role'] == '你':
                activity_indices[entry['round']] = index + 1
        activity_at = {}
        for number in self.activities:
            activity_at.setdefault(activity_indices.get(number, len(self.entries)), []).append(number)
        for index, entry in enumerate(self.entries):
            for number in activity_at.get(index, []):
                parts.append(self.activity_html(number))
            number, role = entry["round"], entry["role"]
            if number and number != previous_round:
                parts.append(tr('<hr><p><b>Round {0}</b></p>').format(number))
                previous_round = number
            if role == "工具":
                color = "#9e1c1c" if entry["failed"] else "#333333"
                status = {"失败": tr("Failed"), "成功": tr("Succeeded"),
                          "等待完成确认": tr("Awaiting completion"), "执行中": tr("In progress")}[entry["status"]]
                title = tr('Tool: {0} · {1}').format(escape(entry['name']), status)
                toggle = tr('Hide details') if entry["expanded"] else tr('Show details')
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
            shown_role = {"你": tr("You"), "系统": tr("System")}.get(role, role)
            heading = escape(shown_role) + (tr(' · Round {0}').format(number) if number else "")
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
        for number in activity_at.get(len(self.entries), []):
            parts.append(self.activity_html(number))
        self.setHtml("".join(parts))
        bar.setValue(bar.maximum() if follow and at_bottom else position)

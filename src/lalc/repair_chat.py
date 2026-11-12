"""Agent Repair 的分轮对话呈现；界面合并工具状态，原始事件不丢弃。"""

from html import escape
import json
import time

from PySide6.QtCore import Signal, QTimer
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


def process_text_parts(content):
    """提取过程段落；工具参数留在工具节点，最终业务回答由外层呈现。"""
    for part in content:
        kind = part.get('type')
        if kind not in {'thinking', 'text'}:
            continue
        value = part.get('thinking' if kind == 'thinking' else 'text', '')
        if kind == 'text':
            try:
                answer = json.loads(value)
            except (ValueError, TypeError):
                answer = None
            if isinstance(answer, dict) and 'message' in answer and 'revise_success' in answer:
                continue
        if value:
            yield value


def working_duration(seconds):
    """工作时长只按秒、分秒或时分显示，不引入更大的时间单位。"""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return tr('{0}s').format(seconds)
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return tr('{0}m {1}s').format(minutes, seconds)
    hours, minutes = divmod(minutes, 60)
    return tr('{0}h {1}m').format(hours, minutes)


class RepairChat(QTextBrowser):
    """用原生富文本区呈现角色与 Markdown，按调用 ID 合并可展开工具记录。"""

    olderRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.batch_render = False
        self._rendering = False
        self.entries = []
        self.tools = {}
        self.activities = {}
        self.activity_round = 0
        self.working_round = None
        self.working_started = None
        self.working_timer = QTimer(self)
        self.working_timer.setInterval(1000)
        self.working_timer.timeout.connect(lambda: self.render(follow=False))
        self.setOpenLinks(False)
        self.anchorClicked.connect(self.open_link)
        self.verticalScrollBar().valueChanged.connect(self._scroll_changed)

    def _scroll_changed(self, value):
        if value == 0 and not self._rendering and not self.batch_render:
            self.olderRequested.emit()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0 and self.verticalScrollBar().value() == 0:
            self.olderRequested.emit()
        super().wheelEvent(event)

    def clear(self):
        self.stop_work()
        self.entries.clear()
        self.tools.clear()
        self.activities.clear()
        self.activity_round = 0
        super().clear()

    def start_work(self, number):
        """仅现场轮次启动单调时钟；状态切换和工具调用不重置计时。"""
        self.working_round, self.working_started = number, time.monotonic()
        self.working_timer.start()

    def stop_work(self):
        """轮次结束或清理时停止界面计时，不向模型或日志写入时钟。"""
        self.working_timer.stop()
        self.working_round = self.working_started = None

    def activity(self, number=None):
        """每轮独立保存生成过程和展开选择，避免续聊覆盖上一轮。"""
        number = self.activity_round if number is None else number
        return self.activities.setdefault(number, {'status': '', 'tooltip': '', 'messages': [],
                                                   'pending': '', 'expanded': False, 'timeline': []})

    def remember_message(self, number, content):
        """复用完整消息记录保留生成过程，不新增逐片持久化或迁移。"""
        self.activity_round = number
        activity = self.activity(number)
        text = raw_output_text(content)
        if text:
            activity['messages'].append(text)
        activity['timeline'].extend(process_text_parts(content))
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
        has_content = bool(activity['timeline'] or activity['pending'])
        title = escape(tr('Thinking and tools'))
        if activity['status']:
            title += ' · ' + escape(activity['status'])
        if self.working_round == number and self.working_started is not None:
            title += ' · ' + escape(tr('Working for {0}').format(working_duration(time.monotonic() - self.working_started)))
        tooltip = escape(activity['tooltip'], quote=True)
        if has_content:
            arrow = '▾' if activity['expanded'] else '▸'
            title = f'<a href="raw:{number}" title="{tooltip}" style="color:#737980;text-decoration:none">{title} {arrow}</a>'
        elif not activity['status']:
            return ''
        body = f'<p style="color:#737980" title="{tooltip}">{title}</p>'
        if has_content and activity['expanded']:
            nodes = list(activity['timeline'])
            if activity['pending']:
                nodes.append(activity['pending'])
            body += '<table width="100%" cellspacing="0" cellpadding="6">'
            for node in nodes:
                content = (self.tool_html(node) if isinstance(node, dict) else
                           '<pre style="white-space: pre-wrap">' + escape(node) + '</pre>')
                body += ('<tr><td width="18" valign="top" style="border-left:1px solid #c5c9ce;color:#737980">•</td>'
                         '<td>' + content + '</td></tr>')
            body += '</table>'
        return body

    def add_message(self, role, text, round_number=0):
        self.entries.append({"role": role, "text": text, "round": round_number})
        self.render()

    def upsert_tool(self, round_number, call_id, name, kind, event):
        """同轮同 ID 更新一条记录；错误状态保留，宿主结果不冒充 pi 完成。"""
        key = (round_number, call_id)
        if key not in self.tools:
            entry = {"role": "工具", "round": round_number, "name": name, "events": {}, "expanded": False, "index": len(self.entries)}
            self.tools[key] = entry
            self.entries.append(entry)
            self.activity(round_number)['timeline'].append(entry)
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

    def tool_html(self, entry):
        """工具摘要保留独立折叠与失败颜色，嵌入本轮过程节点。"""
        color = "#9e1c1c" if entry["failed"] else "#333333"
        status = {"失败": tr("Failed"), "成功": tr("Succeeded"),
                  "等待完成确认": tr("Awaiting completion"), "执行中": tr("In progress")}[entry["status"]]
        title = tr('Tool: {0} · {1}').format(escape(entry['name']), status)
        events = entry['events']
        arguments = events.get('repair_tool', {}).get('arguments', events.get('tool_execution_start', {}).get('args', {}))
        if isinstance(arguments, dict):
            details = []
            for key in ('path', 'filename', 'run_id', 'logical_name', 'asset', 'manifest_id', 'query', 'keyword'):
                value = arguments.get(key)
                if isinstance(value, (str, int)) and str(value):
                    text = str(value).replace('\n', ' ')
                    details.append((key + '=' if key == 'run_id' else '') + (text[:97] + '…' if len(text) > 100 else text))
                if len(details) == 2:
                    break
            if details:
                title += ' · ' + escape(' · '.join(details))
        toggle = tr('Hide details') if entry["expanded"] else tr('Show details')
        body = f'<p style="color:{color}">{title}　<a href="tool:{entry['index']}">{toggle}</a></p>'
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
            body += '<pre style="white-space: pre-wrap">' + escape(json.dumps(shown, ensure_ascii=False, indent=2)) + '</pre>'
        return body

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

    def resizeEvent(self, event):
        """聊天区重新分配高度时保留贴底状态，阅读历史时不主动滚动。"""
        bar = self.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 2
        super().resizeEvent(event)
        if at_bottom:
            bar.setValue(bar.maximum())

    def render(self, *, follow=True):
        """只在本来位于底部时跟随新内容；查看历史与展开详情时保留滚动位置。"""
        if self.batch_render:
            return
        self._rendering = True
        bar = self.verticalScrollBar()
        position = bar.value()
        at_bottom = position >= bar.maximum() - 2
        parts, previous_round = [], None
        # 每轮折叠区跟随该轮用户消息，续聊仍保留旧轮次内容。
        activity_indices = {}
        for index, entry in enumerate(self.entries):
            if entry['role'] == '工具':
                entry['index'] = index
            activity_indices.setdefault(entry['round'], index)
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
        # 富文本可能延迟排版，先取得完整高度再恢复阅读位置。
        self.document().documentLayout().documentSize()
        bar.setValue(bar.maximum() if follow and at_bottom else position)
        self._rendering = False

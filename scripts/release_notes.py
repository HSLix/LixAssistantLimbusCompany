"""汇总上次发行后进入正式版的提交，包括直接提交和共同作者。"""

from collections import defaultdict
import subprocess
import sys

RELEASE_LINKS = """- (推荐，速度快质量好）[已有 Mirror酱 CDK？前往 Mirror酱 高速下载](https://mirrorchyan.com/zh/projects?rid=LALC)
- (GitHub 有时会限制)[GitHub 最新 Release 下载](https://github.com/HSLix/LixAssistantLimbusCompany/releases/latest) | [Download the latest release from GitHub](https://github.com/HSLix/LixAssistantLimbusCompany/releases/latest)
- (不定时更新)[夸克网盘](https://pan.quark.cn/s/333d6608dddd) | Record Important Version in [KuakeDrive](https://pan.quark.cn/s/333d6608dddd).
- [加入 Discord 群聊](https://discord.gg/bVzCuBU4bC) | [Join the discord](https://discord.gg/bVzCuBU4bC)"""


def release_notes(previous, commit):
    """使用 Git 可达范围排除旧版历史，兼容重构历史首次合入。"""
    records = subprocess.check_output(
        ["git", "log", "-z", "--encoding=UTF-8",
         "--format=%aN%x00%h%x00%s%x00%(trailers:key=Co-authored-by,valueonly,separator=%x1f)",
         f"{previous}..{commit}", "--"], encoding="utf-8").split("\0")
    authors = defaultdict(list)
    for author, sha, title, coauthors in zip(records[::4], records[1::4], records[2::4], records[3::4]):
        # Git 提交信息可能包含 Markdown；保持标题作为正文文本显示。
        title = title.replace("\\", "\\\\").replace("<", "&lt;").replace(">", "&gt;")
        for name in dict.fromkeys([author, *(item.split("<", 1)[0].strip() for item in coauthors.split("\x1f"))]):
            if name:
                authors[name].append(f"- {title} (`{sha}`)")
    changes = [RELEASE_LINKS, "", "## 更新记录", ""]
    for author, entries in sorted(authors.items(), key=lambda item: (-len(item[1]), item[0].casefold())):
        changes.extend((f"### {author} ({len(entries)})", "", *entries, ""))
    return "\n".join(changes)


if __name__ == "__main__":
    print(release_notes(*sys.argv[1:]))

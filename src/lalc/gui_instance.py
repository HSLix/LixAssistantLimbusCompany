"""重复 GUI 入口只转交窗口请求，不建立第二套执行服务。"""

from __future__ import annotations

import getpass
import hashlib
from pathlib import Path

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from .process_lock import ProcessLock


class GuiInstance:
    """以操作系统锁裁决启动竞争，以用户私有本地通道唤起窗口。"""

    def __init__(self):
        self.lock = ProcessLock("gui")
        self.name = "lalc-gui-" + hashlib.sha256(f"{Path.home()}:{getpass.getuser()}".encode()).hexdigest()[:20]
        self.server = None
        self.sockets = set()

    def forward(self, developer: bool) -> bool:
        """现有实例正在初始化时短暂等待，不允许竞争者另建服务。"""
        try:
            self.lock.acquire()
            return False
        except OSError:
            from PySide6.QtCore import QThread
            for _ in range(40):
                socket = QLocalSocket()
                socket.connectToServer(self.name)
                if socket.waitForConnected(100):
                    socket.write(b"developer\n" if developer else b"user\n")
                    if not socket.waitForBytesWritten(1000):
                        raise RuntimeError("无法向已有应用转交窗口请求。")
                    if not socket.waitForReadyRead(2000) or bytes(socket.readAll()) != b"ok\n":
                        raise RuntimeError("已有应用未确认窗口请求。")
                    socket.disconnectFromServer()
                    return True
                QThread.msleep(50)
            raise RuntimeError("已有 LALC 实例未响应，请检查其启动或退出状态。")

    def listen(self, open_window):
        """只有启动锁拥有者可清理旧通道并接受窗口唤起请求。"""
        self.server = QLocalServer()
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            self.lock.release()
            raise RuntimeError(self.server.errorString())
        def accept():
            while self.server.hasPendingConnections():
                socket = self.server.nextPendingConnection()
                self.sockets.add(socket)
                def read(socket=socket):
                    if not socket.canReadLine():
                        return
                    command = bytes(socket.readLine(32))
                    if command in {b"developer\n", b"user\n"}:
                        open_window(command == b"developer\n")
                        socket.write(b"ok\n")
                        socket.flush()
                    socket.disconnectFromServer()
                socket.readyRead.connect(read)
                def discard(socket=socket):
                    self.sockets.discard(socket)
                    socket.deleteLater()
                socket.disconnected.connect(discard)
                read()
        self.server.newConnection.connect(accept)

    def close(self):
        if self.server is not None:
            self.server.close()
        for socket in list(self.sockets):
            socket.abort()
        self.lock.release()

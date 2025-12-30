import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:lalc_frontend/task_status_manager.dart';
import 'package:lalc_frontend/websocket_manager.dart';
import 'package:toastification/toastification.dart';
import '../generated/l10n.dart'; // 添加国际化支持

class WorkPage extends StatefulWidget {
  const WorkPage({super.key});

  @override
  State<WorkPage> createState() => _WorkPageState();
}

class _WorkPageState extends State<WorkPage> {
  final ScrollController _scrollController = ScrollController();
  WebSocketManager? _webSocketManager;

  @override
  void initState() {
    super.initState();
    // 在widget构建完成后滚动到底部
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollToBottom();
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    // 移除监听器
    _webSocketManager?.removeListener(_handleWebSocketUpdate);
    super.dispose();
  }

  // 滚动到底部的方法
  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
    }
  }

  // 处理 WebSocket 状态更新
  void _handleWebSocketUpdate() {
    // 检查是否有新的错误消息需要显示 Toast
    if (_webSocketManager != null && _webSocketManager!.lastErrorMessage != null) {
      // 显示长时间持续的红色错误 Toast 通知
      if (mounted && context.mounted) {
        toastification.show(
          context: context,
          title: Text('${S.of(context).error}: ${_webSocketManager!.lastErrorMessage}'),
          autoCloseDuration: const Duration(days: 1), // 持续一天
          type: ToastificationType.error,
          style: ToastificationStyle.flatColored,
        );
        
        // 清除错误消息
        _webSocketManager!.clearLastErrorMessage();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer2<TaskStatusManager, WebSocketManager>(
      builder: (context, taskStatusManager, webSocketManager, child) {
        // 滚动到底部
        if (webSocketManager.logMessages.isNotEmpty) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (_scrollController.hasClients) {
              _scrollController.animateTo(
                _scrollController.position.maxScrollExtent,
                duration: const Duration(milliseconds: 300),
                curve: Curves.easeOut,
              );
            }
          });
        }

        // 监听 WebSocket 更新
        if (_webSocketManager != webSocketManager) {
          _webSocketManager?.removeListener(_handleWebSocketUpdate);
          _webSocketManager = webSocketManager;
          _webSocketManager!.addListener(_handleWebSocketUpdate);
        }

        return Column(
          children: [
            // 上方日志显示框（可自伸缩）
            Expanded(
              child: Container(
                padding: const EdgeInsets.all(16.0),
                alignment: Alignment.center,
                child: Column(
                  children: [
                    // 连接状态显示
                    Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: Colors.grey[800],
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            webSocketManager.isConnected
                                ? Icons.circle
                                : (webSocketManager.isConnecting
                                    ? Icons.access_time
                                    : Icons.warning),
                            color: webSocketManager.isConnected
                                ? Colors.green
                                : (webSocketManager.isConnecting
                                    ? Colors.orange
                                    : Colors.red),
                            size: 16,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            webSocketManager.isConnected
                                ? S.of(context).connected
                                : (webSocketManager.isConnecting
                                    ? S.of(context).connecting
                                    : S.of(context).disconnected),
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(width: 16),
                          Text(
                            '${S.of(context).server}: ${webSocketManager.serverUrl}',
                            style: const TextStyle(
                              color: Colors.white70,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                    
                    // 日志消息显示区域
                    Expanded(
                      child: Container(
                        padding: const EdgeInsets.all(8.0),
                        decoration: BoxDecoration(
                          color: Colors.black54,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: ListView.builder(
                          controller: _scrollController,
                          itemCount: webSocketManager.logMessages.length,
                          itemBuilder: (context, index) {
                            final message = webSocketManager.logMessages[index];
                            return Text(
                              message,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                              ),
                            );
                          },
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            
            // 下方控制按钮区域
            Container(
              padding: const EdgeInsets.all(16.0),
              decoration: BoxDecoration(
                color: Colors.grey[800],
                border: Border(top: BorderSide(color: Colors.grey[600]!)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  Tooltip(
                    message: 'Ctrl+Alt+S',
                    child: ElevatedButton(
                      onPressed: (!taskStatusManager.isRunning && !taskStatusManager.isPaused)
                          ? () {
                              webSocketManager.startTask();
                              toastification.show(
                                context: context,
                                title: Text(S.of(context).task_started),
                                autoCloseDuration: const Duration(seconds: 2),
                                type: ToastificationType.success,
                                style: ToastificationStyle.flatColored,
                              );
                            }
                          : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.green,
                        foregroundColor: Colors.white,
                      ),
                      child: Text(S.of(context).start),
                    ),
                  ),
                  Tooltip(
                    message: 'Ctrl+Alt+P',
                    child: ElevatedButton(
                      onPressed: taskStatusManager.isRunning && !taskStatusManager.isPaused
                          ? () {
                              webSocketManager.pauseTask();
                              toastification.show(
                                context: context,
                                title: Text(S.of(context).task_paused),
                                autoCloseDuration: const Duration(seconds: 2),
                                type: ToastificationType.info,
                                style: ToastificationStyle.flatColored,
                              );
                            }
                          : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.orange,
                        foregroundColor: Colors.white,
                      ),
                      child: Text(S.of(context).pause),
                    ),
                  ),
                  Tooltip(
                    message: 'Ctrl+Alt+R',
                    child: ElevatedButton(
                      onPressed: taskStatusManager.isPaused
                          ? () {
                              webSocketManager.resumeTask();
                              toastification.show(
                                context: context,
                                title: Text(S.of(context).task_resumed),
                                autoCloseDuration: const Duration(seconds: 2),
                                type: ToastificationType.info,
                                style: ToastificationStyle.flatColored,
                              );
                            }
                          : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.blue,
                        foregroundColor: Colors.white,
                      ),
                      child: Text(S.of(context).resume),
                    ),
                  ),
                  Tooltip(
                    message: 'Ctrl+Alt+Q',
                    child: ElevatedButton(
                      onPressed: (taskStatusManager.isRunning || taskStatusManager.isPaused)
                          ? () {
                              webSocketManager.stopTask();
                              toastification.show(
                                context: context,
                                title: Text(S.of(context).task_stopped),
                                autoCloseDuration: const Duration(seconds: 2),
                                type: ToastificationType.error,
                                style: ToastificationStyle.flatColored,
                              );
                            }
                          : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red,
                        foregroundColor: Colors.white,
                      ),
                      child: Text(S.of(context).stop),
                    ),
                  ),
                  ElevatedButton(
                    onPressed: webSocketManager.isConnected
                        ? null
                        : () {
                            webSocketManager.connect();
                            toastification.show(
                              context: context,
                              title: Text(S.of(context).connecting),
                              autoCloseDuration: const Duration(seconds: 2),
                              type: ToastificationType.info,
                              style: ToastificationStyle.flatColored,
                            );
                          },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.purple,
                      foregroundColor: Colors.white,
                      // textStyle: const TextStyle(color: Colors.white),
                    ),
                    child: Text(S.of(context).connect),
                  ),
                  ElevatedButton(
                    onPressed: webSocketManager.isConnected
                        ? () {
                            webSocketManager.disconnect();
                            toastification.show(
                              context: context,
                              title: Text(S.of(context).disconnected),
                              autoCloseDuration: const Duration(seconds: 2),
                              type: ToastificationType.info,
                              style: ToastificationStyle.flatColored,
                            );
                          }
                        : null,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.grey,
                      foregroundColor: Colors.white,
                    ),
                    child: Text(S.of(context).disconnect),
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}
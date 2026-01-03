import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:lalc_frontend/managers/task_status_manager.dart';
import 'package:lalc_frontend/managers/websocket_manager.dart';
import 'package:lalc_frontend/managers/command_gateway.dart'; // 导入命令网关
import 'package:toastification/toastification.dart';
import '../generated/l10n.dart'; // 添加国际化支持

class WorkPage extends StatefulWidget {
  const WorkPage({super.key});

  @override
  State<WorkPage> createState() => _WorkPageState();
}

class _WorkPageState extends State<WorkPage> // 修复继承错误
{ // 移除不需要的TickerProviderStateMixin
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

  // 滚动到底部的方法（对于reverse: true的ListView，实际上是滚动到顶部）
  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      // 对于reverse: true的ListView，滚动到0位置才是显示最新消息
      _scrollController.animateTo(
        0.0,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
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
    
    // 日志更新时自动滚动到底部（对于reverse: true的列表，是滚动到顶部位置0.0）
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollToBottom();
    });
    
    // 重要：触发重建以更新日志列表
    if (mounted) {
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final taskStatus = Provider.of<TaskStatusManager>(context);
    final webSocketManager = Provider.of<WebSocketManager>(context, listen: false);

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
                      reverse: true,
                      controller: _scrollController,
                      itemCount: webSocketManager.logMessages.length,
                      itemBuilder: (context, index) {
                        final message = webSocketManager.logMessages[webSocketManager.logMessages.length - 1 - index];
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
              // 开始按钮
              Tooltip(
                message: 'Ctrl+Alt+S',
                child: ElevatedButton(
                  onPressed: !taskStatus.isRunning
                      ? () {
                          CommandGateway().sendTaskCommand(context, TaskCommand.start, (success, msg) {
                            if (!success && mounted) {
                              toastification.show(
                                context: context,
                                title: Text(msg ?? S.of(context).task_start_failed),
                                type: ToastificationType.error,
                                style: ToastificationStyle.flatColored,
                              );
                            } else if (mounted) {
                              toastification.show(
                                context: context,
                                title: Text(S.of(context).task_started),
                                autoCloseDuration: const Duration(seconds: 2),
                                type: ToastificationType.success,
                                style: ToastificationStyle.flatColored,
                              );
                            }
                          });
                        }
                      : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                  ),
                  child: Text(S.of(context).start),
                ),
              ),

              // 暂停按钮
              Tooltip(
                message: 'Ctrl+Alt+P',
                child: ElevatedButton(
                  onPressed: taskStatus.isRunning && !taskStatus.isPaused
                      ? () {
                          CommandGateway().sendTaskCommand(context, TaskCommand.pause, (success, msg) {
                            if (!success && mounted) {
                              toastification.show(
                                context: context,
                                title: Text(msg ?? S.of(context).task_operation_failed),
                                type: ToastificationType.error,
                                style: ToastificationStyle.flatColored,
                              );
                            } else if (mounted) {
                              toastification.show(
                                context: context,
                                title: Text(S.of(context).task_paused),
                                autoCloseDuration: const Duration(seconds: 2),
                                type: ToastificationType.info,
                                style: ToastificationStyle.flatColored,
                              );
                            }
                          });
                        }
                      : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.orange,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                  ),
                  child: Text(S.of(context).pause),
                ),
              ),

              // 恢复按钮
              Tooltip(
                message: 'Ctrl+Alt+R',
                child: ElevatedButton(
                  onPressed: taskStatus.isPaused
                      ? () {
                          CommandGateway().sendTaskCommand(context, TaskCommand.resume, (success, msg) {
                            if (!success && mounted) {
                              toastification.show(
                                context: context,
                                title: Text(msg ?? S.of(context).task_operation_failed),
                                type: ToastificationType.error,
                                style: ToastificationStyle.flatColored,
                              );
                            } else if (mounted) {
                              toastification.show(
                                context: context,
                                title: Text(S.of(context).task_resumed),
                                autoCloseDuration: const Duration(seconds: 2),
                                type: ToastificationType.info,
                                style: ToastificationStyle.flatColored,
                              );
                            }
                          });
                        }
                      : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                  ),
                  child: Text(S.of(context).resume),
                ),
              ),

              // 停止按钮
              Tooltip(
                message: 'Ctrl+Alt+Q',
                child: ElevatedButton(
                  onPressed: (taskStatus.isRunning || taskStatus.isPaused)
                      ? () {
                          CommandGateway().sendTaskCommand(context, TaskCommand.stop, (success, msg) {
                            if (!success && mounted) {
                              toastification.show(
                                context: context,
                                title: Text(msg ?? S.of(context).task_operation_failed),
                                type: ToastificationType.error,
                                style: ToastificationStyle.flatColored,
                              );
                            } else if (mounted) {
                              toastification.show(
                                context: context,
                                title: Text(S.of(context).task_stopped),
                                autoCloseDuration: const Duration(seconds: 2),
                                type: ToastificationType.error,
                                style: ToastificationStyle.flatColored,
                              );
                            }
                          });
                        }
                      : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                  ),
                  child: Text(S.of(context).stop),
                ),
              ),
              
              // 连接按钮
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
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                ),
                child: Text(S.of(context).connect),
              ),
              
              // 断开连接按钮
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
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                ),
                child: Text(S.of(context).disconnect),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
import 'dart:convert';
import 'dart:async';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart';
import 'package:uuid/uuid.dart';
import 'package:flutter/foundation.dart';
import 'package:lalc_frontend/task_status_manager.dart';
import 'package:lalc_frontend/config_manager.dart';

class WebSocketManager with ChangeNotifier {
  static final WebSocketManager _instance = WebSocketManager._internal();
  factory WebSocketManager() => _instance;
  WebSocketManager._internal();

  WebSocketChannel? _channel;
  bool _isConnected = false;
  bool _isConnecting = false;
  Timer? _heartbeatTimer;
  Timer? _heartbeatTimeoutTimer;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;
  int _currentPortIndex = 0;
  final List<int> _portsToTry = List.generate(3, (index) => 8765 + index); // 8765到8767的端口
  final Uuid _uuid = const Uuid();
  final Map<String, void Function(Map<String, dynamic>)> _pendingRequests = {};
  final List<String> _logMessages = [];
  String? _lastErrorMessage;

  // 新增：下载类响应的常驻回调
  final Map<String, void Function(Map<String, dynamic>)> _downloadCallbacks = {};

  // 添加待执行命令队列
  final List<_PendingCommand> _pendingCommands = [];

  // 添加错误回调函数
  void Function(String)? _onError;

  // 设置错误回调函数
  void setErrorCallback(void Function(String) callback) {
    _onError = callback;
  }

  // 添加新的私有变量用于存储日志文件夹和日志行数据
  final Map<String, List<Map<String, dynamic>>> _logFolderContents = {};
  final Map<String, int> _logFolderLineCounts = {};
  List<String> _logFolders = [];

  // 新增getter方法
  List<String> get logFolders => List.unmodifiable(_logFolders);
  Map<String, List<Map<String, dynamic>>> get logFolderContents => Map.unmodifiable(_logFolderContents);
  Map<String, int> get logFolderLineCounts => Map.unmodifiable(_logFolderLineCounts);

  // 获取最后的错误消息
  String? get lastErrorMessage => _lastErrorMessage;

  // 清除最后的错误消息
  void clearLastErrorMessage() {
    _lastErrorMessage = null;
    notifyListeners();
  }

  // 默认WebSocket地址
  String _serverUrl = 'ws://localhost:8765';

  bool get isConnected => _isConnected;
  bool get isConnecting => _isConnecting;
  List<String> get logMessages => List.unmodifiable(_logMessages);

  String get serverUrl => _serverUrl;
  set serverUrl(String url) {
    _serverUrl = url;
    notifyListeners();
  }

  // 初始化WebSocket连接
  void initialize() {
    debugPrint('初始化WebSocket连接');
    _addLogMessage('初始化WebSocket连接');
    // 添加额外的调试信息
    debugPrint('当前连接状态 - isConnected: $_isConnected, isConnecting: $_isConnecting');
    connect();
  }

  // 获取下一个要尝试的端口URL
  String _getNextServerUrl() {
    final port = _portsToTry[_currentPortIndex];
    return 'ws://localhost:$port';
  }

  // 连接到WebSocket服务器
  Future<void> connect() async {
    // 如果已经在连接或已连接，则直接返回
    if (_isConnecting || _isConnected) {
      debugPrint('WebSocket已在连接中或已连接，跳过重复连接');
      return;
    }
    
    _isConnecting = true;
    notifyListeners();
    
    // 获取当前要尝试连接的URL
    final currentUrl = _getNextServerUrl();
    
    try {
      debugPrint('尝试连接到 $currentUrl (当前端口尝试次数: ${(_reconnectAttempts % _portsToTry.length) + 1})');
      _addLogMessage('正在连接到 $currentUrl... (当前端口尝试次数: ${(_reconnectAttempts % _portsToTry.length) + 1})');
      
      _channel = WebSocketChannel.connect(Uri.parse(currentUrl));
      // 注意：这里不再立即设置_isConnected为true，等待收到服务器消息后再确认连接成功
      // _reconnectAttempts保持不变，直到真正连接成功才重置
      
      // 监听消息
      _channel!.stream.listen(
        _handleMessage,
        onError: _handleError,
        onDone: _handleDisconnect,
      );
      
      // 启动心跳机制
      _startHeartbeat();
    } catch (e) {
      _isConnecting = false;
      notifyListeners();
      debugPrint('WebSocket连接失败: $e');
      _addLogMessage('WebSocket连接失败: $e');
      // 连接失败时增加端口索引并安排重新连接
      _reconnectAttempts++;
      _currentPortIndex = (_currentPortIndex + 1) % _portsToTry.length;
      _scheduleReconnect(const Duration(milliseconds: 500));
    }
  }

  // 处理连接失败
  void _handleConnectionFailure() {
    // 确保连接状态正确
    _isConnected = false;
    _isConnecting = false;
    notifyListeners();
    
    _reconnectAttempts++;
    
    // 切换到下一个端口
    _currentPortIndex = (_currentPortIndex + 1) % _portsToTry.length;
    
    // 如果已经尝试过所有端口，增加重试间隔并重置尝试次数
    if (_currentPortIndex == 0) {
      // 所有端口都尝试过了，增加延迟（指数退避）
      final delaySeconds = 2 * (_reconnectAttempts ~/ _portsToTry.length).clamp(1, 30);
      _addLogMessage('所有端口均连接失败，将在$delaySeconds秒后重试...');
      // 重置尝试次数，开始新的一轮
      _reconnectAttempts = 0;
      _scheduleReconnect(Duration(seconds: delaySeconds));
    } else {
      // 继续尝试下一个端口，使用更短的延迟以提高轮询速度
      _addLogMessage('连接失败，将在0.5秒后尝试重新连接到 ${_getNextServerUrl()}...');
      _scheduleReconnect(const Duration(milliseconds: 500));
    }
  }

  // 安排重连
  void _scheduleReconnect([Duration? delay]) {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay ?? const Duration(milliseconds: 500), () {
      debugPrint('尝试重新连接到 ${_getNextServerUrl()}... (当前端口尝试次数: ${(_reconnectAttempts % _portsToTry.length) + 1})');
      _addLogMessage('尝试重新连接到 ${_getNextServerUrl()}... (当前端口尝试次数: ${(_reconnectAttempts % _portsToTry.length) + 1})');
      // 确保在重连前状态正确
      _isConnected = false;
      _isConnecting = false;
      notifyListeners();
      connect();
    });
  }

  // 断开连接
  void disconnect() {
    _cleanup();
    _reconnectAttempts = 0;
    // 注意：这里不再重置_currentPortIndex，让它保持当前端口位置
    _isConnected = false;
    _isConnecting = false;
    notifyListeners();
    _addLogMessage('WebSocket连接已断开');
    
    // 主动断开连接时将任务状态设置为停止
    TaskStatusManager().stopTask();
  }

  // 清理资源
  void _cleanup() {
    _heartbeatTimer?.cancel();
    _heartbeatTimeoutTimer?.cancel();
    _reconnectTimer?.cancel();
    _pendingRequests.clear();
    _channel?.sink.close(normalClosure);
  }

  // 处理接收到的消息
  void _handleMessage(dynamic message) {
    try {
      
      // 确保消息是字符串类型
      if (message is! String) {
        debugPrint('收到非字符串类型消息: $message');
        _addLogMessage('收到非字符串类型消息: $message');
        return;
      }
      logger.d("收到消息：$message");
      final Map<String, dynamic> data = jsonDecode(message);
      final String type = data['type'] as String;
      final String? id = data['id'] as String?;

      // 如果这是第一条消息，表示连接真正建立成功
      if (!_isConnected) {
        _isConnected = true;
        _isConnecting = false; // 确保连接状态正确更新
        _reconnectAttempts = 0; // 真正连接成功时重置重连次数
        notifyListeners();
        debugPrint('WebSocket连接成功');
        _addLogMessage('WebSocket连接成功');
        
        // 执行待处理的命令
        _executePendingCommands();
      }

      switch (type) {
        case 'response':
          debugPrint('[RX] Response received with id: $id');
          _addLogMessage('收到响应消息');
          
          // 先处理下载类常驻回调
          if (id != null && _downloadCallbacks.containsKey(id)) {
            final payload = data['payload'] as Map<String, dynamic>?;
            if (payload != null) {
              _downloadCallbacks[id]!(payload);
              // 注意：只有 success/error/cancelled 才会 remove，progress 继续保留
            }
            return; // 已经处理完，直接 return，不再走下面的普通回调
          }
          
          // 处理注册的回调函数
          if (id != null && _pendingRequests.containsKey(id)) {
            debugPrint('找到匹配的回调函数，准备执行');
            try {
              final payload = data['payload'] as Map<String, dynamic>?;
              if (payload != null) {
                _pendingRequests[id]!(payload);
                debugPrint('回调函数执行完成');
              } else {
                debugPrint('Payload为空，无法执行回调函数');
              }
            } catch (e, stackTrace) {
              debugPrint('执行回调函数时发生异常: $e\n堆栈跟踪: $stackTrace');
            } finally {
              _pendingRequests.remove(id);
              debugPrint('已从_pendingRequests中移除ID: $id');
            }
          } else if (id != null) {
            debugPrint('未找到匹配的回调函数');
          } else {
            debugPrint('响应ID为空');
          }
          
          // 处理特定的响应类型
          final Map<String, dynamic>? payload = data['payload'] as Map<String, dynamic>?;
          if (payload != null) {
            _handleResponse(payload);
            
            // 显示响应中的消息内容（如果存在）
            final message = payload['message'] as String?;
            if (message != null && message.isNotEmpty) {
              _addLogMessage('响应消息: $message');
            }
            
            // 特别处理下载完成的消息
            final responseType = payload['type'] as String?;
            if (responseType == 'download_complete') {
              // 检查是否有待处理的下载请求，如果有则处理
              if (id != null && _downloadCallbacks.containsKey(id)) {
                // 这是一个下载请求的响应，调用回调处理
                _downloadCallbacks[id]!(payload);
                // 注意：这里不移除回调，因为可能在其他地方处理
              }
            }
          }
          break;
          
        case 'error':
          // 异步错误广播
          final errorMsg = data['payload']?['message'] as String? ?? 'Unknown error';
          debugPrint('[RX] Error: $errorMsg');
          _addLogMessage('错误: $errorMsg');
          
          // 保存错误消息并通知监听器
          _lastErrorMessage = errorMsg;
          notifyListeners();
          
          // 显示长时间持续的红色错误 Toast 通知
          if (_onError != null) {
            _onError!(errorMsg);
          }
          
          // 收到错误时自动发送stop命令
          sendCommand('stop');
          break;
          
        case 'heartbeat_ack':
          // 清除心跳超时计时器
          _heartbeatTimeoutTimer?.cancel();
          debugPrint('[RX] Heartbeat acknowledged');
          break;
          
        case 'task_log':
          // 处理任务日志消息
          final logMessage = data['payload']?['message'] as String?;
          if (logMessage != null) {
            debugPrint('[RX] Task log: $logMessage');
            _addLogMessage(logMessage);
          }
          
          // 检查是否是任务完成消息
          final status = data['payload']?['status'] as String?;
          if (status == 'completed') {
            debugPrint('[RX] Task completed, stopping task');
            _addLogMessage('任务已完成，正在停止...');
            // 任务完成时自动停止任务
            TaskStatusManager().stopTask();
          }
          break;
          
        default:
          debugPrint('[RX] Unknown message type: $type');
          _addLogMessage('未知消息类型: $type');
      }
    } catch (e, stackTrace) {
      debugPrint('处理消息时发生错误: $e\n堆栈跟踪: $stackTrace');
      _addLogMessage('处理消息时发生错误: $e');
    }
  }

  // 处理响应消息中的具体类型
  void _handleResponse(Map<String, dynamic> payload) {
    // 仅仅打日志，不做任何业务处理，交给外部回调
    final responseType = payload['type'] as String? ?? '';
    switch (responseType) {
      case 'log_folders':
        final folders = payload['folders'] as List<dynamic>?;
        debugPrint('[RX] Received log folders: $folders');
        _addLogMessage('收到日志文件夹列表');
        // 更新日志文件夹列表
        if (folders != null) {
          _logFolders = List<String>.from(folders);
          notifyListeners();
        }
        // 不要在这里 notify 或 return，让原回调继续执行
        break;
      case 'log_content_info':
        final folder = payload['folder'] as String?;
        final totalLines = payload['total_lines'] as int?;
        debugPrint('[RX] Received log content info for folder: $folder, total lines: $totalLines');
        _addLogMessage('收到日志内容信息: $folder ($totalLines 行)');
        // 存储总行数
        if (folder != null && totalLines != null) {
          _logFolderLineCounts[folder] = totalLines;
          // 初始化内容数组
          _logFolderContents[folder] = List.filled(totalLines, {});
          notifyListeners();
          
          // 请求每一行日志
          if (totalLines > 0) {
            for (int i = 1; i <= totalLines; i++) {
              sendCommandWithArgs('get_log_line', [folder, '$i'], null);
            }
          }
        }
        break;
      case 'log_line':
        final folder = payload['folder'] as String?;
        final lineNumber = payload['line_number'] as int?;
        final entry = payload['entry'] as Map<String, dynamic>?;
        debugPrint('[RX] Received log line for folder: $folder, line: $lineNumber');
        _addLogMessage('收到日志行: $folder 第 $lineNumber 行');
        // 存储日志行
        if (folder != null && lineNumber != null && entry != null) {
          if (_logFolderContents.containsKey(folder) && 
              lineNumber > 0 && 
              lineNumber <= _logFolderContents[folder]!.length) {
            // 确保entry中的任何嵌套数据都能被正确处理
            final processedEntry = _processLogEntry(entry);
            _logFolderContents[folder]![lineNumber - 1] = processedEntry;
            notifyListeners();
          }
        }
        break;
      case 'log_content':
        final folder = payload['folder'] as String?;
        final entries = payload['entries'] as List<dynamic>?;
        debugPrint('[RX] Received log content for folder: $folder, entries count: ${entries?.length}');
        _addLogMessage('收到日志内容: $folder (${entries?.length} 条记录)');
        if (folder != null && entries != null) {
          final processedEntries = entries.map((e) => 
            e is Map<String, dynamic> ? _processLogEntry(e) : e
          ).toList();
          _logFolderContents[folder] = List<Map<String, dynamic>>.from(processedEntries);
          notifyListeners();
        }
        break;
      case 'log_address':
        // 处理日志地址响应
        final folder = payload['folder'] as String?;
        final address = payload['address'] as String?;
        debugPrint('[RX] Received log address for folder: $folder, address: $address');
        _addLogMessage('收到日志地址: $folder -> $address');
        // 这种响应类型通常由特定的请求处理，这里只是记录日志
        break;
    }
  }

  // 获取日志文件夹列表
  void getLogFolders() {
    sendCommand('get_log_folders');
  }

  // 获取日志文件夹地址
  Future<Map<String, dynamic>?> getLogAddress(String folderName) async {
    final completer = Completer<Map<String, dynamic>?>();
    final requestId = _uuid.v4();

    debugPrint('注册回调函数，requestId: $requestId');
    
    // 注册一次性响应处理器
    _pendingRequests[requestId] = (payload) {
      debugPrint('执行回调函数，requestId: $requestId');
      if (!completer.isCompleted) {
        debugPrint('完成completer，requestId: $requestId');
        completer.complete(payload);
      } else {
        debugPrint('completer已完成，requestId: $requestId');
      }
    };

    // 发送获取日志地址的命令，参数通过args传递
    sendCommandWithArgs('get_log_address', [folderName], requestId);

    // 超时保护
    return completer.future.timeout(
      const Duration(seconds: 5),
      onTimeout: () {
        debugPrint('getLogAddress超时，移除请求处理器，requestId: $requestId');
        _pendingRequests.remove(requestId);
        debugPrint('getLogAddress timeout');
        return null;
      },
    );
  }

  // 添加获取图片地址的方法
  Future<String?> getImgAddress() async {
    final completer = Completer<String?>();
    final requestId = _uuid.v4();

    debugPrint('注册回调函数，requestId: $requestId');
    
    // 注册一次性响应处理器
    _pendingRequests[requestId] = (payload) {
      debugPrint('执行回调函数，requestId: $requestId');
      if (!completer.isCompleted) {
        final status = payload['status'] as String?;
        if (status == 'success') {
          final address = payload['address'] as String?;
          debugPrint('完成completer，requestId: $requestId, address: $address');
          completer.complete(address);
        } else {
          debugPrint('完成completer，requestId: $requestId, status: $status');
          completer.complete(null);
        }
      } else {
        debugPrint('completer已完成，requestId: $requestId');
      }
    };

    // 发送获取图片地址的命令，无参数
    sendCommandWithArgs('get_img_address', [], requestId);

    // 超时保护
    return completer.future.timeout(
      const Duration(seconds: 5),
      onTimeout: () {
        debugPrint('getImgAddress超时，移除请求处理器，requestId: $requestId');
        _pendingRequests.remove(requestId);
        debugPrint('getImgAddress timeout');
        return null;
      },
    );
  }

  // 处理错误
  void _handleError(Object error) {
    debugPrint('WebSocket错误: $error');
    _addLogMessage('WebSocket错误: $error');
    _isConnected = false;
    _isConnecting = false;
    notifyListeners();
    
    // 出现错误时将任务状态设置为停止
    TaskStatusManager().stopTask();
  }

  // 处理连接断开（被动）
  void _handleDisconnect() {
    final wasConnected = _isConnected;
    final wasConnecting = _isConnecting;

    // 清理当前连接状态
    _isConnected = false;
    _isConnecting = false;
    notifyListeners();

    // 记录断开类型
    if (wasConnected) {
      debugPrint('WebSocket已连接状态下断开');
      _addLogMessage('WebSocket连接已断开');
    } else if (wasConnecting) {
      debugPrint('WebSocket连接过程中断开');
      _addLogMessage('WebSocket连接尝试失败');
    } else {
      debugPrint('WebSocket收到非活跃状态的断开事件（可能为残留回调）');
      _addLogMessage('检测到未激活连接的断开事件');
      // 即使不是活跃连接，也可能需要恢复状态（比如上一轮重连刚失败）
    }

    // 触发连接失败处理逻辑（包括端口轮询或延迟重试）
    _handleConnectionFailure();

    // 更新任务状态为停止
    TaskStatusManager().stopTask();
  }

  // 启动心跳机制
  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 30), (timer) {
      if (_isConnected) {
        _sendHeartbeat();
      }
    });
  }

  // 发送心跳
  void _sendHeartbeat() {
    _heartbeatTimeoutTimer?.cancel();
    _heartbeatTimeoutTimer = Timer(const Duration(seconds: 5), () {
      debugPrint('心跳超时，连接可能已断开');
      _addLogMessage('心跳超时，连接可能已断开');
      _isConnected = false;
      _isConnecting = false;
      notifyListeners();
      _handleDisconnect();
      
      // 心跳超时时将任务状态设置为停止
      TaskStatusManager().stopTask();
    });

    // 只有在真正连接时才发送心跳
    if (_isConnected) {
      _sendMessage({
        'type': 'heartbeat',
      });
    }
  }

  // 发送配置
  void sendConfigurations([void Function()? onComplete]) {
    if (!_isConnected) {
      debugPrint('WebSocket未连接，无法发送配置');
      _addLogMessage('WebSocket未连接，无法发送配置');
      
      // 将发送配置作为一个特殊命令添加到待处理队列
      _pendingCommands.add(_PendingCommand('_sendConfigurations', [], onComplete));
      
      // 如果未连接且未正在连接，则尝试自动连接
      if (!_isConnecting) {
        debugPrint('尝试自动连接WebSocket');
        _addLogMessage('尝试自动连接WebSocket');
        connect();
      }
      
      return;
    }

    final configManager = ConfigManager();
    
    // 构建包含所有配置的数据结构
    final configData = {
      'type': 'configurations',
      'payload': {
        'taskConfigs': configManager.taskConfigs.map((key, value) => MapEntry(key, value.toJson())),
        'teamConfigs': configManager.teamConfigs.map((key, value) => MapEntry(key.toString(), value.toJson())),
        'themePackWeights': configManager.themePackWeights,
      }
    };

    // 发送配置数据
    _sendMessage(configData);
    _addLogMessage('已发送配置数据');
    
    // 执行完成回调
    onComplete?.call();
  }

  // 发送命令
  void sendCommand(String command, [void Function()? onComplete]) {
    if (!_isConnected) {
      debugPrint('WebSocket未连接，无法发送命令: $command');
      _addLogMessage('WebSocket未连接，无法发送命令: $command');
      
      // 将命令添加到待处理队列
      _pendingCommands.add(_PendingCommand(command, [], onComplete));
      
      // 如果未连接且未正在连接，则尝试自动连接
      if (!_isConnecting) {
        debugPrint('尝试自动连接WebSocket');
        _addLogMessage('尝试自动连接WebSocket');
        connect();
      }
      
      return;
    }

    final String id = _uuid.v4();
    debugPrint('[TX] Sending command: $command with id: $id');
    _addLogMessage('发送命令: $command');

    _sendMessage({
      'type': 'request',
      'id': id,
      'payload': {
        'command': command,
        'args': [],  // 即使没有参数，也包含args字段
      },
    });

    // 注册响应处理器
    _pendingRequests[id] = (payload) {
      final String status = payload['status'] as String;
      final String message = payload['message'] as String? ?? '命令执行完成';
      
      if (status == 'success') {
        _addLogMessage(message);
        
        // 根据返回消息更新状态
        switch (message) {
          case 'started':
            // 通知状态变为running
            TaskStatusManager().startTask();
            break;
          case 'paused':
            // 通知状态变为paused
            TaskStatusManager().pauseTask();
            break;
          case 'resumed':
            // 通知状态变为running
            TaskStatusManager().resumeTask();
            break;
          case 'stopped':
            // 通知状态变为idle
            TaskStatusManager().stopTask();
            break;
        }
      } else {
        _addLogMessage('命令执行失败: $message');
        TaskStatusManager().stopTask();
      }
      
      // 执行完成回调
      onComplete?.call();
    };
  }

  // 发送带参数的命令
  void sendCommandWithArgs(String command, List<String> args, [String? id, void Function()? onComplete]) {
    if (!_isConnected) {
      debugPrint('WebSocket未连接，无法发送命令: $command');
      _addLogMessage('WebSocket未连接，无法发送命令: $command');
      
      // 将命令添加到待处理队列
      _pendingCommands.add(_PendingCommand(command, args, onComplete));
      
      // 如果未连接且未正在连接，则尝试自动连接
      if (!_isConnecting) {
        debugPrint('尝试自动连接WebSocket');
        _addLogMessage('尝试自动连接WebSocket');
        connect();
      }
      
      return;
    }

    // 如果没有提供id，则生成一个新的
    final String requestId = id ?? _uuid.v4();
    
    debugPrint('[TX] Sending command: $command with args: $args and id: $requestId');
    logger.d("Sending command: $command with args: $args and id: $requestId");
    _addLogMessage('发送命令: $command');

    _sendMessage({
      'type': 'request',
      'id': requestId,
      'payload': {
        'command': command,
        'args': args,  // 现在参数通过args数组传递
      },
    });

    // 如果没有提供id，说明这是一个普通的命令，需要注册默认的响应处理器
    // 如果提供了id，说明调用者会自己注册响应处理器
    if (id == null) {
      // 注册响应处理器
      _pendingRequests[requestId] = (payload) {
        final String status = payload['status'] as String;
        final String message = payload['message'] as String? ?? '命令执行完成';
        
        if (status == 'success') {
          _addLogMessage(message);
          
          // 根据返回消息更新状态
          switch (message) {
            case 'started':
              // 通知状态变为running
              TaskStatusManager().startTask();
              break;
            case 'paused':
              // 通知状态变为paused
              TaskStatusManager().pauseTask();
              break;
            case 'resumed':
              // 通知状态变为running
              TaskStatusManager().resumeTask();
              break;
            case 'stopped':
              // 通知状态变为idle
              TaskStatusManager().stopTask();
              break;
          }
        } else {
          _addLogMessage('命令执行失败: $message');
          TaskStatusManager().stopTask();
        }
        
        // 执行完成回调
        onComplete?.call();
      };
    }
  }

  // 注册响应处理器（供外部使用）
  void registerResponseHandler(String id, void Function(Map<String, dynamic>) handler) {
    _pendingRequests[id] = handler;
  }

  // 发送消息
  void _sendMessage(Map<String, dynamic> message) {
    try {
      final String jsonMessage = jsonEncode(message);
      _channel?.sink.add(jsonMessage);
    } catch (e) {
      debugPrint('发送消息失败: $e');
      _addLogMessage('发送消息失败: $e');
    }
  }

  // 处理日志条目，特别是包含图片等复杂数据的情况
  Map<String, dynamic> _processLogEntry(Map<String, dynamic> entry) {
    // 这里可以添加额外的处理逻辑来支持特殊类型的数据
    // 目前保持原样返回，但为将来扩展提供基础
    return Map<String, dynamic>.from(entry);
  }

  // 添加日志消息
  void _addLogMessage(String message) {
    _logMessages.add('${DateTime.now().toString().split('.').first}: $message');
    // 限制日志数量，避免占用过多内存
    if (_logMessages.length > 1000) {
      _logMessages.removeRange(0, _logMessages.length - 1000);
    }
    notifyListeners();
  }

  // 清空日志
  void clearLogs() {
    _logMessages.clear();
    notifyListeners();
  }
  
  // 执行待处理命令
  void _executePendingCommands() {
    if (!_isConnected) return;
    
    for (final pendingCommand in _pendingCommands) {
      if (pendingCommand.command == '_sendConfigurations') {
        // 处理特殊命令：发送配置
        sendConfigurations(pendingCommand.onComplete);
      } else if (pendingCommand.args.isEmpty) {
        sendCommand(pendingCommand.command, pendingCommand.onComplete);
      } else {
        sendCommandWithArgs(pendingCommand.command, pendingCommand.args, null, pendingCommand.onComplete);
      }
    }
    
    // 清空待处理命令队列
    _pendingCommands.clear();
  }

  /// 下载最新版本
  Future<void> downloadUpdate({
    required String source,          // "github" or "mirrorchan"
    required String saveDir,         // 绝对目录，例如 /Users/xxx/LALC/update
    String? cdk,                     // 仅 mirrorchan 需要
    required Function(double) onProgress,
    required Function(String) onError,
    required Function(String zipPath) onComplete,
  }) async {
    final command = source == 'github'
        ? 'download_from_github'
        : 'download_from_mirrorchan';
    final args = source == 'github' ? [saveDir] : [saveDir, cdk ?? ''];

    // 生成一次性 id，方便自己收响应
    final reqId = _uuid.v4();

    // 1. 注册常驻回调
    _downloadCallbacks[reqId] = (payload) {
      final status = payload['status'] as String;
      switch (status) {
        case 'progress':
          final p = (payload['progress'] as num).toDouble();
          onProgress(p); // p 0~100
          break;
        case 'success':
          final zipPath = payload['file_path'] as String;
          onComplete(zipPath);
          _downloadCallbacks.remove(reqId); // 下载结束清理
          break;
        case 'cancelled':
          onError('用户已取消');
          _downloadCallbacks.remove(reqId);
          break;
        case 'error':
          onError(payload['message'] as String);
          _downloadCallbacks.remove(reqId);
          break;
      }
    };

    // 2. 发命令（注意：这里不再注册到 _pendingRequests）
    sendCommandWithArgs(command, args, reqId);
  }

  /// 主动取消下载
  void cancelDownload() {
    // 当前下载的 reqId 我们没存，简单粗暴：全部清掉并发送 cancel 命令
    _downloadCallbacks.clear();
    sendCommand('cancel_download');
  }

  /// 开始任务
  void startTask() {
    final taskStatusManager = TaskStatusManager();
    
    if (isConnected) {
      // 发送所有配置
      sendConfigurations();
      
      // 发送开始命令
      taskStatusManager.startTask();
      sendCommand('start');
    } else {
      // 如果未连接，则先尝试连接，连接成功后再发送命令
      sendConfigurations();
      taskStatusManager.startTask();
      sendCommand('start');
    }
  }

  /// 暂停任务
  void pauseTask() {
    final taskStatusManager = TaskStatusManager();
    
    if (taskStatusManager.isRunning && !taskStatusManager.isPaused) {
      taskStatusManager.pauseTask();
      sendCommand('pause');
    }
  }

  /// 恢复任务
  void resumeTask() {
    final taskStatusManager = TaskStatusManager();
    
    if (taskStatusManager.isPaused) {
      taskStatusManager.resumeTask();
      sendCommand('resume');
    }
  }

  /// 停止任务
  void stopTask() {
    final taskStatusManager = TaskStatusManager();
    
    if (taskStatusManager.isRunning || taskStatusManager.isPaused) {
      taskStatusManager.stopTask();
      sendCommand('stop');
    }
  }
}

// 定义待处理命令类
class _PendingCommand {
  final String command;
  final List<String> args;
  final void Function()? onComplete;

  _PendingCommand(this.command, this.args, [this.onComplete]);
}

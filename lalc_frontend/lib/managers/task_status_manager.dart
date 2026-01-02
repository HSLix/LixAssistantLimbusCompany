import 'package:flutter/foundation.dart';

/// 任务状态管理器
class TaskStatusManager with ChangeNotifier {
  static final TaskStatusManager _instance = TaskStatusManager._internal();

  factory TaskStatusManager() => _instance;

  TaskStatusManager._internal();

  /// 任务是否正在运行
  bool _isRunning = false;
  
  /// 任务是否暂停
  bool _isPaused = false;

  bool get isRunning => _isRunning;
  bool get isPaused => _isPaused;

  /// 开始任务
  void startTask() {
    _isRunning = true;
    _isPaused = false;
    notifyListeners();
  }

  /// 暂停任务
  void pauseTask() {
    _isPaused = true;
    notifyListeners();
  }

  /// 恢复任务
  void resumeTask() {
    _isPaused = false;
    notifyListeners();
  }

  /// 停止任务
  void stopTask() {
    _isRunning = false;
    _isPaused = false;
    notifyListeners();
  }
}
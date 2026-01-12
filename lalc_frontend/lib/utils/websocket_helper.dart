import 'package:flutter/foundation.dart';
import '../managers/websocket_manager.dart';

class WebSocketHelper {
  static WebSocketManager? _currentManager;
  static DateTime? _lastConnectionTime;
  
  // 安全获取 WebSocketManager 实例
  static WebSocketManager getManager() {
    final now = DateTime.now();
    
    // 如果短时间内重复获取，直接返回现有实例
    if (_currentManager != null && 
        _lastConnectionTime != null && 
        now.difference(_lastConnectionTime!).inSeconds < 1) {
      return _currentManager!;
    }
    
    _currentManager = WebSocketManager.instance;
    _lastConnectionTime = now;
    
    return _currentManager!;
  }
  
  // 安全连接方法
  static Future<void> safeConnect() async {
    final manager = getManager();
    
    if (!manager.isConnected && !manager.isConnecting) {
      await manager.connect();
    }
  }
  
  // 检查实例是否为单例
  static void debugCheckInstance() {
    debugPrint('WebSocketManager instance identity: ${WebSocketManager.instance}');
  }
}
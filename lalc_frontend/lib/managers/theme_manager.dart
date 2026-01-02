import 'package:flutter/material.dart';
import 'package:lalc_frontend/themes/microsoft_theme.dart';
import 'package:lalc_frontend/managers/config_manager.dart';

/// 负责主题模式的热切换
class ThemeManager with ChangeNotifier {
  static final ThemeManager _instance = ThemeManager._internal();
  factory ThemeManager() => _instance;
  ThemeManager._internal();

  String _mode = 'dark'; // 当前模式，dark / light

  /// 供 UI 层读取当前主题数据
  ThemeData get currentTheme =>
      _mode == 'dark' ? MicrosoftTheme.darkTheme : MicrosoftTheme.lightTheme;

  /// 供 UI 层读取当前模式字符串
  String get currentMode => _mode;

  /// 从外部（ConfigManager）注入保存的值
  void initMode(String? saved) {
    _mode = (saved == 'light') ? 'light' : 'dark';
  }

  /// 一键切换并持久化
  Future<void> toggle() async {
    _mode = _mode == 'dark' ? 'light' : 'dark';
    ConfigManager().userConfig.themeMode = _mode;
    await ConfigManager().saveUserConfig();
    notifyListeners(); // 触发 MaterialApp 重建
  }
}
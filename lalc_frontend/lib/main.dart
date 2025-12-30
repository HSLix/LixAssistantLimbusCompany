import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:sidebarx/sidebarx.dart';
import 'package:lalc_frontend/pages/task_page.dart';
import 'package:lalc_frontend/pages/settings_page.dart';
import 'package:lalc_frontend/pages/work_page.dart';
import 'package:lalc_frontend/pages/team_config_page.dart';
import 'package:lalc_frontend/pages/theme_pack_page.dart';
import 'package:lalc_frontend/pages/about_page.dart';
import 'package:lalc_frontend/pages/log_page.dart';
import 'package:lalc_frontend/config_manager.dart';
import 'package:lalc_frontend/task_status_manager.dart';
import 'package:lalc_frontend/debug_path.dart';
import 'package:lalc_frontend/websocket_manager.dart';
import 'package:window_manager/window_manager.dart';
import 'package:provider/provider.dart';
import 'package:hotkey_manager/hotkey_manager.dart';
import 'package:toastification/toastification.dart';
import 'package:lalc_frontend/themes/microsoft_theme.dart'; // 导入Microsoft主题
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:url_launcher/url_launcher.dart';
import 'generated/l10n.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await windowManager.ensureInitialized();
  
  // 初始化hotkey_manager
  await hotKeyManager.unregisterAll();

  // 初始化配置管理器
  await ConfigManager().init();
  
  // 打印调试信息
  await printAppDocPath();

  WindowOptions windowOptions = WindowOptions(
    minimumSize: Size(800, 666),
    // size: Size(800, 600),
    center: true,
    backgroundColor: Colors.transparent,
    skipTaskbar: false,
    // titleBarStyle: TitleBarStyle.hidden,
    title: "LixAssistantLimbusCompany"
  );

  windowManager.waitUntilReadyToShow(windowOptions, () async {
    await windowManager.show();
    await windowManager.focus();
  });
  
  runApp(MyApp());
}

// 全局导航键，用于在应用的任何地方进行导航
final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

// 全局的SidebarX控制器
final SidebarXController sidebarController = SidebarXController(selectedIndex: 0);

// 全局变量，用于存储TeamConfigPage要显示的队伍索引
int selectedTeamIndexForNavigation = 0;

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  List<HotKey> _registeredHotKeys = [];
  WebSocketManager? _webSocketManager;

  @override
  void initState() {
    super.initState();
    _registerHotKeys();
    // 检查是否启用开机自启
    _checkAutoStart();
  }

  @override
  void dispose() {
    _unregisterHotKeys();
    _webSocketManager?.removeListener(_handleWebSocketUpdate);
    super.dispose();
  }

  // 检查是否启用开机自启配置
  void _checkAutoStart() {
    // 延迟执行以确保context可用
    Future.delayed(Duration(milliseconds: 500), () async {
      try {
        // 检查是否启用了开机自启
        if (ConfigManager().userConfig.autoStart) {
          // 等待一段时间确保所有服务初始化完成
          await Future.delayed(Duration(seconds: 3));
          
          // 检查navigatorKey是否已经初始化并且组件仍处于活动状态
          if (navigatorKey.currentState != null) {
            final context = navigatorKey.currentContext!;
            // 确保组件仍处于活动状态再使用context
            if (context.mounted) {
              // 获取WebSocketManager实例
              final webSocketManager = Provider.of<WebSocketManager>(context, listen: false);
              
              // 调用_startTask方法（实际上是startTask）
              webSocketManager.startTask();
              
              // 切换到工作页面
              sidebarController.selectIndex(1);
              
              debugPrint('Auto-start enabled, task started automatically');
            }
          } else {
            debugPrint('Navigator key not initialized yet for auto-start');
          }
        }
      } catch (e) {
        debugPrint('Error during auto-start check: $e');
      }
    });
  }

  void _handleWebSocketUpdate() {
    // 处理 WebSocket 更新，如果有错误则显示长时间 Toast
  }

  // 打开Discord链接的方法
  Future<void> _launchDiscordUrl() async {
    final Uri url = Uri.parse('https://discord.gg/bVzCuBU4bC');
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    } else {
      throw 'Could not launch $url';
    }
  }

  Future<void> _registerHotKeys() async {
    // 注册全局快捷键
    HotKey hotKeyStart = HotKey(
      key: PhysicalKeyboardKey.keyS,
      modifiers: [HotKeyModifier.control, HotKeyModifier.alt],
      scope: HotKeyScope.system,
    );

    HotKey hotKeyPause = HotKey(
      key: PhysicalKeyboardKey.keyP,
      modifiers: [HotKeyModifier.control, HotKeyModifier.alt],
      scope: HotKeyScope.system,
    );

    HotKey hotKeyResume = HotKey(
      key: PhysicalKeyboardKey.keyR,
      modifiers: [HotKeyModifier.control, HotKeyModifier.alt],
      scope: HotKeyScope.system,
    );

    HotKey hotKeyStop = HotKey(
      key: PhysicalKeyboardKey.keyQ,
      modifiers: [HotKeyModifier.control, HotKeyModifier.alt],
      scope: HotKeyScope.system,
    );

    await hotKeyManager.register(
      hotKeyStart,
      keyDownHandler: (hotKey) {
        _handleHotKey('start');
      },
    );

    await hotKeyManager.register(
      hotKeyPause,
      keyDownHandler: (hotKey) {
        _handleHotKey('pause');
      },
    );

    await hotKeyManager.register(
      hotKeyResume,
      keyDownHandler: (hotKey) {
        _handleHotKey('resume');
      },
    );

    await hotKeyManager.register(
      hotKeyStop,
      keyDownHandler: (hotKey) {
        _handleHotKey('stop');
      },
    );

    setState(() {
      _registeredHotKeys = [hotKeyStart, hotKeyPause, hotKeyResume, hotKeyStop];
    });
  }

  Future<void> _unregisterHotKeys() async {
    for (var hotKey in _registeredHotKeys) {
      await hotKeyManager.unregister(hotKey);
    }
    await hotKeyManager.unregisterAll();
  }

  void _handleHotKey(String command) {
    // 延迟一小段时间确保context可用
    Future.delayed(Duration(milliseconds: 100), () {
      try {
        // 检查navigatorKey是否已经初始化并且组件仍处于活动状态
        if (navigatorKey.currentState != null) {
          final context = navigatorKey.currentContext!;
          // 确保组件仍处于活动状态再使用context
          if (context.mounted) {
            final webSocketManager = Provider.of<WebSocketManager>(context, listen: false);
            final taskStatusManager = Provider.of<TaskStatusManager>(context, listen: false);
            
            switch (command) {
              case 'start':
                webSocketManager.startTask();
                debugPrint('Hotkey triggered: Ctrl+Alt+S (Start)');
                // 使用全局的sidebarController切换到WorkPage (索引为1)
                sidebarController.selectIndex(1);
                // 使用正确的上下文显示toast
                if (context.mounted) {
                  toastification.show(
                    context: context,
                    title: Text(S.of(context).task_started),
                    autoCloseDuration: const Duration(seconds: 2),
                    type: ToastificationType.success,
                    style: ToastificationStyle.flatColored,
                  );
                }
                break;
                
              case 'pause':
                if (taskStatusManager.isRunning && !taskStatusManager.isPaused) {
                  webSocketManager.pauseTask();
                  debugPrint('Hotkey triggered: Ctrl+Alt+P (Pause)');
                  if (context.mounted) {
                    toastification.show(
                      context: context,
                      title: Text(S.of(context).task_paused),
                      autoCloseDuration: const Duration(seconds: 2),
                      type: ToastificationType.info,
                      style: ToastificationStyle.flatColored,
                    );
                  }
                }
                break;
                
              case 'resume':
                if (taskStatusManager.isPaused) {
                  webSocketManager.resumeTask();
                  debugPrint('Hotkey triggered: Ctrl+Alt+R (Resume)');
                  if (context.mounted) {
                    toastification.show(
                      context: context,
                      title: Text(S.of(context).task_resumed),
                      autoCloseDuration: const Duration(seconds: 2),
                      type: ToastificationType.info,
                      style: ToastificationStyle.flatColored,
                    );
                  }
                }
                break;
                
              case 'stop':
                if (taskStatusManager.isRunning || taskStatusManager.isPaused) {
                  webSocketManager.stopTask();
                  debugPrint('Hotkey triggered: Ctrl+Alt+Q (Stop)');
                  if (context.mounted) {
                    toastification.show(
                      context: context,
                      title: Text(S.of(context).task_stopped),
                      autoCloseDuration: const Duration(seconds: 2),
                      type: ToastificationType.error,
                      style: ToastificationStyle.flatColored,
                    );
                  }
                }
                break;
            }
          }
        } else {
          debugPrint('Navigator key not initialized yet');
        }
      } catch (e) {
        debugPrint('Error handling hotkey: $e');
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => TaskStatusManager()),
        ChangeNotifierProvider(create: (_) => WebSocketManager()),
        ChangeNotifierProvider(create: (context) {
          // 创建LanguageManager实例并根据配置设置初始语言
          final languageManager = LanguageManager();
          final userLanguage = ConfigManager().userConfig.language;
          if (userLanguage != null) {
            languageManager.setLocale(Locale(userLanguage));
          }
          return languageManager;
        }),
      ],
      child: Consumer<LanguageManager>(
        builder: (context, languageManager, child) {
          return ToastificationWrapper(
            child: MaterialApp(
              navigatorKey: navigatorKey, // 确保navigatorKey被MaterialApp使用
              debugShowCheckedModeBanner: false,
              // 应用Microsoft主题，替换原有的自定义主题设置
              theme: MicrosoftTheme.darkTheme, // 使用深色Microsoft主题
              localizationsDelegates: const [
                S.delegate, // 确保S.delegate在localizationsDelegates中
                GlobalMaterialLocalizations.delegate,
                GlobalCupertinoLocalizations.delegate,
                GlobalWidgetsLocalizations.delegate
              ],
              supportedLocales: S.delegate.supportedLocales, // 使用S.delegate的supportedLocales
              locale: languageManager.locale, // 使用LanguageManager中的locale
              home: Scaffold(
                body: Builder(
                  builder: (context) {
                    // 在这里使用context来获取本地化文本
                    final localization = S.of(context);
                    return Row(
                      children: [
                        SidebarX(
                          controller: sidebarController,
                          theme: SidebarXTheme(
                            margin: EdgeInsets.zero,
                            width: 60,
                            decoration: const BoxDecoration(
                              color: sidebarBg,
                            ),
                            iconTheme: const IconThemeData(
                              color: white,
                              size: 22,
                            ),
                            textStyle: const TextStyle(
                              color: white,
                              fontSize: 14,
                            ),
                            selectedTextStyle: const TextStyle(
                              color: white,
                              fontWeight: FontWeight.bold,
                            ),
                            selectedIconTheme: const IconThemeData(
                              color: white,
                              size: 24,
                            ),
                            selectedItemDecoration: BoxDecoration(
                              color: msBlue,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            hoverIconTheme: const IconThemeData(
                              color: msBlue,
                              size: 22,
                            ),
                            hoverTextStyle: const TextStyle(
                              color: msBlue,
                              fontSize: 14,
                            ),
                          ),
                          extendedTheme: const SidebarXTheme(
                            width: 150,
                            decoration: BoxDecoration(
                              color: sidebarBg,
                            ),
                          ),
                          items: [
                            SidebarXItem(
                              icon: Icons.task,
                              label: localization.sidebar_task,
                            ),
                            SidebarXItem(
                              icon: Icons.play_circle_fill,
                              label: localization.sidebar_work,
                            ),
                            SidebarXItem(
                              icon: Icons.people,
                              label: localization.sidebar_team_config,
                            ),
                            SidebarXItem(
                              icon: Icons.games,
                              label: localization.sidebar_theme_packs,
                            ),
                            SidebarXItem(
                              icon: Icons.library_books,
                              label: localization.sidebar_logs,
                            ),
                            SidebarXItem(
                              icon: Icons.info,
                              label: localization.sidebar_about,
                            ),
                            SidebarXItem(
                              icon: Icons.settings,
                              label: localization.sidebar_settings,
                            ),
                            // 添加Discord图标
                            SidebarXItem(
                              icon: Icons.discord,
                              label: 'Discord',
                              onTap: () {
                                _launchDiscordUrl();
                              },
                            ),
                          ],
                        ),
                        Expanded(
                          child: Container(
                            color: pageBg,
                            child: Center(
                              child: _ScreensExample(controller: sidebarController),
                            ),
                          ),
                        ),
                      ],
                    );
                  }
                ),
              ),
            ),
          );
        }
      ),
    );
  }
}

class _ScreensExample extends StatelessWidget {
  const _ScreensExample({
    required this.controller,
  });

  final SidebarXController controller;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, child) {
        switch (controller.selectedIndex) {
          case 0:
            return HomePage();
          case 1:
            return WorkPage();
          case 2:
            return TeamConfigPage(initialTeamIndex: selectedTeamIndexForNavigation);
          case 3:
            return ThemePackPage();
          case 4:
            return LogPage();
          case 5:
            return AboutPage();
          case 6:
            return SettingsPage();
          default:
            return Text("404 Not Found");
        }
      },
    );
  }
}

const msBlue = Color(0xFF0078D4); // Microsoft Blue
const msBlueLight = Color(0xFF0A84FF); // Fluent accent
const sidebarBg = Color(0xFF1F1F23); // 微软深灰背景
const pageBg = Color(0xFF2B2B30); // 内容区域背景
const white = Colors.white;
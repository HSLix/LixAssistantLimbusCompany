import 'package:lalc_frontend/main.dart';
import 'package:lalc_frontend/managers/config_manager.dart'; // 添加配置管理器导入
import 'package:lalc_frontend/managers/task_status_manager.dart'; // 添加任务状态管理器导入
import 'package:lalc_frontend/managers/websocket_manager.dart'; // 添加WebSocket管理器导入
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:toastification/toastification.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_markdown/flutter_markdown.dart'; // 添加 Markdown 解析导入
import 'package:url_launcher/url_launcher.dart';
import '../generated/l10n.dart'; // 添加国际化支持
import 'dart:async'; // 添加Timer需要的导入

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage>
    with TickerProviderStateMixin {
  int selectedTaskIndex = -1;
  String selectedInfoPanel = ''; // 添加信息面板选择变量
  String? latestReleaseInfo; // 存储最新的GitHub Release信息
  bool isLoadingReleaseInfo = false; // 标记是否正在加载Release信息
  bool isVersionOutdated = false; // 标记是否有新版本

  // 高亮动画控制器
  late final AnimationController _highlightAnimationController;

  // 公告边框脉冲动画
  late final AnimationController _pulseController;
  late final Animation<Color?> _pulseAnimation;

  // 英文 key 列表 —— 与 ConfigManager、后端、磁盘保持完全一致
  static const List<String> _taskKeys = [
    'Daily Lunacy Purchase',
    'Mail',
    'EXP',
    'Thread',
    'Mirror',
    'Reward',
    'At Last',
  ];
  
  // 教程资源路径常量
  static const String _tutorialAssetPath = 'assets/doc/tutorial.md';

  // 仅 UI 层使用：根据当前语言返回显示名字
  String _taskName(BuildContext ctx, String key) {
    final s = S.of(ctx);
    switch (key) {
      case 'Daily Lunacy Purchase': return s.daily_lunacy_purchase;
      case 'Mail':                  return s.mail;
      case 'EXP':                   return s.exp;
      case 'Thread':                return s.thread;
      case 'Mirror':                return s.mirror;
      case 'Reward':                return s.reward;
      case 'At Last':               return s.at_last;
      default:                      return key;   // 兜底
    }
  }

  // 每个任务的开启状态（Mail 和 Reward 强制开启）
  List<bool> taskEnabled = [true, true, true, true, true, true, true];

  /* ===== 真正检查：已选队伍但"首选饰品流派"为空 ===== */
  List<int> _findTeamsWithEmptyPreferTypes() {
    final configManager = ConfigManager();
    final List<int> emptyList = [];

    for (int i = 0; i < 20; i++) {
      final teamCfg = configManager.teamConfigs[i];
      if (teamCfg == null) continue;

      // 1. 只关心被任务实际引用的队伍
      bool isUsed = false;
      for (final taskEntry in configManager.taskConfigs.entries) {
        final taskCfg = taskEntry.value;
        if (taskCfg.enabled &&
            taskCfg.count > 0 &&
            taskCfg.teams.contains(i + 1)) {
          isUsed = true;
          break;
        }
      }
      if (!isUsed) continue;

      // 2. 关键判断：selectedPreferEgoGiftTypes 为空
      if (teamCfg.selectedPreferEgoGiftTypes.isEmpty) {
        emptyList.add(i + 1);
      }
    }
    return emptyList;
  }


  // 仅 EXP / Thread / Mirror 有次数
  Map<String, int> taskCounts = {
    'EXP': 1,
    'Thread': 1,
    'Mirror': 1,
  };
  
  // 各任务详细配置
  Map<String, dynamic> taskConfigs = {
    'Daily Lunacy Purchase': 0,
    'At Last': 'Do Nothing',
    'EXP': {
      'luxcavationMode': 'Enter',
      'expStage': '08',
    },
    'Thread': {
      'luxcavationMode': 'Enter',
      'threadStage': '50',
    },
    'Mirror': {
      'stopPurchaseGiftMoney': 600,
    },
  };

  // 任务队伍配置：记录每个任务使用的队伍索引列表（+1后的值）
  Map<String, List<int>> taskTeams = {
    'EXP': [],
    'Thread': [],
    'Mirror': [],
  };

  // 文本控制器，用于管理输入框的状态
  Map<String, TextEditingController> textControllers = {};

  late final AnimationController _controller;
  late final Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    _slideAnimation = Tween<Offset>(
      begin: const Offset(1.0, 0),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _controller,
      curve: Curves.easeInOut,
    ));
    
    // 初始化高亮动画控制器
    _highlightAnimationController = AnimationController(
      duration: const Duration(seconds: 1),
      vsync: this,
    );
    
    // 公告脉冲
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    );
    _pulseAnimation = ColorTween(
      begin: Colors.grey[600],   // 平时边框颜色
      end: msBlue,               // 脉冲高亮
    ).animate(_pulseController);
    
    // 从配置管理器加载配置
    _loadConfigFromManager();
    
    // 初始化文本控制器
    _initializeTextControllers();
    
    // 页面初始化时自动获取公告信息
    _fetchLatestReleaseInfo();
    
    // 初始化WebSocket连接
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final webSocketManager = Provider.of<WebSocketManager>(context, listen: false);
      if (!webSocketManager.isConnected && !webSocketManager.isConnecting) {
        webSocketManager.initialize();
      }
    });
  }
  
  // 获取GitHub最新的Release信息
  Future<void> _fetchLatestReleaseInfo() async {
    if (latestReleaseInfo != null || isLoadingReleaseInfo) return;

    setState(() => isLoadingReleaseInfo = true);

    try {
      await _fetchLatestReleaseInfoFromBackup();
      // 首先尝试从GitHub获取
      final response = await http
          .get(Uri.parse(
              'https://api.github.com/repos/HSLix/LixAssistantLimbusCompany/releases/latest'))
          .timeout(const Duration(seconds: 10));

      if (!mounted) return; // ← 关键：网络请求完先检查

      String currentVersion = const String.fromEnvironment('CURRENT_VERSION', defaultValue: 'V0.0.0');

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final releaseInfo = '''

  ${S.of(context).current_version}: $currentVersion
  ${S.of(context).latest_release}: ${data['tag_name']}
  ${S.of(context).published_at}: ${data['published_at']?.toString().split('T')[0] ?? 'Unknown'}

  ${data['body'] ?? 'No description provided'}
  ''';
        
        // 检查是否有新版本
        String latestVersion = data['tag_name'].toString(); // 保持带V的格式
        
        if (isNewerVersion(currentVersion, latestVersion)) {
          setState(() {
            isVersionOutdated = true;
            latestReleaseInfo = releaseInfo;
            isLoadingReleaseInfo = false;
          });
          
          // 检测到新版本，显示提示
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              toastification.show(
                context: context,
                title: Text(S.of(context).new_version_available),
                description: Text(S.of(context).check_announcement_for_details),
                autoCloseDuration: const Duration(seconds: 5),
                type: ToastificationType.info,
                style: ToastificationStyle.flatColored,
              );
            }
          });
        } else {
          setState(() {
            latestReleaseInfo = releaseInfo;
            isLoadingReleaseInfo = false;
          });
        }
        
        if (isVersionOutdated) {
          _pulseController.repeat(reverse: true);   // 开始闪烁
        } else {
          _pulseController.stop();                  // 停止
          _pulseController.value = 0;               // 回到初始色
        }
      } else {
        // GitHub渠道失败，尝试备用渠道
        await _fetchLatestReleaseInfoFromBackup();
      }
    } catch (e) {
      debugPrint('Error fetching release info from GitHub: $e');
      // GitHub渠道失败，尝试备用渠道
      await _fetchLatestReleaseInfoFromBackup();
    }
  }
  
  // 从备用渠道获取最新版本信息
  Future<void> _fetchLatestReleaseInfoFromBackup() async {
    try {
      final response = await http
          .get(Uri.parse('https://mirrorchyan.com/api/resources/LALC/latest'))
          .timeout(const Duration(seconds: 5));

      if (!mounted) return; // ← 关键：网络请求完先检查

      if (response.statusCode == 200) {
        final data = json.decode(response.body)['data'];
        final versionName = data['version_name'] ?? 'Unknown';
        final releaseNote = data['release_note'] ?? 'No description provided';
        String currentVersion = const String.fromEnvironment('CURRENT_VERSION', defaultValue: 'V0.0.0');
        
        final releaseInfo = '''
  ${S.of(context).current_version}: $currentVersion
  ${S.of(context).latest_release}: $versionName
  $releaseNote
  ''';
        
        // 检查是否有新版本
        String latestVersion = versionName; // 保持带V的格式
        
        if (isNewerVersion(currentVersion, latestVersion)) {
          setState(() {
            isVersionOutdated = true;
            latestReleaseInfo = releaseInfo;
            isLoadingReleaseInfo = false;
          });
        } else {
          setState(() {
            latestReleaseInfo = releaseInfo;
            isLoadingReleaseInfo = false;
          });
        }
        
        if (isVersionOutdated) {
          _pulseController.repeat(reverse: true);   // 开始闪烁
        } else {
          _pulseController.stop();                  // 停止
          _pulseController.value = 0;               // 回到初始色
        }
      } else {
        throw Exception('Failed to load release info from backup: ${response.statusCode}');
      }
    } catch (e) {
      debugPrint('Error fetching release info from backup: $e');
      if (!mounted) return; // ← 异常分支也要检查

      setState(() {
        latestReleaseInfo = '获取版本信息失败，请检查网络连接。\n\n'
            '错误详情: $e\n\n'
            '您可以手动访问以下链接查看最新版本信息：\n'
            'https://github.com/HSLix/LixAssistantLimbusCompany/releases/latest \n'
            '或访问备用链接：\n'
            'https://mirrorchyan.com/zh/projects?rid=LALC&channel=stable';
        isLoadingReleaseInfo = false;
      });
    }
  }
  
  // 版本号比较方法（支持V*.*.*格式）
  bool isNewerVersion(String currentVersion, String latestVersion) {
    try {
      // 移除可能的 "v" 前缀
      String cleanCurrent = currentVersion.toLowerCase().replaceAll('v', '');
      String cleanLatest = latestVersion.toLowerCase().replaceAll('v', '');
      
      List<String> currentParts = cleanCurrent.split('.');
      List<String> latestParts = cleanLatest.split('.');
      
      // 确保我们有3个部分来比较
      while (currentParts.length < 3) {
        currentParts.add('0');
      }
      while (latestParts.length < 3) {
        latestParts.add('0');
      }
      
      for (int i = 0; i < 3; i++) {
        // 验证每个部分是否只包含数字
        if (!RegExp(r'^\d+$').hasMatch(currentParts[i])) {
          debugPrint('当前版本号格式错误: ${currentParts[i]}');
          return false;
        }
        if (!RegExp(r'^\d+$').hasMatch(latestParts[i])) {
          debugPrint('最新版本号格式错误: ${latestParts[i]}');
          return false;
        }
        
        int currentNum = int.parse(currentParts[i]);
        int latestNum = int.parse(latestParts[i]);
        
        if (latestNum > currentNum) {
          return true;
        } else if (latestNum < currentNum) {
          return false;
        }
      }
    } catch (e) {
      debugPrint('版本号比较错误: $e');
    }
    
    return false; // 相同或解析失败时返回false
  }

  /// 返回空队伍的任务名（英文 key）
  List<String> _findTasksWithEmptyTeam() {
    final List<String> emptyList = [];
    for (int i = 0; i < _taskKeys.length; i++) {
      final key = _taskKeys[i];
      // 只有 EXP / Thread / Mirror 支持队伍配置
      if (!const {'EXP', 'Thread', 'Mirror'}.contains(key)) continue;
      if (taskEnabled[i] && (taskCounts[key] ?? 0) > 0) {
        final teams = taskTeams[key] ?? [];
        if (teams.isEmpty) emptyList.add(key);
      }
    }
    return emptyList;
  }
  
  // 从配置管理器加载配置
  void _loadConfigFromManager() {
    final configManager = ConfigManager();
    
    // 加载任务启用状态
    for (int i = 0; i < _taskKeys.length; i++) {
      final taskName = _taskKeys[i];
      if (configManager.taskConfigs.containsKey(taskName)) {
        taskEnabled[i] = configManager.taskConfigs[taskName]!.enabled;
        taskCounts[taskName] = configManager.taskConfigs[taskName]!.count;
        // 对于新添加的两个简单配置项，我们需要特别处理
        if (taskName == 'Daily Lunacy Purchase') {
          taskConfigs[taskName] = configManager.taskConfigs[taskName]!.count;
        } else if (taskName == 'At Last') {
          taskConfigs[taskName] = configManager.taskConfigs[taskName]!.params['value'] ?? 'Do Nothing';
        } else {
          taskConfigs[taskName] = Map<String, dynamic>.from(configManager.taskConfigs[taskName]!.params);
          // 为镜像迷宫任务初始化mirror_mode参数，如果不存在的话
          if (taskName == 'Mirror' && !taskConfigs[taskName].containsKey('mirror_mode')) {
            taskConfigs[taskName]['mirror_mode'] = 'normal'; // 默认为普通难度（单值）
          } else if (taskName == 'Mirror' && taskConfigs[taskName]['mirror_mode'] is List) {
            // 如果是旧的列表格式，转换为字符串格式
            List modeList = taskConfigs[taskName]['mirror_mode'];
            if (modeList.contains('normal')) {
              taskConfigs[taskName]['mirror_mode'] = 'normal';
            } else {
              taskConfigs[taskName]['mirror_mode'] = modeList.first as String;
            }
          }
        }
        taskTeams[taskName] = List<int>.from(configManager.taskConfigs[taskName]!.teams);
      }
    }
  }
  
  // 保存配置到管理器
  void _saveConfigToManager() {
    final configManager = ConfigManager();
    
    // 更新任务配置
    for (int i = 0; i < _taskKeys.length; i++) {
      final taskName = _taskKeys[i];
      if (configManager.taskConfigs.containsKey(taskName)) {
        configManager.taskConfigs[taskName]!.enabled = taskEnabled[i];
        configManager.taskConfigs[taskName]!.count = taskCounts[taskName] ?? 1;
        // 对于新添加的两个简单配置项，我们需要特别处理
        if (taskName == 'Daily Lunacy Purchase') {
          configManager.taskConfigs[taskName]!.count = taskConfigs[taskName] ?? 0;
        } else if (taskName == 'At Last') {
          configManager.taskConfigs[taskName]!.params['value'] = taskConfigs[taskName] ?? 'Do Nothing';
        } else {
          configManager.taskConfigs[taskName]!.params = Map<String, dynamic>.from(taskConfigs[taskName] ?? {});
        }
        configManager.taskConfigs[taskName]!.teams = List<int>.from(taskTeams[taskName] ?? []);
      } else {
        // 如果任务不存在，创建新的任务配置
        // 对于新添加的两个简单配置项，我们需要特别处理
        if (taskName == 'Daily Lunacy Purchase') {
          configManager.taskConfigs[taskName] = TaskConfig(
            enabled: taskEnabled[i],
            count: taskConfigs[taskName] ?? 0,
            params: {},
            teams: [],
          );
        } else if (taskName == 'At Last') {
          configManager.taskConfigs[taskName] = TaskConfig(
            enabled: taskEnabled[i],
            count: 1,
            params: {'value': taskConfigs[taskName] ?? 'Do Nothing'},
            teams: [],
          );
        } else {
          // 为镜像迷宫任务初始化mirror_mode参数，如果不存在的话
          Map<String, dynamic> params = Map<String, dynamic>.from(taskConfigs[taskName] ?? {});
          if (taskName == 'Mirror' && !params.containsKey('mirror_mode')) {
            params['mirror_mode'] = 'normal'; // 默认为普通难度（单值）
          } else if (taskName == 'Mirror' && params['mirror_mode'] is List) {
            // 如果是旧的列表格式，转换为字符串格式
            List modeList = params['mirror_mode'];
            if (modeList.contains('normal')) {
              params['mirror_mode'] = 'normal';
            } else {
              params['mirror_mode'] = modeList.first as String;
            }
          }
          configManager.taskConfigs[taskName] = TaskConfig(
            enabled: taskEnabled[i],
            count: taskCounts[taskName] ?? 1,
            params: params,
            teams: List<int>.from(taskTeams[taskName] ?? []),
          );
        }
      }
    }
    
    // 保存到文件
    configManager.saveTaskConfig();
  }
  
  void _initializeTextControllers() {
    // 为Mirror任务的Stop Purchase Gift Money输入框创建控制器
    textControllers['Mirror_stopPurchaseGiftMoney'] = TextEditingController(
      text: taskConfigs['Mirror']['stopPurchaseGiftMoney'].toString()
    );
  }
  
  @override
  void dispose() {
    // 释放所有文本控制器
    for (var controller in textControllers.values) {
      controller.dispose();
    }
    _controller.dispose();
    // 停止并释放高亮动画控制器
    _highlightAnimationController
      ..stop()
      ..dispose();
    _pulseController.dispose();
    super.dispose();
  }

  // 关闭并切换到任务详情面板
  void _switchToTaskDetail(int index) {
    // 如果当前就是同一个任务，直接返回，避免重复动画
    if (selectedTaskIndex == index && selectedInfoPanel.isEmpty) return;

    // 1. 先让旧滑窗反向动画
    _controller.reverse().then((_) {
      // 2. 动画结束后再把状态切到"任务面板"
      if (!mounted) return;
      setState(() {
        selectedInfoPanel = '';   // 清掉信息面板
        selectedTaskIndex = index;// 指定新任务
      });
      // 3. 正向播放新滑窗动画
      _controller.forward(from: 0);
    });
  }
  
  void _openTaskDetail(int index) {
    _switchToTaskDetail(index);
  }

  // 关闭任务详情面板
  void _closeTaskDetail() {
    _controller.reverse().then((_) {
      setState(() {
        selectedTaskIndex = -1;
        selectedInfoPanel = ''; // 同时重置信息面板选择
      });
    });
  }

  void _startAllTasks() {
    // 1. 空队伍检查
    final emptyTasks = _findTasksWithEmptyTeam();
    if (emptyTasks.isNotEmpty) {
      for (final taskKey in emptyTasks) {
        if (mounted) {
          toastification.show(
            context: context,
            title: Text(S.of(context).task_start_error),
            description: Text('${_taskName(context, taskKey)}  '
                '${S.of(context).no_team_configured}'),
            autoCloseDuration: const Duration(seconds: 4),
            type: ToastificationType.error,
            style: ToastificationStyle.flatColored,
          );
        }
      }
      return; // 直接终止，不再往下执行
    }

    /* ===== 新增：已选队伍但饰品风格完全未配置 ===== */
    final emptyPreferTeams = _findTeamsWithEmptyPreferTypes();
    if (emptyPreferTeams.isNotEmpty) {
      for (final teamNo in emptyPreferTeams) {
        if (mounted) {
          toastification.show(
            context: context,
            title: Text(S.of(context).task_start_error),
            description: Text('Team $teamNo  '
                '${S.of(context).no_prefer_ego_type_configured}'), // 文案见下
            autoCloseDuration: const Duration(seconds: 4),
            type: ToastificationType.error,
            style: ToastificationStyle.flatColored,
          );
        }
      }
      return; // 终止
    }
    /* ============================================= */

    // 2. 原有启动逻辑保持不变
    final taskStatusManager = Provider.of<TaskStatusManager>(context, listen: false);
    
    // 获取WebSocket管理器并发送配置和start命令
    final webSocketManager = Provider.of<WebSocketManager>(context, listen: false);
    
    // 检查WebSocket连接状态，如果没有连接则尝试连接
    if (!webSocketManager.isConnected) {
      // 初始化WebSocket连接
      webSocketManager.initialize();
      
      // 在连接建立后再执行后续操作
      // 使用定时器检查连接状态
      Timer.periodic(const Duration(milliseconds: 500), (timer) {
        if (webSocketManager.isConnected) {
          timer.cancel(); // 取消定时器
          
          // 发送所有配置
          webSocketManager.sendConfigurations();
          
          // 发送开始命令
          taskStatusManager.startTask();
          webSocketManager.sendCommand('start', () {
            // 使用全局的sidebarController切换到WorkPage (索引为1)
            sidebarController.selectIndex(1);
            
            if (mounted) {
              toastification.show(
                context: context,
                title: Text(S.of(context).all_tasks_started),
                autoCloseDuration: const Duration(seconds: 3),
                type: ToastificationType.success,
                style: ToastificationStyle.flatColored,
              );
            }
          });
        }
      });
    } else {
      // 发送所有配置
      webSocketManager.sendConfigurations();
      
      // 发送开始命令
      taskStatusManager.startTask();
      webSocketManager.sendCommand('start', () {
        // 使用全局的sidebarController切换到WorkPage (索引为1)
        sidebarController.selectIndex(1);
        
        if (mounted) {
          toastification.show(
            context: context,
            title: Text(S.of(context).all_tasks_started),
            autoCloseDuration: const Duration(seconds: 3),
            type: ToastificationType.success,
            style: ToastificationStyle.flatColored,
          );
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          // -----------------------------
          // 左侧任务列表
          // -----------------------------
          Container(
            width: 350,
            color: Theme.of(context).canvasColor,
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Expanded(
                  child: ListView.builder(
                    itemCount: _taskKeys.length,
                    itemBuilder: (context, index) {
                      final task = _taskKeys[index];

                      // 对于特殊的两个配置项，不显示设置按钮
                      bool isSpecialConfig = (task == 'Daily Lunacy Purchase' || task == 'At Last');

                      return Container(
                        margin: const EdgeInsets.only(bottom: 10),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: Colors.grey[800],
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                // -----------------------
                                // 开关（Mail 和 Reward 强制开启 & 不可切换）
                                // -----------------------
                                Switch(
                                  value: taskEnabled[index],
                                  onChanged: (task == 'Mail' || task == 'Reward' || isSpecialConfig)
                                      ? null // 禁用切换
                                      : (val) {
                                          setState(() {
                                            taskEnabled[index] = val;
                                            // 保存配置
                                            _saveConfigToManager();
                                          });
                                        },
                                  activeTrackColor:(task == 'Mail' || task == 'Reward' || isSpecialConfig)?Colors.grey:msBlue,
                                ),
                                const SizedBox(width: 6),

                                Expanded(
                                  child: Text(
                                    _taskName(context, task), // 使用国际化函数
                                    style: const TextStyle(
                                        color: Colors.white, fontSize: 16),
                                  ),
                                ),

                                IconButton(
                                  icon: const Icon(Icons.settings,
                                      color: Colors.white),
                                  onPressed: () => _openTaskDetail(index),
                                ),
                              ],
                            ),
                            
                            // 为EXP、Thread和Mirror任务添加信息预览
                            if (task == 'EXP' || task == 'Thread' || task == 'Mirror')
                              _buildTaskPreview(task),
                          ],
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 10),
                
                // 移除此处的底部区块构建函数调用，因为已移到右侧内容区域
                const SizedBox(height: 10),
                Consumer<TaskStatusManager>(
                  builder: (context, taskStatusManager, child) {
                    return ElevatedButton(
                      onPressed: !taskStatusManager.isRunning ? _startAllTasks : null,
                      style: ElevatedButton.styleFrom(
                        minimumSize: const Size(double.infinity, 48),
                        backgroundColor: Colors.grey[800],
                      ),
                      child: Text(
                        S.of(context).start,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 22,
                        )
                      ),
                    );
                  }
                ),
              ],
            ),
          ),

          // -----------------------------
          // 右侧内容区域
          // -----------------------------
          Expanded(
            child: Stack(
              children: [
                // 默认提示区域替换为公告、教程和声明区块
                Container(
                  color: Theme.of(context).scaffoldBackgroundColor,
                  alignment: Alignment.center,
                  child: selectedTaskIndex == -1 && selectedInfoPanel.isEmpty
                      ? _buildRightSideContent() // 使用新的构建函数
                      : null,
                ),

                // 滑出的详情面板 (任务设置面板)
                selectedTaskIndex != -1
                    ? SlideTransition(
                        position: _slideAnimation,
                        child: Container(
                          width: double.infinity,
                          color: Colors.grey[900],
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // 顶部标题栏
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    '${_taskName(context, _taskKeys[selectedTaskIndex])} ${S.of(context).team_config_title}', // 使用国际化函数
                                    style: const TextStyle(
                                      fontSize: 20,
                                      fontWeight: FontWeight.bold,
                                      color: Colors.white,
                                    ),
                                  ),
                                  IconButton(
                                    icon: const Icon(Icons.close,
                                        color: Colors.white),
                                    onPressed: _closeTaskDetail,
                                  ),
                                ],
                              ),

                              const SizedBox(height: 20),

                              // 详情内容
                              Expanded(
                                child: Container(
                                  decoration: BoxDecoration(
                                    color: Colors.grey[800],
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  padding: const EdgeInsets.all(16),
                                  child: _buildTaskDetailContent(
                                      _taskKeys[selectedTaskIndex]), // 传递英文key
                                ),
                              ),
                            ],
                          ),
                        ),
                      )
                    : const SizedBox.shrink(),
                    
                // 信息面板 (公告/教程)
                selectedInfoPanel.isNotEmpty
                    ? SlideTransition(
                        position: _slideAnimation,
                        child: Container(
                          width: double.infinity,
                          color: Colors.grey[900],
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // 顶部标题栏
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    selectedInfoPanel,
                                    style: const TextStyle(
                                      fontSize: 20,
                                      fontWeight: FontWeight.bold,
                                      color: Colors.white,
                                    ),
                                  ),
                                  IconButton(
                                    icon: const Icon(Icons.close,
                                        color: Colors.white),
                                    onPressed: _closeTaskDetail,
                                  ),
                                ],
                              ),

                              const SizedBox(height: 20),

                              // 详情内容
                              Expanded(
                                child: Container(
                                  decoration: BoxDecoration(
                                    color: Colors.grey[800],
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  padding: const EdgeInsets.all(16),
                                  child: SingleChildScrollView(
                                    child: _buildInfoContent(selectedInfoPanel),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      )
                    : const SizedBox.shrink(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // --------------------------------------
  // 右侧任务详情内容
  // --------------------------------------
  Widget _buildTaskDetailContent(String taskName) {
    // Mail & Reward：简单文本
    if (taskName == 'Mail') {
      return Center(
        child: Text(
          S.of(context).no_other_configs_mail,
          style: const TextStyle(color: Colors.white70, fontSize: 22),
          textAlign: TextAlign.center,
        ),
      );
    }
    
    if (taskName == 'Reward') {
      return Center(
        child: Text(
          S.of(context).no_other_configs_reward,
          style: const TextStyle(color: Colors.white70, fontSize: 22),
          textAlign: TextAlign.center
          ),
        );
    }
    
    // Daily Lunacy Purchase配置
    if (taskName == 'Daily Lunacy Purchase') {
      int currentValue = taskConfigs[taskName] ?? 0;
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(S.of(context).daily_lunacy_purchase_hint),
            DropdownButton<int>(
              value: currentValue,
              items: List.generate(11, (index) => index)
                  .map<DropdownMenuItem<int>>((int value) {
                return DropdownMenuItem<int>(
                  value: value,
                  child: Text(value.toString(), style: const TextStyle(color: Colors.white, fontSize: 22)),
                );
              }).toList(),
              onChanged: (int? newValue) {
                if (newValue != null) {
                  setState(() {
                    taskConfigs[taskName] = newValue;
                    // 保存配置
                    _saveConfigToManager();
                  });
                }
              },
            ),
          ],
        ),
      );
    }
    
    // At Last配置
    if (taskName == 'At Last') {
      String currentValue = taskConfigs[taskName] ?? 'Do Nothing';
      List<String> options = [
        S.of(context).at_last_do_nothing,
        S.of(context).at_last_close_lalc,
        S.of(context).at_last_close_both,
        S.of(context).at_last_shutdown_pc
      ];
      
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            DropdownButton<String>(
              alignment: Alignment.center,
              value: currentValue,
              items: options.map<DropdownMenuItem<String>>((String value) {
                return DropdownMenuItem<String>(
                  alignment: Alignment.center,
                  value: value,
                  child: Text(value, style: const TextStyle(fontSize:20, color: Colors.white)),
                );
              }).toList(),
              onChanged: (String? newValue) {
                if (newValue != null) {
                  setState(() {
                    taskConfigs[taskName] = newValue;
                    // 保存配置
                    _saveConfigToManager();
                  });
                }
              },
            ),
          ],
        ),
      );
    }

    // EXP / Thread / Mirror：次数设置 + 更多配置选项
    final currentCount = taskCounts[taskName] ?? 0;

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        mainAxisAlignment: MainAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                S.of(context).execution_count,
                style: const TextStyle(color: Colors.white, fontSize: 16),
              ),
              Expanded(
                child:Container()
              ),
              IconButton(
                icon: const Icon(Icons.remove, color: Colors.white),
                onPressed: () {
                  setState(() {
                    if (currentCount > 1) {
                      taskCounts[taskName] = currentCount - 1;
                      // 保存配置
                      _saveConfigToManager();
                    }
                  });
                },
              ),

              // -----------------------
              // 可编辑数字输入框（0~99）
              // -----------------------
              SizedBox(
                width: 40,
                child: TextField(
                  textAlign: TextAlign.center,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: Colors.white, fontSize: 18),
                  controller: TextEditingController(text: currentCount.toString())
                    ..selection = TextSelection.collapsed(
                      offset: currentCount.toString().length,
                    ),
                  onChanged: (value) {
                    setState(() {
                      // 过滤掉所有非数字（双重保险）
                      String filtered = value.replaceAll(RegExp(r'[^0-9]'), '');

                      // 如果过滤后是空的
                      if (filtered.isEmpty) {
                        taskCounts[taskName] = 0;
                        // 保存配置
                        _saveConfigToManager();
                        return;
                      }

                      // 解析安全，永不报错
                      int n = int.tryParse(filtered) ?? 0;

                      // 范围限制 0-99
                      if (n > 99) n = 99;

                      taskCounts[taskName] = n;
                      // 保存配置
                      _saveConfigToManager();
                    });
                  },
                ),
              ),

              IconButton(
                icon: const Icon(Icons.add, color: Colors.white),
                onPressed: () {
                  setState(() {
                    if (currentCount < 99) {
                      taskCounts[taskName] = currentCount + 1;
                      // 保存配置
                      _saveConfigToManager();
                    }
                  });
                },
              ),
            ],
          ),
          
          const SizedBox(height: 5),
          
          // 根据任务类型显示不同的额外配置选项
          if (taskName == 'EXP') 
            _buildEXPConfigOptions()
          else if (taskName == 'Thread') 
            _buildThreadConfigOptions()
          else if (taskName == 'Mirror') 
            _buildMirrorConfigOptions(),
            
          const Divider(),
          
          // 添加任务队伍配置组件
          _buildTaskTeamsConfig(taskName),
        ],
      ),
    );
  }
  
  // EXP任务的额外配置选项
  Widget _buildEXPConfigOptions() {
    final expConfig = taskConfigs['EXP'];
    
    return Column(
      children: [
        // Luxcavation Mode下拉框
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(S.of(context).luxcavation_mode, style: const TextStyle(color: Colors.white, fontSize: 16)),
            DropdownButton<String>(
              value: expConfig['luxcavationMode'] == S.of(context).luxcavation_enter ? 'Enter' : 
                     expConfig['luxcavationMode'] == S.of(context).luxcavation_skip_battle ? 'Skip Battle' : 
                     expConfig['luxcavationMode'],
              items: <String>['Enter', 'Skip Battle']
                  .map<DropdownMenuItem<String>>((String value) {
                String displayText = value == 'Enter' ? S.of(context).luxcavation_enter : 
                                    value == 'Skip Battle' ? S.of(context).luxcavation_skip_battle : 
                                    value;
                return DropdownMenuItem<String>(
                  value: value,
                  child: Text(displayText, style: const TextStyle(color: Colors.white)),
                );
              }).toList(),
              onChanged: (String? newValue) {
                if (newValue != null) {
                  setState(() {
                    taskConfigs['EXP']['luxcavationMode'] = newValue;
                    // 保存配置
                    _saveConfigToManager();
                  });
                }
              },
            ),
          ],
        ),
        // Exp Stage下拉框 (08到01)
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(S.of(context).exp_stage, style: const TextStyle(color: Colors.white, fontSize: 16)),
            DropdownButton<String>(
              value: expConfig['expStage'],
              items: <String>['08', '07', '06', '05', '04', '03', '02', '01']
                  .map<DropdownMenuItem<String>>((String value) {
                return DropdownMenuItem<String>(
                  value: value,
                  child: Text(value, style: const TextStyle(color: Colors.white)),
                );
              }).toList(),
              onChanged: (String? newValue) {
                if (newValue != null) {
                  setState(() {
                    taskConfigs['EXP']['expStage'] = newValue;
                    // 保存配置
                    _saveConfigToManager();
                  });
                }
              },
            ),
          ],
        ),
      ],
    );
  }
  
  // Thread任务的额外配置选项
  Widget _buildThreadConfigOptions() {
    final threadConfig = taskConfigs['Thread'];
    
    return Column(
      children: [
        // Luxcavation Mode下拉框
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(S.of(context).luxcavation_mode, style: const TextStyle(color: Colors.white, fontSize: 16)),
            DropdownButton<String>(
              value: threadConfig['luxcavationMode'] == S.of(context).luxcavation_enter ? 'Enter' : 
                     threadConfig['luxcavationMode'] == S.of(context).luxcavation_skip_battle ? 'Skip Battle' : 
                     threadConfig['luxcavationMode'],
              items: <String>['Enter', 'Skip Battle']
                  .map<DropdownMenuItem<String>>((String value) {
                String displayText = value == 'Enter' ? S.of(context).luxcavation_enter : 
                                    value == 'Skip Battle' ? S.of(context).luxcavation_skip_battle : 
                                    value;
                return DropdownMenuItem<String>(
                  value: value,
                  child: Text(displayText, style: const TextStyle(color: Colors.white)),
                );
              }).toList(),
              onChanged: (String? newValue) {
                if (newValue != null) {
                  setState(() {
                    taskConfigs['Thread']['luxcavationMode'] = newValue;
                    // 保存配置
                    _saveConfigToManager();
                  });
                }
              },
            ),
          ],
        ),
        // Thread Stage下拉框 (50到20)
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(S.of(context).thread_stage, style: const TextStyle(color: Colors.white, fontSize: 16)),
            DropdownButton<String>(
              value: threadConfig['threadStage'],
              items: <String>['50', '40', '30', '20']
                  .map<DropdownMenuItem<String>>((String value) {
                return DropdownMenuItem<String>(
                  value: value,
                  child: Text(value, style: const TextStyle(color: Colors.white)),
                );
              }).toList(),
              onChanged: (String? newValue) {
                if (newValue != null) {
                  setState(() {
                    taskConfigs['Thread']['threadStage'] = newValue;
                    // 保存配置
                    _saveConfigToManager();
                  });
                }
              },
            ),
          ],
        ),
      ],
    );
  }
  
  // Mirror任务的额外配置选项
  Widget _buildMirrorConfigOptions() {
    final TextEditingController? controller = textControllers['Mirror_stopPurchaseGiftMoney'];
    
    if (controller == null) {
      // 如果控制器不存在，则返回空的列
      return const Column();
    }
    
    return Column(
      children: [
        // Stop Purchase Gift Money 数字输入框
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(S.of(context).stop_purchase_gift_money, style: const TextStyle(color: Colors.white, fontSize: 16)),
            SizedBox(
              width: 100,
              child: TextField(
                keyboardType: TextInputType.number,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly // 限制只能输入数字
                ],
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  filled: true,
                  fillColor: Colors.grey[700],
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(5),
                  ),
                ),
                controller: controller,
                onChanged: (value) {
                  // 输入过程中实时更新值
                  if (value.isNotEmpty) {
                    int parsedValue = int.tryParse(value) ?? 600;
                    taskConfigs['Mirror']['stopPurchaseGiftMoney'] = parsedValue;
                    // 保存配置
                    _saveConfigToManager();
                  } else {
                    // 当输入框为空时，设置为默认值
                    taskConfigs['Mirror']['stopPurchaseGiftMoney'] = 600;
                    // 保存配置
                    _saveConfigToManager();
                  }
                },
                onEditingComplete: () {
                  // 当用户完成编辑时检查空值并恢复默认值
                  if (controller.text.isEmpty) {
                    setState(() {
                      taskConfigs['Mirror']['stopPurchaseGiftMoney'] = 600;
                      controller.text = '600';
                      // 保存配置
                      _saveConfigToManager();
                    });
                  }
                },
              ),
            ),
          ],
        ),
        
        const SizedBox(height: 10),
        
        // Mirror难度选择下拉框
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(S.of(context).mirror_difficulty, style: const TextStyle(color: Colors.white, fontSize: 16)),
            DropdownButton<String>(
              value: taskConfigs['Mirror']['mirror_mode'] is List
                  ? (taskConfigs['Mirror']['mirror_mode'] as List).first as String
                  : taskConfigs['Mirror']['mirror_mode'] as String?,
              items: <String>[
                          'normal'
                          // , 'hard'
                          ]
                  .map<DropdownMenuItem<String>>((String value) {
                String displayText = value == 'normal' 
                    ? S.of(context).mirror_difficulty_normal 
                    : S.of(context).mirror_difficulty_hard;
                return DropdownMenuItem<String>(
                  value: value,
                  child: Text(displayText, style: const TextStyle(color: Colors.white)),
                );
              }).toList(),
              onChanged: (String? newValue) {
                if (newValue != null) {
                  setState(() {
                    taskConfigs['Mirror']['mirror_mode'] = newValue;
                    // 保存配置
                    _saveConfigToManager();
                  });
                }
              },
              dropdownColor: Colors.grey[800],
              style: const TextStyle(color: Colors.white),
            ),
          ],
        ),
      ],
    );
  }
  
  // 任务队伍配置组件
  Widget _buildTaskTeamsConfig(String taskName) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(
          S.of(context).task_team_config,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 10),
        
        // 添加队伍按钮
        ElevatedButton.icon(
          onPressed: () => _showAddTeamDialog(taskName),
          icon: const Icon(Icons.add),
          label: Text(S.of(context).add_teams),
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.grey[700],
            foregroundColor: Colors.white,
          ),
        ),
        
        const SizedBox(height: 10),
        
        // 队伍列表
        _buildTaskTeamsList(taskName),
      ],
    );
  }
  
  // 构建任务队伍列表
  Widget _buildTaskTeamsList(String taskName) {
    final teams = taskTeams[taskName] ?? [];
    
    if (teams.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(16.0),
        child: Text(
          S.of(context).no_team_for_now,
          style: const TextStyle(color: Colors.grey, fontSize: 16),
          textAlign: TextAlign.center,
        ),
      );
    }
    
    return ReorderableListView(
      buildDefaultDragHandles: false, // 关闭默认拖拽手柄
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      onReorder: (int oldIndex, int newIndex) {
        setState(() {
          if (newIndex > oldIndex) {
            newIndex -= 1;
          }
          
          final updatedTeams = List<int>.from(teams);
          final item = updatedTeams.removeAt(oldIndex);
          updatedTeams.insert(newIndex, item);
          taskTeams[taskName] = updatedTeams;
          // 保存配置
          _saveConfigToManager();
        });
      },
      children: List.generate(teams.length, (index) {
        final teamNumber = teams[index];
        return _buildTaskTeamItem(taskName, teamNumber, index);
      }),
    );
  }
  
  // 构建单个任务队伍项
  Widget _buildTaskTeamItem(String taskName, int teamNumber, int index) {
    // 从配置管理器获取真实的队伍数据
    final configManager = ConfigManager();
    final teamIndex = teamNumber - 1; // 转换为0-based索引
    final teamConfig = configManager.teamConfigs[teamIndex];
    
    // 获取队伍名称，如果没有设置则使用默认名称
    final actualTeamName = teamConfig?.teamName.isNotEmpty == true 
        ? teamConfig!.teamName 
        : 'Team $teamNumber';
    
    // 获取队伍流派类型
    final actualTeamStyle = teamConfig?.selectedTeamStyleType ?? 'Bleed';
    
    // 计算已选择成员数量
    final actualSelectedMembers = teamConfig?.selectedMembers.length ?? 0;
    
    return Container(
      key: ValueKey('$taskName-$teamNumber'),
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey[800],
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          // 队伍信息和拖拽区域
          Expanded(
            child: Stack(
              children: [
                GestureDetector(
                  onTap: () {
                    // 跳转到TeamConfigPage并选中对应队伍
                    _navigateToTeamConfig(teamNumber);
                  },
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        actualTeamName,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${S.of(context).team_index_label}$teamNumber${S.of(context).member_count_label}$actualSelectedMembers/12${S.of(context).team_style_label}$actualTeamStyle',
                        style: const TextStyle(
                          color: Colors.grey,
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),
                // 添加自定义拖拽区域，仅覆盖信息部分
                Positioned.fill(
                  child: ReorderableDragStartListener(
                    index: index,
                    child: Container(
                      color: Colors.transparent,
                    ),
                  ),
                ),
              ],
            ),
          ),
          
          // 删除按钮
          IconButton(
            icon: const Icon(Icons.delete_forever, color: Colors.red),
            onPressed: () {
              _removeTeamFromTask(taskName, teamNumber);
              // 保存配置
              _saveConfigToManager();
            },
          ),
        ],
      ),
    );
  }
  
  // 导航到TeamConfigPage并选中指定队伍
  void _navigateToTeamConfig(int teamNumber) {
    // 设置要显示的队伍索引（teamNumber是1-20，而索引是0-19）
    selectedTeamIndexForNavigation = teamNumber - 1;
    // 选择侧边栏的TeamConfigPage项
    sidebarController.selectIndex(2); // TeamConfigPage在索引2的位置
  }
  
  // 显示添加队伍对话框
  void _showAddTeamDialog(String taskName) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(S.of(context).select_your_teams),
          content: SizedBox(
            width: double.maxFinite,
            child: _buildAvailableTeamsList(taskName),
          ),
          actions: [
            TextButton(
              onPressed: Navigator.of(context).pop,
              child: Text(S.of(context).cancel_button),
            ),
          ],
        );
      },
    ).then((_) {
      // 当对话框关闭时，强制刷新主页面以更新队伍列表
      setState(() {});
      // 保存配置
      _saveConfigToManager();
    });
  }
  
  // 构建可选队伍列表
  Widget _buildAvailableTeamsList(String taskName) {
    // 从配置管理器获取真实的队伍数据
    final configManager = ConfigManager();
    final List<Map<String, dynamic>> availableTeams = [];
    
    // 遍历所有可能的队伍（0-19）
    for (int i = 0; i < 20; i++) {
      final teamConfig = configManager.teamConfigs[i];
      
      // 获取队伍名称，如果没有设置则使用默认名称
      final teamName = teamConfig?.teamName.isNotEmpty == true 
          ? teamConfig!.teamName 
          : 'Team ${i + 1}';
      
      // 获取队伍流派类型
      final teamStyle = teamConfig?.selectedTeamStyleType ?? 'Bleed';
      
      // 计算已选择成员数量
      final selectedMembers = teamConfig?.selectedMembers.length ?? 0;
      
      availableTeams.add({
        'number': i + 1, // 队伍编号（1-20）
        'name': teamName,
        'style': teamStyle,
        'selectedMembers': selectedMembers,
      });
    }
    
    return StatefulBuilder(
      builder: (BuildContext context, StateSetter setState) {
        return ListView.builder(
          shrinkWrap: true,
          itemCount: availableTeams.length,
          itemBuilder: (context, index) {
            final team = availableTeams[index];
            final teamNumber = team['number'];
            final isSelected = taskTeams[taskName]?.contains(teamNumber) ?? false;
            
            return CheckboxListTile(
              title: Text('${team['name']}'),
              subtitle: Text('Team Index: $teamNumber   Member: ${team['selectedMembers']}/12   Team Style:${team['style']} '),
              value: isSelected,
              onChanged: (bool? value) {
                setState(() {
                  if (value == true) {
                    // 添加队伍到任务
                    final teams = taskTeams[taskName] ?? [];
                    if (!teams.contains(teamNumber)) {
                      teams.add(teamNumber);
                      taskTeams[taskName] = teams;
                      // 保存配置
                      _saveConfigToManager();
                    }
                  } else {
                    // 从任务中移除队伍
                    _removeTeamFromTask(taskName, teamNumber);
                    // 保存配置
                    _saveConfigToManager();
                  }
                });
              },
              checkColor: Colors.white,
              activeColor: msBlue,
            );
          },
        );
      },
    );
  }
  
  // 从任务中移除队伍
  void _removeTeamFromTask(String taskName, int teamNumber) {
    setState(() {
      final teams = taskTeams[taskName] ?? [];
      teams.removeWhere((element) => element == teamNumber);
      taskTeams[taskName] = teams;
      // 保存配置
      _saveConfigToManager();
    });
  }
  
  // 构建任务预览信息
  Widget _buildTaskPreview(String taskName) {
    List<Widget> previewWidgets = [];
    
    // 添加执行次数
    final currentCount = taskCounts[taskName] ?? 0;
    previewWidgets.add(
      Text(
        '${S.of(context).execution_count}: $currentCount',
        style: const TextStyle(
          color: Colors.grey,
          fontSize: 12,
        ),
        overflow: TextOverflow.ellipsis,
      ),
    );
    
    // 对于EXP和Thread任务，添加Luxcavation Mode和Stage信息
    if (taskName == 'EXP' || taskName == 'Thread') {
      final config = taskConfigs[taskName];
      if (config is Map<String, dynamic>) {
        // 添加Luxcavation Mode信息，进行国际化处理
        final luxcavationMode = config['luxcavationMode'] ?? 'Enter';
        String localizedLuxcavationMode = luxcavationMode == 'Enter' 
            ? S.of(context).luxcavation_enter 
            : luxcavationMode == 'Skip Battle' 
                ? S.of(context).luxcavation_skip_battle 
                : luxcavationMode;
        previewWidgets.add(
          Text(
            '${S.of(context).luxcavation_mode}: $localizedLuxcavationMode',
            style: const TextStyle(
              color: Colors.grey,
              fontSize: 12,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        );
        
        // 添加Stage信息
        final stage = config['expStage'] ?? config['threadStage'] ?? 'Unknown';
        final stageLabel = taskName == 'EXP' ? S.of(context).exp_stage : S.of(context).thread_stage;
        previewWidgets.add(
          Text(
            '$stageLabel: $stage',
            style: const TextStyle(
              color: Colors.grey,
              fontSize: 12,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        );
      }
    }
    
    // 对于Mirror任务，添加Stop Purchase Gift Money信息
    if (taskName == 'Mirror') {
      final config = taskConfigs[taskName];
      if (config is Map<String, dynamic>) {
        final stopMoney = config['stopPurchaseGiftMoney'] ?? 600;
        previewWidgets.add(
          Text(
            '${S.of(context).stop_purchase_gift_money}: $stopMoney',
            style: const TextStyle(
              color: Colors.grey,
              fontSize: 12,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        );
      }
    }
    
    // 添加队伍名称信息
    final teams = taskTeams[taskName] ?? [];
    if (teams.isNotEmpty) {
      // 获取队伍名称
      final configManager = ConfigManager();
      List<String> teamNames = [];
      
      for (int teamNumber in teams) {
        final teamIndex = teamNumber - 1; // 转换为0-based索引
        final teamConfig = configManager.teamConfigs[teamIndex];
        
        // 获取队伍名称，如果没有设置则使用默认名称
        final teamName = teamConfig?.teamName.isNotEmpty == true 
            ? teamConfig!.teamName 
            : 'Team $teamNumber';
            
        teamNames.add(teamName);
      }
      
      String teamsText = 'Teams: ${teamNames.join(', ')}';
      previewWidgets.add(
        Text(
          teamsText,
          style: const TextStyle(
            color: Colors.grey,
            fontSize: 12,
          ),
          overflow: TextOverflow.ellipsis,
        ),
      );
    } else {
      previewWidgets.add(
        const Text(
          'Teams: None',
          style: TextStyle(
            color: Colors.grey,
            fontSize: 12,
          ),
          overflow: TextOverflow.ellipsis,
        ),
      );
    }
    
    return Padding(
      padding: const EdgeInsets.only(top: 4.0, left: 8.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: previewWidgets,
      ),
    );
  }
  
  // 打开信息面板（公告或教程）
  void _openInfoPanel(String panelType) {
    setState(() {
      selectedInfoPanel = panelType;
      selectedTaskIndex = -1; // 确保任务面板关闭
    });
    _controller.forward();
  }
  
  // 构建信息面板内容
  Widget _buildInfoContent(String panelType) {
    if (panelType == 'Announcement') {
      // 如果还没有获取过Release信息，则获取一次
      if (latestReleaseInfo == null && !isLoadingReleaseInfo) {
        _fetchLatestReleaseInfo();
      }
      
      String content = latestReleaseInfo ?? 
          (isLoadingReleaseInfo 
              ? '正在获取最新版本信息...' 
              : '无法获取最新版本信息');
              
      // 使用Markdown解析显示公告内容
      return MarkdownBody(
        data: content,
        onTapLink: (text, href, title) {        // ← 新增 onTapLink
          if (href != null) {
            launchUrl(Uri.parse(href));
          }
        },
        styleSheet: MarkdownStyleSheet(
          p: const TextStyle(
            color: Colors.white70,
            fontSize: 16,
            height: 1.5,
          ),
          h1: const TextStyle(
            color: Colors.white,
            fontSize: 24,
            fontWeight: FontWeight.bold,
          ),
          h2: const TextStyle(
            color: Colors.white,
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
          h3: const TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
          a: const TextStyle(      // ← 新增链接样式
            color: Colors.blue,
            decoration: TextDecoration.underline,
          ),
          listBullet: const TextStyle(
            color: Colors.white70,
            fontSize: 16,
          ),
        ),
      );
    }

    if (panelType == 'Tutorial') {
      return FutureBuilder<String>(
        future: DefaultAssetBundle.of(context)
            .loadString(_tutorialAssetPath),          // 读取 assets 里的 md 文件
        builder: (context, snapshot) {
          if (snapshot.hasData) {
            final md = snapshot.data!;

            return MarkdownBody(
              data: md,
              onTapLink: (text, href, title) {
                if (href != null) {
                  launchUrl(Uri.parse(href));
                }
              },
              sizedImageBuilder: (element) {
                final url = element.uri.toString();

                // 只渲染本地图片，参考 about_page 的实现
                if (url.startsWith('/img/')) {
                  return Image.asset('assets/doc$url', fit: BoxFit.contain);
                }

                // 其它图片路径一律跳过（不显示）
                return const SizedBox.shrink();
              },
              styleSheet: MarkdownStyleSheet(
                p: const TextStyle(color: Colors.white70, fontSize: 16, height: 1.5),
                h1: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold),
                h2: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
                listBullet: const TextStyle(color: Colors.white70, fontSize: 16),
              ),
            );
          }
          if (snapshot.hasError) {
            return Center(child: Text('教程加载失败：${snapshot.error}'));
          }
          return const Center(child: CircularProgressIndicator());
        },
      );
    }

    return const Text('Content not found.',
        style: TextStyle(color: Colors.white70, fontSize: 16));
  }
  
  // 构建右侧内容区域
  // 
  Widget _buildRightSideContent() {
  String announcementPreview = '';
  if (latestReleaseInfo != null) {
    announcementPreview = latestReleaseInfo!.length > 100
        ? '${latestReleaseInfo!.substring(0, 100)}...'
        : latestReleaseInfo!;
  } else if (isLoadingReleaseInfo) {
    announcementPreview = '正在获取公告...';
  } else {
    announcementPreview = '点击查看更多';
  }

  return Column(                 // 最外层 Column 纵向撑满
    children: [
      Expanded(                 
        flex: 1,
        child: AnimatedBuilder(          // ← 新增
          animation: _pulseAnimation,
          builder: (context, child) {
            return Container(
              width: double.infinity,
              margin: const EdgeInsets.only(bottom: 8),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12),
                border: isVersionOutdated               // 只有过时才显示脉冲
                    ? Border.all(
                        color: _pulseAnimation.value!,  // 动画颜色
                        width: 3.0,
                      )
                    : Border.all(
                        color: Colors.transparent,      // 平时不画边
                        width: 0,
                      ),
              ),
              child: ElevatedButton(
                onPressed: () => _openInfoPanel('Announcement'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.grey[700],
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(S.of(context).announcement,
                        style: const TextStyle(color: Colors.white, fontSize: 22)),
                    const SizedBox(height: 8),
                    Text(announcementPreview,
                        style: const TextStyle(color: Colors.white70, fontSize: 16),
                        maxLines: 7,
                        overflow: TextOverflow.ellipsis),
                  ],
                ),
              ),
            );
          },
        ),
      ),
      Expanded(                  // 教程 1/3
        flex: 1,
        child: Container(
          width: double.infinity,
          margin: const EdgeInsets.only(bottom: 8),
          child: ElevatedButton(
            onPressed: () => _openInfoPanel('Tutorial'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.grey[700],
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(S.of(context).tutorial,
                    style:
                        const TextStyle(color: Colors.white, fontSize: 22)),
                const SizedBox(height: 8),
                Text(S.of(context).check_how_to_use_app,
                    style: const TextStyle(
                        color: Colors.white70, fontSize: 16)),
              ],
            ),
          ),
        ),
      ),
      Expanded(                
        flex: 1,
        child: GestureDetector(
          onTap: () => sidebarController.selectIndex(5),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: Colors.grey[800],
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(S.of(context).statement,
                    style: TextStyle(color: Colors.white, fontSize: 22)),
                const SizedBox(height: 4),
                const Text(
                  '''
                  LALC is a free open source software, if you paid for LALC from any channel, please refund for your rights.
                  LALC 是一款免费开源软件，仅供学习交流使用，如果你在任何渠道付费购买了 LALC，请为您自身权益退款。
                  Project repository 项目地址：https://github.com/HSLix/LixAssistantLimbusCompany
                  ''',
                  style: TextStyle(color: Colors.white, fontSize: 14),
                  textAlign: TextAlign.center,
                ),
                Text(S.of(context).click_to_see_full_declaration,
                    style: const TextStyle(
                        color: Colors.blue,
                        fontSize: 14,
                        decoration: TextDecoration.underline)),
              ],
            ),
          ),
        ),
      ),
    ],
  );
}
}

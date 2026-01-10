import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:logger/logger.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'dart:io';
import '../../utils/zip_helper.dart';
import 'package:flutter/material.dart';
import 'package:platform_device_id/platform_device_id.dart';
import 'package:flutter/services.dart' show rootBundle;
import '../../utils/encrypt_helper.dart';

/// 语言状态管理类
class LanguageManager with ChangeNotifier {
  static final LanguageManager _instance = LanguageManager._internal();
  
  factory LanguageManager() => _instance;
  
  LanguageManager._internal();
  
  Locale? _locale;
  
  Locale? get locale => _locale;
  
  void setLocale(Locale? locale) {
    _locale = locale;
    notifyListeners();
  }
  
  static LanguageManager get instance => _instance;
}

/// 自定义文件日志输出类
class FileLogOutput extends LogOutput {
  Directory? _logDirectory;
  
  @override
  Future<void> init() async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      final lalcDirectory = Directory(path.join(directory.path, 'LALC'));
      if (!await lalcDirectory.exists()) {
        await lalcDirectory.create(recursive: true);
      }
      _logDirectory = Directory(path.join(lalcDirectory.path, 'logs'));
      if (!await _logDirectory!.exists()) {
        await _logDirectory!.create(recursive: true);
      }
    } catch (e) {
      // 如果无法创建日志目录，使用临时目录
      try {
        final tempDir = Directory.systemTemp;
        _logDirectory = Directory(path.join(tempDir.path, 'LALC_logs'));
        if (!await _logDirectory!.exists()) {
          await _logDirectory!.create(recursive: true);
        }
      } catch (e) {
        // 如果连临时目录都无法创建，则不写入文件日志
        _logDirectory = null;
      }
    }
    await super.init();
  }

  @override
  void output(OutputEvent event) {
    // 只有在日志目录成功初始化后才写入文件
    if (_logDirectory == null) {
      return;
    }
    
    try {
      // 使用日期作为日志文件名
      final DateTime now = DateTime.now();
      final String dateStr = "${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}";
      final File file = File(path.join(_logDirectory!.path, 'app_$dateStr.log'));
      
      // 格式化日志内容
      final StringBuffer sb = StringBuffer();
      for (final line in event.lines) {
        sb.writeln('[${now.toIso8601String()}] $line');
      }
      
      // 写入文件
      file.writeAsStringSync(sb.toString(), mode: FileMode.append);
      
      // 限制日志文件数量，只保留最新的三个文件
      _cleanupOldLogFiles();
    } catch (e) {
      // 如果写入文件失败，至少在控制台输出错误信息
      if (kDebugMode) {
        print('Failed to write log to file: $e');
      }
    }
  }
  
  /// 清理旧的日志文件，只保留最新的三个
  void _cleanupOldLogFiles() {
    try {
      final List<FileSystemEntity> files = _logDirectory!.listSync();
      final List<File> logFiles = files
          .whereType<File>()
          .where((file) => file.path.endsWith('.log'))
          .toList();
      
      // 按修改时间排序， newest first
      logFiles.sort((a, b) => b.lastModifiedSync().compareTo(a.lastModifiedSync()));
      
      // 删除超出三个的旧文件
      if (logFiles.length > 3) {
        for (int i = 3; i < logFiles.length; i++) {
          logFiles[i].deleteSync();
        }
      }
    } catch (e) {
      // 清理过程出错不影响主要功能
      if (kDebugMode) {
        print('Failed to cleanup old log files: $e');
      }
    }
  }
  
  @override
  Future<void> destroy() async {
    await super.destroy();
  }
}

/// 日志记录器实例
final logger = Logger(
  printer: HybridPrinter(PrettyPrinter(methodCount: 0)),
  level: Level.debug,
  output: MultiOutput([
    ConsoleOutput(),
    FileLogOutput(),
  ]),
);

/// 用户配置类
class UserConfig {
  String? language;  // 改为可空类型，null表示跟随系统
  bool autoStart;
  String? mirrorChanCDK;
  String? themeMode; // 添加主题模式配置，'light' 或 'dark'

  UserConfig({
    this.language,  // 默认值改为null，表示跟随系统
    this.autoStart = false,
    this.mirrorChanCDK,
    this.themeMode = "dark", // 默认值为null，表示使用暗色主题
  });

  factory UserConfig.fromJson(Map<String, dynamic> json) {
    return UserConfig(
      language: json['language'] as String?,  // 移除默认值
      autoStart: json['autoStart'] as bool? ?? false,
      mirrorChanCDK: json['mirrorChanCDK'] as String?,
      themeMode: json['themeMode'] as String?, // 添加主题模式
    );
  }

  Map<String, dynamic> toJson() => {
        'language': language,
        'autoStart': autoStart,
        'mirrorChanCDK': mirrorChanCDK,
        'themeMode': themeMode,
      };
}

/// 任务配置类
class TaskConfig {
  bool enabled;
  int count;
  Map<String, dynamic> params;
  List<int> teams;

  TaskConfig({
    required this.enabled,
    required this.count,
    required this.params,
    required this.teams,
  });

  factory TaskConfig.fromJson(Map<String, dynamic> json) {
    return TaskConfig(
      enabled: json['enabled'] as bool? ?? false,
      count: json['count'] as int? ?? 1,
      params: Map<String, dynamic>.from(json['params'] as Map? ?? {}),
      teams: List<int>.from(json['teams'] as List? ?? []),
    );
  }

  Map<String, dynamic> toJson() => {
        'enabled': enabled,
        'count': count,
        'params': params,
        'teams': teams,
      };
}

/// 队伍配置类
class TeamConfig {
  List<String> selectedMembers;
  bool shopHealAll;
  String selectedTeamStyleType;
  List<String> selectedPreferEgoGiftTypes;
  List<String> selectedAccessoryTypes;
  Map<String, String> giftName2Status;
  Map<String, bool> skillReplacementEnabled;
  Map<String, List<List<int>>> skillReplacementOrders;
  String teamName; // 添加队伍名称字段
  List<int> initialEgoGifts; // 添加初始饰品配置字段
  Map<String, bool> mirrorStarEnabled; // 添加镜像星光启用状态
  Map<String, String> mirrorStarValues; // 添加镜像星光值

  TeamConfig({
    required this.selectedMembers,
    required this.shopHealAll,
    required this.selectedTeamStyleType,
    required this.selectedPreferEgoGiftTypes,
    required this.selectedAccessoryTypes,
    required this.giftName2Status,
    required this.skillReplacementEnabled,
    required this.skillReplacementOrders,
    this.teamName = '', // 默认为空字符串
    this.initialEgoGifts = const [1, 2, 3], // 默认为[1, 2, 3]
    this.mirrorStarEnabled = const {}, // 默认为空映射
    this.mirrorStarValues = const {}, // 默认为空映射
  });

  factory TeamConfig.fromJson(Map<String, dynamic> json) {
    return TeamConfig(
      selectedMembers: List<String>.from(json['selectedMembers'] as List? ?? []),
      shopHealAll: json['shopHealAll'] as bool? ?? false,
      selectedTeamStyleType: json['selectedTeamStyleType'] as String? ?? 'Bleed',
      selectedPreferEgoGiftTypes:
          List<String>.from(json['selectedPreferEgoGiftTypes'] as List? ?? []),
      selectedAccessoryTypes:
          List<String>.from(json['selectedAccessoryTypes'] as List? ?? []),
      giftName2Status: Map<String, String>.from(json['giftName2Status'] as Map? ?? {}),
      skillReplacementEnabled:
          Map<String, bool>.from(json['skillReplacementEnabled'] as Map? ?? {}),
      skillReplacementOrders: (json['skillReplacementOrders'] as Map?)
              ?.map((key, value) => MapEntry(
                  key,
                  (value as List)
                      .map((pair) => List<int>.from(pair as List))
                      .toList())) ??
          {},
      teamName: json['teamName'] as String? ?? '', // 从JSON加载队伍名称
      initialEgoGifts: List<int>.from(json['initialEgoGifts'] as List? ?? [1, 2, 3]), // 从JSON加载初始饰品配置
      mirrorStarEnabled: Map<String, bool>.from(json['mirrorStarEnabled'] as Map? ?? {}), // 从JSON加载镜像星光启用状态
      mirrorStarValues: Map<String, String>.from(json['mirrorStarValues'] as Map? ?? {}), // 从JSON加载镜像星光值
    );
  }

  Map<String, dynamic> toJson() => {
        'selectedMembers': selectedMembers,
        'shopHealAll': shopHealAll,
        'selectedTeamStyleType': selectedTeamStyleType,
        'selectedPreferEgoGiftTypes': selectedPreferEgoGiftTypes,
        'selectedAccessoryTypes': selectedAccessoryTypes,
        'giftName2Status': giftName2Status,
        'skillReplacementEnabled': skillReplacementEnabled,
        'skillReplacementOrders': skillReplacementOrders,
        'teamName': teamName, // 将队伍名称保存到JSON
        'initialEgoGifts': initialEgoGifts, // 将初始饰品配置保存到JSON
        'mirrorStarEnabled': mirrorStarEnabled, // 将镜像星光启用状态保存到JSON
        'mirrorStarValues': mirrorStarValues, // 将镜像星光值保存到JSON
      };
}

/// 全局配置管理器
class ConfigManager {
  static final ConfigManager _instance = ConfigManager._internal();

  factory ConfigManager() => _instance;

  ConfigManager._internal();

  /// 配置数据
  Map<String, TaskConfig> taskConfigs = {};
  Map<int, TeamConfig> teamConfigs = {};
  Map<String, int> themePackWeights = {};
  UserConfig userConfig = UserConfig();
  
  /// 获取已加密的 CDK，与磁盘保持一致，网络层直接调用
  String? get encryptedMirrorChanCDK => userConfig.mirrorChanCDK;

  /// 公共加密方法，供外部调用加密CDK
  Future<String> encryptCDK(String cdk) async {
    return await _encryptCDK(cdk);
  }

  /// 配置文件路径
  late File _taskConfigFile;
  late File _teamConfigFile;
  late File _themePackConfigFile;
  late File _userConfigFile;
  late Directory _logsDirectory;
  late Directory _configsDirectory; // 配置集目录

  /// 初始化配置管理器
  Future<void> init() async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      
      // 确保目录存在
      if (!await directory.exists()) {
        await directory.create(recursive: true);
      }
      
      // 创建lalc子目录
      final lalcDirectory = Directory(path.join(directory.path, 'LALC'));
      if (!await lalcDirectory.exists()) {
        await lalcDirectory.create(recursive: true);
      }
      
      // 创建logs子目录
      _logsDirectory = Directory(path.join(lalcDirectory.path, 'logs'));
      if (!await _logsDirectory.exists()) {
        await _logsDirectory.create(recursive: true);
      }
      
      // 创建configs子目录用于存储配置集
      _configsDirectory = Directory(path.join(lalcDirectory.path, 'configs'));
      if (!await _configsDirectory.exists()) {
        await _configsDirectory.create(recursive: true);
      }
      
      _taskConfigFile = File(path.join(lalcDirectory.path, 'task_config.json'));
      _teamConfigFile = File(path.join(lalcDirectory.path, 'team_config.json'));
      _themePackConfigFile = File(path.join(lalcDirectory.path, 'theme_pack_config.json'));
      _userConfigFile = File(path.join(lalcDirectory.path, 'user_config.json'));

      // 检查是否有luyaoqi_config配置集，如果没有则从assets解压
      await _checkAndExtractDefaultConfig();

      await loadTaskConfig();
      await loadTeamConfig();
      await loadThemePackConfig();
      await loadUserConfig();
      
      logger.d('配置管理器初始化成功');
    } catch (e) {
      logger.e('配置管理器初始化失败: $e');
    }
  }
  
  /// 检查并解压默认配置
  Future<void> _checkAndExtractDefaultConfig() async {
    final luyaoqiConfigDir = Directory(path.join(_configsDirectory.path, 'luyaoqi_config'));
    final luyaoqiConfigZip = File(path.join(_configsDirectory.path, 'luyaoqi_config.zip'));
    
    // 检查是否已存在luyaoqi_config配置
    if (await luyaoqiConfigDir.exists() || await luyaoqiConfigZip.exists()) {
      logger.d('luyaoqi_config已存在，跳过解压');
      return;
    }
    
    try {
      logger.d('未找到luyaoqi_config，开始从assets复制...');
      
      // 从assets读取luyaoqi_config.zip
      final byteData = await rootBundle.load('assets/luyaoqi_config.zip');
      final bytes = byteData.buffer.asUint8List();
      
      // 将ZIP文件直接复制到configs目录
      await luyaoqiConfigZip.writeAsBytes(bytes);
      
      logger.d('luyaoqi_config.zip已复制到configs目录');
    } catch (e) {
      logger.e('复制luyaoqi_config.zip失败: $e');
      // 如果是找不到资源的错误，可能是assets中没有这个文件
      if (e is FlutterError || e.toString().contains('Unable to load asset')) {
        logger.w('assets/luyaoqi_config.zip 不存在于资源中');
      }
    }
  }

  /// 加载任务配置（公开方法）
  Future<void> loadTaskConfig() async {
    await _loadTaskConfig();
  }

  /// 加载队伍配置（公开方法）
  Future<void> loadTeamConfig() async {
    await _loadTeamConfig();
  }

  /// 加载主题包配置（公开方法）
  Future<void> loadThemePackConfig() async {
    await _loadThemePackConfig();
  }

  /// 加载用户配置（公开方法）
  Future<void> loadUserConfig() async {
    await _loadUserConfig();
  }

  /// 加载任务配置
  Future<void> _loadTaskConfig() async {
    if (await _taskConfigFile.exists()) {
      try {
        final content = await _taskConfigFile.readAsString();
        final jsonMap = json.decode(content) as Map<String, dynamic>;
        taskConfigs = jsonMap.map((key, value) {
          return MapEntry(key, TaskConfig.fromJson(value as Map<String, dynamic>));
        });
        logger.d('任务配置加载成功');
      } catch (e) {
        logger.e('加载任务配置失败: $e');
        _createDefaultTaskConfig();
      }
    } else {
      _createDefaultTaskConfig();
    }
  }

  /// 创建默认任务配置
  void _createDefaultTaskConfig() {
    taskConfigs = {
      'Mail': TaskConfig(
        enabled: true,
        count: 1,
        params: {},
        teams: [],
      ),
      'EXP': TaskConfig(
        enabled: true,
        count: 1,
        params: {
          'luxcavationMode': 'Enter',
          'expStage': '08',
        },
        teams: [],
      ),
      'Thread': TaskConfig(
        enabled: true,
        count: 1,
        params: {
          'luxcavationMode': 'Enter',
          'threadStage': '50',
        },
        teams: [],
      ),
      'Mirror': TaskConfig(
        enabled: true,
        count: 1,
        params: {
          'stopPurchaseGiftMoney': 600,
          'mirror_mode': 'normal',  // 默认仍为normal
          'battle_fail_handle': 'continue_next_team',
          'enable_fuse_ego_gifts': true,
          'enable_replace_skill_purchase_ego_gifts': true,
          'enable_enhance_ego_gifts': true,
          'accept_reward': true,
        },
        teams: [],
      ),
      'Reward': TaskConfig(
        enabled: true,
        count: 1,
        params: {},
        teams: [],
      ),
    };
    saveTaskConfig();
  }

  /// 保存任务配置
  Future<void> saveTaskConfig() async {
    try {
      final jsonMap = taskConfigs.map((key, value) => MapEntry(key, value.toJson()));
      await _taskConfigFile.writeAsString(JsonEncoder.withIndent('  ').convert(jsonMap));
      logger.d('任务配置保存成功');
    } catch (e) {
      logger.e('保存任务配置失败: $e');
    }
  }

  /// 加载队伍配置
  Future<void> _loadTeamConfig() async {
    if (await _teamConfigFile.exists()) {
      try {
        final content = await _teamConfigFile.readAsString();
        final jsonMap = json.decode(content) as Map<String, dynamic>;
        teamConfigs = jsonMap.map((key, value) {
          return MapEntry(int.parse(key), TeamConfig.fromJson(value as Map<String, dynamic>));
        });
        logger.d('队伍配置加载成功');
      } catch (e) {
        logger.e('加载队伍配置失败: $e');
        _createDefaultTeamConfig();
      }
    } else {
      _createDefaultTeamConfig();
    }
  }

  /// 创建默认队伍配置
  void _createDefaultTeamConfig() {
    const sinnerNames = [
      "Yi Sang", "Faust", "Gregor", "Don Quixote", "Ishmael", "Rodion", "Ryoshu", 
      "Meursault", "Hong Lu", "Heathcliff", "Sinclair", "Outis"
    ];

    teamConfigs = {};
    for (int i = 0; i < 20; i++) {
      teamConfigs[i] = TeamConfig(
        teamName: "Team ${i+1}",
        selectedMembers: [],
        shopHealAll: false,
        selectedTeamStyleType: 'Bleed',
        selectedPreferEgoGiftTypes: [],
        selectedAccessoryTypes: [],
        giftName2Status: {
          
        },
        skillReplacementEnabled: {
          for (var name in sinnerNames) name: false,
        },
        skillReplacementOrders: {
          for (var name in sinnerNames)
            name: [
              [1, 2],
              [2, 3],
              [1, 3]
            ],
        },
      );
    }
    saveTeamConfig();
  }

  /// 保存队伍配置
  Future<void> saveTeamConfig() async {
    try {
      final jsonMap = teamConfigs.map((key, value) => MapEntry(key.toString(), value.toJson()));
      await _teamConfigFile.writeAsString(JsonEncoder.withIndent('  ').convert(jsonMap));
      logger.d('队伍配置保存成功');
    } catch (e) {
      logger.e('保存队伍配置失败: $e');
    }
  }

  /// 加载主题包配置
  Future<void> _loadThemePackConfig() async {
    if (await _themePackConfigFile.exists()) {
      try {
        final content = await _themePackConfigFile.readAsString();
        final jsonMap = json.decode(content) as Map<String, dynamic>;
        themePackWeights = jsonMap.map((key, value) => MapEntry(key, value as int));
        logger.d('主题包配置加载成功');
      } catch (e) {
        logger.e('加载主题包配置失败: $e');
        _createDefaultThemePackConfig();
      }
    } else {
      _createDefaultThemePackConfig();
    }
  }

  /// 创建默认主题包配置
  void _createDefaultThemePackConfig() {
    themePackWeights = {};
    saveThemePackConfig();
  }

  /// 保存主题包配置
  Future<void> saveThemePackConfig() async {
    try {
      await _themePackConfigFile.writeAsString(JsonEncoder.withIndent('  ').convert(themePackWeights));
      logger.d('主题包配置保存成功');
    } catch (e) {
      logger.e('保存主题包配置失败: $e');
    }
  }
  
  /// 加载用户配置
  Future<void> _loadUserConfig() async {
    if (await _userConfigFile.exists()) {
      try {
        final content = await _userConfigFile.readAsString();
        final jsonMap = json.decode(content) as Map<String, dynamic>;
        userConfig = UserConfig.fromJson(jsonMap);
        
        // 保持CDK为加密状态，不自动解密
        // 如果有加密的CDK，保留原样
        // if (userConfig.mirrorChanCDK != null && userConfig.mirrorChanCDK!.isNotEmpty) {
        //   try {
        //     userConfig.mirrorChanCDK = await _decryptCDK(userConfig.mirrorChanCDK!);
        //   } catch (e) {
        //     logger.e('解密CDK失败: $e');
        //     // 解密失败时，将CDK设置为null以避免后续使用错误的数据
        //     userConfig.mirrorChanCDK = null;
        //   }
        // }
        
        logger.d('用户配置加载成功');
      } catch (e) {
        logger.e('加载用户配置失败: $e');
        userConfig = UserConfig();
        saveUserConfig();
      }
    } else {
      userConfig = UserConfig();
      saveUserConfig();
    }
  }

  /// 保存用户配置
  Future<void> saveUserConfig() async {
    try {
      // 检查CDK是否已经是加密格式（包含冒号分隔符）
      String? finalCDK = userConfig.mirrorChanCDK;
      
      // 创建临时配置用于保存，避免修改内存中的原始数据
      final tempConfig = UserConfig(
        language: userConfig.language,
        autoStart: userConfig.autoStart,
        mirrorChanCDK: finalCDK,  // 直接使用内存中的值，因为已经是加密的
      );
      
      await _userConfigFile.writeAsString(JsonEncoder.withIndent('  ').convert(tempConfig.toJson()));
      logger.d('用户配置保存成功');
    } catch (e) {
      logger.e('保存用户配置失败: $e');
    }
  }
  
  /// 加密CDK
  Future<String> _encryptCDK(String cdk) async {
    try {
      return await EncryptHelper.encrypt(cdk);
    } catch (e) {
      logger.e('CDK加密失败: $e');
      rethrow; // 直接上报错误
    }
  }
  
  /// 解密CDK
  Future<String> _decryptCDK(String encryptedData) async {
    try {
      return await EncryptHelper.decrypt(encryptedData);
    } catch (e) {
      logger.e('CDK解密失败: $e');
      rethrow; // 直接上报错误
    }
  }
  
  /// 仅供 UI 展示用：若解密失败则返回原文，避免弹窗显示空白
  Future<String> decryptCDKIfPossible(String encrypted) async {
    if (encrypted.isEmpty) return '';
    try {
      return await _decryptCDK(encrypted);
    } catch (e) {
      logger.w('UI展示解密失败，返回原文: $e');
      return encrypted; // 兼容旧数据或异常场景
    }
  }
  
  /// 复制队伍配置
  void copyTeamConfig(int sourceIndex, int targetIndex) {
    if (teamConfigs.containsKey(sourceIndex)) {
      // 创建源队伍配置的深拷贝
      final sourceConfig = teamConfigs[sourceIndex]!;
      final copiedConfig = TeamConfig(
        selectedMembers: List<String>.from(sourceConfig.selectedMembers),
        shopHealAll: sourceConfig.shopHealAll,
        selectedTeamStyleType: sourceConfig.selectedTeamStyleType,
        selectedPreferEgoGiftTypes: List<String>.from(sourceConfig.selectedPreferEgoGiftTypes),
        selectedAccessoryTypes: List<String>.from(sourceConfig.selectedAccessoryTypes),
        giftName2Status: Map<String, String>.from(sourceConfig.giftName2Status),
        skillReplacementEnabled: Map<String, bool>.from(sourceConfig.skillReplacementEnabled),
        skillReplacementOrders: sourceConfig.skillReplacementOrders.map(
          (key, value) => MapEntry(key, value.map((list) => List<int>.from(list)).toList()),
        ),
        teamName: sourceConfig.teamName,
        initialEgoGifts: List<int>.from(sourceConfig.initialEgoGifts),
        mirrorStarEnabled: Map<String, bool>.from(sourceConfig.mirrorStarEnabled),
        mirrorStarValues: Map<String, String>.from(sourceConfig.mirrorStarValues),
      );
      
      // 将复制的配置赋给目标队伍
      teamConfigs[targetIndex] = copiedConfig;
      
      logger.d('队伍配置从 $sourceIndex 复制到 $targetIndex 成功');
    } else {
      logger.e('源队伍配置不存在: $sourceIndex');
    }
  }
  
  /// 获取日志目录
  Directory getLogsDirectory() {
    return _logsDirectory;
  }
  
  /// 获取配置集目录
  Directory getConfigsDirectory() {
    return _configsDirectory;
  }

  /// 导出配置集为ZIP文件
  Future<void> exportConfigSet(String setName) async {
    try {
      final configSetDir = Directory(path.join(_configsDirectory.path, setName));
      
      if (await configSetDir.exists()) {
        // 先创建ZIP文件
        final zipFilePath = path.join(_configsDirectory.path, '$setName.zip');
        await ZipHelper.zipDir(srcDir: configSetDir.path, dstZip: zipFilePath);
        
        // 成功创建ZIP后删除原目录
        await configSetDir.delete(recursive: true);
        logger.d('配置集 $setName 导出为ZIP文件成功');
      } else {
        logger.w('配置集 $setName 不存在');
      }
    } catch (e) {
      logger.e('导出配置集 $setName 为ZIP文件失败: $e');
    }
  }
  
  /// 保存当前配置为配置集
  Future<void> saveCurrentConfigAsSet(String setName) async {
    try {
      // 创建配置集目录
      final configSetDir = Directory(path.join(_configsDirectory.path, setName));
      if (await configSetDir.exists()) {
        // 如果目录已存在，先删除
        await configSetDir.delete(recursive: true);
      }
      await configSetDir.create(recursive: true);
      
      // 复制当前配置文件到配置集目录
      final taskConfigFile = File(path.join(configSetDir.path, 'task_config.json'));
      final teamConfigFile = File(path.join(configSetDir.path, 'team_config.json'));
      final themePackConfigFile = File(path.join(configSetDir.path, 'theme_pack_config.json'));
      final userConfigFile = File(path.join(configSetDir.path, 'user_config.json'));
      
      await taskConfigFile.writeAsBytes(await _taskConfigFile.readAsBytes());
      await teamConfigFile.writeAsBytes(await _teamConfigFile.readAsBytes());
      await themePackConfigFile.writeAsBytes(await _themePackConfigFile.readAsBytes());
      
      // 用户配置需要特殊处理，清除CDK信息
      final userConfigContent = await _userConfigFile.readAsString();
      final userConfigJson = json.decode(userConfigContent) as Map<String, dynamic>;
      userConfigJson['mirrorChanCDK'] = null;
      await userConfigFile.writeAsString(JsonEncoder.withIndent('  ').convert(userConfigJson));
      
      logger.d('当前配置已保存为配置集 $setName');
      
      // 然后将其压缩为ZIP文件并删除目录
      await exportConfigSet(setName);
    } catch (e) {
      logger.e('保存当前配置为配置集 $setName 失败: $e');
    }
  }
  
  /// 获取所有可用的配置集名称
  Future<List<String>> getAvailableConfigSets() async {
    try {
      final List<FileSystemEntity> entities = _configsDirectory.listSync();
      final List<String> configSets = [];
      
      for (final entity in entities) {
        if (entity is Directory) {
          configSets.add(entity.uri.pathSegments.where((segment) => segment.isNotEmpty).last);
        } else if (entity is File && entity.path.endsWith('.zip')) {
          // 移除.zip扩展名
          final basename = path.basename(entity.path);
          final setName = basename.substring(0, basename.length - 4);
          configSets.add(setName);
        }
      }
      
      return configSets;
    } catch (e) {
      logger.e('获取配置集列表失败: $e');
      return [];
    }
  }
  
  /// 导入配置集
  Future<void> importConfigSet(String setName, {bool importTasks = true, bool importTeams = true, 
      bool importThemePacks = true, bool importUserConfig = true, Function(String)? onProgress}) async {
    try {
      onProgress?.call('开始导入配置集 $setName...');
      
      // 检查ZIP文件是否存在
      final configSetZipFile = File(path.join(_configsDirectory.path, '$setName.zip'));
      final configSetDirectory = Directory(path.join(_configsDirectory.path, setName));
      
      if (await configSetZipFile.exists()) {
        // 解压ZIP文件到临时目录
        final tempDir = await getTemporaryDirectory();
        final tempUnzipDir = Directory(path.join(tempDir.path, 'unzipped_config_$setName'));
        await tempUnzipDir.create(recursive: true);
        
        onProgress?.call('正在解压配置集...');
        await ZipHelper.unzipTo(zipFile: configSetZipFile.path, dstDir: tempUnzipDir.path);
        
        // 导入各个配置文件（根据选项）
        int completedSteps = 0;
        int totalSteps = [importTasks, importTeams, importThemePacks, importUserConfig].where((b) => b).length;
        
        if (importTasks) {
          final sourceTaskConfigFile = File(path.join(tempUnzipDir.path, 'task_config.json'));
          if (await sourceTaskConfigFile.exists()) {
            await _taskConfigFile.writeAsString(await sourceTaskConfigFile.readAsString());
            await _loadTaskConfig(); // 重新加载
          }
          completedSteps++;
          onProgress?.call('任务配置已导入 ($completedSteps/$totalSteps)');
        }
        
        if (importTeams) {
          final sourceTeamConfigFile = File(path.join(tempUnzipDir.path, 'team_config.json'));
          if (await sourceTeamConfigFile.exists()) {
            await _teamConfigFile.writeAsString(await sourceTeamConfigFile.readAsString());
            await _loadTeamConfig(); // 重新加载
          }
          completedSteps++;
          onProgress?.call('队伍配置已导入 ($completedSteps/$totalSteps)');
        }
        
        if (importThemePacks) {
          final sourceThemePackConfigFile = File(path.join(tempUnzipDir.path, 'theme_pack_config.json'));
          if (await sourceThemePackConfigFile.exists()) {
            await _themePackConfigFile.writeAsString(await sourceThemePackConfigFile.readAsString());
            await _loadThemePackConfig(); // 重新加载
          }
          completedSteps++;
          onProgress?.call('主题包配置已导入 ($completedSteps/$totalSteps)');
        }
        
        if (importUserConfig) {
          final sourceUserConfigFile = File(path.join(tempUnzipDir.path, 'user_config.json'));
          if (await sourceUserConfigFile.exists()) {
            await _userConfigFile.writeAsString(await sourceUserConfigFile.readAsString());
            await _loadUserConfig(); // 重新加载
          }
          completedSteps++;
          onProgress?.call('用户配置已导入 ($completedSteps/$totalSteps)');
        }
        
        // 清理临时目录
        await tempUnzipDir.delete(recursive: true);
      } else if (await configSetDirectory.exists()) {
        // 兼容旧版目录格式
        onProgress?.call('检测到本地配置集目录，开始导入...');
        
        // 导入各个配置文件（根据选项）
        int completedSteps = 0;
        int totalSteps = [importTasks, importTeams, importThemePacks, importUserConfig].where((b) => b).length;
        
        if (importTasks) {
          final sourceTaskConfigFile = File(path.join(configSetDirectory.path, 'task_config.json'));
          if (await sourceTaskConfigFile.exists()) {
            await _taskConfigFile.writeAsString(await sourceTaskConfigFile.readAsString());
            await _loadTaskConfig(); // 重新加载
          }
          completedSteps++;
          onProgress?.call('任务配置已导入 ($completedSteps/$totalSteps)');
        }
        
        if (importTeams) {
          final sourceTeamConfigFile = File(path.join(configSetDirectory.path, 'team_config.json'));
          if (await sourceTeamConfigFile.exists()) {
            await _teamConfigFile.writeAsString(await sourceTeamConfigFile.readAsString());
            await _loadTeamConfig(); // 重新加载
          }
          completedSteps++;
          onProgress?.call('队伍配置已导入 ($completedSteps/$totalSteps)');
        }
        
        if (importThemePacks) {
          final sourceThemePackConfigFile = File(path.join(configSetDirectory.path, 'theme_pack_config.json'));
          if (await sourceThemePackConfigFile.exists()) {
            await _themePackConfigFile.writeAsString(await sourceThemePackConfigFile.readAsString());
            await _loadThemePackConfig(); // 重新加载
          }
          completedSteps++;
          onProgress?.call('主题包配置已导入 ($completedSteps/$totalSteps)');
        }
        
        if (importUserConfig) {
          final sourceUserConfigFile = File(path.join(configSetDirectory.path, 'user_config.json'));
          if (await sourceUserConfigFile.exists()) {
            await _userConfigFile.writeAsString(await sourceUserConfigFile.readAsString());
            await _loadUserConfig(); // 重新加载
          }
          completedSteps++;
          onProgress?.call('用户配置已导入 ($completedSteps/$totalSteps)');
        }
      } else {
        logger.e('配置集 $setName 不存在');
        return;
      }
      
      onProgress?.call('配置集 $setName 导入成功！');
      logger.d('配置集 $setName 导入成功');
    } catch (e) {
      onProgress?.call('导入配置集 $setName 失败: $e');
      logger.e('导入配置集 $setName 失败: $e');
    }
  }
  
  /// 导出当前配置到指定目录（用于分享）
  Future<void> exportConfigToDirectory(String directoryPath) async {
    try {
      final exportDirectory = Directory(directoryPath);
      if (!await exportDirectory.exists()) {
        await exportDirectory.create(recursive: true);
      }
      
      // 导出各个配置文件
      final taskConfigFile = File('${exportDirectory.path}/task_config.json');
      final teamConfigFile = File('${exportDirectory.path}/team_config.json');
      final themePackConfigFile = File('${exportDirectory.path}/theme_pack_config.json');
      
      // 用户配置需要特殊处理，清除CDK信息
      final userConfigFile = File('${exportDirectory.path}/user_config.json');
      final userConfigContent = await _userConfigFile.readAsString();
      final userConfigJson = json.decode(userConfigContent) as Map<String, dynamic>;
      userConfigJson['mirrorChanCDK'] = null;
      
      await taskConfigFile.writeAsString(await _taskConfigFile.readAsString());
      await teamConfigFile.writeAsString(await _teamConfigFile.readAsString());
      await themePackConfigFile.writeAsString(await _themePackConfigFile.readAsString());
      await userConfigFile.writeAsString(JsonEncoder.withIndent('  ').convert(userConfigJson));
      
      logger.d('配置导出到目录 $directoryPath 成功');
    } catch (e) {
      logger.e('导出配置到目录 $directoryPath 失败: $e');
    }
  }
  
  /// 设置原始任务配置内容
  Future<void> setTaskConfigRaw(String content) async {
    await _taskConfigFile.writeAsString(content);
    await _loadTaskConfig();
  }
  
  /// 设置原始队伍配置内容
  Future<void> setTeamConfigRaw(String content) async {
    await _teamConfigFile.writeAsString(content);
    await _loadTeamConfig();
  }
  
  /// 设置原始主题包配置内容
  Future<void> setThemePackConfigRaw(String content) async {
    await _themePackConfigFile.writeAsString(content);
    await _loadThemePackConfig();
  }
  
  /// 设置原始用户配置内容
  Future<void> setUserConfigRaw(String content) async {
    await _userConfigFile.writeAsString(content);
    await _loadUserConfig();
  }
  
  /// 加载所有配置
  Future<void> loadAllConfigs() async {
    await _loadTaskConfig();
    await _loadTeamConfig();
    await _loadThemePackConfig();
    await _loadUserConfig();
  }
  
  /// 获取应用应该使用的语言代码
  /// 如果用户设置了语言偏好，则使用用户设置
  /// 否则根据系统语言自动判断
  String? getPreferredLanguageCode() {
    // 如果用户设置了语言偏好，直接返回
    if (userConfig.language != null) {
      return userConfig.language;
    }
    
    // 如果用户选择跟随系统，返回null让系统自动判断
    return null;
  }

}

/// 获取设备ID
Future<String> getDeviceId() async {
  try {
    return await PlatformDeviceId.getDeviceId ?? 'default_device_id';
  } catch (e) {
    logger.e('获取设备ID失败: $e');
    return 'default_device_id';
  }
}


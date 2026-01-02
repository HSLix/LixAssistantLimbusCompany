// ignore_for_file: deprecated_member_use

import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:path/path.dart' as path;
import 'dart:io';
import 'package:toastification/toastification.dart';
import '../managers/config_manager.dart';
import '../generated/l10n.dart';
import 'package:provider/provider.dart';
import '../utils/zip_helper.dart';
import 'package:path_provider/path_provider.dart';
import '../managers/websocket_manager.dart';
import 'package:archive/archive.dart';
import 'package:archive/archive_io.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  late UserConfig _userConfig;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    setState(() {
      _isLoading = true;
    });

    setState(() {
      _userConfig = ConfigManager().userConfig;
      _isLoading = false;
    });
    
    // 加载可用的配置集
    _loadAvailableConfigSets();
  }
  
  Future<void> _loadAvailableConfigSets() async {
    try {
      await ConfigManager().getAvailableConfigSets();
      setState(() {
      });
    } catch (e) {
      debugPrint('加载配置集列表失败: $e');
    }
  }

  Future<void> _saveLanguage(BuildContext context, String? language) async {
    _userConfig.language = language; // 允许为null表示跟随系统
    await ConfigManager().saveUserConfig();
    
    // 更新语言管理器中的语言设置
    final languageManager = Provider.of<LanguageManager>(context, listen: false);
    if (language != null) {
      languageManager.setLocale(Locale(language));
    } else {
      languageManager.setLocale(null); // 跟随系统
    }
    
    setState(() {});
    
    // 显示成功提示
    if (mounted) {
      toastification.show(
        context: context,
        title: Text(S.of(context).language_setting_saved),
        style: ToastificationStyle.flatColored,
        type: ToastificationType.success,
        autoCloseDuration: const Duration(seconds: 3),
      );
    }
  }

  Future<void> _saveAutoStart(bool autoStart) async {
    _userConfig.autoStart = autoStart;
    await ConfigManager().saveUserConfig();
    setState(() {});
    
    // 显示成功提示
    if (mounted) {
      toastification.show(
        context: context,
        title: Text(S.of(context).autostart_setting_saved),
        style: ToastificationStyle.flatColored,
        type: ToastificationType.success,
        autoCloseDuration: const Duration(seconds: 3),
      );
    }
  }

  Future<void> _saveMirrorChanCDK(String? cdk) async {
    if (cdk == null || cdk.isEmpty) {
      // 清除CDK
      _userConfig.mirrorChanCDK = null;
      debugPrint('MirrorChan CDK 已清除');
    } else {
      // 验证CDK是否已经是加密格式（包含冒号分隔符）
      String encryptedCDK;
      if (cdk.contains(':')) {
        // 如果CDK已经包含冒号，认为它已经是加密格式
        encryptedCDK = cdk;
      } else {
        // 如果CDK不包含冒号，认为它是明文，需要加密
        encryptedCDK = await ConfigManager().encryptCDK(cdk);
      }
      _userConfig.mirrorChanCDK = encryptedCDK;
      debugPrint('MirrorChan CDK 已加密保存: $encryptedCDK');
    }
    
    await ConfigManager().saveUserConfig();
    
    // 保存后自动读取并调试打印
    // final savedCDK = _userConfig.mirrorChanCDK;
    // if (savedCDK != null) {
    //   debugPrint('从UserConfig读取的MirrorChan CDK: $savedCDK');
    // } else {
    //   debugPrint('UserConfig中MirrorChan CDK为空');
    // }
    
    setState(() {});
    
    // 显示成功提示
    if (mounted) {
      toastification.show(
        context: context,
        title: Text(S.of(context).cdk_saved),
        style: ToastificationStyle.flatColored,
        type: ToastificationType.success,
        autoCloseDuration: const Duration(seconds: 3),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return Scaffold(
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: ListView(
          children: [
            _buildSettingCard(
              icon: Icons.language,
              title: S.of(context).language_setting,
              child: _buildLanguageSelector(context),
            ),
            const SizedBox(height: 16),
            _buildSettingCard(
              icon: Icons.key,
              title: S.of(context).mirrorchan_cdk,
              child: _buildMirrorChanCDKInput(),
            ),
            const SizedBox(height: 16),
            _buildSettingCard(
              icon: Icons.settings_applications,
              title: S.of(context).config_set_management,
              child: _buildConfigSetManagement(),
            ),
            const SizedBox(height: 16),
            _buildSettingCard(
              icon: Icons.sync_alt,
              title: S.of(context).auto_update,
              child: _buildAutoUpdate(),
            ),
            const SizedBox(height: 16),
            _buildSettingCard(
              icon: Icons.settings_power,
              title: S.of(context).autostart,
              child: _buildAutoStartToggle(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSettingCard({
    required IconData icon,
    required String title,
    required Widget child,
  }) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 24),
                const SizedBox(width: 8),
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            child,
          ],
        ),
      ),
    );
  }

  Widget _buildLanguageSelector(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        RadioListTile<String?>(
          title: Text(S.of(context).follow_system),
          value: null, // null 表示跟随系统
          groupValue: _userConfig.language,
          onChanged: (value) {
            _saveLanguage(context, value);
          },
        ),
        RadioListTile<String?>(
          title: const Text('中文'),
          value: 'zh',
          groupValue: _userConfig.language,
          onChanged: (value) {
            _saveLanguage(context, value);
          },
        ),
        RadioListTile<String?>(
          title: const Text('English'),
          value: 'en',
          groupValue: _userConfig.language,
          onChanged: (value) {
            _saveLanguage(context, value);
          },
        ),
      ],
    );
  }

  Widget _buildAutoStartToggle() {
    return Center(
      child: Switch(
        value: _userConfig.autoStart,
        onChanged: (value) {
          _saveAutoStart(value);
        },
      ),
    );
  }

  Widget _buildMirrorChanCDKInput() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // 显示是否存在 CDK
        ListTile(
          title: Text(S.of(context).cdk_status),
          trailing: Text(
            _userConfig.mirrorChanCDK != null && _userConfig.mirrorChanCDK!.isNotEmpty
                ? S.of(context).set
                : S.of(context).not_set,
            style: TextStyle(
              color: _userConfig.mirrorChanCDK != null && _userConfig.mirrorChanCDK!.isNotEmpty
                  ? Colors.green
                  : Colors.red,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        const SizedBox(height: 12),
        // 编辑 CDK 按钮
        ElevatedButton(
          onPressed: () {
            _showEditCDKDialog();
          },
          child: Text(S.of(context).edit_cdk),
        ),
      ],
    );
  }
  
  Widget _buildConfigSetManagement() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // 保存当前配置到本地配置
        ElevatedButton(
          onPressed: () {
            _showSaveConfigSetDialog();
          },
          child: Text(S.of(context).save_current_config),
        ),
        const SizedBox(height: 12),
        // 管理本地配置
        ElevatedButton(
          onPressed: () {
            _showManageConfigSetsDialog();
          },
          child: Text(S.of(context).manage_local_configs),
        ),
        const SizedBox(height: 12),
        // 导出当前配置
        ElevatedButton(
          onPressed: () {
            _showExportCurrentConfigDialog();
          },
          child: Text(S.of(context).export_current_config),
        ),
        const SizedBox(height: 12),
        // 导入到当前配置
        ElevatedButton(
          onPressed: () {
            _showImportToCurrentConfigDialog();
          },
          child: Text(S.of(context).import_to_current_config),
        ),
      ],
    );
  }
  
  Widget _buildAutoUpdate() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // 从MirrorChan更新配置
        ElevatedButton(
          onPressed: () {
            _checkWebSocketAndShowDownloadProgressDialog('MirrorChan');
          },
          child: Text(S.of(context).update_from_mirrorchan),
        ),
        const SizedBox(height: 12),
        // 从GitHub更新配置
        ElevatedButton(
          onPressed: () {
            _checkWebSocketAndShowDownloadProgressDialog('GitHub');
          },
          child: Text(S.of(context).update_from_github),
        ),
        const SizedBox(height: 12),
        // 本地更新（从已下载的包覆盖更新）
        ElevatedButton(
          onPressed: () {
            _showLocalUpdateDialog();
          },
          child: Text(S.of(context).local_update),
        ),
      ],
    );
  }
  
  /// 检查WebSocket连接状态并显示下载进度弹窗
  void _checkWebSocketAndShowDownloadProgressDialog(String source) {
    if (!WebSocketManager().isConnected) {
      // 如果WebSocket未连接，显示错误提示
      if (mounted) {
        toastification.show(
          context: context,
          title: Text(S.of(context).websocket_disconnected),
          style: ToastificationStyle.flatColored,
          type: ToastificationType.error,
          autoCloseDuration: const Duration(seconds: 3),
        );
      }
      return;
    }
    
    _showDownloadProgressDialog(source);
  }
  
  /// 显示下载进度弹窗
  void _showDownloadProgressDialog(String source) {
    double progress = 0.0;
    StateSetter? progressStateSetter;
    
    // 创建进度对话框
    final dialog = StatefulBuilder(
      builder: (BuildContext context, StateSetter setDialogState) {
        progressStateSetter = setDialogState;
        return AlertDialog(
          title: Text('${S.of(context).downloading_from} $source'),
          content: SizedBox(
            height: 150,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const CircularProgressIndicator(),
                const SizedBox(height: 20),
                Text(
                  '${(progress * 100).round()}%',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 10),
                LinearProgressIndicator(
                  value: progress,
                  backgroundColor: Colors.grey[300],
                  valueColor: const AlwaysStoppedAnimation<Color>(Colors.blue),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () {
                // 取消下载
                WebSocketManager().cancelDownload();
                if (Navigator.of(context).canPop()) {
                  Navigator.of(context).pop();
                }
              },
              child: Text(S.of(context).cancel),
            ),
          ],
        );
      },
    );

    // 显示对话框
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (BuildContext dialogContext) {
        // 在这里启动下载，确保dialogContext已初始化
        WidgetsBinding.instance.addPostFrameCallback((_) {
          // 添加debugPrint输出CDK值
          final cdkToSend = source == 'MirrorChan' ? ConfigManager().encryptedMirrorChanCDK : null;
          debugPrint('发送的CDK值: $cdkToSend');
          _realDownload(
            dialogContext: context, // 使用页面context而非dialogContext
            source: source == 'GitHub' ? 'github' : 'mirrorchan',
            cdk: cdkToSend,
            onProgress: (p) {
              // 修复进度值处理：将百分比转换为0-1之间的值
              final double normalized = p / 100.0;
              if (mounted) {
                progressStateSetter!(() => progress = normalized.clamp(0.0, 1.0));
              }
            },
            onDone: () {
              // 1. 先关弹窗，再弹 toast，顺序不能反
              if (mounted && Navigator.canPop(context)) {
                Navigator.pop(context);          // 使用页面context
              }

              // 显示下载完成的toast
              if (mounted) {
                toastification.show(
                  context: context,
                  title: Text('$source ${S.of(context).update_completed}'),
                  style: ToastificationStyle.flatColored,
                  type: ToastificationType.success,
                  autoCloseDuration: const Duration(seconds: 3),
                );
              }
            },
            onFail: (err) {
              if (mounted && Navigator.canPop(context)) {
                Navigator.pop(context); // 使用页面context
                toastification.show(
                  context: context,
                  title: Text(err),
                  style: ToastificationStyle.flatColored,
                  type: ToastificationType.error,
                  autoCloseDuration: const Duration(days: 1),
                );
              }
            },
          );
        });
        
        return dialog;
      },
    );
  }
  

  /// 获取更新目录
  Future<Directory> _getUpdateDir() async {
    final doc = await getApplicationDocumentsDirectory();
    final lalc = Directory(path.join(doc.path, 'LALC'));
    if (!await lalc.exists()) await lalc.create();
    final update = Directory(path.join(lalc.path, 'update'));
    if (!await update.exists()) await update.create();
    return update;
  }

  /// 解压更新包到LALC目录
  Future<Directory> _unzipToLalcFolder(String zipPath) async {
    final updateDir = await _getUpdateDir();
    final targetLalc = Directory(path.join(updateDir.path, 'lalc'));

    // 存在就删
    if (await targetLalc.exists()) {
      await targetLalc.delete(recursive: true);
    }

    // 用 archive 库解压
    final bytes = File(zipPath).readAsBytesSync();
    final archive = ZipDecoder().decodeBytes(bytes);
    for (final file in archive) {
      final filename = file.name;
      if (file.isFile) {
        final outFile = File(path.join(updateDir.path, filename))
          ..createSync(recursive: true);
        outFile.writeAsBytesSync(file.content);
      } else {
        Directory(path.join(updateDir.path, filename)).createSync(recursive: true);
      }
    }

    // 记录绝对路径
    final abs = targetLalc.resolveSymbolicLinksSync();
    logger.d('更新包已解压到: $abs');
    return targetLalc;
  }

  /// 真实下载实现
  Future<void> _realDownload({
    required BuildContext dialogContext, // 添加dialogContext参数
    required String source,
    required String? cdk,
    required Function(double) onProgress,
    required VoidCallback onDone,
    required Function(String) onFail,
  }) async {
    try {
      final updateDir = await _getUpdateDir();
      final ws = WebSocketManager();

      ws.downloadUpdate(
        source: source,
        saveDir: updateDir.path,
        cdk: cdk,
        onProgress: (progressData) {
          // 进度回调：progressData是0到1之间的数值
          onProgress(progressData.toDouble());
        },
        onError: (msg) {
          onFail(msg);
          ws.cancelDownload();
        },
        onComplete: (zipPath) async {
          // 检查上下文是否仍然有效
          if (!mounted) return;
          
          try {
            await _unzipToLalcFolder(zipPath);
            // 可以顺手把 zip 删掉
            File(zipPath).deleteSync();
            
            // 关闭进度弹窗后显示确认弹窗
            if (mounted && Navigator.canPop(context)) {
              Navigator.pop(context);
            }
            
            // 显示确认弹窗
            final confirm = await showDialog<bool>(
              context: context,
              builder: (context) => AlertDialog(
                title: Text(S.of(context).confirm_auto_update),
                content: Text(S.of(context).auto_update_warning),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(false),
                    child: Text(S.of(context).no_manual_update),
                  ),
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(true),
                    child: Text(S.of(context).yes_auto_update),
                  ),
                ],
              ),
            );
            
            if (confirm == true) {
              // 用户选择自动更新，输出update_to.bat的绝对路径和项目自身路径
              final updateDir = await _getUpdateDir();
              final lalcDir = Directory('${updateDir.parent.path}/lalc');
              final batFile = File('${lalcDir.path}/update_to.bat');
              
              // 获取项目自身的绝对路径
              String executablePath = Platform.resolvedExecutable;
              String projectDir = path.dirname(path.dirname(executablePath));
              
              if (mounted) {
                toastification.show(
                  context: context,
                  title: Text('${S.of(context).update_bat_path}: ${batFile.path}\n${S.of(context).project_path}: $projectDir'),
                  style: ToastificationStyle.flatColored,
                  type: ToastificationType.info,
                  autoCloseDuration: const Duration(seconds: 15),
                );
              }
            } else {
              // 用户选择手动更新，打开下载的update文件夹
              final updateDir = await _getUpdateDir();
              if (await updateDir.exists()) {
                await Process.run('explorer', [updateDir.path]);
              }
            }
            
            onDone();
          } catch (e) {
            // 检查上下文是否仍然有效
            if (mounted) {
              onFail('解压失败: $e');
            }
          }
        },
      );
    } catch (e) {
      onFail('下载失败: $e');
    }
  }

  void _showEditCDKDialog() async {
    // 1. 临时解密给用户看
    final plain = await ConfigManager().decryptCDKIfPossible(
      _userConfig.mirrorChanCDK ?? '',
    );
    final controller = TextEditingController(text: plain);

    showDialog(
      context: context,
      barrierDismissible: true,
      builder: (_) => AlertDialog(
        title: Text(S.of(context).edit_mirrorchan_cdk),
        content: TextField(
          controller: controller,
          obscureText: true,
          decoration: InputDecoration(
            hintText: S.of(context).enter_cdk,
            border: const OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(S.of(context).cancel),
          ),
          TextButton(
            onPressed: () {
              // 2. 保存时会自动再走一次加密
              _saveMirrorChanCDK(controller.text.trim());
              Navigator.pop(context);
            },
            child: Text(S.of(context).save),
          ),
        ],
      ),
    );
  }


  void _showSaveConfigSetDialog() {
    final controller = TextEditingController();

    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(S.of(context).save_config_set),
          content: TextField(
            controller: controller,
            decoration: InputDecoration(
              hintText: S.of(context).enter_config_set_name,
              border: const OutlineInputBorder(),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
              },
              child: Text(S.of(context).cancel),
            ),
            TextButton(
              onPressed: () async {
                if (controller.text.isNotEmpty) {
                  await ConfigManager().saveCurrentConfigAsSet(controller.text);
                  await _loadAvailableConfigSets(); // 重新加载配置集列表
                  Navigator.of(context).pop();
                  // 显示成功提示
                  if (mounted) {
                    toastification.show(
                      context: context,
                      title: Text(S.of(context).config_set_saved),
                      style: ToastificationStyle.flatColored,
                      type: ToastificationType.success,
                      autoCloseDuration: const Duration(seconds: 3),
                    );
                  }
                }
              },
              child: Text(S.of(context).save),
            ),
          ],
        );
      },
    );
  }

  void _showManageConfigSetsDialog() {
    late BuildContext dialogContext; // 定义dialogContext在整个方法中可用
    
    showDialog(
      context: context,
      builder: (BuildContext context) {
        dialogContext = context; // 在dialog中设置dialogContext
        return AlertDialog(
          title: Text(S.of(context).manage_local_configs),
          content: SizedBox(
            width: double.maxFinite,
            child: FutureBuilder<List<String>>(
              future: ConfigManager().getAvailableConfigSets(),
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                } else if (snapshot.hasError) {
                  return Text('${S.of(context).load_failed}: ${snapshot.error}');
                } else if (snapshot.hasData) {
                  final configSets = snapshot.data!;
                  if (configSets.isEmpty) {
                    return Text(S.of(context).no_local_configs);
                  }
                  
                  return ListView.builder(
                    shrinkWrap: true,
                    itemCount: configSets.length,
                    itemBuilder: (context, index) {
                      final setName = configSets[index];
                      // 不允许删除默认配置
                      if (setName == 'default') {
                        return ListTile(
                          title: const Text('default (系统默认)'),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                icon: const Icon(Icons.download, color: Colors.blue),
                                onPressed: () async {
                                  bool importTasks = true;
                                  bool importTeams = true;
                                  bool importThemePacks = true;
                                  bool importUserConfig = false;
                                  
                                  // 显示选择对话框，让用户选择要导入的部分
                                  final selectedOptions = await showDialog<Map<String, bool>?>(
                                    context: context,
                                    builder: (context) {
                                      return StatefulBuilder(
                                        builder: (context, setState) {
                                          return AlertDialog(
                                            title: Text(S.of(context).load_config),
                                            content: Column(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                Text(S.of(context).load_config_warning),
                                                const SizedBox(height: 16),
                                                CheckboxListTile(
                                                  title: Text(S.of(context).task_config),
                                                  value: importTasks,
                                                  onChanged: (bool? value) {
                                                    setState(() {
                                                      importTasks = value ?? false;
                                                    });
                                                  },
                                                ),
                                                CheckboxListTile(
                                                  title: Text(S.of(context).team_config),
                                                  value: importTeams,
                                                  onChanged: (bool? value) {
                                                    setState(() {
                                                      importTeams = value ?? false;
                                                    });
                                                  },
                                                ),
                                                CheckboxListTile(
                                                  title: Text(S.of(context).theme_pack_config),
                                                  value: importThemePacks,
                                                  onChanged: (bool? value) {
                                                    setState(() {
                                                      importThemePacks = value ?? false;
                                                    });
                                                  },
                                                ),
                                                CheckboxListTile(
                                                  title: Text(S.of(context).user_config),
                                                  value: importUserConfig,
                                                  onChanged: (bool? value) {
                                                    setState(() {
                                                      importUserConfig = value ?? false;
                                                    });
                                                  },
                                                ),
                                              ],
                                            ),
                                            actions: [
                                              TextButton(
                                                onPressed: () {
                                                  Navigator.of(context).pop(null);
                                                },
                                                child: Text(S.of(context).cancel),
                                              ),
                                              TextButton(
                                                onPressed: () {
                                                  Navigator.of(context).pop({
                                                    'importTasks': importTasks,
                                                    'importTeams': importTeams,
                                                    'importThemePacks': importThemePacks,
                                                    'importUserConfig': importUserConfig,
                                                  });
                                                },
                                                child: Text(S.of(context).confirm),
                                              ),
                                            ],
                                          );
                                        },
                                      );
                                    },
                                  );
                                  
                                  // 用户确认后再执行读取操作
                                  if (selectedOptions != null) {
                                    // 读取配置逻辑，复用导入逻辑
                                    final configSetPath = path.join(ConfigManager().getConfigsDirectory().path, setName);
                                    
                                    // 检查配置集是否为ZIP文件
                                    final zipFile = File('$configSetPath.zip');
                                    if (await zipFile.exists()) {
                                      // 如果是ZIP文件，先解压到临时目录
                                      final tempDir = await getTemporaryDirectory();
                                      final tempUnzipDir = Directory('${tempDir.path}/unzipped_${setName}_${DateTime.now().millisecondsSinceEpoch}');
                                      await tempUnzipDir.create(recursive: true);
                                      
                                      try {
                                        await ZipHelper.unzipTo(zipFile: zipFile.path, dstDir: tempUnzipDir.path);
                                        
                                        // 执行选择性导入
                                        await _selectiveImportConfigFromDirectory(
                                          tempUnzipDir.path,
                                          importTasks: selectedOptions['importTasks'] ?? true,
                                          importTeams: selectedOptions['importTeams'] ?? true,
                                          importThemePacks: selectedOptions['importThemePacks'] ?? true,
                                          importUserConfig: selectedOptions['importUserConfig'] ?? false,
                                        );
                                        
                                        // 删除临时解压目录
                                        await tempUnzipDir.delete(recursive: true);
                                      } catch (e) {
                                        // 如果解压失败，清理临时目录
                                        await tempUnzipDir.delete(recursive: true);
                                        rethrow;
                                      }
                                    } else {
                                      // 如果是目录格式，直接导入
                                      await _selectiveImportConfigFromDirectory(
                                        configSetPath,
                                        importTasks: selectedOptions['importTasks'] ?? true,
                                        importTeams: selectedOptions['importTeams'] ?? true,
                                        importThemePacks: selectedOptions['importThemePacks'] ?? true,
                                        importUserConfig: selectedOptions['importUserConfig'] ?? false,
                                      );
                                    }
                                    
                                    await _loadConfig();
                                    
                                    if (context.mounted) {
                                      Navigator.of(context).pop();
                                      toastification.show(
                                        context: context,
                                        title: Text(S.of(context).config_loaded),
                                        style: ToastificationStyle.flatColored,
                                        type: ToastificationType.success,
                                        autoCloseDuration: const Duration(seconds: 3),
                                      );
                                    }
                                  }
                                },
                              ),
                              IconButton(
                                icon: const Icon(Icons.lock, color: Colors.grey),
                                onPressed: null,
                              ),
                            ],
                          ),
                        );
                      }

                      return ListTile(
                        title: Text(setName),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            // 读取配置按钮
                            IconButton(
                              icon: const Icon(Icons.download, color: Colors.blue),
                              onPressed: () async {
                                bool importTasks = true;
                                bool importTeams = true;
                                bool importThemePacks = true;
                                bool importUserConfig = false;
                                
                                // 显示选择对话框，让用户选择要导入的部分
                                final selectedOptions = await showDialog<Map<String, bool>?>(
                                  context: context,
                                  builder: (context) {
                                    return StatefulBuilder(
                                      builder: (context, setState) {
                                        return AlertDialog(
                                          title: Text(S.of(context).load_config),
                                          content: Column(
                                            mainAxisSize: MainAxisSize.min,
                                            children: [
                                              Text(S.of(context).load_config_warning),
                                              const SizedBox(height: 16),
                                              CheckboxListTile(
                                                title: Text(S.of(context).task_config),
                                                value: importTasks,
                                                onChanged: (bool? value) {
                                                  setState(() {
                                                    importTasks = value ?? false;
                                                  });
                                                },
                                              ),
                                              CheckboxListTile(
                                                title: Text(S.of(context).team_config),
                                                value: importTeams,
                                                onChanged: (bool? value) {
                                                  setState(() {
                                                    importTeams = value ?? false;
                                                  });
                                                },
                                              ),
                                              CheckboxListTile(
                                                title: Text(S.of(context).theme_pack_config),
                                                value: importThemePacks,
                                                onChanged: (bool? value) {
                                                  setState(() {
                                                    importThemePacks = value ?? false;
                                                  });
                                                },
                                              ),
                                              CheckboxListTile(
                                                title: Text(S.of(context).user_config),
                                                value: importUserConfig,
                                                onChanged: (bool? value) {
                                                  setState(() {
                                                    importUserConfig = value ?? false;
                                                  });
                                                },
                                              ),
                                            ],
                                          ),
                                          actions: [
                                            TextButton(
                                              onPressed: () {
                                                Navigator.of(context).pop(null);
                                              },
                                              child: Text(S.of(context).cancel),
                                            ),
                                            TextButton(
                                              onPressed: () {
                                                Navigator.of(context).pop({
                                                  'importTasks': importTasks,
                                                  'importTeams': importTeams,
                                                  'importThemePacks': importThemePacks,
                                                  'importUserConfig': importUserConfig,
                                                });
                                              },
                                              child: Text(S.of(context).confirm),
                                            ),
                                          ],
                                        );
                                      },
                                    );
                                  },
                                );
                                
                                // 用户确认后再执行读取操作
                                if (selectedOptions != null) {
                                  // 读取配置逻辑，复用导入逻辑
                                  final configSetPath = path.join(ConfigManager().getConfigsDirectory().path, setName);
                                  
                                  // 检查配置集是否为ZIP文件
                                  final zipFile = File('$configSetPath.zip');
                                  if (await zipFile.exists()) {
                                    // 如果是ZIP文件，先解压到临时目录
                                    final tempDir = await getTemporaryDirectory();
                                    final tempUnzipDir = Directory('${tempDir.path}/unzipped_${setName}_${DateTime.now().millisecondsSinceEpoch}');
                                    await tempUnzipDir.create(recursive: true);
                                    
                                    try {
                                      await ZipHelper.unzipTo(zipFile: zipFile.path, dstDir: tempUnzipDir.path);
                                      
                                      // 执行选择性导入
                                      await _selectiveImportConfigFromDirectory(
                                        tempUnzipDir.path,
                                        importTasks: selectedOptions['importTasks'] ?? true,
                                        importTeams: selectedOptions['importTeams'] ?? true,
                                        importThemePacks: selectedOptions['importThemePacks'] ?? true,
                                        importUserConfig: selectedOptions['importUserConfig'] ?? false,
                                      );
                                      
                                      // 删除临时解压目录
                                      await tempUnzipDir.delete(recursive: true);
                                    } catch (e) {
                                      // 如果解压失败，清理临时目录
                                      await tempUnzipDir.delete(recursive: true);
                                      rethrow;
                                    }
                                  } else {
                                    // 如果是目录格式，直接导入
                                    await _selectiveImportConfigFromDirectory(
                                      configSetPath,
                                      importTasks: selectedOptions['importTasks'] ?? true,
                                      importTeams: selectedOptions['importTeams'] ?? true,
                                      importThemePacks: selectedOptions['importThemePacks'] ?? true,
                                      importUserConfig: selectedOptions['importUserConfig'] ?? false,
                                    );
                                  }
                                  
                                  await _loadConfig();
                                  
                                  if (context.mounted) {
                                    Navigator.of(context).pop();
                                    toastification.show(
                                      context: context,
                                      title: Text(S.of(context).config_loaded),
                                      style: ToastificationStyle.flatColored,
                                      type: ToastificationType.success,
                                      autoCloseDuration: const Duration(seconds: 3),
                                    );
                                  }
                                }
                              },
                            ),
                            // 删除配置按钮
                            IconButton(
                              icon: const Icon(Icons.delete, color: Colors.red),
                              onPressed: () async {
                                final confirm = await showDialog<bool>(
                                  context: context,
                                  builder: (context) => AlertDialog(
                                    title: Text(S.of(context).confirm_delete),
                                    content: Text('${S.of(context).confirm_delete_message} "$setName" ${S.of(context).irreversible}'),
                                    actions: [
                                      TextButton(
                                        onPressed: () => Navigator.of(context).pop(false),
                                        child: Text(S.of(context).cancel),
                                      ),
                                      TextButton(
                                        onPressed: () => Navigator.of(context).pop(true),
                                        child: Text(S.of(context).delete),
                                      ),
                                    ],
                                  ),
                                );
                                
                                if (confirm == true) {
                                  try {
                                    // 尝试删除目录格式的配置集
                                    final configSetDir = Directory('${ConfigManager().getConfigsDirectory().path}/$setName');
                                    if (await configSetDir.exists()) {
                                      await configSetDir.delete(recursive: true);
                                    }
                                    
                                    // 尝试删除ZIP格式的配置集
                                    final configSetZip = File('${ConfigManager().getConfigsDirectory().path}/$setName.zip');
                                    if (await configSetZip.exists()) {
                                      await configSetZip.delete();
                                    }
                                    
                                    // 重新加载配置集列表
                                    await _loadAvailableConfigSets();
                                    // 更新UI
                                    if (mounted) {
                                      (context as Element).markNeedsBuild();
                                    }
                                    if (mounted) {
                                      Navigator.of(dialogContext).pop(); // 使用定义的dialogContext
                                      toastification.show(
                                        context: context,
                                        title: Text(S.of(context).delete_success),
                                        style: ToastificationStyle.flatColored,
                                        type: ToastificationType.success,
                                        autoCloseDuration: const Duration(seconds: 3),
                                      );
                                    }
                                  } catch (e) {
                                    if (mounted) {
                                      toastification.show(
                                        context: context,
                                        title: Text(S.of(context).delete_failed),
                                        style: ToastificationStyle.flatColored,
                                        type: ToastificationType.error,
                                        autoCloseDuration: const Duration(seconds: 3),
                                      );
                                    }
                                  }
                                }
                              },
                            ),
                          ],
                        ),
                      );
                    },
                  );
                } else {
                  return Text(S.of(context).no_local_configs);
                }
              },
            ),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(); // 使用定义的dialogContext
              },
              child: Text(S.of(context).close),
            ),
          ],
        );
      },
    );
  }

  void _showExportCurrentConfigDialog() {
    // 首先显示确认对话框，提醒用户导出会清除CDK
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(S.of(context).export_current_config),
          content: Text(S.of(context).export_config_warning),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
              },
              child: Text(S.of(context).cancel),
            ),
            TextButton(
              onPressed: () async {
                Navigator.of(context).pop(); // 关闭确认对话框
                await _exportCurrentConfig(); // 执行导出操作
              },
              child: Text(S.of(context).confirm),
            ),
          ],
        );
      },
    );
  }

  void _showImportToCurrentConfigDialog() {
    bool importTasks = true;
    bool importTeams = true;
    bool importThemePacks = true;
    bool importUserConfig = false;
    
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: Text(S.of(context).import_to_current_config),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(S.of(context).import_config_warning),
                  const SizedBox(height: 16),
                  CheckboxListTile(
                    title: Text(S.of(context).task_config),
                    value: importTasks,
                    onChanged: (bool? value) {
                      setState(() {
                        importTasks = value ?? false;
                      });
                    },
                  ),
                  CheckboxListTile(
                    title: Text(S.of(context).team_config),
                    value: importTeams,
                    onChanged: (bool? value) {
                      setState(() {
                        importTeams = value ?? false;
                      });
                    },
                  ),
                  CheckboxListTile(
                    title: Text(S.of(context).theme_pack_config),
                    value: importThemePacks,
                    onChanged: (bool? value) {
                      setState(() {
                        importThemePacks = value ?? false;
                      });
                    },
                  ),
                  CheckboxListTile(
                    title: Text(S.of(context).user_config),
                    value: importUserConfig,
                    onChanged: (bool? value) {
                      setState(() {
                        importUserConfig = value ?? false;
                      });
                    },
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () {
                    Navigator.of(context).pop();
                  },
                  child: Text(S.of(context).cancel),
                ),
                TextButton(
                  onPressed: () async {
                    Navigator.of(context).pop();
                    // 执行导入操作
                    await _importToCurrentConfig(importTasks: importTasks, 
                                                importTeams: importTeams, 
                                                importThemePacks: importThemePacks, 
                                                importUserConfig: importUserConfig);
                  },
                  child: Text(S.of(context).confirm),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _exportCurrentConfig() async {
    try {
      // 使用文件选择器选择导出ZIP文件
      final String? selectedPath = await FilePicker.platform.saveFile(
        dialogTitle: S.of(context).select_export_directory,
        fileName: 'lalc_config_${DateTime.now().millisecondsSinceEpoch}.zip',
        type: FileType.custom,
        allowedExtensions: ['zip'],
      );
      
      if (selectedPath != null) {
        // 显示导出中弹窗
        late BuildContext dialogContext;
        final dialog = AlertDialog(
          content: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(width: 20),
              Text(S.of(context).exporting),
            ],
          ),
        );

        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (BuildContext context) {
            dialogContext = context;
            return dialog;
          },
        );
        
        // 创建临时目录用于准备导出的文件
        final tempDir = await getTemporaryDirectory();
        final exportTempDir = Directory('${tempDir.path}/export_${DateTime.now().millisecondsSinceEpoch}');
        await exportTempDir.create(recursive: true);
        
        // 导出各个配置文件到临时目录
        await ConfigManager().exportConfigToDirectory(exportTempDir.path);
        
        // 创建ZIP文件（现在在后台线程执行）
        await ZipHelper.zipDir(srcDir: exportTempDir.path, dstZip: selectedPath);
        
        // 清理临时目录
        await exportTempDir.delete(recursive: true);
        
        // 关闭导出中弹窗
        if (mounted && Navigator.canPop(dialogContext)) {
          Navigator.pop(dialogContext);
        }
        
        if (mounted) {
          toastification.show(
            context: context,
            title: Text('${S.of(context).config_export_success}(ZIP)'),
            style: ToastificationStyle.flatColored,
            type: ToastificationType.success,
            autoCloseDuration: const Duration(seconds: 3),
          );
        }
      }
    } catch (e) {
      // 关闭导出中弹窗（如果还存在）
      try {
        final navigator = Navigator.of(context);
        if (navigator.canPop()) {
          navigator.pop();
        }
      } catch (e) {
        // 忽略导航错误
      }
      
      if (mounted) {
        toastification.show(
          context: context,
          title: Text('${S.of(context).config_export_failed}: $e'),
          style: ToastificationStyle.flatColored,
          type: ToastificationType.error,
          autoCloseDuration: const Duration(days: 1),
        );
      }
    }
  }

  /// 执行导入到当前配置的核心逻辑。
  /// 此方法会尝试从ZIP文件导入配置文件，并覆盖当前配置。
  Future<void> _importToCurrentConfig({bool importTasks = true, bool importTeams = true, 
                                     bool importThemePacks = true, bool importUserConfig = false}) async {
    try {
      // 使用文件选择器选择导入ZIP文件
      final FilePickerResult? result = await FilePicker.platform.pickFiles(
        dialogTitle: S.of(context).select_import_directory,
        type: FileType.custom,
        allowedExtensions: ['zip'],
      );
      
      if (result != null) {
        final selectedFile = File(result.files.single.path!);
        
        // 显示导入中弹窗
        late BuildContext dialogContext;
        final dialog = AlertDialog(
          content: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(width: 20),
              Text(S.of(context).importing),
            ],
          ),
        );

        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (BuildContext context) {
            dialogContext = context;
            return dialog;
          },
        );
        
        // 解压ZIP文件到临时目录
        final tempDir = await getTemporaryDirectory();
        final tempUnzipDir = Directory('${tempDir.path}/unzipped_${DateTime.now().millisecondsSinceEpoch}');
        await tempUnzipDir.create(recursive: true);
        
        try {
          await ZipHelper.unzipTo(zipFile: selectedFile.path, dstDir: tempUnzipDir.path);
        } catch (e) {
          // 关闭导入中弹窗
          if (mounted && Navigator.canPop(dialogContext)) {
            Navigator.pop(dialogContext);
          }
          
          if (mounted) {
            toastification.show(
              context: context,
              title: const Text('解压失败，可能不是合法 ZIP'),
              style: ToastificationStyle.flatColored,
              type: ToastificationType.error,
              autoCloseDuration: const Duration(days: 1),
            );
          }
          
          // 清理临时目录
          await tempUnzipDir.delete(recursive: true);
          return;
        }
        
        // 检查所选目录是否包含必要的配置文件
        final requiredFiles = [
          if (importTasks) 'task_config.json',
          if (importTeams) 'team_config.json',
          if (importThemePacks) 'theme_pack_config.json',
          if (importUserConfig) 'user_config.json'
        ];
        
        bool hasAllFiles = true;
        for (final fileName in requiredFiles) {
          final file = File('${tempUnzipDir.path}/$fileName');
          if (!await file.exists()) {
            // 检查是否在子目录中
            bool foundInSubDirs = false;
            await for (final entity in tempUnzipDir.list(recursive: true)) {
              if (entity is File && path.basename(entity.path) == fileName) {
                foundInSubDirs = true;
                break;
              }
            }
            
            if (!foundInSubDirs) {
              hasAllFiles = false;
              break;
            }
          }
        }
        
        if (!hasAllFiles) {
          // 关闭导入中弹窗
          if (mounted && Navigator.canPop(dialogContext)) {
            Navigator.pop(dialogContext);
          }
          
          if (mounted) {
            toastification.show(
              context: context,
              title: Text(S.of(context).missing_required_files),
              style: ToastificationStyle.flatColored,
              type: ToastificationType.error,
              autoCloseDuration: const Duration(seconds: 3),
            );
          }
          
          // 清理临时目录
          await tempUnzipDir.delete(recursive: true);
          return;
        }
        
        // 导入配置文件
        if (importTasks) {
          final directFile = File('${tempUnzipDir.path}/task_config.json');
          File sourceTaskConfigFile = directFile;
          
          // 如果直接文件不存在，查找子目录中的文件
          if (!await directFile.exists()) {
            await for (final entity in tempUnzipDir.list(recursive: true)) {
              if (entity is File && path.basename(entity.path) == 'task_config.json') {
                sourceTaskConfigFile = entity;
                break;
              }
            }
          }
          
          if (await sourceTaskConfigFile.exists()) {
            await ConfigManager().setTaskConfigRaw(await sourceTaskConfigFile.readAsString());
          }
        }
        
        if (importTeams) {
          final directFile = File('${tempUnzipDir.path}/team_config.json');
          File sourceTeamConfigFile = directFile;
          
          // 如果直接文件不存在，查找子目录中的文件
          if (!await directFile.exists()) {
            await for (final entity in tempUnzipDir.list(recursive: true)) {
              if (entity is File && path.basename(entity.path) == 'team_config.json') {
                sourceTeamConfigFile = entity;
                break;
              }
            }
          }
          
          if (await sourceTeamConfigFile.exists()) {
            await ConfigManager().setTeamConfigRaw(await sourceTeamConfigFile.readAsString());
          }
        }
        
        if (importThemePacks) {
          final directFile = File('${tempUnzipDir.path}/theme_pack_config.json');
          File sourceThemePackConfigFile = directFile;
          
          // 如果直接文件不存在，查找子目录中的文件
          if (!await directFile.exists()) {
            await for (final entity in tempUnzipDir.list(recursive: true)) {
              if (entity is File && path.basename(entity.path) == 'theme_pack_config.json') {
                sourceThemePackConfigFile = entity;
                break;
              }
            }
          }
          
          if (await sourceThemePackConfigFile.exists()) {
            await ConfigManager().setThemePackConfigRaw(await sourceThemePackConfigFile.readAsString());
          }
        }
        
        if (importUserConfig) {
          final directFile = File('${tempUnzipDir.path}/user_config.json');
          File sourceUserConfigFile = directFile;
          
          // 如果直接文件不存在，查找子目录中的文件
          if (!await directFile.exists()) {
            await for (final entity in tempUnzipDir.list(recursive: true)) {
              if (entity is File && path.basename(entity.path) == 'user_config.json') {
                sourceUserConfigFile = entity;
                break;
              }
            }
          }
          
          if (await sourceUserConfigFile.exists()) {
            await ConfigManager().setUserConfigRaw(await sourceUserConfigFile.readAsString());
          }
        }
        
        // 清理临时目录
        await tempUnzipDir.delete(recursive: true);
        
        // 关闭导入中弹窗
        if (mounted && Navigator.canPop(dialogContext)) {
          Navigator.pop(dialogContext);
        }
        
        if (mounted) {
          toastification.show(
            context: context,
            title: Text(S.of(context).config_import_success),
            style: ToastificationStyle.flatColored,
            type: ToastificationType.success,
            autoCloseDuration: const Duration(seconds: 3),
          );
        }
        
        // 重新加载配置
        await ConfigManager().loadAllConfigs();
        if (mounted) {
          setState(() {});
        }
      }
    } catch (e) {
      // 关闭导入中弹窗（如果还存在）
      try {
        final navigator = Navigator.of(context);
        if (navigator.canPop()) {
          navigator.pop();
        }
      } catch (e) {
        // 忽略导航错误
      }
      
      if (mounted) {
        toastification.show(
          context: context,
          title: Text('${S.of(context).config_import_failed}: $e'),
          style: ToastificationStyle.flatColored,
          type: ToastificationType.error,
          autoCloseDuration: const Duration(days: 1),
        );
      }
    }
  }

  /// 选择性导入配置
  Future<void> _selectiveImportConfigFromDirectory(String directoryPath, 
                                                  {bool importTasks = true, 
                                                   bool importTeams = true, 
                                                   bool importThemePacks = true, 
                                                   bool importUserConfig = false}) async {
    try {
      final importDirectory = Directory(directoryPath);
      if (!await importDirectory.exists()) {
        logger.e('导入目录 $directoryPath 不存在');
        return;
      }
      
      final configManager = ConfigManager();
      
      // 根据选项导入配置文件
      if (importTasks) {
        final sourceTaskConfigFile = File('${importDirectory.path}/task_config.json');
        if (await sourceTaskConfigFile.exists()) {
          final taskConfigFile = File('${configManager.getConfigsDirectory().parent.path}/task_config.json');
          await taskConfigFile.writeAsString(await sourceTaskConfigFile.readAsString());
          await configManager.loadTaskConfig(); // 重新加载
        }
      }
      
      if (importTeams) {
        final sourceTeamConfigFile = File('${importDirectory.path}/team_config.json');
        if (await sourceTeamConfigFile.exists()) {
          final teamConfigFile = File('${configManager.getConfigsDirectory().parent.path}/team_config.json');
          await teamConfigFile.writeAsString(await sourceTeamConfigFile.readAsString());
          await configManager.loadTeamConfig(); // 重新加载
        }
      }
      
      if (importThemePacks) {
        final sourceThemePackConfigFile = File('${importDirectory.path}/theme_pack_config.json');
        if (await sourceThemePackConfigFile.exists()) {
          final themePackConfigFile = File('${configManager.getConfigsDirectory().parent.path}/theme_pack_config.json');
          await themePackConfigFile.writeAsString(await sourceThemePackConfigFile.readAsString());
          await configManager.loadThemePackConfig(); // 重新加载
        }
      }
      
      if (importUserConfig) {
        final sourceUserConfigFile = File('${importDirectory.path}/user_config.json');
        if (await sourceUserConfigFile.exists()) {
          final userConfigFile = File('${configManager.getConfigsDirectory().parent.path}/user_config.json');
          await userConfigFile.writeAsString(await sourceUserConfigFile.readAsString());
          await configManager.loadUserConfig(); // 重新加载
        }
      }
      
      logger.d('从目录 $directoryPath 选择性导入配置成功');
    } catch (e) {
      logger.e('从目录 $directoryPath 选择性导入配置失败: $e');
    }
  }

  /// 显示本地更新确认弹窗
  void _showLocalUpdateDialog() async {
    // 检查update文件夹下是否存在lalc文件夹
    final updateDir = await _getUpdateDir();
    final lalcDir = Directory('${updateDir.path}/lalc');
    
    if (!await lalcDir.exists()) {
      // 如果不存在lalc文件夹，显示错误提示
      if (mounted) {
        toastification.show(
          context: context,
          title: Text(S.of(context).lalc_folder_not_exist),
          style: ToastificationStyle.flatColored,
          type: ToastificationType.error,
          autoCloseDuration: const Duration(seconds: 3),
        );
      }
      return;
    }
    
    // 显示确认弹窗
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(S.of(context).confirm_auto_update),
        content: Text(S.of(context).auto_update_warning),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: Text(S.of(context).no_manual_update),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(S.of(context).yes_auto_update),
          ),
        ],
      ),
    );
    
    if (confirm == true) {
      // 用户选择自动更新，执行更新脚本
      _executeUpdateScript();
    } else {
      // 用户选择手动更新，打开下载的update文件夹
      final updateDir = await _getUpdateDir();
      if (await updateDir.exists()) {
        logger.d("要打开:$updateDir");
        await Process.run('explorer', [updateDir.path]);
      }
    }
  }
  
  /// 执行更新脚本
  void _executeUpdateScript() async {
    final updateDir = await _getUpdateDir();
    final lalcDir = Directory('${updateDir.path}/lalc');
    final batFile = File('${lalcDir.path}/update_to.bat');
    
    // 获取项目自身的绝对路径
    String executablePath = Platform.resolvedExecutable;
    String projectDir = path.dirname(path.dirname(executablePath));
    
    if (await batFile.exists()) {
      try {
        // 使用start命令在新窗口中执行bat脚本，这样用户可以看到执行过程
        Process.start('cmd', ['/c', 'start', 'cmd', '/k', batFile.path, lalcDir.path, projectDir]);
        if (mounted) {
          toastification.show(
            context: context,
            title: Text(S.of(context).update_script_executed),
            style: ToastificationStyle.flatColored,
            type: ToastificationType.success,
            autoCloseDuration: const Duration(seconds: 3),
          );
        }
      } catch (e) {
        if (mounted) {
          toastification.show(
            context: context,
            title: Text('${S.of(context).update_script_failed}: $e'),
            style: ToastificationStyle.flatColored,
            type: ToastificationType.error,
            autoCloseDuration: const Duration(seconds: 3),
          );
        }
      }
    } else {
      if (mounted) {
        toastification.show(
          context: context,
          title: Text(S.of(context).update_script_not_found),
          style: ToastificationStyle.flatColored,
          type: ToastificationType.error,
          autoCloseDuration: const Duration(seconds: 3),
        );
      }
    }
  }
  
}

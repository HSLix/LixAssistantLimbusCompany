import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:lalc_frontend/config_manager.dart';

Future<void> printAppDocPath() async {
  try {
    final directory = await getApplicationDocumentsDirectory();
    logger.d('Application Documents Directory: ${directory.path}');
    
    // 检查配置文件是否存在
    final taskConfigFile = File('${directory.path}/task_config.json');
    final teamConfigFile = File('${directory.path}/team_config.json');
    final themePackConfigFile = File('${directory.path}/theme_pack_config.json');
    
    logger.d('Task config file exists: ${await taskConfigFile.exists()}');
    logger.d('Team config file exists: ${await teamConfigFile.exists()}');
    logger.d('Theme pack config file exists: ${await themePackConfigFile.exists()}');
    
    if (await taskConfigFile.exists()) {
      logger.d('Task config content: ${await taskConfigFile.readAsString()}');
    }
    
    if (await teamConfigFile.exists()) {
      logger.d('Team config content: ${await teamConfigFile.readAsString()}');
    }
    
    if (await themePackConfigFile.exists()) {
      logger.d('Theme pack config content: ${await themePackConfigFile.readAsString()}');
    }
  } catch (e) {
    logger.e('Error getting app doc path: $e');
  }
}
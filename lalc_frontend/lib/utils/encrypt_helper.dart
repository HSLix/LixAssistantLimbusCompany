import 'dart:convert';
import 'dart:io';
import 'package:platform_device_id/platform_device_id.dart';
import 'package:logger/logger.dart';

// 初始化logger实例
final _logger = Logger(
  printer: PrettyPrinter(methodCount: 0),
  level: Level.debug,
);

class EncryptHelper {
  /// 获取设备ID - Windows平台使用wmic命令，其他平台使用platform_device_id包
  static Future<String> _getDeviceId() async {
    if (Platform.isWindows) {
      try {
        final result = Process.runSync(
          'wmic', ['csproduct', 'get', 'UUID', '/value'],
          runInShell: true,
        );
        final lines = LineSplitter.split(result.stdout as String);
        for (final line in lines) {
          if (line.startsWith('UUID=')) {
            final uuid = line.substring(5).trim();
            if (uuid.isNotEmpty && !uuid.toUpperCase().startsWith('FFFFFFFF')) {
              return uuid;
            }
          }
        }
      } catch (e) {
        _logger.e('获取设备ID时WMIC命令执行失败: $e');
      }
    }
    
    // 对于非Windows平台或Windows命令失败时，使用platform_device_id
    try {
      final deviceId = await PlatformDeviceId.getDeviceId;
      if (deviceId != null) {
        return deviceId;
      }
    } catch (e) {
      _logger.e('使用platform_device_id获取设备ID失败: $e');
    }
    
    final error = Exception("获取设备 ID 失败");
    _logger.e(error.toString());
    throw error;
  }

  /// 生成XOR密钥
  static Future<List<int>> _getXorKey() async {
    final deviceId = await _getDeviceId();
    final combinedKey = "${deviceId}LALC";
    return combinedKey.codeUnits;
  }

  /// XOR加密/解密字节数据
  static List<int> _xorBytes(List<int> data, List<int> key) {
    final len = key.length;
    return List.generate(data.length, (i) => data[i] ^ key[i % len]);
  }

  /// 加密字符串
  static Future<String> encrypt(String plain) async {
    try {
      final key = await _getXorKey();
      final data = _xorBytes(plain.codeUnits, key);
      return base64.encode(data);
    } catch (e) {
      _logger.e('加密失败: $e');
      final error = Exception('加密失败: $e');
      throw error;
    }
  }

  /// 解密字符串
  static Future<String> decrypt(String cipher) async {
    try {
      final key = await _getXorKey();
      final data = _xorBytes(base64.decode(cipher), key);
      return String.fromCharCodes(data);
    } catch (e) {
      _logger.e('解密失败: $e');
      final error = Exception('解密失败: $e');
      throw error;
    }
  }
}
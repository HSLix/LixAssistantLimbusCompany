import 'dart:io';
import 'package:archive/archive_io.dart';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as path;

/// ZIP助手类，提供文件夹压缩和解压功能
class ZipHelper {
  /// 将指定目录压缩为ZIP文件
  ///
  /// [srcDir] 要压缩的源目录路径
  /// [dstZip] 目标ZIP文件路径
  ///
  /// 返回目标ZIP文件路径
  static Future<String> zipDir({
    required String srcDir,
    required String dstZip,
  }) async {
    return await compute(_zipDirInternal, {'srcDir': srcDir, 'dstZip': dstZip});
  }

  /// 内部ZIP压缩方法，在 isolate 中执行
  static String _zipDirInternal(Map<String, String> params) {
    final srcDir = params['srcDir']!;
    final dstZip = params['dstZip']!;
    
    final encoder = ZipFileEncoder();
    encoder.create(dstZip);
    
    // 添加目录中的每个文件，而不是整个目录
    final sourceDir = Directory(srcDir);
    sourceDir.listSync(recursive: true).forEach((entity) {
      if (entity is File) {
        // 计算相对于源目录的路径
        final relativePath = path.relative(entity.path, from: srcDir);
        encoder.addFile(entity, relativePath);
      }
    });
    
    encoder.close();
    return dstZip;
  }

  /// 将ZIP文件解压到指定目录
  ///
  /// [zipFile] ZIP文件路径
  /// [dstDir] 目标目录路径
  ///
  /// 返回目标目录路径
  static Future<String> unzipTo({
    required String zipFile,
    required String dstDir,
  }) async {
    return await compute(_unzipToInternal, {'zipFile': zipFile, 'dstDir': dstDir});
  }

  /// 内部ZIP解压方法，在 isolate 中执行
  static String _unzipToInternal(Map<String, String> params) {
    final zipFile = params['zipFile']!;
    final dstDir = params['dstDir']!;
    
    // 创建目标目录
    final destination = Directory(dstDir);
    if (!destination.existsSync()) {
      destination.createSync(recursive: true);
    }

    // 读取并解压ZIP文件
    final bytes = File(zipFile).readAsBytesSync();
    final archive = ZipDecoder().decodeBytes(bytes);

    // 解压所有文件和目录
    for (final file in archive) {
      final filename = file.name;
      // 处理路径分隔符，确保在不同平台上都能正确解压
      final normalizedFilename = filename.replaceAll('\\', '/');
      final filePath = path.join(dstDir, normalizedFilename);
      
      // 确保父目录存在
      final fileDir = Directory(path.dirname(filePath));
      if (!fileDir.existsSync()) {
        fileDir.createSync(recursive: true);
      }
      
      if (file.isFile) {
        final data = file.content as List<int>;
        final fileToWrite = File(filePath);
        fileToWrite.createSync(recursive: true);
        fileToWrite.writeAsBytesSync(data);
      } else {
        // 创建目录
        final dir = Directory(filePath);
        dir.createSync(recursive: true);
      }
    }

    return dstDir;
  }
}
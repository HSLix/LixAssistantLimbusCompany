import 'dart:io' show Directory, File;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:lalc_frontend/websocket_manager.dart';
import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:toastification/toastification.dart';
import '../generated/l10n.dart'; // 添加国际化支持
import '../utils/zip_helper.dart'; // 添加ZIP支持

class LogPage extends StatefulWidget {
  const LogPage({super.key});

  @override
  State<LogPage> createState() => _LogPageState();
}

class LogEntry {
  final String timestamp;
  final String level;
  final String message;
  final String? imagePath;

  const LogEntry({
    required this.timestamp,
    required this.level,
    required this.message,
    this.imagePath,
  });
}

// 添加一个新的类来表示UI中的日志条目状态
class LogEntryUiState {
  bool isExpanded;
  
  LogEntryUiState({this.isExpanded = false});
}

// 添加一个辅助函数来创建日志项UI状态
LogEntryUiState _createLogEntryUiState(LogEntry entry) {
  // 有图片的日志项默认展开
  return LogEntryUiState(isExpanded: entry.imagePath != null);
}

class _LogPageState extends State<LogPage> {
  String? _selectedFolder;
  String? _logDirectoryAbsolutePath;
  bool _isLoading = false;
  double _loadingProgress = 0.0; // 添加进度变量
  String? _errorMessage;
  List<LogEntry> _logEntries = [];
  List<LogEntry> _filteredLogEntries = [];
  final Set<String> _selectedLevels = {'INFO', 'WARNING', 'ERROR'};
  bool _showOnlyImageLogs = true; // 默认只显示带图片的日志
  final ScrollController _scrollController = ScrollController();
  
  // 添加搜索相关变量
  String _searchQuery = '';
  final TextEditingController _searchController = TextEditingController();

  // 修改导入日志相关变量，存储完整路径而不是仅仅文件夹名
  final Map<String, String> _importedLogFolders = {};

  // 添加日志项UI状态映射
  final Map<int, LogEntryUiState> _logEntryUiStates = {};

  // 添加分页相关变量
  static const int _pageSize = 50; // 每页显示50条日志
  int _currentPage = 0;
  bool _hasMoreData = true;

  @override
  void initState() {
    super.initState();
    _loadLogFolders();
    
    // 添加滚动监听器以实现无限滚动加载
    _scrollController.addListener(_scrollListener);
  }

  @override
  void dispose() {
    _scrollController.removeListener(_scrollListener);
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollListener() {
    // 当用户滚动到底部附近时加载更多数据
    if (_scrollController.position.extentAfter < 30 && _hasMoreData && !_isLoading) {
      _loadMoreData();
    }
  }

  void _loadMoreData() {
    setState(() {
      _currentPage++;
    });
    _filterLogs(); // 重新过滤以包含更多数据
  }

  void _resetPagination() {
    setState(() {
      _currentPage = 0;
      _hasMoreData = true;
      // 每次重置分页时清空UI状态
      _logEntryUiStates.clear();
    });
  }

  void _filterLogs() {
    setState(() {
      List<LogEntry> filteredEntries = [];
      
      if (_searchQuery.isEmpty) {
        filteredEntries = _logEntries.where((entry) {
          final levelMatches = _selectedLevels.contains(entry.level);
          final imageMatches = !_showOnlyImageLogs || (entry.imagePath != null);
          return levelMatches && imageMatches;
        }).toList();
      } else {
        filteredEntries = _logEntries.where((entry) {
          final matchesLevel = _selectedLevels.contains(entry.level);
          final matchesSearch = entry.message.toLowerCase().contains(_searchQuery.toLowerCase()) ||
              entry.timestamp.contains(_searchQuery) ||
              entry.level.toLowerCase().contains(_searchQuery.toLowerCase());
          final imageMatches = !_showOnlyImageLogs || (entry.imagePath != null);
          return matchesLevel && matchesSearch && imageMatches;
        }).toList();
      }
      
      // 按时间倒序排列（最新的在前面）
      filteredEntries.sort((a, b) {
        return b.timestamp.compareTo(a.timestamp);
      });
      
      // 实现分页
      final totalItems = filteredEntries.length;
      final itemsToShow = (_currentPage + 1) * _pageSize;
      
      if (itemsToShow >= totalItems) {
        _filteredLogEntries = filteredEntries;
        _hasMoreData = false;
      } else {
        _filteredLogEntries = filteredEntries.take(itemsToShow).toList();
        _hasMoreData = true;
      }
      
      // 每次过滤日志时重置UI状态并重新应用默认展开逻辑
      _logEntryUiStates.clear();
      // 为新的过滤结果预创建UI状态
      for (int i = 0; i < _filteredLogEntries.length; i++) {
        _logEntryUiStates[i] = _createLogEntryUiState(_filteredLogEntries[i]);
      }
    });
  }

  void _loadLogFolders() {
    final websocketManager = context.read<WebSocketManager>();
    // 如果没有连接，则自动连接
    if (!websocketManager.isConnected && !websocketManager.isConnecting) {
      // 使用addPostFrameCallback确保不在build过程中调用initialize
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          websocketManager.initialize();
        }
      });
    } else if (websocketManager.isConnected) {
      // 如果已经连接，则直接获取日志文件夹列表
      // 使用addPostFrameCallback确保不在build过程中调用getLogFolders
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          websocketManager.getLogFolders();
        }
      });
    }
  }

  void _refreshLogs() {
    setState(() {
      _selectedFolder = null;
      _logEntries.clear();
    });
    
    final websocketManager = context.read<WebSocketManager>();
    // 使用addPostFrameCallback确保不在build过程中调用方法
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        // 如果没有连接，则自动连接
        if (!websocketManager.isConnected) {
          websocketManager.initialize();
        }
        websocketManager.getLogFolders();
      }
    });
  }

  void _onLevelChanged(String level, bool? isChecked) {
    setState(() {
      if (isChecked == true) {
        _selectedLevels.add(level);
      } else {
        _selectedLevels.remove(level);
      }
      // 更新日志过滤结果
      _resetPagination(); // 重置分页
      _filterLogs();
    });
  }

  // 添加一个新的方法来处理图片日志筛选开关的变化
  void _onShowOnlyImageLogsChanged(bool? value) {
    setState(() {
      _showOnlyImageLogs = value ?? false;
      _resetPagination(); // 重置分页
      _filterLogs();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<WebSocketManager>(
      builder: (context, websocketManager, child) {
        // 连接成功后自动刷新
        if (websocketManager.isConnected && websocketManager.logFolders.isEmpty) {
          // 使用addPostFrameCallback确保在帧渲染完成后执行
          WidgetsBinding.instance.addPostFrameCallback((_) {
            // 再次检查状态以确保组件仍然挂载
            if (mounted) {
              websocketManager.getLogFolders();
            }
          });
        }
        
        // 合并原始日志文件夹和导入的日志文件夹
        final allFolders = [...websocketManager.logFolders, ..._importedLogFolders.keys];
        
        return Column(
          children: [
            // 顶部状态栏和刷新按钮
            Container(
              padding: EdgeInsets.all(8.0),
              decoration: BoxDecoration(
                color: Colors.grey[800],
                border: Border(bottom: BorderSide(color: Colors.grey[600]!)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Icon(
                        websocketManager.isConnected 
                          ? Icons.circle 
                          : (websocketManager.isConnecting 
                              ? Icons.access_time 
                              : Icons.warning),
                        color: websocketManager.isConnected 
                          ? Colors.green 
                          : (websocketManager.isConnecting 
                              ? Colors.orange 
                              : Colors.red),
                        size: 16,
                      ),
                      SizedBox(width: 8),
                      Text(
                        websocketManager.isConnected 
                          ? S.of(context).connected
                          : (websocketManager.isConnecting 
                              ? S.of(context).connecting 
                              : S.of(context).disconnected),
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                        ),
                      ),
                      SizedBox(width: 16),
                      // 添加日志级别选择复选框
                      ...['ERROR', 'WARNING', 'INFO', 'DEBUG'].map((level) {
                        Color color;
                        switch (level) {
                          case 'ERROR':
                            color = Colors.red;
                            break;
                          case 'WARNING':
                            color = Colors.orange;
                            break;
                          case 'INFO':
                            color = Colors.green;
                            break;
                          case 'DEBUG':
                            color = Colors.blue;
                            break;
                          default:
                            color = Colors.white;
                        }
                        
                        return Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Theme(
                              data: Theme.of(context).copyWith(
                                unselectedWidgetColor: Colors.white,
                              ),
                              child: Checkbox(
                                value: _selectedLevels.contains(level),
                                onChanged: (checked) => _onLevelChanged(level, checked),
                                activeColor: color,
                                checkColor: Colors.white,
                              ),
                            ),
                            Text(
                              level, 
                              style: TextStyle(
                                color: Colors.white, 
                                fontSize: 12
                              )
                            ),
                            SizedBox(width: 8),
                          ],
                        );
                      }),
                      // 添加搜索框
                      SizedBox(
                        width: 150,
                        child: TextField(
                          controller: _searchController,
                          style: TextStyle(color: Colors.white, fontSize: 14),
                          decoration: InputDecoration(
                            hintText: S.of(context).search_logs,
                            hintStyle: TextStyle(color: Colors.grey[400], fontSize: 12),
                            filled: true,
                            fillColor: Colors.grey[700],
                            contentPadding: EdgeInsets.symmetric(vertical: 0, horizontal: 8),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(4),
                              borderSide: BorderSide.none,
                            ),
                            prefixIcon: Icon(Icons.search, color: Colors.grey[400], size: 16),
                          ),
                          onChanged: (value) {
                            setState(() {
                              _searchQuery = value;
                              _resetPagination(); // 重置分页
                              _filterLogs();
                            });
                          },
                        ),
                      ),
                      // 添加筛选带图片日志的开关
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Theme(
                            data: Theme.of(context).copyWith(
                              unselectedWidgetColor: Colors.white,
                            ),
                            child: Checkbox(
                              value: _showOnlyImageLogs,
                              onChanged: _onShowOnlyImageLogsChanged,
                              activeColor: Colors.purple,
                              checkColor: Colors.white,
                            ),
                          ),
                          Text(
                            S.of(context).pic_only, 
                            style: TextStyle(
                              color: Colors.white, 
                              fontSize: 12
                            )
                          ),
                          SizedBox(width: 8),
                        ],
                      ),
                    ],
                  ),
                  IconButton(
                    icon: Icon(Icons.refresh, color: Colors.white),
                    onPressed: _refreshLogs,
                    tooltip: S.of(context).refresh,
                  ),
                ],
              ),
            ),
            
            // 主要内容区域
            Expanded(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 左侧日志文件夹列表
                  SizedBox(
                    width: 230,
                    child: Column(
                      children: [
                        Expanded(
                          child: ListView.builder(
                            itemCount: allFolders.length,
                            itemBuilder: (context, index) {
                              final folder = allFolders[index];
                              final isImported = _importedLogFolders.containsKey(folder);
                              final displayFolderName = isImported 
                                  ? folder.replaceFirst('Imported_', '') 
                                  : folder;
                              
                              return ListTile(
                                title: Row(
                                  children: [
                                    Text(
                                      displayFolderName,
                                      style: TextStyle(
                                        color: Colors.white, // 白色文字
                                      ),
                                    ),
                                    // if (isImported) ...[
                                    //   SizedBox(width: 2),
                                    //   Icon(
                                    //     Icons.upload_file,
                                    //     size: 14,
                                    //     color: Colors.grey[400],
                                    //   ),
                                    // ]
                                  ],
                                ),
                                selected: _selectedFolder == folder,
                                onTap: () {
                                  if (isImported) {
                                    _loadImportedLogContent(folder);
                                  } else {
                                    _loadLogContent(folder);
                                  }
                                },
                                // 在右侧添加导入/导出按钮，根据是否是导入的日志显示不同图标
                                trailing: IconButton(
                                  icon: Icon(
                                    isImported ? Icons.upload_file : Icons.download,
                                    color: Colors.white70,
                                  ),
                                  onPressed: () {
                                    if (isImported) {
                                      _importLogFolder();
                                    } else {
                                      _exportLogFolder(folder);
                                    }
                                  },
                                  tooltip: isImported ? S.of(context).reimport_log : S.of(context).export_the_log,
                                ),
                              );
                            },
                          ),
                        ),
                        // 添加导入日志按钮
                        Container(
                          decoration: BoxDecoration(
                            border: Border(top: BorderSide(color: Colors.grey[600]!)),
                          ),
                          child: ListTile(
                            title: Text(
                              S.of(context).import_the_log,
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: Colors.white70,
                                fontSize: 14,
                              ),
                            ),
                            onTap: _importLogFolder,
                          ),
                        ),
                      ],
                    ),
                  ),
                  
                  // 分割线
                  VerticalDivider(
                    width: 1,
                    thickness: 1,
                    color: Colors.grey[600],
                  ),
                  
                  // 右侧日志内容显示区域
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: _selectedFolder == null
                        ? Center(
                            child: Text(
                              S.of(context).choose_a_log,
                              style: TextStyle(color: Colors.white70),
                            ),
                          )
                        : Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                child: _buildLogContent(),
                              ),
                            ],
                          ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  // 获取日志文件夹的绝对路径并读取日志内容
  void _loadLogContent(String folderName) async {
    debugPrint('开始加载日志内容，文件夹: $folderName');
    
    setState(() {
      _selectedFolder = folderName;
      _isLoading = true;
      _loadingProgress = 0.0; // 重置进度
      _errorMessage = null;
      _logEntries.clear();
      _resetPagination(); // 重置分页
    });

    final websocketManager = context.read<WebSocketManager>();
    
    try {
      final response = await websocketManager.getLogAddress(folderName);
      debugPrint('收到响应: $response');
      
      if (response == null) {
        if (mounted) {
          setState(() {
            _isLoading = false;
            _errorMessage = '获取日志地址失败：无响应';
          });
        }
        return;
      }

      
      // 安全地获取 status 字段
      final statusObj = response['status'];
      if (statusObj is! String) {
        debugPrint('响应格式错误: status字段缺失或类型不正确，status类型为: ${statusObj.runtimeType}');
        if (mounted) {
          setState(() {
            _isLoading = false;
            _errorMessage = '响应格式错误: status字段缺失或类型不正确';
          });
        }
        return;
      }
      
      final String status = statusObj;
      debugPrint('响应状态: $status');
      
      if (status == 'success') {
        // 安全地获取 type 字段
        final typeObj = response['type'];
        final String responseType = typeObj is String ? typeObj : '';
        debugPrint('响应类型: $responseType');
        
        if (responseType == 'log_address') {
          // 安全地获取 address 字段
          final addressObj = response['address'];
          if (addressObj is! String) {
            debugPrint('响应格式错误: address字段缺失或类型不正确，address类型为: ${addressObj.runtimeType}');
            if (mounted) {
              setState(() {
                _isLoading = false;
                _errorMessage = '响应格式错误: address字段缺失或类型不正确';
              });
            }
            return;
          }
          
          final String address = addressObj;
          debugPrint('获取到日志地址: $address');
          
          try {
            // 读取日志文件内容
            final logDir = Directory(address);
            final logFile = File('${logDir.path}/run.log');
            debugPrint('尝试读取日志文件: ${logFile.path}');
            
            if (await logFile.exists()) {
              debugPrint('日志文件存在，开始读取内容');

              // 先获取文件总行数用于进度计算
              int totalLines = 0;
              try {
                final linesStream = logFile.openRead().transform(utf8.decoder).transform(const LineSplitter());
                await for (var line in linesStream) {
                  if (line.trim().isNotEmpty) {
                    totalLines++;
                  }
                }
              } catch (e) {
                debugPrint('计算总行数时出错: $e');
              }
              
              debugPrint('日志文件总行数: $totalLines');
              
              // 重新打开文件流进行实际读取
              final linesStream = logFile.openRead().transform(utf8.decoder).transform(const LineSplitter());
              final List<LogEntry> entries = [];
              int processedLines = 0;
              // ignore: unused_local_variable
              int parsedCount = 0;
              
              await for (var line in linesStream) {
                if (!mounted) break; // 组件已销毁则退出
                
                if (line.trim().isEmpty) continue;
                
                processedLines++;
                
                // 解析日志行
                final entry = _parseLogLine(line);
                if (entry != null) {
                  entries.add(entry);
                  parsedCount++;
                }
                
                // 每处理1000行更新一次进度和UI，避免界面冻结
                if (processedLines % 1000 == 0) {
                  if (mounted) {
                    setState(() {
                      _logEntries = List.from(entries);
                      _filterLogs();
                      // 更新进度（如果能获取到总行数）
                      if (totalLines > 0) {
                        _loadingProgress = processedLines / totalLines;
                        // 限制进度不超过90%，因为还有后续处理
                        if (_loadingProgress > 0.9) _loadingProgress = 0.9;
                      }
                    });
                  }
                }
              }
              
              debugPrint('解析出 ${entries.length} 条有效日志');
              
              if (mounted) {
                setState(() {
                  _isLoading = false;
                  _loadingProgress = 1.0; // 完成
                  _logEntries = entries;
                  _logDirectoryAbsolutePath = address; // 保存日志目录的绝对路径
                  _filterLogs(); // 添加这一行来更新过滤后的日志列表
                  debugPrint('成功更新UI状态，日志条目数: ${entries.length}');
                });
              }
            } else {
              debugPrint('日志文件不存在: ${logFile.path}');
              if (mounted) {
                setState(() {
                  _isLoading = false;
                  _errorMessage = '日志文件不存在: run.log';
                });
              }
            }
          } catch (e, stackTrace) {
            debugPrint('读取日志文件时发生异常: $e\nStackTrace: $stackTrace');
            if (mounted) {
              setState(() {
                _isLoading = false;
                _errorMessage = '读取日志文件失败: $e';
              });
            }
          }
        } else {
          // 处理未知的响应类型
          debugPrint('收到未知响应类型: $responseType');
          if (mounted) {
            setState(() {
              _isLoading = false;
              _errorMessage = '收到未知响应类型: $responseType';
            });
          }
        }
      } else {
        // 处理错误状态
        final messageObj = response['message'];
        final String message = messageObj is String ? messageObj : '未知错误';
        debugPrint('获取日志地址失败: $message');
        if (mounted) {
          setState(() {
            _isLoading = false;
            _errorMessage = '获取日志地址失败: $message';
          });
        }
      }
    } catch (e, stackTrace) {
      // 处理解析错误
      debugPrint('处理日志响应时发生异常: $e\nStackTrace: $stackTrace');
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = '处理响应时发生错误: $e';
        });
      }
    }
  }

  // 解析单行日志
  LogEntry? _parseLogLine(String line) {
    // 匹配日志格式: timestamp | level | message [| IMAGE:image_path]
    final RegExp logRegex = RegExp(
      r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s*\|\s*(\w+)\s*\|\s*((?:(?!\s*\|\s*IMAGE:).)*?)(?:\s*\|\s*IMAGE:(.+))?$'
    );
    line = line.trimRight();
    final match = logRegex.firstMatch(line);

    if (match != null) {
      final timestamp = match.group(1) ?? '';
      final level = match.group(2) ?? '';
      
      // 对消息部分进行额外处理，去除首尾空格
      String message = (match.group(3) ?? '').trim();
      
      // 获取图片路径（可能为null）
      final imagePath = match.group(4)?.trim(); 

      return LogEntry(
        timestamp: timestamp,
        level: level,
        message: message,
        imagePath: imagePath,
      );
    } else {
      debugPrint('解析失败，无法匹配日志行: $line');
    }

    return null;
  }


  /// 尝试解析并格式化消息中的JSON内容
  String _formatJsonInMessage(String message) {
    try {
      // 首先尝试在整个消息上解析JSON（适用于整个消息就是一个JSON对象的情况）
      var decodedJson = jsonDecode(message);
      
      // 使用 JsonEncoder 将 Dart 对象转回格式化的 JSON 字符串
      var encoder = JsonEncoder.withIndent('  '); // 使用 2 个空格缩进
      return encoder.convert(decodedJson);
    } catch (e) {
      // 如果整个消息不是JSON，则尝试查找并格式化消息中的JSON片段
      try {
        // 查找以{开头和}结尾的JSON对象
        RegExp objectRegex = RegExp(r'\{[^{}]*\}'); // 简单对象匹配
        message = message.replaceAllMapped(objectRegex, (Match match) {
          try {
            final jsonString = match[0]!;
            var decodedJson = jsonDecode(jsonString);
            var encoder = JsonEncoder.withIndent('  ');
            return encoder.convert(decodedJson);
          } catch (e) {
            return match[0]!;
          }
        });
        
        // 查找以[开头和]结尾的JSON数组
        RegExp arrayRegex = RegExp(r'\[[^\[\]]*\]'); // 简单数组匹配
        message = message.replaceAllMapped(arrayRegex, (Match match) {
          try {
            final jsonString = match[0]!;
            var decodedJson = jsonDecode(jsonString);
            var encoder = JsonEncoder.withIndent('  ');
            return encoder.convert(decodedJson);
          } catch (e) {
            return match[0]!;
          }
        });
        
        return message;
      } catch (e) {
        // 如果处理失败，返回原始消息
        return message;
      }
    }
  }

  Widget _buildLogContent() {
    if (_isLoading) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            SizedBox(
              width: 50,
              height: 50,
              child: CircularProgressIndicator(
                strokeWidth: 4,
                value: _loadingProgress > 0 ? _loadingProgress : null, // 根据进度显示具体数值或旋转动画
              ),
            ),
            SizedBox(height: 16),
            Text(
              _loadingProgress > 0 
                ? '${S.of(context).loading} (${(_loadingProgress * 100).toStringAsFixed(1)}%)' 
                : S.of(context).loading,
              style: TextStyle(
                color: Colors.white70,
                fontSize: 16,
              ),
            ),
          ],
        ),
      );
    }

    if (_errorMessage != null) {
      return Center(
        child: Text(
          _errorMessage!,
          style: TextStyle(color: Colors.red),
        ),
      );
    }

    return Scrollbar(
      thumbVisibility: true,
      controller: _scrollController,
      child: _filteredLogEntries.isEmpty
        ? Center(
            child: Text(
              S.of(context).no_logs_match_criteria,
              style: TextStyle(
                color: Colors.white70,
                fontSize: 16,
              ),
            ),
          )
        : ListView.builder(
            controller: _scrollController,
            itemCount: _filteredLogEntries.length + (_hasMoreData ? 1 : 0), // 添加加载更多项
            cacheExtent: 5000, // 增加缓存范围
            itemBuilder: (context, index) {
              // 如果是最后一项且还有更多数据，显示加载指示器
              if (_hasMoreData && index == _filteredLogEntries.length) {
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(8.0),
                    child: CircularProgressIndicator(),
                  ),
                );
              }
          
          final entry = _filteredLogEntries[index];
          
          // 获取或创建该日志项的UI状态
          final uiState = _logEntryUiStates.putIfAbsent(index, () => _createLogEntryUiState(entry));
          
          // 根据级别设置颜色
          Color textColor;
          switch (entry.level.toUpperCase()) {
            case 'ERROR':
              textColor = Colors.red;
              break;
            case 'WARNING':
              textColor = Colors.orange;
              break;
            case 'INFO':
              textColor = Colors.green;
              break;
            case 'DEBUG':
              textColor = Colors.blue;
              break;
            default:
              textColor = Colors.white;
          }

          // 截取消息的前100个字符用于折叠状态显示
          final isLongMessage = entry.message.length > 100;
          final displayedMessage = uiState.isExpanded 
              ? entry.message 
              : '${entry.message.substring(0, isLongMessage ? 100 : entry.message.length)}${isLongMessage ? '...' : ''}';

          List<Widget> widgets = [
            GestureDetector(
              onTap: () {
                setState(() {
                  uiState.isExpanded = !uiState.isExpanded;
                });
              },
              child: Container(
                // 移除固定的height，使用padding来控制间距
                padding: EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 时间戳
                    SizedBox(
                      width: 120,
                      child: Text(
                        entry.timestamp,
                        style: TextStyle(
                          color: Colors.grey[400],
                          fontSize: 12,
                        ),
                      ),
                    ),
                    
                    SizedBox(width: 8),
                    
                    // 日志级别
                    SizedBox(
                      width: 70,
                      child: Text(
                        '[${entry.level}]',
                        style: TextStyle(
                          color: textColor,
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                        ),
                      ),
                    ),
                    
                    SizedBox(width: 8),
                    
                    // 日志消息
                    Expanded(
                      child: Text(
                        uiState.isExpanded 
                            ? _formatJsonInMessage(entry.message) 
                            : displayedMessage,
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                        ),
                        overflow: TextOverflow.ellipsis,
                        maxLines: uiState.isExpanded ? null : 2,
                      ),
                    ),
                    
                    // 如果有图片路径，显示图片图标
                    if (entry.imagePath != null) ...[
                      SizedBox(width: 8),
                      Icon(
                        Icons.image,
                        color: Colors.purple,
                        size: 16,
                      ),
                    ],
                    
                    // 如果消息很长，添加展开/折叠图标
                    if (isLongMessage) ...[
                      SizedBox(width: 8),
                      Icon(
                        uiState.isExpanded ? Icons.expand_less : Icons.expand_more,
                        color: Colors.grey,
                        size: 16,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ];

          // 如果有图片路径，则在日志项下方单独显示图片
          if (entry.imagePath != null && _logDirectoryAbsolutePath != null) {
            final imageFile = File('$_logDirectoryAbsolutePath/${entry.imagePath}');
            widgets.add(
              Padding(
                padding: const EdgeInsets.only(left: 16.0, right: 16.0, bottom: 16.0),
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    return Image.file(
                      imageFile,
                      width: constraints.maxWidth,
                      fit: BoxFit.contain,
                      errorBuilder: (context, error, stackTrace) {
                        return Container(
                          width: constraints.maxWidth,
                          height: 200,
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.red),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.broken_image,
                                color: Colors.red,
                                size: 48,
                              ),
                              SizedBox(height: 8),
                              Text(
                                S.of(context).image_load_failed,
                                style: TextStyle(color: Colors.red),
                              ),
                              Text(
                                '${S.of(context).path}: $_logDirectoryAbsolutePath/${entry.imagePath}',
                                style: TextStyle(color: Colors.grey),
                                textAlign: TextAlign.center,
                              ),
                            ],
                          ),
                        );
                      },
                    );
                  }
                ),
              ),
            );
          }

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: widgets,
          );
        },
      ),
    );
  }

  // 添加导入日志的方法
  void _importLogFolder() async {
    try {
      // 使用文件选择器让用户选择ZIP文件
      final result = await FilePicker.platform.pickFiles(
        dialogTitle: S.of(context).please_select_log_folder,
        type: FileType.custom,
        allowedExtensions: ['zip'],
      );
      
      if (result == null) {
        // 用户取消了操作
        return;
      }
      
      // 显示导入中弹窗
      late BuildContext dialogContext;
      if (!mounted) return;
      final dialog = AlertDialog(
        content: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(width: 20),
            Text(S.of(context).importing_logs),
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
      
      final selectedFile = File(result.files.single.path!);
      
      // 解压ZIP文件到临时目录
      final tempDir = await getTemporaryDirectory();
      final tempUnzipDir = Directory('${tempDir.path}/unzipped_log_${DateTime.now().millisecondsSinceEpoch}');
      await tempUnzipDir.create(recursive: true);
      
      try {
        await ZipHelper.unzipTo(zipFile: selectedFile.path, dstDir: tempUnzipDir.path);
      } catch (e) {
        if (mounted) {
          toastification.show(
            context: context,
            title: const Text('解压失败，可能不是合法 ZIP'),
            style: ToastificationStyle.flatColored,
            type: ToastificationType.error,
            autoCloseDuration: const Duration(seconds: 3),
          );
        }
        
        // 清理临时目录
        await tempUnzipDir.delete(recursive: true);
        
        // 关闭导入中弹窗
        if (mounted && Navigator.canPop(dialogContext)) {
          Navigator.pop(dialogContext);
        }
        
        return;
      }
      
      // 检查解压后的目录是否包含 run.log 文件和 images 文件夹
      final runLogFile = File('${tempUnzipDir.path}/run.log');
      final imagesDir = Directory('${tempUnzipDir.path}/images');
      
      if (!await runLogFile.exists() || !await imagesDir.exists()) {
        if (mounted) {
          toastification.show(
            context: context,
            title: Text(S.of(context).invalid_log_folder),
            style: ToastificationStyle.flatColored,
            type: ToastificationType.error,
            autoCloseDuration: const Duration(seconds: 3),
          );
        }
        
        // 清理临时目录
        await tempUnzipDir.delete(recursive: true);
        
        // 关闭导入中弹窗
        if (mounted && Navigator.canPop(dialogContext)) {
          Navigator.pop(dialogContext);
        }
        
        return;
      }
      
      // 获取文件夹名称并添加到导入的日志文件夹列表
      final folderName = path.basenameWithoutExtension(selectedFile.path);
      final uniqueFolderName = 'Imported_$folderName';
      
      setState(() {
        _importedLogFolders[uniqueFolderName] = tempUnzipDir.path;
      });
      
      if (mounted) {
        toastification.show(
          context: context,
          title: Text(S.of(context).log_folder_import_success),
          style: ToastificationStyle.flatColored,
          type: ToastificationType.success,
          autoCloseDuration: const Duration(seconds: 3),
        );
      }
      
      // 关闭导入中弹窗
      if (mounted && Navigator.canPop(dialogContext)) {
        Navigator.pop(dialogContext);
      }
    } catch (e) {
      // 关闭导入中弹窗（如果还存在）
      final navigator = Navigator.of(context);
      if (navigator.canPop()) {
        navigator.pop();
      }
      
      
      debugPrint('导入日志文件夹时出错: $e');
      if (mounted) {
        toastification.show(
          context: context,
          title: Text('${S.of(context).import_failed}: $e'),
          style: ToastificationStyle.flatColored,
          type: ToastificationType.error,
          autoCloseDuration: const Duration(seconds: 3),
        );
      }
    }
  }

  // 添加导出日志文件夹的方法
  void _exportLogFolder(String folderName) async {
    try {
      // 获取日志文件夹的源路径
      final websocketManager = context.read<WebSocketManager>();
      final response = await websocketManager.getLogAddress(folderName);
      
      if (response == null || response['status'] != 'success' || response['type'] != 'log_address') {
        if (mounted) {
          toastification.show(
            context: context,
            title: Text(S.of(context).cannot_get_log_folder_path),
            style: ToastificationStyle.flatColored,
            type: ToastificationType.error,
            autoCloseDuration: const Duration(seconds: 3),
          );
        }
        return;
      }
      
      final sourcePath = response['address'] as String;
      final sourceDir = Directory(sourcePath);
      
      if (!await sourceDir.exists()) {
        if (mounted) {
          toastification.show(
            context: context,
            title: Text(S.of(context).source_log_folder_not_exist),
            style: ToastificationStyle.flatColored,
            type: ToastificationType.error,
            autoCloseDuration: const Duration(seconds: 3),
          );
        }
        return;
      }
      
      // 使用文件选择器让用户选择保存位置和文件名
      final savePath = await FilePicker.platform.saveFile(
        dialogTitle: S.of(context).please_select_save_location,
        fileName: '$folderName.zip',
        type: FileType.custom,
        allowedExtensions: ['zip'],
      );
      
      if (savePath == null) {
        // 用户取消了操作
        return;
      }
      
      // 显示导出中弹窗
      late BuildContext dialogContext;
      final dialog = AlertDialog(
        content: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(width: 20),
            Text(S.of(context).exporting_logs),
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
      final exportTempDir = Directory('${tempDir.path}/export_log_${DateTime.now().millisecondsSinceEpoch}');
      await exportTempDir.create(recursive: true);
      
      // 复制日志文件夹内容到临时目录
      await _copyDirectory(sourceDir, exportTempDir);
      
      // 添加导出LALC/logs目录
      try {
        final appDocDir = await getApplicationDocumentsDirectory();
        final lalcLogsDir = Directory('${appDocDir.path}/LALC/logs');
        
        if (await lalcLogsDir.exists()) {
          final targetLalcLogsDir = Directory('${exportTempDir.path}/LALC/logs');
          await _copyDirectory(lalcLogsDir, targetLalcLogsDir);
        }
      } catch (e, stackTrace) {
        debugPrint('导出LALC日志时出错: $e\nStack trace: $stackTrace');
        // 即使LALC日志导出失败，也不应该中断主流程
      }
      
      // 创建ZIP文件（现在在后台线程执行）
      await ZipHelper.zipDir(srcDir: exportTempDir.path, dstZip: savePath);
      
      // 清理临时目录
      await exportTempDir.delete(recursive: true);
      
      // 关闭导出中弹窗
      if (mounted && Navigator.canPop(dialogContext)) {
        Navigator.pop(dialogContext);
      }
      
      if (mounted) {
        toastification.show(
          context: context,
          title: Text(S.of(context).log_folder_export_success),
          style: ToastificationStyle.flatColored,
          type: ToastificationType.success,
          autoCloseDuration: const Duration(seconds: 3),
        );
      }
    } catch (e, stackTrace) {
      // 关闭导出中弹窗（如果还存在）
      try {
        final navigator = Navigator.of(context);
        if (navigator.canPop()) {
          navigator.pop();
        }
      } catch (e) {
        // 忽略导航错误
      }
      
      debugPrint('导出日志文件夹时出错: $e\nStack trace: $stackTrace');
      if (mounted) {
        toastification.show(
          context: context,
          title: Text('${S.of(context).export_failed}: $e'),
          style: ToastificationStyle.flatColored,
          type: ToastificationType.error,
          autoCloseDuration: const Duration(seconds: 3),
        );
      }
    }
  }
  
  // 辅助方法：复制整个目录
  Future<void> _copyDirectory(Directory source, Directory target) async {
    await target.create(recursive: true);
    
    await for (final entity in source.list()) {
      final newPath = path.join(target.path, path.basename(entity.path));
      
      if (entity is Directory) {
        await _copyDirectory(entity, Directory(newPath));
      } else if (entity is File) {
        await entity.copy(newPath);
      }
    }
  }

  // 加载导入的日志内容
  void _loadImportedLogContent(String folderName) async {
    debugPrint('开始加载导入的日志内容，文件夹: $folderName');
    
    setState(() {
      _selectedFolder = folderName;
      _isLoading = true;
      _loadingProgress = 0.0; // 重置进度
      _errorMessage = null;
      _logEntries.clear();
    });

    try {
      // 从_importedLogFolders映射中获取实际路径
      final actualPath = _importedLogFolders[folderName];
      if (actualPath == null) {
        if (mounted) {
          setState(() {
            _isLoading = false;
            _errorMessage = '找不到日志文件夹路径';
          });
        }
        return;
      }
      
      final logDir = Directory(actualPath);
      final logFile = File('${logDir.path}/run.log');
      debugPrint('尝试读取日志文件: ${logFile.path}');
      
      if (await logFile.exists()) {
        debugPrint('日志文件存在，开始读取内容');
        
        // 先获取文件总行数用于进度计算
        int totalLines = 0;
        try {
          final linesStream = logFile.openRead().transform(utf8.decoder).transform(const LineSplitter());
          await for (var line in linesStream) {
            if (line.trim().isNotEmpty) {
              totalLines++;
            }
          }
        } catch (e) {
          debugPrint('计算总行数时出错: $e');
        }
        
        debugPrint('日志文件总行数: $totalLines');
        
        // 重新打开文件流进行实际读取
        final linesStream = logFile.openRead().transform(utf8.decoder).transform(const LineSplitter());
        final List<LogEntry> entries = [];
        int processedLines = 0;
        // ignore: unused_local_variable
        int parsedCount = 0;
        
        await for (var line in linesStream) {
          if (!mounted) break; // 组件已销毁则退出
          
          if (line.trim().isEmpty) continue;
          
          processedLines++;
          
          // 解析日志行
          final entry = _parseLogLine(line);
          if (entry != null) {
            entries.add(entry);
            parsedCount++;
          }
          
          // 每处理1000行更新一次进度和UI，避免界面冻结
          if (processedLines % 1000 == 0) {
            if (mounted) {
              setState(() {
                _logEntries = List.from(entries);
                _filterLogs();
                // 更新进度（如果能获取到总行数）
                if (totalLines > 0) {
                  _loadingProgress = processedLines / totalLines;
                  // 限制进度不超过90%，因为还有后续处理
                  if (_loadingProgress > 0.9) _loadingProgress = 0.9;
                }
              });
            }
          }
        }
        
        debugPrint('解析出 ${entries.length} 条有效日志');
        
        if (mounted) {
          setState(() {
            _isLoading = false;
            _loadingProgress = 1.0; // 完成
            _logEntries = entries;
            _logDirectoryAbsolutePath = logDir.path; // 保存日志目录的绝对路径
            _filterLogs(); // 添加这一行来更新过滤后的日志列表
            debugPrint('成功更新UI状态，日志条目数: ${entries.length}');
          });
        }
      } else {
        debugPrint('日志文件不存在: ${logFile.path}');
        if (mounted) {
          setState(() {
            _isLoading = false;
            _errorMessage = '日志文件不存在: run.log';
          });
        }
      }
    } catch (e, stackTrace) {
      debugPrint('读取日志文件时发生异常: $e\nStackTrace: $stackTrace');
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = '读取日志文件失败: $e';
        });
      }
    }
  }
}

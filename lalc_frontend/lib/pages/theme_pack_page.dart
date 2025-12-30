import 'package:flutter/material.dart';
import 'package:lalc_frontend/main.dart';
import 'package:lalc_frontend/config_manager.dart';
import 'package:lalc_frontend/websocket_manager.dart';
import 'package:flutter/services.dart';
import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import '../generated/l10n.dart';

// 排序选项枚举
enum SortOption { 
  name, 
  weight 
}

class ThemePackPage extends StatefulWidget {
  const ThemePackPage({super.key});

  @override
  ThemePackPageState createState() => ThemePackPageState();
}

class ThemePackPageState extends State<ThemePackPage> {
  // 存储从 assets/theme_packs 中获取的图片文件列表
  List<String> imageNames = [];
  List<int> weights = [];
  
  // 添加 ConfigManager 实例作为成员变量
  late ConfigManager configManager;
  
  // 添加搜索和排序相关变量
  String searchQuery = '';
  SortOption sortOption = SortOption.weight;
  
  // 添加搜索控制器
  TextEditingController searchController = TextEditingController();
  
  // 存储筛选和排序后的主题包列表
  List<Map<String, dynamic>> filteredAndSortedThemes = [];

  // 存储权重输入控制器列表
  List<TextEditingController> weightControllers = [];
  
  // 记录当前正在编辑的TextField索引
  int currentlyEditingIndex = -1;
  
  // 添加图片根地址变量
  String? _imgRootAddress;

  @override
  void initState() {
    super.initState();
    // 初始化 ConfigManager 实例
    configManager = ConfigManager();
    _loadImages();
    
    // 获取图片地址
    _getImageAddress();
  }

  @override
  void dispose() {
    searchController.dispose();
    // 释放所有权重控制器
    for (var controller in weightControllers) {
      controller.dispose();
    }
    super.dispose();
  }

  // 从 assets/theme_packs 动态加载图片文件
  Future<void> _loadImages() async {
    try {
      // 获取所有 asset 文件清单
      final manifestContent = await rootBundle.loadString('AssetManifest.json');
      
      // 解析 JSON 内容
      final Map<String, dynamic> manifestMap = json.decode(manifestContent);
      
      // 筛选出 theme_packs 目录下的所有图片文件
      final List<String> themePackAssets = manifestMap.keys
          .where((key) => key.startsWith('assets/theme_packs/'))
          .toList();
      
      // 提取文件名部分
      final List<String> fileNames = themePackAssets
          .map((path) => path.split('/').last)
          .toList();
      
      setState(() {
        imageNames = fileNames;
        // 从配置管理器加载权重
        _loadWeightsFromManager();
        // 初始化筛选和排序后的列表
        _updateFilteredAndSortedThemes();
      });
    } catch (e) {
      debugPrint('Error loading theme packs: $e');
      // 如果出现异常，使用空列表
      setState(() {
        imageNames = [];
        weights = [];
        weightControllers = []; // 清空控制器列表
        // 初始化筛选和排序后的列表
        _updateFilteredAndSortedThemes();
      });
    }
  }
  
  // 从配置管理器加载权重
  void _loadWeightsFromManager() {
    weights = List.generate(imageNames.length, (index) {
      final imageName = imageNames[index];
      // 去除.png后缀以匹配配置管理器中的键
      final cleanImageName = imageName.endsWith('.png') ? imageName.substring(0, imageName.length - 4) : imageName;
      return configManager.themePackWeights[cleanImageName] ?? 10; // 默认权重为10
    });
    
    // 初始化权重控制器列表
    weightControllers = List.generate(
      imageNames.length, 
      (index) => TextEditingController(text: weights[index].toString())
    );
  }
  
  // 保存权重到配置管理器
  void _saveWeightsToManager() {
    for (int i = 0; i < imageNames.length; i++) {
      // 去除.png后缀以匹配配置管理器中的键
      final cleanImageName = imageNames[i].endsWith('.png') ? imageNames[i].substring(0, imageNames[i].length - 4) : imageNames[i];
      configManager.themePackWeights[cleanImageName] = weights[i];
    }
    configManager.saveThemePackConfig();
  }

  // 更新权重
  void updateWeight(int index, String value) {
    final int? newWeight = int.tryParse(value);
    if (newWeight != null && newWeight >= 0 && newWeight <= 999) {
      setState(() {
        weights[index] = newWeight;
        // 更新筛选和排序后的列表
        _updateFilteredAndSortedThemes();
        // 保存到配置管理器
        _saveWeightsToManager();
      });
    }
  }
  
  // 根据搜索条件和排序选项过滤和排序主题包
  void _updateFilteredAndSortedThemes() {
    // 创建包含名称和权重的映射列表
    List<Map<String, dynamic>> themes = List.generate(
      imageNames.length, 
      (index) => {
        'name': imageNames[index],
        'weight': weights[index],
        'index': index,
      }
    );
    
    // 根据搜索查询过滤（模仿TeamConfig中的搜索方式）
    if (searchQuery.isNotEmpty) {
      themes = themes.where((theme) => 
        theme['name'].toLowerCase().contains(searchQuery.toLowerCase())
      ).toList();
    }
    
    // 根据排序选项排序
    switch (sortOption) {
      case SortOption.name:
        themes.sort((a, b) => a['name'].compareTo(b['name']));
        break;
      case SortOption.weight:
        themes.sort((a, b) => b['weight'].compareTo(a['weight'])); // 降序排列
        break;
    }
    
    // 更新筛选和排序后的列表
    filteredAndSortedThemes = themes;
  }
  
  // 获取图片地址
  Future<void> _getImageAddress() async {
    try {
      final wsManager = WebSocketManager();
      wsManager.initialize();
      final address = await wsManager.getImgAddress();
      if (address != null) {
        setState(() {
          _imgRootAddress = address;
        });
      }
    } catch (e) {
      debugPrint('获取图片地址失败: $e');
    }
  }
  
  // 构建主题包图片路径
  String _getThemePackImagePath(String imageName) {
    if (_imgRootAddress != null) {
      return '$_imgRootAddress/theme_packs/$imageName';
    }
    // Fallback to assets
    return 'assets/theme_packs/$imageName';
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        // 当用户点击页面其他地方时，提交当前正在编辑的TextField
        if (currentlyEditingIndex != -1 && weightControllers.length > currentlyEditingIndex) {
          updateWeight(currentlyEditingIndex, weightControllers[currentlyEditingIndex].text);
          currentlyEditingIndex = -1;
        }
      },
      child: Scaffold(
        body: Column(
        children: [
          // 添加搜索和排序控件行
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                // 搜索框（模仿TeamConfig中的搜索框）
                Expanded(
                  flex: 3,
                  child: TextField(
                    controller: searchController,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      labelText: S.of(context).search_theme_pack,
                      labelStyle: const TextStyle(color: Colors.white),
                      filled: true,
                      fillColor: Colors.grey[700],
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                    onChanged: (query) {
                      setState(() {
                        searchQuery = query;
                        // 更新筛选和排序后的列表
                        _updateFilteredAndSortedThemes();
                      });
                    },
                  ),
                ),
                const SizedBox(width: 10,),
                // 排序下拉框
                DropdownButton<SortOption>(
                  value: sortOption,
                  dropdownColor: const Color(0xFF333333),
                  underline: Container(),
                  items: [
                    DropdownMenuItem(
                      value: SortOption.weight,
                      child: Text(
                        S.of(context).weight,
                        style: const TextStyle(color: Colors.white),
                      ),
                    ),
                    DropdownMenuItem(
                      value: SortOption.name,
                      child: Text(
                        S.of(context).alphabetical,
                        style: const TextStyle(color: Colors.white),
                      ),
                    ),
                  ],
                  onChanged: (value) {
                    if (value != null) {
                      setState(() {
                        sortOption = value;
                        // 更新筛选和排序后的列表
                        _updateFilteredAndSortedThemes();
                      });
                    }
                  },
                ),
              ],
            ),
          ),
          // 主题包网格
          Expanded(
            child: imageNames.isEmpty
              ? Center(
                  child: Text(
                    S.of(context).no_theme_packs,
                    style: const TextStyle(color: Colors.grey, fontSize: 16),
                  ),
                )
              : LayoutBuilder(
                  builder: (_, constraints) {
                    final double cellWidth = (constraints.maxWidth - 2 * 10) / 3;
                    const double maxDesiredHeight = 350; // 增加网格项高度
                    final double fixedHeight = math.min(
                      maxDesiredHeight,
                      cellWidth / 0.5, // 保持宽高比 170x330 ≈ 0.515
                    );
                    
                    return GridView.builder(
                      padding: const EdgeInsets.all(10),
                      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 3, 
                        crossAxisSpacing: 10, // 水平间距
                        mainAxisSpacing: 10, // 垂直间距
                        mainAxisExtent: fixedHeight, // 使用固定高度而非宽高比
                      ),
                      itemCount: filteredAndSortedThemes.length, // 使用筛选和排序后的列表长度
                      itemBuilder: (context, index) {
                        // 使用筛选和排序后的列表数据
                        final theme = filteredAndSortedThemes[index];
                        final imageName = theme['name'];
                        final weight = theme['weight'];
                        final originalIndex = theme['index']; // 原始索引用于更新权重
                        
                        final isHighWeight = weight > 10;

                        // 为每个文本框创建独立的 FocusNode
                        final focusNode = FocusNode();

                        // 监听焦点获取事件，记录当前正在编辑的索引
                        focusNode.addListener(() {
                          if (focusNode.hasFocus) {
                            setState(() {
                              currentlyEditingIndex = originalIndex;
                            });
                          }
                        });

                        return Container(
                          decoration: BoxDecoration(
                            border: Border.all(
                              color: isHighWeight ? msBlue : Colors.grey, // 权重大于 10 时边缘为 msBlue
                              width: 2,
                            ),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            crossAxisAlignment: CrossAxisAlignment.center,
                            children: [
                              // 图片
                              Image.asset(
                                _getThemePackImagePath(imageName),
                                width: 150,
                                height: fixedHeight * 0.7,
                                fit: BoxFit.cover,
                                errorBuilder: (context, error, stackTrace) {
                                  // 如果网络图片加载失败，回退到assets
                                  return Image.asset(
                                    'assets/theme_packs/$imageName',
                                    width: 150,
                                    height: fixedHeight * 0.7,
                                    fit: BoxFit.cover,
                                  );
                                },
                              ),
                              const SizedBox(height: 2),
                              // 图片名字
                              Text(
                                imageName.replaceAll('.png', '').replaceAll('_', ' '), // 格式化图片名字
                                style: const TextStyle(
                                  fontSize: 16,
                                  color: Colors.white,
                                ),
                              ),
                              const SizedBox(height: 2),
                              // 权重输入框
                              Flexible(
                                child: 
                                  Focus(
                                    onFocusChange: (hasFocus) {
                                      if (hasFocus) {
                                        // 当前TextField获得焦点
                                        currentlyEditingIndex = originalIndex;
                                      } else if (currentlyEditingIndex == originalIndex) {
                                        // 当前TextField失去焦点，提交更改
                                        if (weightControllers.length > originalIndex) {
                                          updateWeight(originalIndex, weightControllers[originalIndex].text);
                                          currentlyEditingIndex = -1;
                                        }
                                      }
                                    },
                                    child: TextField(
                                      keyboardType: TextInputType.number,
                                      style: const TextStyle(color: Colors.white, fontSize: 16),
                                      decoration: InputDecoration(
                                        labelText: S.of(context).weight,
                                        labelStyle: const TextStyle(color: Colors.white70),
                                        filled: true,
                                        fillColor: Colors.grey[700],
                                        border: OutlineInputBorder(
                                          borderRadius: BorderRadius.circular(10),
                                        ),
                                        floatingLabelAlignment: FloatingLabelAlignment.center,
                                      ),
                                      // 使用权重控制器列表中的控制器
                                      controller: weightControllers.length > originalIndex 
                                        ? weightControllers[originalIndex] 
                                        : TextEditingController(text: weight.toString()),
                                      // 修改为只在完成编辑时更新权重
                                      onSubmitted: (value) {
                                        updateWeight(originalIndex, value);
                                        currentlyEditingIndex = -1; // 重置编辑索引
                                      },
                                      onTapOutside: (event) {
                                        // 点击外部时也更新权重
                                        if (weightControllers.length > originalIndex) {
                                          updateWeight(originalIndex, weightControllers[originalIndex].text);
                                          currentlyEditingIndex = -1;
                                        }
                                      },
                                      // 限制只能输入数字
                                      inputFormatters: <TextInputFormatter>[
                                        FilteringTextInputFormatter.digitsOnly
                                      ],
                                      textAlign: TextAlign.center,
                                    ),
                                  ),
                                )
                            ],
                          ),
                        );
                      },
                    );
                  },
                )
            )
          ],
        ),
      ),
    );
  }
}
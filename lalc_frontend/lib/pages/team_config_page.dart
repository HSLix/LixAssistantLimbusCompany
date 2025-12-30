import 'package:lalc_frontend/main.dart';
import 'package:lalc_frontend/config_manager.dart';
import 'package:lalc_frontend/websocket_manager.dart';
import 'package:flutter/material.dart';
import 'dart:convert';
import 'dart:math' as math;
import '../generated/l10n.dart';

// 罪人名字的中英文对照
const sinnerNames = [
  "Yi Sang", "Faust", "Don Quixote", "Ryoshu", "Meursault", "Hong Lu", "Heathcliff", "Ishmael", "Rodion", "Sinclair", "Outis", "Gregor"
];

const List<String> sinnerNamesZh = [
  "李箱", "浮士德", "堂吉诃德", "良秀", "默尔索", "鸿璐", "希斯克利夫", "以实玛利", "罗佳", "辛克莱", "奥提斯", "格里高尔"
];

// 饰品数据
class EgoGift {
  final String name;
  final String type; // 饰品类型/流派
  final String image;

  EgoGift({required this.name, required this.type, required this.image});
}

// 流派类型的中英文对照
const List<String> styleTypes = [
  "Bleed", "Burn", "Rupture", "Poise", "Tremor", "Blunt", "Pierce", "Slash", "Charge", "Sinking", "Keywordless"
];

const List<String> styleTypesZh = [
  "流血", "燃烧", "破裂", "呼吸法", "震颤", "打击", "突刺", "斩击", "充能", "沉沦", "泛用"
];

List<EgoGift> egoGifts = [];

// 为每个队伍保存独立配置的数据结构
class TeamPageConfig {  // 重命名以避免与config_manager.dart中的TeamConfig冲突
  bool shopHealAll;
  String selectedStyleType;
  Set<String> selectedAccessoryTypes;
  Set<String> selectedPreferEgoGiftTypes;
  Map<String, String> giftName2Status;
  Map<String, bool> skillReplacementEnabled; // 技能替换启用状态
  Map<String, List<List<int>>> skillReplacementOrders; // 技能替换顺序配置
  String teamName; // 添加队伍名称字段
  List<int> initialEgoGifts; // 添加初始饰品配置字段
  Map<String, bool> mirrorStarEnabled; // 添加镜像星光启用状态
  Map<String, String> mirrorStarValues; // 添加镜像星光值

  TeamPageConfig({
    this.shopHealAll = false,
    this.selectedStyleType = 'Bleed',
    required this.selectedAccessoryTypes,
    required this.selectedPreferEgoGiftTypes,
    required this.giftName2Status,
    required this.skillReplacementEnabled,
    required this.skillReplacementOrders,
    this.teamName = '', // 默认为空字符串
    this.initialEgoGifts = const [1, 2, 3], // 默认初始饰品配置，与config_manager.dart保持一致
    this.mirrorStarEnabled = const {}, // 默认镜像星光启用状态
    this.mirrorStarValues = const {}, // 默认镜像星光值
  });

  // 创建副本，防止引用问题
  TeamPageConfig copyWith({
    bool? shopHealAll,
    String? selectedStyleType,
    Set<String>? selectedAccessoryTypes,
    Set<String>? selectedPreferEgoGiftTypes,
    Map<String, String>? giftName2Status,
    Map<String, bool>? skillReplacementEnabled,
    Map<String, List<List<int>>>? skillReplacementOrders,
    String? teamName,
    List<int>? initialEgoGifts,
    Map<String, bool>? mirrorStarEnabled,
    Map<String, String>? mirrorStarValues,
  }) {
    return TeamPageConfig(
      shopHealAll: shopHealAll ?? this.shopHealAll,
      selectedStyleType: selectedStyleType ?? this.selectedStyleType,
      selectedAccessoryTypes: selectedAccessoryTypes ?? Set<String>.from(this.selectedAccessoryTypes),
      selectedPreferEgoGiftTypes: selectedPreferEgoGiftTypes ?? Set<String>.from(this.selectedPreferEgoGiftTypes),
      giftName2Status: giftName2Status ?? Map<String, String>.from(this.giftName2Status),
      skillReplacementEnabled: skillReplacementEnabled ?? Map<String, bool>.from(this.skillReplacementEnabled),
      skillReplacementOrders: skillReplacementOrders ?? Map<String, List<List<int>>>.from(this.skillReplacementOrders),
      teamName: teamName ?? this.teamName,
      initialEgoGifts: initialEgoGifts ?? List<int>.from(this.initialEgoGifts),
      mirrorStarEnabled: mirrorStarEnabled ?? Map<String, bool>.from(this.mirrorStarEnabled),
      mirrorStarValues: mirrorStarValues ?? Map<String, String>.from(this.mirrorStarValues),
    );
  }
}

class TeamConfigPage extends StatefulWidget {
  final int? initialTeamIndex;

  const TeamConfigPage({super.key, this.initialTeamIndex});

  @override
  State<TeamConfigPage> createState() => _TeamConfigPageState();
}

class _TeamConfigPageState extends State<TeamConfigPage>
    with TickerProviderStateMixin {
  int selectedTeamIndex = 0;
  int selectedPanelIndex = -1;

  // 添加图片根地址变量
  String? _imgRootAddress;

  // 每个队伍的配置列表
  late List<TeamPageConfig> teamConfigs;  // 使用TeamPageConfig而不是TeamConfig
  List<String> teamNames = List.generate(20, (index) => "Team ${index + 1}");
  final List<List<int>> teamOrders = List.generate(20, (_) => List.generate(12, (_) => -1));

  TextEditingController searchController = TextEditingController();
  // 控制队伍名称
  TextEditingController teamNameController = TextEditingController();

  late final AnimationController _controller;
  late final Animation<Offset> _slideAnimation;
  
  // 添加用于未选中方框边缘闪烁动画的控制器
  late final AnimationController _pulseController;
  late final Animation<Color?> _pulseAnimation;
  
  int get nextOrder {
    final orders = teamOrders[selectedTeamIndex];
    int used = orders.where((e) => e > 0).length;
    return used < 12 ? used + 1 : 12;
  }

  // 获取当前选中的成员列表，按选择顺序排序
  List<String> getSelectedMembersInOrder() {
    final orders = teamOrders[selectedTeamIndex];
    // 创建一个包含索引和顺序的列表
    final indexedOrders = <Map<String, dynamic>>[];
    for (int i = 0; i < orders.length; i++) {
      if (orders[i] > 0) {
        indexedOrders.add({'index': i, 'order': orders[i]});
      }
    }
    
    // 按照顺序排序
    indexedOrders.sort((a, b) => a['order'].compareTo(b['order']));
    
    // 提取成员名称
    return indexedOrders.map((item) => sinnerNames[item['index']]).toList();
  }

  // 获取当前队伍的配置
  TeamPageConfig get currentTeamConfig => teamConfigs[selectedTeamIndex];  // 使用TeamPageConfig

  // 选择成员
  void selectMember(int memberIndex) {
    final orders = teamOrders[selectedTeamIndex];
    setState(() {
      if (orders[memberIndex] == -1) {
        orders[memberIndex] = nextOrder;
      } else {
        orders[memberIndex] = -1;
      }
      // 保存配置
      _saveCurrentTeamConfig();
    });
  }

  // 清空当前选择
  void clearSelection() {
    setState(() {
      teamOrders[selectedTeamIndex] = List.generate(12, (_) => -1);
      // 保存配置
      _saveCurrentTeamConfig();
    });
  }

  // 更新队伍名称
  void updateTeamName(String value) {
    setState(() {
      teamNames[selectedTeamIndex] = value;
      // 同时更新teamConfigs中的teamName字段
      teamConfigs[selectedTeamIndex] = teamConfigs[selectedTeamIndex].copyWith(teamName: value);
      // 保存配置
      _saveCurrentTeamConfig();
    });
  }

  // 切换到指定队伍
  void switchToTeam(int index) {
    setState(() {
      selectedTeamIndex = index;
      teamNameController.text = teamNames[index];
    });
  }

  // 打开面板详情
  void _openPanelDetail(int index) {
    setState(() {
      selectedPanelIndex = index;
    });
    _controller.forward(from: 0);
  }

  // 关闭面板详情
  void _closePanelDetail() {
    _controller.reverse().then((_) {
      setState(() {
        selectedPanelIndex = -1;
      });
    });
  }

  // 保存当前队伍配置到配置管理器
  void _saveCurrentTeamConfig() {
    final configManager = ConfigManager();
    final currentTeamConfig = teamConfigs[selectedTeamIndex];
    
    // 获取当前选中的成员列表（按正确顺序）
    final List<String> selectedMembers = getSelectedMembersInOrder();
    
    // 更新配置管理器中的队伍配置
    configManager.teamConfigs[selectedTeamIndex] = TeamConfig(
      selectedMembers: selectedMembers, // 正确保存选中的成员列表
      shopHealAll: currentTeamConfig.shopHealAll,
      selectedStyleType: currentTeamConfig.selectedStyleType,
      selectedPreferEgoGiftTypes: List<String>.from(currentTeamConfig.selectedPreferEgoGiftTypes),
      selectedAccessoryTypes: List<String>.from(currentTeamConfig.selectedAccessoryTypes),
      giftName2Status: Map<String, String>.from(currentTeamConfig.giftName2Status),
      skillReplacementEnabled: Map<String, bool>.from(currentTeamConfig.skillReplacementEnabled),
      skillReplacementOrders: Map<String, List<List<int>>>.from(currentTeamConfig.skillReplacementOrders),
      teamName: currentTeamConfig.teamName,
      initialEgoGifts: List<int>.from(currentTeamConfig.initialEgoGifts), // 保存初始饰品配置
      mirrorStarEnabled: Map<String, bool>.from(currentTeamConfig.mirrorStarEnabled), // 保存镜像星光启用状态
      mirrorStarValues: Map<String, String>.from(currentTeamConfig.mirrorStarValues), // 保存镜像星光值
    );
    
    // 保存到文件
    configManager.saveTeamConfig();
  }

  // 递归遍历assets/ego_gifts目录下的所有图片文件
  Future<void> _loadEgoGifts() async {
    try {
      // 使用新的 AssetManifest API 加载资产清单
      final manifest = await DefaultAssetBundle.of(context).loadString('AssetManifest.json');
      final Map<String, dynamic> json = jsonDecode(manifest);

      // 清空现有的egoGifts列表
      egoGifts.clear();

      // 遍历所有以 assets/ego_gifts/ 开头的路径，找到所有子文件夹中的 .png 文件
      for (final path in json.keys) {
        // print(path);
        if (path.startsWith('assets/ego_gifts/')) {
          final pathParts = path.split('/');
          if (pathParts.length >= 4) {
            final type = pathParts[2]; // 类型是子目录名，例如 "Bleed"
            final fileName = pathParts.sublist(3).join('/'); // 包含子目录的完整文件名
            final displayName = fileName.replaceAll('.png', ''); // 获取饰品名称（去掉扩展名）

            // 创建EgoGift对象并添加到列表
            if (path.endsWith('.png')) {
              egoGifts.add(EgoGift(
                name: displayName,
                type: type,
                image: path,
              ));
            }
          }
        }
      }

      // print("Loaded ego gifts: $egoGifts");
      setState(() {});
    } catch (e) {
      debugPrint('Error loading ego gifts: $e');
      _loadDefaultEgoGifts();  // 加载默认数据作为备选
    }
  }


  void _loadDefaultEgoGifts() {
    // 清空现有列表
    egoGifts.clear();

    // 添加一些默认饰品数据用于演示
    for (var type in styleTypes) {
      egoGifts.add(EgoGift(
        name: '$type Default Gift',
        type: type,
        image: 'assets/sinners/Yi Sang.png', // 使用已知存在的图像
      ));
    }
  }

  // 检查当前是否为中文环境
  bool _isChineseLocale(BuildContext context) {
    final locale = Localizations.localeOf(context);
    return locale.languageCode == 'zh';
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

  // 构建罪人图片路径
  String _getSinnerImagePath(String imageName) {
    if (_imgRootAddress != null) {
      return '$_imgRootAddress/sinners/$imageName.png';
    }
    // Fallback to assets
    return 'assets/sinners/$imageName.png';
  }

  // 构建星光图片路径
  String _getStarImagePath(String imageName) {
    if (_imgRootAddress != null) {
      return '$_imgRootAddress/stars/$imageName.png';
    }
    // Fallback to assets
    return 'assets/stars/$imageName.png';
  }

  // 构建EGO饰品图片路径
  String _getEgoGiftImagePath(String imagePath) {
    if (_imgRootAddress != null && imagePath.startsWith('assets/ego_gifts/')) {
      // 从assets路径转换为服务器路径
      final relativePath = imagePath.replaceFirst('assets/', '');
      return '$_imgRootAddress/$relativePath';
    }
    // Fallback to assets
    return imagePath;
  }

  @override
  void initState() {
    super.initState();
    // 如果传入了初始队伍索引，则使用该索引
    if (widget.initialTeamIndex != null && 
        widget.initialTeamIndex! >= 0 && 
        widget.initialTeamIndex! < 20) {
      selectedTeamIndex = widget.initialTeamIndex!;
    }
    
    // 初始化动画控制器
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
    
    // 初始化脉冲动画控制器
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000), // 延长动画周期使闪烁更明显
    );
    
    // 创建颜色动画，从灰色到蓝色的强烈对比
    _pulseAnimation = ColorTween(
      begin: Colors.grey[600],
      end: msBlue,
    ).animate(_pulseController);
    
    // 重复播放动画
    _pulseController.repeat(reverse: false); // 单向循环使闪烁更明显

    // 初始化teamConfigs
    teamConfigs = List.generate(20, (index) => _defaultTeamConfig(index));
    
    // 从配置管理器加载队伍配置
    _loadTeamConfigsFromManager();
    
    // 在设置selectedTeamIndex后再初始化控制器文本
    teamNameController.text = teamNames[selectedTeamIndex];

    _loadEgoGifts();
    
    // 获取图片地址
    _getImageAddress();
  }
  
  // 从配置管理器加载队伍配置
  void _loadTeamConfigsFromManager() {
    final configManager = ConfigManager();
    for (int i = 0; i < 20; i++) {
      if (configManager.teamConfigs.containsKey(i)) {
        final teamConfig = configManager.teamConfigs[i]!;
        teamConfigs[i] = TeamPageConfig(
          shopHealAll: teamConfig.shopHealAll,
          selectedStyleType: teamConfig.selectedStyleType,
          selectedAccessoryTypes: Set<String>.from(teamConfig.selectedAccessoryTypes),
          selectedPreferEgoGiftTypes: Set<String>.from(teamConfig.selectedPreferEgoGiftTypes),
          giftName2Status: Map<String, String>.from(teamConfig.giftName2Status),
          skillReplacementEnabled: Map<String, bool>.from(teamConfig.skillReplacementEnabled),
          skillReplacementOrders: Map<String, List<List<int>>>.from(teamConfig.skillReplacementOrders),
          teamName: teamConfig.teamName,
          initialEgoGifts: List<int>.from(teamConfig.initialEgoGifts), // 加载初始饰品配置
          mirrorStarEnabled: Map<String, bool>.from(teamConfig.mirrorStarEnabled), // 加载镜像星光启用状态
          mirrorStarValues: Map<String, String>.from(teamConfig.mirrorStarValues), // 加载镜像星光值
        );
        // 同步更新teamNames数组
        teamNames[i] = teamConfig.teamName;
        
        // 同步更新teamOrders数组（成员选择顺序）
        // 首先清空原来的teamOrders
        teamOrders[i] = List.generate(12, (_) => -1);
        
        // 将selectedMembers转换为teamOrders中的索引和顺序
        for (int j = 0; j < teamConfig.selectedMembers.length; j++) {
          final memberName = teamConfig.selectedMembers[j];
          final memberIndex = sinnerNames.indexOf(memberName);
          if (memberIndex != -1) {
            // 成员存在，设置其顺序（注意：顺序从1开始）
            teamOrders[i][memberIndex] = j + 1;
          }
        }
      }
      // 注意：如果配置不存在，保留默认配置不变
    }

    // 刷新 UI
    setState(() {});
  }

  @override
  void dispose() {
    _controller.dispose();
    _pulseController.dispose();
    super.dispose();
  }


  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          // -------------------------
          // 左侧队伍列表（窄）
          // -------------------------
          Container(
            width: 140,
            color: Colors.grey[900],
            child: ListView.builder(
              padding: const EdgeInsets.only(top: 20),
              itemCount: 20,
              itemBuilder: (context, index) {
                return GestureDetector(
                  onTap: () {
                    switchToTeam(index);
                  },
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: selectedTeamIndex == index
                          ? Colors.blueGrey[700]
                          : Colors.grey[800],
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: selectedTeamIndex == index
                            ? Colors.white
                            : Colors.transparent,
                        width: 1.5,
                      ),
                    ),
                    child: Text(
                      teamNames[index], // 使用动态队伍名称
                      style: const TextStyle(color: Colors.white, fontSize: 16),
                    ),
                  ),
                );
              },
            ),
          ),

          // -------------------------
          // 右侧主配置区域
          // -------------------------
          Expanded(
            child: Stack(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  color: Colors.grey[850],
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    mainAxisAlignment: MainAxisAlignment.start,
                    children: [
                      // 可编辑队伍名称
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: TextField(
                              controller: teamNameController,
                              onChanged: (value) {
                                updateTeamName(value); // 更新队伍名称
                              },
                              style: const TextStyle(color: Colors.white),
                              decoration: InputDecoration(
                                labelText: S.of(context).team_name,
                                labelStyle: const TextStyle(color: Colors.white),
                                filled: true,
                                fillColor: Colors.grey[700],
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(10),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          ElevatedButton(
                            onPressed: _showCopyToDialog,
                            child: Text(
                              S.of(context).copy_to,
                              style: const TextStyle(
                                fontSize: 16,
                              ),
                            ),
                          ),
                          
                        ],
                      ),
                      const SizedBox(height: 10),

                      // -------------------------
                      // 人员顺序，两行六列
                      // -------------------------
                      Flexible(
                        fit: FlexFit.loose,
                        child: LayoutBuilder(
                          builder: (context, constraints) {
                            // 基于可用宽度计算网格项的理想大小
                            final double crossAxisSpacing = 10;
                            final double mainAxisSpacing = 10;
                            final int crossAxisCount = 6;
                            
                            // 计算每个网格项的理想宽度
                            final double totalSpacingWidth = crossAxisSpacing * (crossAxisCount - 1);
                            final double availableWidth = constraints.maxWidth - totalSpacingWidth;
                            final double idealItemWidth = availableWidth / crossAxisCount;
                            
                            // 设置最小和最大尺寸
                            final double minItemWidth = 80.0;
                            final double maxItemWidth = 150.0;
                            final double actualItemWidth = idealItemWidth.clamp(minItemWidth, maxItemWidth);
                            
                            // 根据实际项宽度计算其他尺寸
                            final double imageSize = actualItemWidth * 0.7;
                            final double fontSize = (actualItemWidth * 0.12).clamp(10.0, 18.0);
                            final double selectedFontSize = (actualItemWidth * 0.35).clamp(18.0, 32.0);
                            final double selectedLabelFontSize = (actualItemWidth * 0.15).clamp(12.0, 20.0);
                            final double borderRadius = (actualItemWidth * 0.1).clamp(6.0, 12.0);
                            final double borderWidth = (actualItemWidth * 0.04).clamp(2.0, 5.0);
                            
                            return GridView.builder(
                              shrinkWrap: true,
                              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                                crossAxisCount: crossAxisCount,
                                crossAxisSpacing: crossAxisSpacing,
                                mainAxisSpacing: mainAxisSpacing,
                                childAspectRatio: 1,
                              ),
                              itemCount: 12,
                              itemBuilder: (context, index) {
                                final order = teamOrders[selectedTeamIndex][index];
                                final bool selected = order > 0;
                                final imageName = sinnerNames[index];

                                return GestureDetector(
                                  onTap: () => selectMember(index),
                                  child: AnimatedBuilder(
                                    animation: _pulseController,
                                    builder: (context, child) {
                                      return Container(
                                        decoration: BoxDecoration(
                                          color: Colors.grey[700],
                                          borderRadius: BorderRadius.circular(borderRadius),
                                          border: Border.all(
                                            // 使用动画颜色，如果是选中的则保持msBlue边框，未选中的使用动画颜色
                                            color: selected 
                                                ?  Color(0xFF0078D4) // 微软蓝色
                                                : _pulseAnimation.value ?? Colors.grey[600]!,
                                            width: selected ? borderWidth * 1.5 : borderWidth,
                                          ),
                                        ),
                                        child: Stack(
                                          children: [
                                            Center(
                                              child: Column(
                                                mainAxisAlignment: MainAxisAlignment.center,
                                                children: [
                                                  // 图片
                                                  Image.asset(
                                                    _getSinnerImagePath(imageName),
                                                    width: imageSize,
                                                    height: imageSize * 1.1,
                                                    fit: BoxFit.cover,
                                                    errorBuilder: (context, error, stackTrace) {
                                                      // 如果网络图片加载失败，回退到assets
                                                      return Image.asset(
                                                        'assets/sinners/$imageName.png',
                                                        width: imageSize,
                                                        height: imageSize * 1.1,
                                                        fit: BoxFit.cover,
                                                      );
                                                    },
                                                  ),
                                                  // 文本
                                                  Flexible(
                                                    fit: FlexFit.loose,
                                                    child: Text(
                                                      _isChineseLocale(context) ? sinnerNamesZh[index] : sinnerNames[index],
                                                      style: TextStyle(
                                                        color: Colors.white,
                                                        fontSize: fontSize,
                                                      ),
                                                      overflow: TextOverflow.ellipsis,
                                                      maxLines: 1,
                                                      textAlign: TextAlign.center,
                                                    ),
                                                  ),
                                                ],
                                              ),
                                            ),
                                            // 如果选中，添加灰色蒙版、selected 标签和顺序数字
                                            if (selected)
                                              Positioned.fill(
                                                child: Container(
                                                  decoration: BoxDecoration(
                                                    color: Colors.black.withValues(alpha: .5), // 灰色蒙版
                                                    borderRadius: BorderRadius.circular(borderRadius),
                                                  ),
                                                  child: Center(
                                                    child: Column(
                                                      mainAxisAlignment: MainAxisAlignment.center,
                                                      children: [
                                                        // 顺序数字，黄色字体，稍大一些
                                                        Text(
                                                          "$order",
                                                          style: TextStyle(
                                                            color: Colors.yellow, 
                                                            fontSize: selectedFontSize, 
                                                            fontWeight: FontWeight.bold
                                                          ),
                                                        ),
                                                        SizedBox(height: selectedFontSize * 0.2),
                                                        // 选择状态，居中显示 "SELECTED"
                                                        Container(
                                                          padding: EdgeInsets.symmetric(
                                                            horizontal: selectedLabelFontSize * 0.4, 
                                                            vertical: selectedLabelFontSize * 0.2
                                                          ),
                                                          decoration: BoxDecoration(
                                                            color: const Color.fromARGB(255, 148, 35, 27),
                                                            borderRadius: BorderRadius.circular(selectedLabelFontSize * 0.3),
                                                          ),
                                                          child: Text(
                                                            S.of(context).selected,
                                                            style: TextStyle(
                                                              color: Colors.yellow, 
                                                              fontSize: selectedLabelFontSize, 
                                                              fontWeight: FontWeight.w700
                                                            ),
                                                          ),
                                                        ),
                                                      ],
                                                    ),
                                                  ),
                                                ),
                                              ),
                                          ],
                                        ),
                                      );
                                    },
                                  ),
                                );
                              },
                            );
                          }
                        ),
                      ),
                      SizedBox(height: 5,),
                      // 底部按钮和计数
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          // "Clear Selection" 按钮
                          ElevatedButton(
                            onPressed: clearSelection,
                            style: ElevatedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(horizontal: 20),
                            ),
                            child: Text(
                              S.of(context).clear_selection,
                              style: const TextStyle(
                                fontSize: 16,
                              ),
                            ),
                          ),
                          // 计数显示
                          Text(
                            "${teamOrders[selectedTeamIndex].where((e) => e > 0).length} / ${sinnerNames.length}",
                            style: const TextStyle(color: Colors.white, fontSize: 16),
                          ),
                        ],
                      ),

                      const Divider(),
                      // 配置初始星光
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            S.of(context).mirror_star_config,
                            style: TextStyle(
                              fontSize: 22,
                            ),
                          ),
                          ElevatedButton(
                            onPressed: () => _openPanelDetail(2),
                            child: Text(S.of(context).configure),
                          ),
                        ],
                      ),
                      // 显示选中的星光预览
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            "${S.of(context).selected_stars}: ",
                            style: const TextStyle(
                              fontSize: 16,
                            ),
                          ),
                          Flexible(
                            child: Text(
                              _getSelectedStarsPreview(),
                              style: const TextStyle(
                                fontSize: 16,
                              ),
                              overflow: TextOverflow.ellipsis,
                              maxLines: 1,
                            ),
                          ),
                        ],
                      ),

                      const Divider(),
                      
                      // 流派选择下拉框
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            _isChineseLocale(context) ? "队伍流派" : "Team Style",
                            style: TextStyle(
                              fontSize: 22,
                            ),
                          ),
                          DropdownButton<String>(
                            alignment: Alignment.center,
                            value: currentTeamConfig.selectedStyleType,
                            items: styleTypes
                                .where((type) => type != "Keywordless") // 过滤掉"Keywordless"
                                .map((String type) {
                              // 获取对应的中文名称
                              final int typeIndex = styleTypes.indexOf(type);
                              final String displayType = _isChineseLocale(context) 
                                  ? styleTypesZh[typeIndex] 
                                  : type;
                              return DropdownMenuItem<String>( 
                                alignment: Alignment.center,
                                value: type,
                                child: Text(displayType, style: const TextStyle(color: Colors.white)),
                              );
                            }).toList(),
                            onChanged: (newValue) {
                              setState(() {
                                teamConfigs[selectedTeamIndex] = currentTeamConfig.copyWith(selectedStyleType: newValue);
                                _saveCurrentTeamConfig(); // 保存配置到ConfigManager
                              });
                            },
                          ),
                        ],
                      ),
                      const SizedBox(height: 5,),
                      // 配置初始饰品选择
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          Text(
                            _isChineseLocale(context) ? "启程EGO饰品" : "Initial Ego Gifts",
                            style: TextStyle(
                              fontSize: 22,
                            ),
                          ),

                          SizedBox(
                            height: 50,
                            width: 300, // 设置一个固定宽度
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.end,
                              children: [
                                ReorderableListView(
                                  buildDefaultDragHandles: false,
                                  scrollDirection: Axis.horizontal,
                                  shrinkWrap: true,
                                  physics: NeverScrollableScrollPhysics(),
                                  onReorder: (int oldIndex, int newIndex) {
                                    setState(() {
                                      final List<int> newInitialEgoGifts = 
                                          List<int>.from(teamConfigs[selectedTeamIndex].initialEgoGifts);
                                      
                                      if (newIndex > oldIndex) {
                                        newIndex -= 1;
                                      }
                                      
                                      final int item = newInitialEgoGifts.removeAt(oldIndex);
                                      newInitialEgoGifts.insert(newIndex, item);
                                      
                                      teamConfigs[selectedTeamIndex] = 
                                          teamConfigs[selectedTeamIndex].copyWith(initialEgoGifts: newInitialEgoGifts);
                                      _saveCurrentTeamConfig();
                                    });
                                  },
                                  children: List.generate(
                                    teamConfigs[selectedTeamIndex].initialEgoGifts.length,
                                    (index) {
                                      return Container(
                                        key: ValueKey('$index-${teamConfigs[selectedTeamIndex].initialEgoGifts[index]}'),
                                        width: 50,
                                        margin: EdgeInsets.all(4),
                                        decoration: BoxDecoration(
                                          color: Colors.white,
                                          borderRadius: BorderRadius.circular(8),
                                        ),
                                        child: Stack(
                                          children: [
                                            Center(
                                              child: 
                                                Text(
                                                  '${teamConfigs[selectedTeamIndex].initialEgoGifts[index]}',
                                                  style: TextStyle(
                                                    fontSize: 24,
                                                    fontWeight: FontWeight.bold,
                                                    color: msBlue,
                                                  ),
                                                ),          
                                            ),
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
                                      );
                                    },
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),

                      const Divider(),
                      // 商店全体疗伤开关
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            _isChineseLocale(context) ? "商店全体疗伤" : "Mirror Shop Heal",
                            style: TextStyle(
                              fontSize:22
                            ),
                          ),
                          Switch(
                            value: currentTeamConfig.shopHealAll,
                            onChanged: (value) {
                              setState(() {
                                teamConfigs[selectedTeamIndex] = currentTeamConfig.copyWith(shopHealAll: value);
                                _saveCurrentTeamConfig(); // 保存配置到ConfigManager
                              });
                            },
                          ),
                        ],
                      ),
                      
                      const Divider(),
                      
                      // 镜像配置按钮
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            _isChineseLocale(context) ? "镜像饰品配置" : "Mirror Ego Gift Config",
                            style: TextStyle(
                              fontSize: 22,
                            ),
                          ),
                          ElevatedButton(
                            onPressed: () => _openPanelDetail(0),
                            child: Text(S.of(context).configure),
                          ),
                        ],
                      ),
                      
                      // 显示首选类型的预览文本
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            "${_isChineseLocale(context) ? "首选类型" : "Preferred Types"}: ",
                            style: const TextStyle(
                              fontSize: 16,
                            ),
                          ),
                          Flexible(
                            child: Text(
                              () {
                                // 将英文类型转换为本地化显示
                                List<String> localizedTypes = [];
                                for (String type in currentTeamConfig.selectedPreferEgoGiftTypes) {
                                  final int typeIndex = styleTypes.indexOf(type);
                                  if (typeIndex != -1) {
                                    localizedTypes.add(_isChineseLocale(context) 
                                        ? styleTypesZh[typeIndex] 
                                        : type);
                                  } else {
                                    localizedTypes.add(type);
                                  }
                                }
                                return localizedTypes.join(", ");
                              }(),
                              style: const TextStyle(
                                fontSize: 16,
                              ),
                              overflow: TextOverflow.ellipsis,
                              maxLines: 1,
                            ),
                          ),
                        ],
                      ),
                      
                      const Divider(),
                      
                      // 技能替换配置按钮
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            _isChineseLocale(context) ? "技能替换配置" : "Skill Replacement Config",
                            style: TextStyle(
                              fontSize: 22,
                            ),
                          ),
                          ElevatedButton(
                            onPressed: () => _openPanelDetail(1),
                            child: Text(
                              S.of(context).configure,
                            ),
                          ),
                        ],
                      ),
                      // 技能替换启用人员的预览
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            "${_isChineseLocale(context) ? "启用角色" : "Enabled Characters"}: ",
                            style: const TextStyle(
                              fontSize: 16,
                            ),
                          ),
                          Flexible(
                            child: Text(
                              () {
                                // 将英文罪人名转换为本地化显示
                                List<String> localizedNames = [];
                                for (var entry in currentTeamConfig.skillReplacementEnabled.entries) {
                                  if (entry.value) {
                                    final int nameIndex = sinnerNames.indexOf(entry.key);
                                    if (nameIndex != -1) {
                                      localizedNames.add(_isChineseLocale(context) 
                                          ? sinnerNamesZh[nameIndex] 
                                          : entry.key);
                                    } else {
                                      localizedNames.add(entry.key);
                                    }
                                  }
                                }
                                return localizedNames.join(", ");
                              }(),
                              style: const TextStyle(
                                fontSize: 16,
                              ),
                              overflow: TextOverflow.ellipsis,
                              maxLines: 1,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                // 滑出的详情面板
                selectedPanelIndex != -1
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
                                    selectedPanelIndex == 0 
                                        ? (_isChineseLocale(context) ? "镜像饰品配置" : "Mirror Ego Gift Config")
                                        : selectedPanelIndex == 1
                                          ? (_isChineseLocale(context) ? "技能替换配置" : "Skill Replacement Config")
                                          : (_isChineseLocale(context) ? "配置初始星光" : "Mirror Star Config"),
                                    style: const TextStyle(
                                      fontSize: 20,
                                      fontWeight: FontWeight.bold,
                                      color: Colors.white,
                                    ),
                                  ),
                                  IconButton(
                                    icon: const Icon(Icons.close,
                                        color: Colors.white),
                                    onPressed: _closePanelDetail,
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              // 详情内容
                              Expanded(
                                child: Container(
                                  decoration: BoxDecoration(
                                    color: Colors.grey[800],
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  padding: const EdgeInsets.all(16),
                                  child: selectedPanelIndex == 0 
                                      ? _buildMirrorGiftConfigContent()
                                      : selectedPanelIndex == 1
                                        ? _buildSkillReplaceContent()
                                        : _buildMirrorStarConfigContent(),
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


  // 构建技能替换配置面板内容
  Widget _buildSkillReplaceContent() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 20),
        // 展示人员顺序选择网格（只读展示）
        Expanded(
          child: LayoutBuilder(
            builder: (_, constraints) {
              final double cellWidth = (constraints.maxWidth - 5 * 10) / 6;
              const double maxDesiredHeight = 250;
              final double fixedHeight = math.min(
                maxDesiredHeight,
                cellWidth / 0.3,
              );
              
              return GridView.builder(
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 6,
                  crossAxisSpacing: 10,
                  mainAxisSpacing: 10,
                  mainAxisExtent: fixedHeight,
                ),
                itemCount: sinnerNames.length,
                itemBuilder: (context, index) {
                  final imageName = sinnerNames[index];
                  // 获取当前角色的技能替换启用状态，默认为false
                  final isSkillReplacementEnabled = 
                      currentTeamConfig.skillReplacementEnabled[imageName] ?? false;
                  
                  return Container(
                    decoration: BoxDecoration(
                      color: Colors.grey[700],
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isSkillReplacementEnabled 
                            ? msBlue
                            : Colors.grey[600]!,
                        width: 2,
                      ),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        // 角色图像
                        Image.asset(
                          _getSinnerImagePath(imageName),
                          width: 50,
                          height: 55,
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) {
                            // 如果网络图片加载失败，回退到assets
                            return Image.asset(
                              'assets/sinners/$imageName.png',
                              width: 50,
                              height: 55,
                              fit: BoxFit.cover,
                            );
                          },
                        ),
                        const SizedBox(height: 5),
                        // 角色名字（只展示，无交互）
                        Text(
                          _isChineseLocale(context) ? sinnerNamesZh[index] : sinnerNames[index],
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                          ),
                          overflow: TextOverflow.ellipsis,
                          maxLines: 1,
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 5),
                        // 启用状态开关（可交互）
                        Transform.scale(
                          scale: 0.8,
                          child: Switch(
                            value: isSkillReplacementEnabled,
                            onChanged: (value) {
                              setState(() {
                                final updatedMap = 
                                    Map<String, bool>.from(
                                        currentTeamConfig.skillReplacementEnabled);
                                updatedMap[imageName] = value;
                                teamConfigs[selectedTeamIndex] = 
                                    currentTeamConfig.copyWith(
                                        skillReplacementEnabled: updatedMap);
                                _saveCurrentTeamConfig(); // 保存配置到ConfigManager
                              });
                            },
                            activeTrackColor: msBlue,
                          ),
                        ),
                        // 技能替换顺序列表
                        SizedBox(
                          height: fixedHeight * 0.4,
                          child: _buildReorderableSkillList(imageName, isSkillReplacementEnabled),
                        ),
                      ],
                    ),
                  );
                },
              );
            },
          ),
        ),
      ],
    );
  }
  

  // 构建可重排的技能列表
  Widget _buildReorderableSkillList(String characterName, bool isSkillReplacementEnabled) {
    // 获取当前角色的技能顺序配置，默认为[[1,2],[2,3],[1,3]]
    List<List<int>> skillOrders = currentTeamConfig.skillReplacementOrders[characterName] ?? [
      [1, 2],
      [2, 3],
      [1, 3]
    ];
    
    return ReorderableListView(
      buildDefaultDragHandles: false, // 关闭默认拖拽手柄
      scrollDirection: Axis.vertical,
      padding: const EdgeInsets.all(2),
      onReorder: (int oldIndex, int newIndex) {
        setState(() {
          // 调整索引以适应插入行为
          if (newIndex > oldIndex) {
            newIndex -= 1;
          }
          
          final updatedMap = 
              Map<String, List<List<int>>>.from(currentTeamConfig.skillReplacementOrders);
          
          // 重新排列技能顺序
          final item = skillOrders.removeAt(oldIndex);
          skillOrders.insert(newIndex, item);
          
          updatedMap[characterName] = skillOrders;
          teamConfigs[selectedTeamIndex] = 
              currentTeamConfig.copyWith(skillReplacementOrders: updatedMap);
          _saveCurrentTeamConfig(); // 保存配置到ConfigManager
        });
      },
      children: List.generate(skillOrders.length, (index) {
        final skillOrder = skillOrders[index];
        return Container(
          key: ValueKey('$characterName-${skillOrder[0]}-${skillOrder[1]}'),
          margin: const EdgeInsets.all(2),
          child: Stack(
            children: [
              Container(
                width: double.infinity,
                height: 25,
                decoration: BoxDecoration(
                  color: isSkillReplacementEnabled 
                                ? msBlue
                                : Colors.grey[600]!,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: Colors.white,
                    width: 1,
                  ),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${skillOrder[0]}->${skillOrder[1]}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                ),
              ),
              // 添加自定义拖拽区域
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
        );
      }),
    );
  }


  // 构建镜像星光配置面板内容
  Widget _buildMirrorStarConfigContent() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 20),
        Expanded(
          child: LayoutBuilder(
            builder: (_, constraints) {
              final double cellWidth = (constraints.maxWidth - 4 * 10) / 5;
              const double maxDesiredHeight = 200;
              final double fixedHeight = maxDesiredHeight;
              
              return GridView.builder(
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 5,
                  crossAxisSpacing: 10,
                  mainAxisSpacing: 10,
                  mainAxisExtent: fixedHeight,
                ),
                itemCount: 10, // 10个星光
                itemBuilder: (context, index) {
                  // 获取当前星光的配置
                  final starIndex = index.toString();
                  final isEnabled = currentTeamConfig.mirrorStarEnabled[starIndex] ?? false;
                  final value = _getStarValue(index);
                  
                  return Container(
                    decoration: BoxDecoration(
                      color: Colors.grey[700],
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isEnabled || value != starIndex ? msBlue : Colors.grey[600]!,
                        width: 2,
                      ),
                    ),
                    child: GestureDetector(
                      onTap: () {
                        _toggleStarSelection(index);
                      },
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          // 星光图像
                          Image.asset(
                            _getStarImagePath('mirror_${index.toString().padLeft(2, '0')}'),
                            width: cellWidth * 0.8,
                            height: fixedHeight * 0.5,
                            fit: BoxFit.contain,
                            errorBuilder: (context, error, stackTrace) {
                              // 如果网络图片加载失败，回退到assets
                              return Image.asset(
                                'assets/stars/mirror_${index.toString().padLeft(2, '0')}.png',
                                width: cellWidth * 0.8,
                                height: fixedHeight * 0.5,
                                fit: BoxFit.contain,
                              );
                            },
                          ),
                          
                          // 选择复选框
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Checkbox(
                                value: isEnabled,
                                onChanged: (value) {
                                  _setStarSelection(index, value ?? false);
                                },
                                activeColor: msBlue,
                              ),
                              Text(_isChineseLocale(context) ? "选择" : "Select", style: const TextStyle(color: Colors.white, fontSize: 12)),
                            ],
                          ),
                          
                          // + 和 ++ 按钮
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                            children: [
                              ElevatedButton(
                                onPressed: () {
                                  _setStarValue(index, '+');
                                },
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: _getStarValue(index) == '$index+' ? msBlue : Colors.grey[600],
                                  padding: EdgeInsets.zero,
                                  minimumSize: Size(40, 30),
                                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                ),
                                child: Text('+', style: TextStyle(fontSize: 16, color: Colors.white)),
                              ),
                              ElevatedButton(
                                onPressed: () {
                                  _setStarValue(index, '++');
                                },
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: _getStarValue(index) == '$index++' ? msBlue : Colors.grey[600],
                                  padding: EdgeInsets.zero,
                                  minimumSize: Size(40, 30),
                                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                ),
                                child: Text('++', style: TextStyle(fontSize: 16, color: Colors.white)),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  );
                },
              );
            },
          ),
        ),
      ],
    );
  }
  
  // 切换星光选择状态
  void _toggleStarSelection(int index) {
    final starIndex = index.toString();
    final updatedEnabled = Map<String, bool>.from(currentTeamConfig.mirrorStarEnabled);
    final currentValue = updatedEnabled[starIndex] ?? false;
    updatedEnabled[starIndex] = !currentValue;
    
    // 同时更新mirrorStarValues
    final updatedValues = Map<String, String>.from(currentTeamConfig.mirrorStarValues);
    if (!currentValue) {
      // 如果是选中状态，但在mirrorStarValues中没有记录，则添加默认值
      if (!updatedValues.containsKey(starIndex)) {
        updatedValues[starIndex] = starIndex;
      }
    }
    
    setState(() {
      teamConfigs[selectedTeamIndex] = currentTeamConfig.copyWith(
        mirrorStarEnabled: updatedEnabled,
        mirrorStarValues: updatedValues
      );
      _saveCurrentTeamConfig();
    });
  }
  
  // 设置星光选择状态
  void _setStarSelection(int index, bool selected) {
    final starIndex = index.toString();
    final updatedEnabled = Map<String, bool>.from(currentTeamConfig.mirrorStarEnabled);
    updatedEnabled[starIndex] = selected;
    
    // 同时更新mirrorStarValues
    final updatedValues = Map<String, String>.from(currentTeamConfig.mirrorStarValues);
    if (selected) {
      // 如果是选中状态，但在mirrorStarValues中没有记录，则添加默认值
      if (!updatedValues.containsKey(starIndex)) {
        updatedValues[starIndex] = starIndex;
      }
    }
    
    setState(() {
      teamConfigs[selectedTeamIndex] = currentTeamConfig.copyWith(
        mirrorStarEnabled: updatedEnabled,
        mirrorStarValues: updatedValues
      );
      _saveCurrentTeamConfig();
    });
  }
  
  // 获取星光值
  String _getStarValue(int index) {
    final starIndex = index.toString();
    return currentTeamConfig.mirrorStarValues[starIndex] ?? starIndex;
  }
  
  // 设置星光值
  void _setStarValue(int index, String modifier) {
    final starIndex = index.toString();
    final newValue = '$starIndex$modifier';
    final updatedValues = Map<String, String>.from(currentTeamConfig.mirrorStarValues);
    
    // 如果点击已经激活的修饰符，则恢复为默认值
    if (updatedValues[starIndex] == newValue) {
      updatedValues[starIndex] = starIndex; // 恢复为默认值而不是删除
    } else {
      updatedValues[starIndex] = newValue;
    }
    
    // 确保该星光也被标记为启用
    final updatedEnabled = Map<String, bool>.from(currentTeamConfig.mirrorStarEnabled);
    updatedEnabled[starIndex] = true;
    
    setState(() {
      teamConfigs[selectedTeamIndex] = currentTeamConfig.copyWith(
        mirrorStarValues: updatedValues,
        mirrorStarEnabled: updatedEnabled
      );
      _saveCurrentTeamConfig();
    });
  }
  
  // 获取选中的星光预览文本
  String _getSelectedStarsPreview() {
    // 获取所有被启用的星光ID
    final enabledStars = currentTeamConfig.mirrorStarEnabled.entries
        .where((entry) => entry.value)
        .map((entry) => entry.key)
        .toList();
        
    // 获取所有有自定义值的星光ID（包括+和++），但排除那些值等于键的（即未修改的）
    final modifiedStars = currentTeamConfig.mirrorStarValues.entries
        .where((entry) => entry.value != entry.key)
        .map((entry) => entry.key)
        .toList();
    
    // 合并所有相关的星光ID，去重并排序
    final allStars = <String>{...enabledStars, ...modifiedStars}.toList();
    allStars.sort((a, b) => int.parse(a).compareTo(int.parse(b)));
    
    if (allStars.isEmpty) {
      return _isChineseLocale(context) ? "无" : "None";
    }
    
    // 为每个星光生成显示文本
    // 如果该星光有自定义值则使用自定义值，否则使用原始ID
    return allStars.map((starIndex) {
      final value = currentTeamConfig.mirrorStarValues[starIndex] ?? starIndex;
      return value;
    }).join(', ');
  }

  // --------------------------------------
  // 镜像饰品配置内容
  // --------------------------------------
  Widget _buildMirrorGiftConfigContent() { // 修改方法名
    return Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            _isChineseLocale(context) ? "镜像首选EGO饰品流派" : "Mirror Prefer Ego Gift Style",
            style: TextStyle(
              fontSize: 22,
            ),
          ),
          const SizedBox(height: 10,),
          Wrap(
            children: styleTypes.map((type) {
              // 获取对应的中文名称
              final int typeIndex = styleTypes.indexOf(type);
              final String displayType = _isChineseLocale(context) 
                  ? styleTypesZh[typeIndex] 
                  : type;
              return FilterChip(
                label: Text(displayType, style: const TextStyle(color: Colors.white)),
                selected: currentTeamConfig.selectedPreferEgoGiftTypes.contains(type),
                onSelected: (isSelected) {
                  setState(() {
                    final updatedSet = Set<String>.from(currentTeamConfig.selectedPreferEgoGiftTypes);
                    if (isSelected) {
                      updatedSet.add(type);
                    } else {
                      updatedSet.remove(type);
                    }
                    teamConfigs[selectedTeamIndex] = currentTeamConfig.copyWith(selectedPreferEgoGiftTypes: updatedSet);
                    _saveCurrentTeamConfig(); // 保存配置到ConfigManager
                  });
                },
              );
            }).toList(),
          ),
          
          const Divider(),
          Text(
            _isChineseLocale(context) ? "镜像饰品白名单和黑名单" : "Mirror Ego Gift Allow List & Block List",
            style: TextStyle(
              fontSize: 22,
            ),
          ),
          const SizedBox(height: 10,),
          // 饰品种类筛选
          Wrap(
            children: styleTypes.map((type) {
              // 获取对应的中文名称
              final int typeIndex = styleTypes.indexOf(type);
              final String displayType = _isChineseLocale(context) 
                  ? styleTypesZh[typeIndex] 
                  : type;
              return FilterChip(
                label: Text(displayType, style: const TextStyle(color: Colors.white)),
                selected: currentTeamConfig.selectedAccessoryTypes.contains(type),
                onSelected: (isSelected) {
                  setState(() {
                    final updatedSet = Set<String>.from(currentTeamConfig.selectedAccessoryTypes);
                    if (isSelected) {
                      updatedSet.add(type);
                    } else {
                      updatedSet.remove(type);
                    }
                    teamConfigs[selectedTeamIndex] = currentTeamConfig.copyWith(selectedAccessoryTypes: updatedSet);
                    _saveCurrentTeamConfig(); // 保存配置到ConfigManager
                  });
                },
              );
            }).toList(),
          ),
          const SizedBox(height: 10,),
          // 饰品列表和搜索框
          TextField(
            controller: searchController,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              labelText: _isChineseLocale(context) ? "搜索饰品" : "Search Gift",
              labelStyle: const TextStyle(color: Colors.white),
              filled: true,
              fillColor: Colors.grey[700],
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            onChanged: (query) {
              setState(() {});
            },
          ),
          const SizedBox(height: 10),
          
          // 显示饰品列表
          Expanded(
            child: egoGifts.isEmpty
              ? Center(
                  child: Text(
                    _isChineseLocale(context) ? "暂无饰品数据" : "No gift data",
                    style: const TextStyle(color: Colors.grey, fontSize: 16),
                  ),
                )
              : ListView.builder(
                  itemCount: egoGifts.length,
                  itemBuilder: (context, index) {
                    final accessory = egoGifts[index];
                    
                    // 搜索过滤：只有当搜索框有内容时才进行过滤
                    final searchText = searchController.text.trim().toLowerCase();
                    if (searchText.isNotEmpty && 
                        !accessory.name.toLowerCase().contains(searchText)) {
                      return Container(); // 返回空容器以跳过该项
                    }
                    
                    // 类型筛选过滤：只有当选择了特定类型时才进行过滤
                    if (currentTeamConfig.selectedAccessoryTypes.isNotEmpty && 
                        !currentTeamConfig.selectedAccessoryTypes.contains(accessory.type)) {
                      return Container(); // 返回空容器以跳过该项
                    }
                    
                    // 如果通过了所有过滤条件，则显示该项
                    return ListTile(
                      contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      leading: ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: Image.asset(
                          _getEgoGiftImagePath(accessory.image), 
                          width: 50, 
                          height: 50,
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) {
                            // 如果网络图片加载失败，回退到assets
                            return Image.asset(
                              accessory.image,
                              width: 50,
                              height: 50,
                              fit: BoxFit.cover,
                            );
                          },
                        ),
                      ),
                      title: Text(
                        accessory.name, 
                        style: const TextStyle(color: Colors.white, fontSize: 16),
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: Text(
                        () {
                          // 获取对应的中文名称
                          final int typeIndex = styleTypes.indexOf(accessory.type);
                          return _isChineseLocale(context) && typeIndex != -1
                              ? styleTypesZh[typeIndex] 
                              : accessory.type;
                        }(), 
                        style: const TextStyle(color: Colors.grey, fontSize: 14),
                      ),
                      trailing: SizedBox(
                        width: 120,
                        child: DropdownButton<String>(
                          isExpanded: true,
                          value: currentTeamConfig.giftName2Status[accessory.name] ?? 'Default',
                          items: ['Default', 'Allow List', 'Block List'].map((String status) {
                            Color statusColor = Colors.white; // 默认颜色
                            String displayStatus = status;
                            if (status == 'Allow List') {
                              statusColor = Colors.greenAccent; // 允许列表使用绿色
                              displayStatus = _isChineseLocale(context) ? "白名单" : "Allow List";
                            } else if (status == 'Block List') {
                              statusColor = Colors.redAccent; // 阻止列表使用红色
                              displayStatus = _isChineseLocale(context) ? "黑名单" : "Block List";
                            } else {
                              displayStatus = _isChineseLocale(context) ? "默认" : "Default";
                            }
                            
                            return DropdownMenuItem<String>(
                              value: status,
                              alignment: Alignment.center,
                              child: Text(
                                displayStatus, 
                                style: TextStyle(color: statusColor), // 使用状态特定的颜色
                              ),
                            );
                          }).toList(),
                          onChanged: (newValue) {
                            setState(() {
                              final updatedMap = Map<String, String>.from(currentTeamConfig.giftName2Status);
                              if (newValue == 'Default') {
                                // 如果设置为Default，则从映射中删除该项
                                updatedMap.remove(accessory.name);
                              } else {
                                // 否则更新映射值
                                updatedMap[accessory.name] = newValue!;
                              }
                              teamConfigs[selectedTeamIndex] = currentTeamConfig.copyWith(giftName2Status: updatedMap);
                              _saveCurrentTeamConfig(); // 保存配置到ConfigManager
                            });
                          },
                        ),
                      ),
                      // 根据状态添加装饰，使选择更明显
                      tileColor: () {
                        final status = currentTeamConfig.giftName2Status[accessory.name] ?? 'Default';
                        if (status == 'Allow List') {
                          return Colors.green.withValues(alpha: 0.1); // 允许列表使用绿色背景
                        } else if (status == 'Block List') {
                          return Colors.red.withValues(alpha: 0.1); // 阻止列表使用红色背景
                        }
                        return null; // 默认无背景色
                      }(),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                        side: () {
                          final status = currentTeamConfig.giftName2Status[accessory.name] ?? 'Default';
                          if (status == 'Allow List') {
                            return BorderSide(color: Colors.green, width: 2); // 允许列表使用绿色边框
                          } else if (status == 'Block List') {
                            return BorderSide(color: Colors.red, width: 2); // 阻止列表使用红色边框
                          }
                          return BorderSide.none; // 默认无边框
                        }(),
                      ),
                    );
                  },
                ),
          ),
        ],
      );
  }

  TeamPageConfig _defaultTeamConfig(int teamIndex) {
    return TeamPageConfig(
      shopHealAll: false,
      selectedStyleType: 'Bleed',
      selectedAccessoryTypes: <String>{},
      selectedPreferEgoGiftTypes: <String>{},
      giftName2Status: {
        for (var gift in egoGifts) gift.name: 'Default',
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
      teamName: "Team ${teamIndex + 1}", // 设置默认队伍名称
      initialEgoGifts: [1, 2, 3], // 设置默认初始饰品配置
      mirrorStarEnabled: {}, // 设置默认镜像星光启用状态
      mirrorStarValues: {}, // 设置默认镜像星光值
    );
  }
  
  // 添加显示CopyTo对话框的方法
  void _showCopyToDialog() {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(_isChineseLocale(context) ? "选择目标队伍" : "Select Target Team"),
          content: SizedBox(
            width: double.maxFinite,
            child: _buildAvailableTeamsList(),
          ),
          actions: [
            TextButton(
              onPressed: Navigator.of(context).pop,
              child: Text(_isChineseLocale(context) ? "取消" : "Cancel"),
            ),
          ],
        );
      },
    );
  }

  // 构建可选队伍列表
  Widget _buildAvailableTeamsList() {
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
      final teamStyle = teamConfig?.selectedStyleType ?? 'Bleed';
      
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
            final isSelected = selectedTeamIndex == teamNumber - 1;
            
            // 获取对应的中文名称
            final int styleIndex = styleTypes.indexOf(team['style']);
            final String displayStyle = _isChineseLocale(context) && styleIndex != -1
                ? styleTypesZh[styleIndex] 
                : team['style'];
            
            return Card(
              color: isSelected ? Colors.blueGrey[700] : Colors.grey[800],
              child: InkWell(
                onTap: () {
                  if (!isSelected) {
                    _showCopyConfirmationDialog(teamNumber - 1);
                  }
                },
                child: Container(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${team['name']}',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${_isChineseLocale(context) ? "队伍索引" : "Team Index"}: $teamNumber   ${_isChineseLocale(context) ? "成员" : "Member"}: ${team['selectedMembers']}/12   ${_isChineseLocale(context) ? "队伍流派" : "Team Style"}:$displayStyle ',
                        style: const TextStyle(
                          color: Colors.grey,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
  
  // 显示复制确认对话框
  void _showCopyConfirmationDialog(int targetTeamIndex) {
    final configManager = ConfigManager();
    final sourceTeamName = teamNames[selectedTeamIndex];
    final targetTeamName = configManager.teamConfigs[targetTeamIndex]?.teamName.isNotEmpty == true
        ? configManager.teamConfigs[targetTeamIndex]!.teamName
        : 'Team ${targetTeamIndex + 1}';
    
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text(_isChineseLocale(context) ? "确认复制" : "Confirm Copy"),
          content: Text(
              '${_isChineseLocale(context) ? "将复制" : "It will copy"} [$sourceTeamName] ${_isChineseLocale(context) ? "到" : "to"} [$targetTeamName]',
              style: TextStyle(color: msBlue),
              ),
          actions: [
            TextButton(
              onPressed: Navigator.of(context).pop,
              child: Text(_isChineseLocale(context) ? "取消" : "Cancel"),
            ),
            TextButton(
              onPressed: () {
                Navigator.of(context).pop(); // 关闭确认对话框
                Navigator.of(context).pop(); // 关闭队伍选择对话框
                
                // 执行复制操作
                _copyTeamConfiguration(targetTeamIndex);
              },
              child: Text(_isChineseLocale(context) ? "确定" : "Confirm"),
            ),
          ],
        );
      },
    );
  }
  
  // 复制队伍配置
  void _copyTeamConfiguration(int targetTeamIndex) {
    final configManager = ConfigManager();
    
    // 调用ConfigManager的复制方法
    configManager.copyTeamConfig(selectedTeamIndex, targetTeamIndex);
    
    // 保存配置
    configManager.saveTeamConfig();
    
    // 重新加载配置并刷新UI
    _loadTeamConfigsFromManager();
    
    setState(() {});
    
    // 显示成功提示
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(_isChineseLocale(context) ? "队伍配置复制成功" : "Team configuration copied successfully"),
        duration: Duration(seconds: 2),
      ),
    );
  }
}
import 'package:flutter/material.dart';

class StyleTypeHelper {
  static const List<String> styleTypes = [
    "Bleed", "Burn", "Rupture", "Poise", "Tremor", "Blunt", "Pierce", "Slash", "Charge", "Sinking", "Keywordless"
  ];
  
  static const List<String> styleTypesZh = [
    "流血", "燃烧", "破裂", "呼吸法", "震颤", "打击", "突刺", "斩击", "充能", "沉沦", "泛用"
  ];
  
  // 将英文流派类型转换为本地化显示名称
  static String getLocalizedStyleType(String styleType, BuildContext context) {
    int styleIndex = styleTypes.indexOf(styleType);
    if (styleIndex != -1) {
      bool isChinese = _isChineseLocale(context);
      return isChinese ? styleTypesZh[styleIndex] : styleTypes[styleIndex];
    }
    
    return styleType; // 如果未找到对应类型，则返回原始值
  }
  
  // 检查当前是否为中文环境
  static bool _isChineseLocale(BuildContext context) {
    final locale = Localizations.localeOf(context);
    return locale.languageCode == 'zh';
  }
  
  // 获取所有流派类型的英文名称
  static List<String> getStyleTypeKeys() {
    return List.from(styleTypes);
  }
  
  // 获取所有流派类型的中文名称
  static List<String> getStyleTypeValues() {
    return List.from(styleTypesZh);
  }
}
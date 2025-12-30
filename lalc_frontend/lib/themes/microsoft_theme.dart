import 'package:flutter/material.dart';

/// 微软主题风格实现
class MicrosoftTheme {
  /// 创建微软风格的主题数据
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: false,
      primarySwatch: Colors.blue,
      brightness: Brightness.light,
      scaffoldBackgroundColor: Colors.white,
      
      // AppBar 样式
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF0078D4), // 微软蓝色
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      
      // 按钮样式
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith<Color>(
            (Set<WidgetState> states) {
              if (states.contains(WidgetState.disabled)) {
                return const Color(0xFFCCCCCC);
              }
              return const Color(0xFF0078D4); // 微软蓝色
            },
          ),
          foregroundColor: WidgetStateProperty.resolveWith<Color>(
            (Set<WidgetState> states) {
              if (states.contains(WidgetState.disabled)) {
                return Colors.black54;
              }
              return Colors.white;
            },
          ),
          padding: WidgetStateProperty.all<EdgeInsets>(
            const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          ),
          shape: WidgetStateProperty.all<RoundedRectangleBorder>(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(4),
            ),
          ),
        ),
      ),
      
      // 文本按钮样式
      textButtonTheme: TextButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStateProperty.resolveWith<Color>(
            (Set<WidgetState> states) {
              if (states.contains(WidgetState.disabled)) {
                return const Color(0xFFCCCCCC);
              }
              return const Color(0xFF0078D4);
            },
          ),
        ),
      ),
      
      // 文本字段样式
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFFCCCCCC)),
          borderRadius: BorderRadius.zero,
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFF0078D4), width: 2),
          borderRadius: BorderRadius.zero,
        ),
        enabledBorder: OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFFCCCCCC)),
          borderRadius: BorderRadius.zero,
        ),
      ),
      
      // 卡片样式
      cardTheme: const CardThemeData(
        color: Colors.white,
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.zero,
          side: BorderSide(color: Color(0xFFE1E1E1), width: 1),
        ),
      ),
      
      // 列表磁贴样式
      listTileTheme: const ListTileThemeData(
        iconColor: Color(0xFF0078D4),
      ),
      
      // 单选框和复选框样式
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith<Color?>(
          (Set<WidgetState> states) {
            if (states.contains(WidgetState.selected)) {
              return const Color(0xFF0078D4);
            }
            return null;
          },
        ),
        checkColor: WidgetStateProperty.all<Color>(Colors.white),
        side: const BorderSide(color: Color(0xFFCCCCCC), width: 2),
      ),
      
      radioTheme: RadioThemeData(
        fillColor: WidgetStateProperty.resolveWith<Color?>(
          (Set<WidgetState> states) {
            if (states.contains(WidgetState.selected)) {
              return const Color(0xFF0078D4);
            }
            return null;
          },
        ),
      ),
      
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith<Color?>(
          (Set<WidgetState> states) {
            if (states.contains(WidgetState.selected)) {
              return Colors.white;
            }
            return null;
          },
        ),
        trackColor: WidgetStateProperty.resolveWith<Color?>(
          (Set<WidgetState> states) {
            if (states.contains(WidgetState.selected)) {
              return const Color(0xFF0078D4);
            }
            return null;
          },
        ),
      ),
      
      // 进度条样式
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: Color(0xFF0078D4),
        circularTrackColor: Color(0xFFCCCCCC),
      ),
      
      // Snackbar样式
      snackBarTheme: const SnackBarThemeData(
        backgroundColor: Color(0xFF0078D4),
        contentTextStyle: TextStyle(
          color: Colors.white,
        ),
      ),
      
      // Tooltip样式
      tooltipTheme: const TooltipThemeData(
        decoration: BoxDecoration(
          color: Color(0xFF0078D4),
          borderRadius: BorderRadius.zero,
        ),
        textStyle: TextStyle(
          color: Colors.white,
        ),
      ),
      
      // 下拉按钮样式
      dropdownMenuTheme: DropdownMenuThemeData(
        textStyle: const TextStyle(color: Color(0xFF0078D4)),
        menuStyle: MenuStyle(
          backgroundColor: WidgetStateProperty.all<Color>(Colors.white),
        ),
      ),
      
      // FilterChip样式
      chipTheme: const ChipThemeData(
        selectedColor: Color(0xFF0078D4),
        backgroundColor: Color(0xFFE1E1E1),
        labelStyle: TextStyle(color: Colors.black),
        secondaryLabelStyle: TextStyle(color: Colors.white),
        padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      ),
    );
  }
  
  /// 创建深色微软主题
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: false,
      primarySwatch: Colors.blue,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: const Color(0xFF1F1F1F),
      fontFamily: "SmileySans",
      
      // AppBar 样式
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF0078D4), // 微软蓝色
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      
      // 按钮样式
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith<Color>(
            (Set<WidgetState> states) {
              if (states.contains(WidgetState.disabled)) {
                return const Color(0xFF454545);
              }
              return const Color(0xFF0078D4); // 微软蓝色
            },
          ),
          foregroundColor: WidgetStateProperty.resolveWith<Color>(
            (Set<WidgetState> states) {
              if (states.contains(WidgetState.disabled)) {
                return Colors.white38;
              }
              return Colors.white;
            },
          ),
          padding: WidgetStateProperty.all<EdgeInsets>(
            const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          ),
          shape: WidgetStateProperty.all<RoundedRectangleBorder>(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(4),
            ),
          ),
        ),
      ),
      
      // 文本按钮样式
      textButtonTheme: TextButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStateProperty.resolveWith<Color>(
            (Set<WidgetState> states) {
              if (states.contains(WidgetState.disabled)) {
                return const Color(0xFF454545);
              }
              return const Color(0xFF0078D4);
            },
          ),
        ),
      ),
      
      // 文本字段样式
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFF454545)),
          borderRadius: BorderRadius.zero,
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFF0078D4), width: 2),
          borderRadius: BorderRadius.zero,
        ),
        enabledBorder: OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFF454545)),
          borderRadius: BorderRadius.zero,
        ),
      ),
      
      // 卡片样式
      cardTheme: const CardThemeData(
        color: Color(0xFF2D2D2D),
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.zero,
          side: BorderSide(color: Color(0xFF3D3D3D), width: 1),
        ),
      ),
      
      // 列表磁贴样式
      listTileTheme: const ListTileThemeData(
        iconColor: Color(0xFF0078D4),
      ),
      
      // 单选框和复选框样式
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith<Color?>(
          (Set<WidgetState> states) {
            if (states.contains(WidgetState.selected)) {
              return const Color(0xFF0078D4);
            }
            return null;
          },
        ),
        checkColor: WidgetStateProperty.all<Color>(Colors.white),
        side: const BorderSide(color: Color(0xFF454545), width: 2),
      ),
      
      radioTheme: RadioThemeData(
        fillColor: WidgetStateProperty.resolveWith<Color?>(
          (Set<WidgetState> states) {
            if (states.contains(WidgetState.selected)) {
              return const Color(0xFF0078D4);
            }
            return null;
          },
        ),
      ),
      
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith<Color?>(
          (Set<WidgetState> states) {
            if (states.contains(WidgetState.selected)) {
              return Colors.white;
            }
            return null;
          },
        ),
        trackColor: WidgetStateProperty.resolveWith<Color?>(
          (Set<WidgetState> states) {
            if (states.contains(WidgetState.selected)) {
              return const Color(0xFF0078D4);
            }
            return null;
          },
        ),
      ),
      
      // 进度条样式
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: Color(0xFF0078D4),
        circularTrackColor: Color(0xFF454545),
      ),
      
      // Snackbar样式
      snackBarTheme: const SnackBarThemeData(
        backgroundColor: Color(0xFF0078D4),
        contentTextStyle: TextStyle(
          color: Colors.white,
        ),
      ),
      
      // Tooltip样式
      tooltipTheme: const TooltipThemeData(
        decoration: BoxDecoration(
          color: Color(0xFF0078D4),
          borderRadius: BorderRadius.zero,
        ),
        textStyle: TextStyle(
          color: Colors.white,
        ),
      ),
      
      // 下拉按钮样式
      dropdownMenuTheme: DropdownMenuThemeData(
        textStyle: const TextStyle(color: Colors.white),
        menuStyle: MenuStyle(
          backgroundColor: WidgetStateProperty.all<Color>(Color(0xFF2D2D2D)),
        ),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(
            borderSide: BorderSide(color: Color(0xFF454545)),
            borderRadius: BorderRadius.zero,
          ),
          focusedBorder: OutlineInputBorder(
            borderSide: BorderSide(color: Color(0xFF0078D4), width: 2),
            borderRadius: BorderRadius.zero,
          ),
          enabledBorder: OutlineInputBorder(
            borderSide: BorderSide(color: Color(0xFF454545)),
            borderRadius: BorderRadius.zero,
          ),
        ),
      ),
      
      // FilterChip样式
      chipTheme: const ChipThemeData(
        selectedColor: Color(0xFF0078D4),
        backgroundColor: Color(0xFF454545),
        labelStyle: TextStyle(color: Colors.white),
        secondaryLabelStyle: TextStyle(color: Colors.white),
        padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      ),
    );
  }
}
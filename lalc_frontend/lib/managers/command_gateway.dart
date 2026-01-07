import 'package:flutter/material.dart';
import 'package:lalc_frontend/managers/websocket_manager.dart';
import 'package:lalc_frontend/managers/task_status_manager.dart';
import 'package:lalc_frontend/managers/config_manager.dart';
import 'package:lalc_frontend/generated/l10n.dart';

enum TaskCommand { start, pause, resume, stop, semiAutoStart }

extension _TaskCommandExt on TaskCommand {
  String get name => toString().split('.').last;
  String get backendCommand {
    switch (this) {
      case TaskCommand.semiAutoStart:
        return 'semi_auto_start';   // 后端认识的字符串
      default:
        return name;
    }
  }
}

/// 全局唯一指令网关
class CommandGateway with ChangeNotifier {
  CommandGateway._();
  static final CommandGateway _ins = CommandGateway._();
  factory CommandGateway() => _ins;

  /* ==================== 唯一对外 API ==================== */
  /// 返回值：true-命令已发出；false-因任何预检失败被拒绝
  Future<bool> sendTaskCommand(
    BuildContext context,
    TaskCommand cmd, [
    void Function(bool success, String? msg)? onComplete,
  ]) async {
    final ws = WebSocketManager();
    if (!ws.isConnected) {
      onComplete?.call(false, S.of(context).websocket_not_connected);
      return false;
    }

    final status = TaskStatusManager();

    /* --------- 1. 状态机合法性检查 --------- */
    switch (cmd) {
      case TaskCommand.start:
      case TaskCommand.semiAutoStart:          // ← 新增
        if (status.isRunning) {
          onComplete?.call(false, S.of(context).task_already_running);
          return false;
        }
        break;
      case TaskCommand.pause:
        if (!status.isRunning || status.isPaused) return false;
        break;
      case TaskCommand.resume:
        if (!status.isPaused) return false;
        break;
      case TaskCommand.stop:
        if (!status.isRunning && !status.isPaused) return false;
        break;
    }

    /* --------- 2. 空队伍 / 空流派检查（仅对 start 命令） --------- */
    if (cmd == TaskCommand.start || cmd == TaskCommand.semiAutoStart) {
      final emptyTeams = _findTasksWithEmptyTeam();
      if (emptyTeams.isNotEmpty) {
        onComplete?.call(
            false,
            '${S.of(context).task_start_error}：'
            '${emptyTeams.map((e) => _taskName(context, e)).join(', ')} '
            '${S.of(context).no_team_configured}');
        return false;
      }

      final emptyPrefer = _findTeamsWithEmptyPreferTypes();
      if (emptyPrefer.isNotEmpty) {
        onComplete?.call(
            false,
            '${S.of(context).task_start_error}：'
            'Team ${emptyPrefer.join(', ')} '
            '${S.of(context).no_prefer_ego_type_configured}');
        return false;
      }
    }

    /* --------- 3. 发送配置（仅对 start 命令） --------- */
    if (cmd == TaskCommand.start || cmd == TaskCommand.semiAutoStart) {
      final ws = WebSocketManager();
      ws.sendConfigurations();
    }

    /* --------- 4. 真正发命令 --------- */
    ws.sendCommand(cmd.backendCommand, () => onComplete?.call(true, null));
    return true;
  }

  /* ==================== 私有辅助 ==================== */
  List<String> _findTasksWithEmptyTeam() {
    final cfg = ConfigManager();
    final List<String> empty = [];
    const needTeams = {'EXP', 'Thread', 'Mirror'};
    for (final task in needTeams) {
      final tc = cfg.taskConfigs[task];
      if (tc == null || !tc.enabled || tc.count <= 0) continue;
      if (tc.teams.isEmpty) empty.add(task);
    }
    return empty;
  }

  List<int> _findTeamsWithEmptyPreferTypes() {
    final cfg = ConfigManager();
    final List<int> empty = [];
    for (int i = 0; i < 20; i++) {
      final tc = cfg.teamConfigs[i];
      if (tc == null) continue;
      // 只检查被任务实际引用的队伍
      bool used = cfg.taskConfigs.values.any((t) =>
          t.enabled && t.count > 0 && t.teams.contains(i + 1));
      if (!used) continue;
      if (tc.selectedPreferEgoGiftTypes.isEmpty) empty.add(i + 1);
    }
    return empty;
  }

  String _taskName(BuildContext ctx, String key) {
    final s = S.of(ctx);
    switch (key) {
      case 'EXP':
        return s.exp;
      case 'Thread':
        return s.thread;
      case 'Mirror':
        return s.mirror;
      default:
        return key;
    }
  }
}
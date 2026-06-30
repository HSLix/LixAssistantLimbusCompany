"""
LALC 状态机驱动层

替换旧的轮询式 pipeline（error_handler 每 1.1s 截图×6次模板匹配 → 全空 → 继续），
用确定性的状态机驱动。

核心原则：
  - 大多数游戏流程是确定的（主菜单→脑啡肽→EXP/纽→镜牢）
  - 状态转换表驱动，不搞"我在哪？"的轮询
  - 轻量屏指纹验证取代全量模板匹配
  - 错误拦截器固定间隔执行（5s 一次），不占用每 tick 开销

用法：
  from state_machine.transitions import build_daily_flow
  from state_machine.engine import GameStateMachine, MachineContext
  
  flow = build_daily_flow(check_config)
  machine = GameStateMachine(context)
  machine.run(flow)

注意：engine.py 依赖 win32（input_handler），只可在 Windows 上运行。
states.py 和 transitions.py 纯逻辑，可在 WSL 上测试。
"""

# 不直接导入 engine（依赖 win32），由 _run_state_machine 动态导入

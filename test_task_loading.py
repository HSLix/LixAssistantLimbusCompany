#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试新的任务加载系统
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_task_loading():
    """测试新的任务加载系统"""
    print("=== 测试新的任务加载系统 ===")
    
    try:
        from executor.task import initJsonTask
        
        # 加载任务
        print("正在加载任务...")
        tasks = initJsonTask()
        
        print(f"\n✓ 成功加载了 {len(tasks)} 个任务")
        
        # 按模块统计任务数量
        task_modules = {}
        for task_name in tasks.keys():
            if task_name.startswith("FullAuto"):
                module = "FullAuto"
            elif task_name.startswith("SemiAuto"):
                module = "SemiAuto"
            elif task_name.startswith("EXP") or task_name.startswith("SkipEXP"):
                module = "EXP"
            elif task_name.startswith("Thread") or task_name.startswith("SkipThread"):
                module = "Thread"
            elif task_name in ["End", "TouchToStart", "GetPassMissionCoin", "test"]:
                module = "Common"
            else:
                module = "Other"
            
            task_modules[module] = task_modules.get(module, 0) + 1
        
        print("\n任务模块统计:")
        for module, count in sorted(task_modules.items()):
            print(f"  {module}: {count} 个任务")
        
        # 检查关键任务是否存在
        key_tasks = [
            "End", "TouchToStart", "FullAutoEntrance", "SemiAutoEntrance",
            "EXPEntrance", "ThreadEntrance", "MirrorEntrance",
            "EXPCheckpoint", "ThreadCheckpoint", "MirrorCheckpoint"
        ]
        
        print("\n关键任务检查:")
        for task_name in key_tasks:
            if task_name in tasks:
                print(f"  ✓ {task_name}")
            else:
                print(f"  ✗ {task_name} (缺失)")
        
        # 检查Checkpoint任务
        checkpoint_tasks = [name for name, task in tasks.items() if task.action == 'Checkpoint']
        print(f"\nCheckpoint任务 ({len(checkpoint_tasks)} 个):")
        for task_name in checkpoint_tasks:
            task = tasks[task_name]
            print(f"  {task_name}: {task.checkpoint_name} (max: {task.max_count})")
        
        print("\n✓ 任务加载测试完成")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_task_loading() 
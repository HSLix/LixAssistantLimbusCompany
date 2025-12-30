# 全局任务节点注册表
import os
import json

from workflow.task_node import TaskNode



TASK_REGISTRY = {}

def get_task(task_name:str):
    if task_name not in TASK_REGISTRY:
        raise KeyError(f"未找到名称为 '{task_name}' 的任务节点")
    return TASK_REGISTRY[task_name]

def register_task_node(task_node):
    """
    注册任务节点到全局注册表
    :param task_node: 任务节点实例
    """
    TASK_REGISTRY[task_node.name] = task_node

def create_task_node(task_name, task_config):
    """
    根据配置创建任务节点（基本任务节点不在其中）
    :param task_name: 任务名称
    :param task_config: 任务配置
    :return: TaskNode实例
    """
    # 获取任务类型，默认为普通任务节点
    task_type = task_config.get("type", "normal")
    action_name = task_config.get("action", "empty")

    recognition = task_config.get("recognition", "direct")
    is_inverse = task_config.get("inverse", False)
    rate_limit_time = task_config.get("rate_limit", 1)
    
    # 获取params参数，如果没有则使用空字典
    params = task_config.get("params", {})
    
    # 获取next参数
    next_tasks = task_config.get("next", [])
    
    # 获取interrupt参数
    interrupt_tasks = task_config.get("interrupt", None)
    if interrupt_tasks is None:
        interrupt_tasks = ["error_handler"]
    
    # 创建基础任务节点
    task_node = TaskNode(
        name=task_name,
        action=action_name,
        type=task_type,
        recognition=recognition,
        inverse=is_inverse,
        rate_limit=rate_limit_time,
        **params
    )

    if task_type == "check":
        task_node.set_param("execute_count", task_node.get_param("execute_count", 0))
    
    # 设置next属性
    task_node.next = next_tasks
    task_node.interrupt = interrupt_tasks
    
    return task_node

def clear_error_task_interrupts():
    """
    将来自error.json的任务节点的interrupt置空
    """
    for task_name, task_node in TASK_REGISTRY.items():
        # 检查任务名称是否包含error_（通常error.json中的任务会包含error_关键字）
        if "error_" in task_name.lower():
            task_node.interrupt = []

def replace_action_with_task_node():
    """
    遍历所有任务，将action中的值替换为实际的task node
    """
    for task_name, task_node in TASK_REGISTRY.items():
        task_node.action = get_task(task_node.action)
        # 如果action不是指向注册表中的任务，则报错

def replace_next_interrupt_with_task_nodes():
    """
    遍历所有任务节点，将next和interrupt列表中的任务名称替换为对应的实际任务节点对象
    """
    for task_name, task_node in TASK_REGISTRY.items():
        # 替换next列表中的任务名称为实际任务节点对象
        if hasattr(task_node, 'next'):
            # next必须是列表
            if not isinstance(task_node.next, list):
                raise TypeError(f"任务 '{task_name}' 的next属性必须是列表")
            
            # 原位替换next列表中的任务名称
            for i, next_task_name in enumerate(task_node.next):
                task_node.next[i] = get_task(next_task_name)
        
        # 替换interrupt列表中的任务名称为实际任务节点对象
        if hasattr(task_node, 'interrupt'):
            # interrupt必须是列表
            if not isinstance(task_node.interrupt, list):
                raise TypeError(f"任务 '{task_name}' 的interrupt属性必须是列表")
            
            # 原位替换interrupt列表中的任务名称
            for i, interrupt_task_name in enumerate(task_node.interrupt):
                task_node.interrupt[i] = get_task(interrupt_task_name)



def replace_params_origin_with_task_node():
    """
    遍历所有任务节点，将params中origin和disable_node属性的字符串值替换为对应的任务节点对象
    """
    for task_name, task_node in TASK_REGISTRY.items():
        # 检查params中是否有origin属性
        if 'origin' in task_node.params:
            origin_value = task_node.params['origin']
            # 检查origin是否为字符串类型
            if isinstance(origin_value, str):
                # 检查origin指向的任务是否存在
                if origin_value in TASK_REGISTRY:
                    # 将origin的字符串值替换为实际的task node
                    task_node.params['origin'] = get_task(origin_value)
            else:
                raise TypeError(f"任务 '{task_name}' 的parms/origin属性必须是字符串")
            
        if 'disable_node' in task_node.params:
            disable_value = task_node.params['disable_node']
            # 检查origin是否为字符串类型
            if isinstance(disable_value, str):
                # 检查origin指向的任务是否存在
                if disable_value in TASK_REGISTRY:
                    # 将origin的字符串值替换为实际的task node
                    task_node.params['disable_node'] = get_task(disable_value)
            else:
                raise TypeError(f"任务 '{task_name}' 的parms/disable_node属性必须是字符串")

def load_all_task_configs():
    """
    刷新从配置目录中读取所有JSON文件，注册成任务节点
    """
    # 尝试多个可能的配置目录路径
    config_dirs = [r"./config/task", r"../config/task"]
    config_root = None
    
    for config_path in config_dirs:
        if os.path.exists(config_path):
            config_root = config_path
            break
    
    if config_root is None:
        raise FileNotFoundError("无法找到config/task目录")
    
    # 遍历配置目录下的所有JSON文件
    for filename in os.listdir(config_root):
        if filename.endswith('.json'):
            file_path = os.path.join(config_path, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                
            # 为每个配置项创建任务节点
            for task_name, task_config in config_data.items():
                # 创建任务节点
                task_node = create_task_node(task_name, task_config)
                
                # 注册任务节点
                register_task_node(task_node)

def validate_task_references():
    """
    验证所有任务节点的next引用是否存在
    如果引用的任务不存在，则抛出异常
    """
    for task_name, task_node in TASK_REGISTRY.items():
        # 检查任务节点的next属性必须是列表
        if hasattr(task_node, 'next'):
            if not isinstance(task_node.next, list):
                raise TypeError(f"任务 '{task_name}' 的next属性必须是列表")
            
            # 检查每个引用的任务是否存在
            for next_task_item in task_node.next:
                # 如果是字符串，直接检查TASK_REGISTRY
                if isinstance(next_task_item, str):
                    if next_task_item not in TASK_REGISTRY:
                        raise ValueError(f"任务 '{task_name}' 引用了不存在的下一个任务 '{next_task_item}'")
                # 如果是TaskNode对象，检查其name是否在TASK_REGISTRY中
                elif hasattr(next_task_item, 'name'):
                    if next_task_item.name not in TASK_REGISTRY:
                        raise ValueError(f"任务 '{task_name}' 引用了不存在的下一个任务 '{next_task_item.name}'")
        
        # 检查interrupt属性必须是列表
        if hasattr(task_node, 'interrupt'):
            if not isinstance(task_node.interrupt, list):
                raise TypeError(f"任务 '{task_name}' 的interrupt属性必须是列表")
            
            # 检查每个引用的任务是否存在
            for interrupt_task_item in task_node.interrupt:
                # 如果是字符串，直接检查TASK_REGISTRY
                if isinstance(interrupt_task_item, str):
                    if interrupt_task_item not in TASK_REGISTRY:
                        raise ValueError(f"任务 '{task_name}' 引用了不存在的interrupt任务 '{interrupt_task_item}'")
                # 如果是TaskNode对象，检查其name是否在TASK_REGISTRY中
                elif hasattr(interrupt_task_item, 'name'):
                    if interrupt_task_item.name not in TASK_REGISTRY:
                        raise ValueError(f"任务 '{task_name}' 引用了不存在的interrupt任务 '{interrupt_task_item.name}'")
                

def list_registered_tasks():
    """
    列出所有已注册的任务节点
    """
    print("Registered Tasks:")
    for name, task in TASK_REGISTRY.items():
        print(f"- {name}: {task}")

def init_tasks():
    # 自动加载所有任务配置，由于会刷新，必须先放最前面
    load_all_task_configs()
    
    # 清空error.json中任务节点的interrupt
    clear_error_task_interrupts()
    
    # 替换 action 的 action name 为真正的任务节点
    replace_action_with_task_node()
    
    # 替换 next 和 interrupt 中的任务名称为实际任务节点对象
    replace_next_interrupt_with_task_nodes()
    
    # 替换 params 中的 origin 属性为实际任务节点对象
    replace_params_origin_with_task_node()
    
    # 验证任务引用
    validate_task_references()

if __name__ == "__main__":
    init_tasks()
    # 测试函数，输出所有已注册的任务节点
    list_registered_tasks()
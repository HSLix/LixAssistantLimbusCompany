"""测试自有应用动作注册；不通过 Manifest 加载 Action 源码。"""
from types import MappingProxyType
from lalc.actions import TrustedAction, application_actions


def name_ready(ctx, *, name: str) -> bool:
    return bool(name.strip())


def simulated_greeting(ctx, *, name: str) -> str:
    return f"Hello, {name.strip()}！"


def observe(ctx, *, name: str = "state") -> dict[str, str]:
    return {"name": name}


def control(ctx, *, name: str = "click") -> dict[str, str]:
    return {"name": name}


def test_actions():
    return {**application_actions(),
            "actions.name_ready": TrustedAction(name_ready, "observe"),
            "actions.simulated_greeting": TrustedAction(simulated_greeting, "control"),
            "observe": TrustedAction(observe, "observe"),
            "control": TrustedAction(control, "control")}


def register_sources(manager, sources):
    """将测试的有状态 callable 注册在应用层，供正式执行路径调用。"""
    actions = dict(manager.actions)
    for name, (source, classification) in sources.items():
        namespace = {"__name__": f"test_action_{name}", "__file__": f"<test-action:{name}>"}
        exec(compile(source, namespace["__file__"], "exec"), namespace)
        actions[name] = TrustedAction(namespace["execute"], classification)
    manager.actions = MappingProxyType(actions)

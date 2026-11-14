"""应用统一注册的 Trusted Actions；Manifest 和 Agent 不拥有注册权限。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, overload


@dataclass(frozen=True)
class TrustedAction:
    """由应用提供的固定分类与可调用实现，签名和 docstring 即调用契约。"""

    execute: Callable[..., Any]
    classification: str

    def __post_init__(self) -> None:
        if self.classification not in {"observe", "control"} or not callable(self.execute):
            raise ValueError("Trusted Action requires a callable and observe/control classification.")


def capture_screen(ctx, *, save: bool = False, auto_park_cursor: bool = True) -> dict[str, int | str]:
    """重新捕获目标窗口客户区，替换当前内存帧，供后续匹配或 OCR 使用。

    默认只更新内存，不保存截图文件；返回观察 ID、尺寸等截图元数据，不返回原始像素。

    参数：
        ctx：执行器自动传入的运行上下文，调用 ctx.action 时不要手动提供。
        save：是否同时保存当前帧为运行证据；默认 False，True 时返回证据路径等信息。
        auto_park_cursor：是否在截图前尝试将客户区内的鼠标移到窗口右下角外；默认 True。
            归位最多尝试三次，失败记录 warning 后继续截图；False 时跳过归位。

    返回值：
        截图元数据字典，不包含原始像素：
            observation：当前窗口会话内递增的观察 ID；后续匹配和 OCR 返回同一帧的 ID。
            width、height：本次截图的完整客户区宽高，单位为原图像素。
        仅当 save=True 时另含：
            evidence_path：已保存截图证据文件的路径。
            evidence_id：证据标识，格式为 Run ID/观察 ID。
            captured_at：该帧捕获时间的 UTC ISO 8601 字符串，不是文件保存时间。
    """
    return ctx.capture_screen(save=save, auto_park_cursor=auto_park_cursor)


def ocr(ctx, *, region: dict[str, int] | None = None, min_score: float = 0.0) -> dict[str, int | dict[str, int] | list[dict[str, str | float | dict[str, int] | list[int] | list[list[int]]]]]:
    """识别当前已捕获帧中的文字，不重新截图；不支持韩文。

    返回 observation、实际 region 和完整 items，含文字、置信度、原图框、轮廓和中心坐标。
    执行器自动保留已有帧作为诊断图；未捕获截图或识别失败时抛出错误。

    参数：
        ctx：执行器自动传入的运行上下文，调用 ctx.action 时不要手动提供。
        region：客户区原图像素矩形 {x, y, width, height}；默认 None 表示全图。
            坐标须为整数，宽高须为正且矩形完全位于客户区内；返回坐标仍相对于原图。
        min_score：保留文字项的最低置信度，范围 0–1，默认 0.0；提高会过滤更多低置信度文字。

    返回值：
        字典，包含 observation、region、items：
            observation：识别所用截图的观察 ID。
            region：实际识别的原图矩形 {x, y, width, height}；全图时为完整客户区矩形。
            items：通过 min_score 过滤的文字项列表；无文字或全部被过滤时为 []。
        每个 items 元素为一个字典，包含：
            text：识别出的文字字符串。
            score：该文字项的识别置信度，范围 0–1，不是模板匹配分数或 SIFT 内点数。
            box：文字的原图轴对齐包围框 {x, y, width, height}，坐标和宽高均为整数像素。
            polygon：文字轮廓的四个原图顶点，格式为 [[x1, y1], ..., [x4, y4]]，坐标为整数。
            centerxy：文字包围框中心 [x, y]，坐标为整数。
        所有位置均相对于完整客户区左上角，已加回 region 偏移，调用方不要重复平移。
    """
    return ctx.ocr(region=region, min_score=min_score)


def match_asset(ctx, *, asset: str, priority_tags: list[str] | None = None, region: dict[str, int] | None = None,
                threshold: float = 0.9, nms: bool = True,
                nms_iou_threshold: float = 0.5) -> list[dict[str, str | int | float | list[str] | tuple[int, int] | dict[str, float]]]:
    """在当前已捕获帧中按 Asset 逻辑名执行原尺寸模板匹配，不重新截图或自动保存截图。

    合并选定模板批次的结果，再统一 NMS；按分数降序、同分按 y、x 和模板哈希排序。
    返回全部命中及 centerxy、分数、模板来源、标签、归一化框和 observation；无命中返回 []。
    多个命中由业务 Step 判断歧义并记录 warning，不自动选一个或执行点击；非空结果更新使用索引。

    参数：
        ctx：执行器自动传入的运行上下文，调用 ctx.action 时不要手动提供。
        asset：共享素材库中的完整逻辑名，例如 ui/claim；不含文件扩展名或图片哈希。
        priority_tags：优先标签列表，默认 None；None 或 [] 表示尝试全部模板。
            包含任一优先标签的模板先整组匹配；有命中则只返回该批，否则匹配剩余模板。
        region：客户区原图像素矩形 {x, y, width, height}；默认 None 表示全图。
            各值须为整数，宽高为正且不能越界；命中框和中心仍使用原图坐标。
        threshold：模板匹配最低分数，范围 0–1，默认 0.9；越高越严格，不是 SIFT 内点比例。
        nms：是否抑制同一批次中重叠的命中框，默认 True；False 保留全部达标候选。
        nms_iou_threshold：NMS 的矩形交并比阈值，范围 0–1，默认 0.5。
            IoU 严格大于阈值时保留排序更靠前的框；越低抑制越强，仅在 nms=True 时生效。

    返回值：
        全部保留命中的列表，按分数降序、同分按 y、x 和模板哈希排序；无命中返回 []。
        每个命中为一个字典，包含：
            x、y：命中矩形左上角的客户区原图像素坐标，整数。
            width、height：命中矩形宽高，单位为原图像素，整数。
            centerxy：命中框中心的整数坐标 (x, y)，可直接用于 control.click 的 centerxy 参数。
            path：素材库内的相对路径，格式为逻辑名/完整哈希.png；不是截图文件路径。
            sha256：实际使用模板的完整 SHA-256 哈希。
            tags：该模板本次读取的标签列表，无标签时为 []。
            logical_name：本次匹配的 Asset 逻辑名。
            observation：所用截图的观察 ID，可与 capture_screen 的 observation 对应。
            normalized_region：{x, y, width, height} 的归一化框；x/width 除以完整客户区宽度，
                y/height 除以完整客户区高度，不以搜索 region 的宽高为分母。
            score：模板匹配分数，范围 0–1，越高表示像素匹配越接近；不是概率。
        命中坐标已加回 region 偏移；width、height 等于所用模板的原始宽高。
    """
    return ctx.match_asset(asset, priority_tags=priority_tags, region=region, threshold=threshold, nms=nms,
                           nms_iou_threshold=nms_iou_threshold)


def match_feature(ctx, *, asset: str, region: dict[str, int] | None = None,
                  nms: bool = True, nms_iou_threshold: float = 0.4,
                  grayscale: bool = True, scale: int = 3, clahe: bool = True,
                  nfeatures: int = 0, n_octave_layers: int = 3, contrast_threshold: float = 0.04,
                  edge_threshold: float = 10.0, sigma: float = 1.6, precise_upscale: bool = False,
                  pair_ratio: float = 0.75, ransac_threshold: float = 4 / 3, min_inliers: int = 6,
                  min_inlier_ratio: float = 0.4, min_scale: float = 0.5, max_scale: float = 2.0,
                  max_deformation: float = 2.0, min_coverage: float = 0.1) -> list[dict[str, str | int | float | list[str] | tuple[int, int] | dict[str, float]]]:
    """在当前已捕获帧中按 Asset 逻辑名执行 SIFT 多目标特征匹配，适用于缩放或形变目标。

    尝试该逻辑名下全部模板，不使用优先标签短路；统一排序和 NMS，不重新截图或自动保存截图。
    返回原图框、centerxy、模板来源、标签、observation，以及内点数／比例、覆盖率和几何指标。
    score 是内点数，不能与模板相似度分数比较；无命中返回 []，非空结果更新使用索引。
    多命中由业务 Step 判断歧义，不自动点击；低纹理、重复图案或退化投影仍可能误检或漏检。

    参数：
        ctx：执行器自动传入的运行上下文，调用 ctx.action 时不要手动提供。
        asset：共享素材库中的完整逻辑名，例如 mirror/node/regular_encounter；不含扩展名或哈希。
        region：客户区原图像素矩形 {x, y, width, height}；默认 None 表示全图。
            各值须为整数，宽高为正且不能越界；结果始终还原为原图坐标。
        nms：是否对整组结果统一抑制重叠框，默认 True；False 保留全部达标候选。
        nms_iou_threshold：NMS 矩形交并比阈值，范围 0–1，默认 0.4；仅在 nms=True 时生效。
            按内点数降序、同分按 y、x 和模板哈希保留框，抑制 IoU 严格超限的后续框；越低抑制越强。
        grayscale：是否在增强前先转灰度，默认 True；False 时 CLAHE 只增强彩色图的 Lab 亮度。
            无论此项取值如何，SIFT 最终均提取灰度特征，不提供彩色描述子。
        scale：处理图放大倍数，整数 1–5，默认 3；截图和模板同时放大，不改变返回坐标的单位。
        clahe：是否使用 CLAHE 增强局部对比度，默认 True；处理始终从原始像素生成。
        nfeatures：每幅处理图的 SIFT 特征数量上限，整数 0–100000，默认 0 表示不限。
        n_octave_layers：SIFT 每组尺度空间的层数，整数 1–10，默认 3。
        contrast_threshold：SIFT 低对比度特征过滤阈值，大于 0 且不超过 1，默认 0.04。
            提高会过滤更多弱特征，可能减少噪声，也可能漏掉低对比度目标。
        edge_threshold：SIFT 边缘响应过滤阈值，大于 0 且不超过 100，默认 10.0。
            提高会放宽边缘特征过滤，保留更多边缘响应。
        sigma：SIFT 初始高斯平滑的 sigma，大于 0 且不超过 10，默认 1.6，单位为处理图像素。
        precise_upscale：是否启用 SIFT 的精确上采样，默认 False；与 scale 的整图放大分别生效。
        pair_ratio：描述子最近邻／次近邻距离比阈值，严格位于 0–1 之间，默认 0.75。
            只有最近邻距离小于该阈值乘次近邻距离才保留配对；越低越严格。
        ransac_threshold：RANSAC 几何重投影容差，单位为原图像素，大于 0 且不超过 100，默认 4/3。
            内部随 scale 换算；越大越允许配对点偏离几何模型。
        min_inliers：每个候选的最少内点数，整数 4–100000，默认 6；同一位置的重复方向不重复计数。
        min_inlier_ratio：候选内点数占其投影范围内配对位置数的最低比例，大于 0 且不超过 1，默认 0.4。
            只统计当前候选范围，不以全屏特征为分母；必须同时满足 min_inliers。
        min_scale：目标相对于原始模板的最小几何缩放，范围 0.001–100，默认 0.5。
            与处理图放大倍数 scale 无关，不能大于 max_scale。
        max_scale：目标相对于原始模板的最大几何缩放，范围 0.001–100，默认 2.0。
        max_deformation：投影局部最大拉伸形变比，范围 1–100，默认 2.0；越接近 1 越严格。
        min_coverage：内点凸包在模板和目标投影中的最低面积占比，范围 0–1，默认 0.1。
            两侧覆盖率都须达标；提高可过滤仅靠局部证据支撑的大框，但可能增加漏检。

    返回值：
        全部保留命中的列表，按内点数降序、同分按 y、x 和模板哈希排序；无命中返回 []。
        每个命中为一个字典，包含：
            x、y：命中矩形左上角的客户区原图像素坐标，整数。
            width、height：命中矩形宽高，单位为原图像素，整数。
            centerxy：命中框中心的整数坐标 (x, y)，可直接用于 control.click 的 centerxy 参数。
            path：素材库内的相对路径，格式为逻辑名/完整哈希.png；不是截图文件路径。
            sha256：实际使用模板的完整 SHA-256 哈希。
            tags：该模板本次读取的标签列表，无标签时为 []。
            logical_name：本次匹配的 Asset 逻辑名。
            observation：所用截图的观察 ID，可与 capture_screen 的 observation 对应。
            normalized_region：{x, y, width, height} 的归一化框；x/width 除以完整客户区宽度，
                y/height 除以完整客户区高度，不以搜索 region 的宽高为分母。
            score：用于排序的内点数，与 inliers 相同；不是 0–1 的相似度或概率。
            inliers：当前候选通过几何模型验证并按特征位置去重后的内点数。
            good_matches：候选投影范围内、通过描述子距离比筛选的配对位置数量；同一截图位置只计一次。
            inlier_ratio：inliers / good_matches；分母是当前候选范围的配对位置数，不是全屏特征数。
            template_coverage：内点在模板中的凸包面积除以处理后模板面积。
            target_coverage：内点在目标中的凸包面积除以目标投影面积。
            min_scale、max_scale：投影角点局部变换的最小／最大几何缩放，相对于模板，
                不包含处理图放大倍数 scale；是实测指标，不是传入的过滤界限。
            deformation：投影角点局部变换的最大拉伸比，越接近 1 表示局部形变越小。
        矩形是目标投影的轴对齐包围框，已加回 region 偏移并还原为原图像素；可能不同于模板尺寸。
    """
    return ctx.match_feature(asset, region=region, nms=nms, nms_iou_threshold=nms_iou_threshold,
        grayscale=grayscale, scale=scale, clahe=clahe,
        nfeatures=nfeatures, n_octave_layers=n_octave_layers, contrast_threshold=contrast_threshold,
        edge_threshold=edge_threshold, sigma=sigma, precise_upscale=precise_upscale,
        pair_ratio=pair_ratio, ransac_threshold=ransac_threshold, min_inliers=min_inliers,
        min_inlier_ratio=min_inlier_ratio, min_scale=min_scale, max_scale=max_scale,
        max_deformation=max_deformation, min_coverage=min_coverage)


def crop_asset(ctx, *, asset: str, region: dict[str, int], tags: list[str] | None = None) -> dict[str, str | int | list[str] | dict[str, int]]:
    """重新截图并将指定客户区裁剪为共享 Asset，保存完整哈希图片、标签和来源记录。

    裁剪使用本次新截图，不使用旧内存帧或截图文件；不修改 Manifest，后续匹配可立即读取。
    同哈希图片复用且不覆盖原图；标签按本次 tags 整体替换。返回素材路径、哈希、标签及观察来源。

    参数：
        ctx：执行器自动传入的运行上下文，调用 ctx.action 时不要手动提供。
        asset：裁剪图所属的完整逻辑名，例如 ui/claim；目录可新建，不含扩展名或图片哈希。
        region：本次新截图中的客户区原图像素矩形 {x, y, width, height}。
            各值须为整数，宽高须为正且不能越界；调用前应确认界面稳定，避免裁到变化后的内容。
        tags：该哈希图片的标签列表，例如 ["zh", "event"]；默认 None，按空列表保存。
            不是追加；同名同哈希再次裁剪也会整体替换标签，None 或 [] 会清空已有标签。
    """
    return ctx.crop_asset(asset, region=region, tags=tags)


@overload
def click(ctx, *, centerxy: tuple[int, int]) -> None: ...


@overload
def click(ctx, *, x: int, y: int) -> None: ...


def click(ctx, *, centerxy: tuple[int, int] | None = None, x: int | None = None, y: int | None = None) -> None:
    """在目标窗口客户区执行一次鼠标点击；返回不代表业务状态已完成，应重新截图确认。

    优先使用 centerxy=target["centerxy"]；也可提供完整 x/y，两种形式不可混用。
    坐标以客户区左上角为原点，单位为原图像素，须位于当前客户区内。

    参数：
        ctx：执行器自动传入的运行上下文，调用 ctx.action 时不要手动提供。
        centerxy：整数坐标元组 (x, y)，通常直接取匹配结果的 centerxy；默认 None。
            提供时不能同时传 x 或 y。
        x：点击位置的横坐标整数；默认 None，仅在不用 centerxy 时与 y 一起提供。
        y：点击位置的纵坐标整数；默认 None，仅在不用 centerxy 时与 x 一起提供。
    """
    if centerxy is not None:
        if x is not None or y is not None:
            raise ValueError("click requires either centerxy or x/y, not both")
        x, y = centerxy
    elif x is None or y is None:
        raise ValueError("click requires centerxy or both x and y")
    ctx.control_input("click", x=x, y=y)


def key_press(ctx, *, key: str) -> None:
    """向目标窗口发送一次按键并释放；不表示游戏已完成该按键对应的业务操作。

    参数：
        ctx：执行器自动传入的运行上下文，调用 ctx.action 时不要手动提供。
        key：按键名称，只支持 esc、p、enter，不区分大小写；不支持组合键或任意键名。
    """
    ctx.control_input("key_press", key=key)


def drag(ctx, *, x: int, y: int, end_x: int, end_y: int, seconds: float = 2.5) -> None:
    """在目标窗口客户区按住鼠标，从起点拖动到终点后释放，过程中响应物理接管与取消。

    起终点均使用客户区原图像素坐标，须位于当前客户区内；返回后应重新观察业务状态。

    参数：
        ctx：执行器自动传入的运行上下文，调用 ctx.action 时不要手动提供。
        x：拖动起点的横坐标整数。
        y：拖动起点的纵坐标整数。
        end_x：拖动终点的横坐标整数。
        end_y：拖动终点的纵坐标整数。
        seconds：拖动持续时间，单位为秒，范围 0–60，默认 2.5；必须为有限数值。
    """
    ctx.control_input("drag", x=x, y=y, end_x=end_x, end_y=end_y, seconds=seconds)


def wait(ctx, *, seconds: float) -> None:
    """协作等待指定时长，不注入鼠标或键盘输入，属于 observe 动作。

    等待期间继续响应暂停、物理接管与取消；Workflow 中发生接管并恢复后，重新等待完整时长。
    等待返回只表示时间已到，不证明加载或动画已结束，业务代码仍需观察确认。

    参数：
        ctx：执行器自动传入的运行上下文，调用 ctx.action 时不要手动提供。
        seconds：等待时长，单位为秒，范围 0–60，必须为有限数值；无默认值。
    """
    ctx.control_input("wait", seconds=seconds)


def restart_game(ctx) -> None:
    """从已保存的 Steam 安装重启游戏，并等待新目标窗口绑定和置前。

    先尝试正常关闭，超时后强制终止；随后启动游戏并重新建立窗口会话。
    返回不保证已登录或已进入可操作业务界面，需重新截图确认；重启失败会终止本次运行。
    不接受业务参数，不能通过此动作指定其他程序或安装路径。

    参数：
        ctx：执行器自动传入的运行上下文，调用 ctx.action 时不要手动提供。
    """
    ctx.control_input("restart_game")


def application_actions() -> dict[str, TrustedAction]:
    """构建应用唯一动作表；测试可由应用层提供替身表。"""
    return {
        "observe.capture_screen": TrustedAction(capture_screen, "observe"),
        "observe.ocr": TrustedAction(ocr, "observe"),
        "observe.match_asset": TrustedAction(match_asset, "observe"),
        "observe.match_feature": TrustedAction(match_feature, "observe"),
        "observe.crop_asset": TrustedAction(crop_asset, "observe"),
        "control.click": TrustedAction(click, "control"),
        "control.key_press": TrustedAction(key_press, "control"),
        "control.drag": TrustedAction(drag, "control"),
        "observe.wait": TrustedAction(wait, "observe"),
        "control.restart_game": TrustedAction(restart_game, "control"),
    }

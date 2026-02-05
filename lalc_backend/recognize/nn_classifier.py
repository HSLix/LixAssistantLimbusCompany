import os
import numpy as np
import onnxruntime as ort
from PIL import Image
from scipy.special import softmax

# 模型基础目录
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ai/model")

# 两个模型的配置
MODELS = {
    "mirror_legend": {
        "path": os.path.join(MODEL_DIR, "mirror_legend", "best_model.onnx"),
        "classes": os.path.join(MODEL_DIR, "mirror_legend", "classes.txt"),
        "width": 130,
        "height": 110,
    },
    "skill_icon": {
        "path": os.path.join(MODEL_DIR, "skill_icon", "best_model.onnx"),
        "classes": os.path.join(MODEL_DIR, "skill_icon", "classes.txt"),
        "width": 80,
        "height": 80,
    },
    "mirror_path": {
        "path": os.path.join(MODEL_DIR, "mirror_path", "best_model.onnx"),
        "connections": os.path.join(MODEL_DIR, "mirror_path", "connections.txt"),
        "width": 224,
        "height": 224,
        "resize_to_model": True,
    },
    "sinner_avatar": {
        "path": os.path.join(MODEL_DIR, "sinner_avatar", "best_model.onnx"),
        "classes": os.path.join(MODEL_DIR, "sinner_avatar", "classes.txt"),
        "width": 80,
        "height": 55,
    },
}

# 全局变量：模型会话和类别映射
_sessions = {}
_class_names = {}
_connections = {}  # mirror_path专用的连接映射
_thresholds = {}  # mirror_path专用的最优阈值
_input_names = {}
_output_names = {}

# 默认使用的模型类型
DEFAULT_MODEL = "mirror_legend"


def _load_class_names(classes_path):
    """加载类别名称"""
    class_names = {}
    if os.path.exists(classes_path):
        with open(classes_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(" ", 1)
                if len(parts) >= 2:
                    idx = int(parts[0])
                    name = parts[1]
                    class_names[idx] = name
    return class_names


def _load_connections(connections_path):
    """加载连接配置（mirror_path专用）"""
    connections = {}
    if os.path.exists(connections_path):
        with open(connections_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(" ", 1)
                if len(parts) >= 2:
                    idx = int(parts[0])
                    name = parts[1]
                    connections[idx] = name
    return connections


def _load_training_config(model_path):
    """加载训练配置，获取最优阈值（mirror_path专用）"""
    config_path = os.path.join(os.path.dirname(model_path), "training_config.json")
    config = {}
    if os.path.exists(config_path):
        import json

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    return config.get("best_thresholds", None)


def _init_model(model_type="mirror_legend"):
    """
    初始化指定类型的ONNX模型

    Args:
        model_type: 模型类型 ('mirror_legend', 'skill_icon', 'mirror_path', 'sinner_avatar')
    """
    global \
        _sessions, \
        _class_names, \
        _connections, \
        _thresholds, \
        _input_names, \
        _output_names

    if model_type not in MODELS:
        raise ValueError(
            f"不支持的模型类型: {model_type}，支持的类型: {list(MODELS.keys())}"
        )

    # 检查模型文件是否存在
    model_config = MODELS[model_type]
    if not os.path.exists(model_config["path"]):
        raise FileNotFoundError(f"模型文件不存在: {model_config['path']}")

    # 如果已初始化，跳过
    if model_type in _sessions:
        return

    # 加载类别名称或连接映射
    if model_type == "mirror_path":
        _connections[model_type] = _load_connections(model_config["connections"])
        _thresholds[model_type] = _load_training_config(model_config["path"])
        print(f"加载连接映射: {len(_connections[model_type])} 个连接")
        if _thresholds[model_type] is not None:
            print(f"加载最优阈值: {_thresholds[model_type].tolist()}")
    else:
        if not os.path.exists(model_config["classes"]):
            raise FileNotFoundError(f"类别文件不存在: {model_config['classes']}")
        _class_names[model_type] = _load_class_names(model_config["classes"])

    # 初始化ONNX Runtime推理会话
    _sessions[model_type] = ort.InferenceSession(model_config["path"])
    _input_names[model_type] = _sessions[model_type].get_inputs()[0].name
    _output_names[model_type] = _sessions[model_type].get_outputs()[0].name

    print(f"加载模型: {model_type}")
    print(f"  路径: {model_config['path']}")
    print(f"  输入尺寸: {model_config['width']}x{model_config['height']}")
    if model_type == "mirror_path":
        print(f"  连接数: {len(_connections[model_type])}")
    else:
        print(f"  类别数: {len(_class_names[model_type])}")


def _preprocess_image(pil_image, model_type="mirror_legend"):
    """
    预处理PIL Image为模型输入格式

    Args:
        pil_image: PIL.Image 对象
        model_type: 模型类型

    Returns:
        numpy.ndarray: 预处理后的图像

    Raises:
        ValueError: 图片尺寸不匹配
    """
    model_config = MODELS[model_type]

    expected_width = model_config["width"]
    expected_height = model_config["height"]

    # mirror_path需要先resize到模型尺寸
    if model_config.get("resize_to_model", False):
        pil_image = pil_image.resize(
            (expected_width, expected_height), Image.Resampling.LANCZOS
        )

    # 确保是RGB格式
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")

    # 检查图片尺寸（非mirror_path模型）
    if not model_config.get("resize_to_model", False):
        width, height = pil_image.size
        if (width, height) != (expected_width, expected_height):
            raise ValueError(
                f"图片尺寸不匹配! 期望: {expected_width}x{expected_height}, "
                f"实际: {width}x{height}"
            )

    # 归一化处理
    image_np = np.array(pil_image, dtype=np.float32) / 255.0

    # 标准化处理，与训练时保持一致
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    image_np = (image_np - mean) / std

    # 调整维度顺序 (H, W, C) -> (C, H, W)
    image_np = np.transpose(image_np, (2, 0, 1))

    # 添加批次维度 (1, C, H, W)
    image_np = np.expand_dims(image_np, axis=0)

    return image_np


def classify_images(pil_images, model_type="mirror_legend"):
    """
    批量分类PIL Image，返回对应的标签名列表

    Args:
        pil_images: List[PIL.Image] - PIL Image对象列表
        model_type: 模型类型 ('mirror_legend' 或 'skill_icon')

    Returns:
        List[str]: 对应的标签名列表，顺序与输入一致
    """
    # 初始化模型
    _init_model(model_type)

    if not pil_images:
        return []

    session = _sessions[model_type]
    input_name = _input_names[model_type]
    output_name = _output_names[model_type]
    class_names = _class_names[model_type]

    results = []

    for pil_image in pil_images:
        # 预处理图片
        processed_image = _preprocess_image(pil_image, model_type)

        # 使用模型进行预测
        output = session.run([output_name], {input_name: processed_image})

        # 获取预测结果
        logits = output[0][0]

        # 应用softmax函数将logits转换为概率
        probabilities = softmax(logits)

        # 获取预测类别
        predicted_class_idx = int(np.argmax(probabilities))

        # 获取类别名称
        predicted_class_name = class_names.get(
            predicted_class_idx, f"未知类别({predicted_class_idx})"
        )

        results.append(predicted_class_name)

    return results


def classify_image(pil_image, model_type="mirror_legend"):
    """
    单张图片分类

    Args:
        pil_image: PIL.Image - 单张PIL Image对象
        model_type: 模型类型 ('mirror_legend' 或 'skill_icon')

    Returns:
        str: 预测的标签名
    """
    results = classify_images([pil_image], model_type)
    return results[0] if results else None


def classify_mirror_legend(pil_images):
    """使用镜像地牢模型分类"""
    return classify_images(pil_images, model_type="mirror_legend")


def classify_skill_icon(pil_images):
    """使用技能图标模型分类"""
    return classify_images(pil_images, model_type="skill_icon")


def classify_mirror_path(pil_images):
    """
    使用镜像路径模型识别连接（多标签分类）

    Args:
        pil_images: List[PIL.Image] - PIL Image对象列表

    Returns:
        List[Dict]: 每张图片的连接识别结果
            {
                "connections": List[bool] - 9个连接的布尔值
                "connection_names": List[str] - 激活的连接名称
            }
    """
    _init_model("mirror_path")

    if not pil_images:
        return []

    session = _sessions["mirror_path"]
    input_name = _input_names["mirror_path"]
    output_name = _output_names["mirror_path"]
    connections = _connections["mirror_path"]
    thresholds = _thresholds["mirror_path"]

    results = []

    for pil_image in pil_images:
        processed_image = _preprocess_image(pil_image, model_type="mirror_path")

        output = session.run([output_name], {input_name: processed_image})
        logits = output[0][0]

        # 应用sigmoid转换为概率
        probabilities = 1 / (1 + np.exp(-logits))

        # 使用最优阈值进行判断
        if thresholds is not None:
            predictions = probabilities > thresholds
        else:
            predictions = probabilities > 0.5

        # 获取激活的连接名称
        active_connections = []
        for idx, is_active in enumerate(predictions):
            if is_active:
                conn_name = connections.get(idx, f"未知连接({idx})")
                active_connections.append(conn_name)

        results.append(
            {
                "connections": predictions.tolist(),
                "connection_names": active_connections,
            }
        )

    return results


def classify_sinner_avatar(pil_images):
    """使用罪人头像模型分类"""
    return classify_images(pil_images, model_type="sinner_avatar")


def get_class_names(model_type="mirror_legend"):
    """
    获取指定模型的所有类别名称

    Args:
        model_type: 模型类型

    Returns:
        Dict[int, str]: 类别索引到类别名称的映射
    """
    _init_model(model_type)
    return _class_names[model_type].copy()


def get_input_shape(model_type="mirror_legend"):
    """
    获取指定模型的输入尺寸

    Args:
        model_type: 模型类型

    Returns:
        tuple: (width, height)
    """
    _init_model(model_type)
    model_config = MODELS[model_type]
    return (model_config["width"], model_config["height"])


def set_default_model(model_type):
    """
    设置默认使用的模型类型

    Args:
        model_type: 模型类型 ('mirror_legend' 或 'skill_icon')
    """
    global DEFAULT_MODEL
    if model_type in MODELS:
        DEFAULT_MODEL = model_type
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")


if __name__ == "__main__":
    import glob

    # 测试镜像地牢模型 (130x110)
    print("=== 测试镜像地牢模型 (130x110) ===")
    val_dir = "img/dataset/mirror_legend/val"

    if os.path.exists(val_dir):
        # 收集所有验证图片
        image_paths = []
        for class_dir in os.listdir(val_dir):
            class_path = os.path.join(val_dir, class_dir)
            if os.path.isdir(class_path):
                png_files = glob.glob(os.path.join(class_path, "*.png"))
                for img_path in png_files:
                    image_paths.append((img_path, class_dir))

        if image_paths:
            all_count = len(image_paths)
            correct_count = 0
            class_stats = {}

            print(f"找到 {all_count} 张验证图片，开始分类...\n")

            # 遍历所有验证图片
            for image_path, true_label in image_paths:
                if true_label not in class_stats:
                    class_stats[true_label] = {"total": 0, "correct": 0}
                class_stats[true_label]["total"] += 1

                try:
                    pil_image = Image.open(image_path).convert("RGB")
                    predicted_label = classify_image(
                        pil_image, model_type="mirror_legend"
                    )

                    is_correct = predicted_label == true_label
                    if is_correct:
                        correct_count += 1
                        class_stats[true_label]["correct"] += 1

                except Exception as e:
                    print(f"处理图片 {os.path.basename(image_path)} 时出现错误: {e}")

            # 输出总准确率
            total_accuracy = correct_count / all_count if all_count > 0 else 0
            print(f"总准确率：{total_accuracy:.4f}")
            print("\n各类别准确率：")
            print("=" * 50)

            # 输出各类别准确率
            for label, stats in sorted(class_stats.items()):
                accuracy = (
                    stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                )
                print(f"{label}: {stats['correct']}/{stats['total']} = {accuracy:.4f}")

    print("\n=== 模型信息 ===")
    print(f"默认模型: {DEFAULT_MODEL}")
    for model_type, config in MODELS.items():
        exists = "✓" if os.path.exists(config["path"]) else "✗"
        print(f"{model_type}: {config['width']}x{config['height']} {exists}")

    # 测试技能图标模型 (80x80)
    print("\n=== 测试技能图标模型 (80x80) ===")
    skill_val_dir = "img/dataset/skill_icon/val"

    if os.path.exists(skill_val_dir):
        # 收集所有验证图片
        skill_image_paths = []
        for skill_class_dir in os.listdir(skill_val_dir):
            skill_class_path = os.path.join(skill_val_dir, skill_class_dir)
            if os.path.isdir(skill_class_path):
                skill_png_files = glob.glob(os.path.join(skill_class_path, "*.png"))
                for skill_img_path in skill_png_files:
                    skill_image_paths.append((skill_img_path, skill_class_dir))

        if skill_image_paths:
            skill_all_count = len(skill_image_paths)
            skill_correct_count = 0
            skill_class_stats = {}

            print(f"找到 {skill_all_count} 张验证图片，开始分类...\n")

            # 遍历所有验证图片
            for skill_image_path, skill_true_label in skill_image_paths:
                if skill_true_label not in skill_class_stats:
                    skill_class_stats[skill_true_label] = {"total": 0, "correct": 0}
                skill_class_stats[skill_true_label]["total"] += 1

                try:
                    skill_pil_image = Image.open(skill_image_path).convert("RGB")
                    skill_predicted_label = classify_image(
                        skill_pil_image, model_type="skill_icon"
                    )

                    skill_is_correct = skill_predicted_label == skill_true_label
                    if skill_is_correct:
                        skill_correct_count += 1
                        skill_class_stats[skill_true_label]["correct"] += 1

                except Exception as e:
                    print(
                        f"处理图片 {os.path.basename(skill_image_path)} 时出现错误: {e}"
                    )

            # 输出总准确率
            skill_total_accuracy = (
                skill_correct_count / skill_all_count if skill_all_count > 0 else 0
            )
            print(f"总准确率：{skill_total_accuracy:.4f}")
            print("\n各类别准确率：")
            print("=" * 50)

            # 输出各类别准确率
            for skill_label, skill_stats in sorted(skill_class_stats.items()):
                skill_accuracy = (
                    skill_stats["correct"] / skill_stats["total"]
                    if skill_stats["total"] > 0
                    else 0
                )
                print(
                    f"{skill_label}: {skill_stats['correct']}/{skill_stats['total']} = {skill_accuracy:.4f}"
                )
    else:
        print(f"技能图标验证集目录不存在: {skill_val_dir}")
        print("请先运行 train_skill_icon.bat 训练模型")

    # 测试镜像路径模型 (224x224)
    print("\n=== 测试镜像路径模型 (224x224) ===")
    mirror_path_val_dir = "img/dataset/mirror_path/val"

    if os.path.exists(mirror_path_val_dir):
        # 收集所有验证图片
        mirror_image_paths = []
        for conn_dir in os.listdir(mirror_path_val_dir):
            conn_path = os.path.join(mirror_path_val_dir, conn_dir)
            if os.path.isdir(conn_path):
                png_files = glob.glob(os.path.join(conn_path, "*.png"))
                for img_path in png_files:
                    # 从文件名解析真实标签（最后9位二进制）
                    filename = os.path.basename(img_path)
                    name_without_ext = os.path.splitext(filename)[0]
                    true_label_str = (
                        name_without_ext[-9:] if len(name_without_ext) >= 9 else ""
                    )
                    mirror_image_paths.append((img_path, true_label_str))

        if mirror_image_paths:
            mirror_all_count = len(mirror_image_paths)
            mirror_correct_count = 0
            mirror_conn_stats = {}

            print(f"找到 {mirror_all_count} 张验证图片，开始分类...\n")

            # 遍历所有验证图片
            for image_path, true_label_str in mirror_image_paths:
                if true_label_str not in mirror_conn_stats:
                    mirror_conn_stats[true_label_str] = {"total": 0, "correct": 0}
                mirror_conn_stats[true_label_str]["total"] += 1

                try:
                    pil_image = Image.open(image_path).convert("RGB")
                    predicted_result = classify_mirror_path([pil_image])[0]

                    # 打印分类函数返回值
                    # print(f"分类结果: {predicted_result}")

                    # 翻译connections为二进制字符串 (True=1, False=0)
                    predicted_binary = "".join(
                        "1" if conn else "0" for conn in predicted_result["connections"]
                    )

                    # print(f"预测二进制: {predicted_binary}")
                    # print(f"真实二进制: {true_label_str}")

                    # 比较预测的二进制字符串和真实标签字符串
                    is_correct = predicted_binary == true_label_str
                    if is_correct:
                        mirror_correct_count += 1
                        mirror_conn_stats[true_label_str]["correct"] += 1

                except Exception as e:
                    print(f"处理图片 {os.path.basename(image_path)} 时出现错误: {e}")

            # 输出总准确率
            mirror_total_accuracy = (
                mirror_correct_count / mirror_all_count if mirror_all_count > 0 else 0
            )
            print(f"总准确率：{mirror_total_accuracy:.4f}")
            print("\n各连接组合准确率：")
            print("=" * 50)

            # 输出各连接组合准确率
            for label, stats in sorted(mirror_conn_stats.items()):
                accuracy = (
                    stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                )
                print(f"{label}: {stats['correct']}/{stats['total']} = {accuracy:.4f}")
    else:
        print(f"镜像路径验证集目录不存在: {mirror_path_val_dir}")
        print("请先运行 train_mirror_path.bat 训练模型")

    # 测试罪人头像模型 
    print("\n=== 测试罪人头像模型 ===")
    sinner_avatar_val_dir = "img/dataset/sinner_avatar/val"

    if os.path.exists(sinner_avatar_val_dir):
        # 收集所有验证图片
        sinner_image_paths = []
        for class_dir in os.listdir(sinner_avatar_val_dir):
            class_path = os.path.join(sinner_avatar_val_dir, class_dir)
            if os.path.isdir(class_path):
                png_files = glob.glob(os.path.join(class_path, "*.png"))
                for img_path in png_files:
                    sinner_image_paths.append((img_path, class_dir))

        if sinner_image_paths:
            sinner_all_count = len(sinner_image_paths)
            sinner_correct_count = 0
            sinner_class_stats = {}

            print(f"找到 {sinner_all_count} 张验证图片，开始分类...\n")

            # 遍历所有验证图片
            for image_path, true_label in sinner_image_paths:
                if true_label not in sinner_class_stats:
                    sinner_class_stats[true_label] = {"total": 0, "correct": 0}
                sinner_class_stats[true_label]["total"] += 1

                try:
                    pil_image = Image.open(image_path).convert("RGB")
                    predicted_label = classify_sinner_avatar([pil_image])[0]

                    # 打印分类函数返回值
                    # print(f"分类结果: {predicted_label}")

                    is_correct = predicted_label == true_label
                    if is_correct:
                        sinner_correct_count += 1
                        sinner_class_stats[true_label]["correct"] += 1

                except Exception as e:
                    print(f"处理图片 {os.path.basename(image_path)} 时出现错误: {e}")

            # 输出总准确率
            sinner_total_accuracy = (
                sinner_correct_count / sinner_all_count if sinner_all_count > 0 else 0
            )
            print(f"总准确率：{sinner_total_accuracy:.4f}")
            print("\n各类别准确率：")
            print("=" * 50)

            # 输出各类别准确率
            for label, stats in sorted(sinner_class_stats.items()):
                accuracy = (
                    stats["correct"] / stats["total"] if stats["total"] > 0 else 0
                )
                print(f"{label}: {stats['correct']}/{stats['total']} = {accuracy:.4f}")
    else:
        print(f"罪人头像验证集目录不存在: {sinner_avatar_val_dir}")
        print("请先运行 train_sinner_avatar.bat 训练模型")

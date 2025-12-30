import os
from PIL import Image
import difflib

# 全局模板图片注册表
IMG_REGISTRY = {}

# 全局带 tag 的图片注册表
TAG_REGISTRY = {}


def _register_tag(tag: str, image_name: str, image: Image.Image):
    """向 TAG_REGISTRY 中写入一个 tag → (name, image)"""
    if tag not in TAG_REGISTRY:
        TAG_REGISTRY[tag] = []
    TAG_REGISTRY[tag].append((image_name, image))


def register_images_from_directory():
    """
    遍历img目录下的所有PNG图片，读取为PIL Image格式并存放到IMG_REGISTRY中
    
    Raises:
        Exception: 当遇到非PNG格式图片时抛出异常并输出图片名称
    """
    IMG_REGISTRY.clear()
    TAG_REGISTRY.clear()

    img_dirs = [".\\img", "..\\img"]
    img_root = None

    for img_dir in img_dirs:
        if os.path.exists(img_dir):
            img_root = img_dir
            break

    if img_root is None:
        raise FileNotFoundError("无法找到 img 目录")

    # 遍历
    for root, dirs, files in os.walk(img_root):
        for file in files:
            if file.lower().endswith(".png"):
                file_path = os.path.join(root, file)

                file_name_without_ext = os.path.splitext(file)[0]

                # ---- 原有功能：检查重名 ----
                if file_name_without_ext in IMG_REGISTRY:
                    raise Exception(f"发现重名图片: {file_path}")

                # ---- 读取图片 ----
                image = Image.open(file_path)
                IMG_REGISTRY[file_name_without_ext] = image

                # ============================================================
                #             支持多层嵌套 tag 注册逻辑（增强）
                # ============================================================
                # 例： relative_path = "a/b/c"
                relative_path = os.path.relpath(root, img_root)

                if relative_path != ".":
                    path_parts = relative_path.replace("\\", "/").split("/")

                    # 逐层生成 tag：
                    # 例如 ["a","b","c"] =>
                    #   "a"
                    #   "a_b"
                    #   "a_b_c"
                    for i in range(1, len(path_parts) + 1):
                        tag = "_".join(path_parts[:i])
                        _register_tag(tag, file_name_without_ext, image)

            elif "." in file and not file.lower().endswith(".png"):
                raise Exception(f"发现非PNG格式图片: {os.path.join(root, file)}")



def get_image(name) -> Image.Image:
    """
    根据名称返回注册图像文件的副本
    
    Args:
        name (str): 图像名称（不包含扩展名）
        
    Returns:
        PIL.Image: 图像副本
        
    Raises:
        KeyError: 当指定名称的图像不存在时抛出异常
    """
    if name not in IMG_REGISTRY:
        raise KeyError(f"未找到名称为 '{name}' 的图像")
    
    # 返回图像的副本
    return IMG_REGISTRY[name].copy()


def get_images_by_tag(tag: str):
    """
    根据 tag 返回 [(name, PIL.Image), ...]
    若 tag 不存在，返回空 list
    """
    if tag not in TAG_REGISTRY:
        raise Exception(f"未知 tag:{tag}")
    # 返回 image.copy()，避免外部修改
    return [(name, img.copy()) for name, img in TAG_REGISTRY[tag]]


def check_image_confusion(width=1302, height=776, threshold=0.7):
    """
    检测已注册图片之间是否存在混淆风险。
    返回一个字典，其中每种匹配方式的混淆图片对以元组形式存储。
    """
    # === 创建第一个临时列表（原图 copy） ===
    temp_list1 = []
    name_list = []
    # for name, image in IMG_REGISTRY.items():
    for name, image in get_images_by_tag("ego_gifts"):
        temp_list1.append(image.copy())
        name_list.append(name)

    # === 创建第二个临时列表（扩展后的大图） ===
    temp_list2 = []
    for image in temp_list1:
        expanded_image = Image.new("RGB", (width, height), (0, 0, 0))
        expanded_image.paste(image, (0, 0))
        temp_list2.append(expanded_image)

    # === 导入匹配函数 ===
    try:
        from recognize.template_match import template_match
        from recognize.color_template_match import color_template_match
        from recognize.feature_match import feature_match
        from recognize.pyramid_template_match import pyramid_template_match
        
    except ImportError:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from recognize.template_match import template_match
        from recognize.color_template_match import color_template_match
        from recognize.feature_match import feature_match
        from recognize.pyramid_template_match import pyramid_template_match
      
    # === 新增：存储所有混淆结果 ===
    confusion_results = {
        "template_match": [],
        "color_template_match": [],
        "feature_match": [],
        "pyramid_template_match":[],
        "edge_template_match":[],
    }

    # === 遍历匹配 ===
    for i, template_img in enumerate(temp_list1):
        template_name = name_list[i]

        for j, target_img in enumerate(temp_list2):
            if i == j:
                continue

            target_name = name_list[j]

            # 1) 模板匹配
            # if template_match(target_img, template_img, threshold, grayscale=True):
            #     confusion_results["template_match"].append((template_name, target_name))

            # 2) 颜色直方图模板匹配
            # if color_template_match(target_img, template_img, threshold, grayscale=False):
            #     confusion_results["color_template_match"].append((template_name, target_name))

            # 3) 特征匹配
            # if feature_match(target_img, template_img):
            #     confusion_results["feature_match"].append((template_name, target_name))

            # 4) 金字塔模板匹配
            # if pyramid_template_match(target_img, template_img, threshold, grayscale=True):
            #     confusion_results["pyramid_template_match"].append((template_name, target_name))
            
    
    print("TemplateMatch:")
    for key, item in confusion_results["template_match"]:
        print(f"{key} : {item}")
    print("FeatureMatch:")
    for key, item in confusion_results["feature_match"]:
        print(f"{key} : {item}")
    print("PyramidTemplateMatch:")
    for key, item in confusion_results["pyramid_template_match"]:
        print(f"{key} : {item}")


    return confusion_results



def print_tag_tree():
    """
    打印 TAG_REGISTRY 中所有 tag 的内容
    """
    for tag, images in TAG_REGISTRY.items():
        print(f"Tag '{tag}':")
        for image_name, _ in images:
            print(f"  - {image_name}")
        print()  # Empty line for better readability


def test_register_images():
    """
    测试函数，用于运行register_images_from_directory函数
    """
    try:
        register_images_from_directory()
        print(f"成功注册 {len(IMG_REGISTRY)} 张图片:")
        for name in IMG_REGISTRY.keys():
            print(f"  - {name}")
    except Exception as e:
        print(f"注册图片时发生错误: {e}")


def get_max_similarity_pair(strings)->tuple[float, tuple[str, str]]:
    """
    计算字符串列表中任意两个字符串之间的最大相似度，并返回这两个最相似的字符串。
    
    :param strings: 字符串列表
    :return: 最大相似度值, 最相似的两个字符串组成的元组
    """
    max_similarity = 0.0
    max_pair = ("", "")

    # 遍历每一对不同的字符串
    for i in range(len(strings)):
        for j in range(i + 1, len(strings)):  # 避免重复计算和自己与自己比较
            sm = difflib.SequenceMatcher(None, strings[i], strings[j])
            similarity = sm.ratio()

            if similarity > max_similarity:
                max_similarity = similarity
                max_pair = (strings[i], strings[j])
    
    return max_similarity, max_pair


def get_max_radio_of_ego_gifts()->float:
    """
    :return: ego gifts 名字的最大相似度
    """
    ans, str_pair = get_max_similarity_pair([x[0] for x in get_images_by_tag("ego_gifts")])
    if ans >= 0.97:
        print(f"相似度过高：ego gifts 中 {str_pair} 之间的相似度高达 {ans}")
    return ans


def get_max_radio_of_theme_packs()->float:
    """
    :return: theme packs 名字的最大相似度
    """
    ans, str_pair = get_max_similarity_pair([x[0] for x in get_images_by_tag("theme_packs")])
    if ans >= 0.9:
        print(f"相似度过高：theme packs 中 {str_pair} 之间的相似度高达 {ans}")
    return ans



if __name__ == "__main__":
    # from template_match import template_match
    # import sys
    # import os
    # sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    # from input.input_handler import input_handler
    # input_handler.refresh_window_state()
    register_images_from_directory()
    # template_match(input_handler.capture_screenshot(), get_image("owned_ego_resources"), visualize=True)
    # test_register_images()
    # check_image_confusion()
    # print_tag_tree()

    # print(get_max_similarity_pair([x[0] for x in get_images_by_tag("ego_gifts")]))
    # print(get_max_similarity_pair([x[0] for x in get_images_by_tag("theme_packs")]))
    get_max_radio_of_theme_packs()
    s = difflib.get_close_matches("GE Regular Check-ne", [x[0] for x in get_images_by_tag("theme_packs")], cutoff=0.7)
    print(s)
import json

def round_to_nearest_5(x):
    return round(x / 5) * 5

def process_json(data):
    processed_info = []
    for key, value in data.items():
        if "target" in value:
            original_target = value["target"]
            if (type(original_target) == bool):
                continue
            new_second_value = round_to_nearest_5(original_target[1] * 3 / 4)
            new_target = [original_target[0], new_second_value]
            value["target"] = new_target
            processed_info.append({
                "字段名": f"{key}.target",
                "原字段值": original_target,
                "新字段值": new_target
            })
        if "recognize_area" in value:
            original_area = value["recognize_area"]
            new_second_value = round_to_nearest_5(original_area[1] * 3 / 4)
            new_area = [original_area[0], new_second_value] + original_area[2:]
            value["recognize_area"] = new_area
            processed_info.append({
                "字段名": f"{key}.recognize_area",
                "原字段值": original_area,
                "新字段值": new_area
            })
    return data, processed_info

# 读取 JSON 文件
with open('task.json', 'r', encoding='utf-8') as file:
    json_data = json.load(file)

# 处理 JSON 数据
processed_data, info = process_json(json_data)

# 输出处理信息
for item in info:
    print(f"字段名: {item['字段名']}")
    print(f"原字段值: {item['原字段值']}")
    print(f"新字段值: {item['新字段值']}")
    print()

# 保存处理后的 JSON 数据到新文件
with open('processed_task.json', 'w', encoding='utf-8') as file:
    json.dump(processed_data, file, indent=4, ensure_ascii=False)
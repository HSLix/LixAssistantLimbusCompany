import os
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms as transforms
import torchvision.datasets as datasets
import torchvision.models as models
from torch.utils.data import DataLoader
import logging
import numpy as np

# Check if CUDA is available for mixed precision training
if torch.cuda.is_available():
    try:
        from torch.amp.grad_scaler import GradScaler
        from torch.amp.autocast_mode import autocast
    except ImportError:
        GradScaler = None
        autocast = None
else:
    GradScaler = None
    autocast = None

# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 检查CUDA是否可用
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"使用设备: {device}")

# 配置参数
CONFIG = {
    "input_height": 55,
    "input_width": 80,
    "batch_size": 32,
    "epochs": 50,
    "learning_rate": 1e-3,
    "weight_decay": 0.05,
    "label_smoothing": 0.1,
    "num_workers": 2,
    "model_architecture": "mobilenet_v3_small",  # efficientnet_b1, mobilenet_v3_large, mobilenet_v3_small
}


def create_model(num_classes=2, architecture="efficientnet_b1"):
    """
    创建预训练模型并修改分类器
    """
    logger.info(f"使用模型架构: {architecture}")

    if architecture == "efficientnet_b1":
        # EfficientNet-B1: 平衡准确率和效率
        model = models.efficientnet_b1(
            weights=models.EfficientNet_B1_Weights.IMAGENET1K_V2
        )
        # 替换分类器
        in_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(p=0.2, inplace=True), nn.Linear(in_features, num_classes)
        )
    elif architecture == "mobilenet_v3_large":
        # MobileNetV3-Large: 更快，参数更少
        model = models.mobilenet_v3_large(
            weights=models.MobileNet_V3_Large_Weights.IMAGENET1K_V2
        )
        in_features = model.classifier[0].in_features
        model.classifier = nn.Sequential(
            nn.Linear(in_features, num_classes),
            nn.Softmax(dim=1),  # MobileNetV3没有内置softmax
        )
    elif architecture == "mobilenet_v3_small":
        # MobileNetV3-Small: 最轻量
        model = models.mobilenet_v3_small(
            weights=models.MobileNet_V3_Small_Weights.IMAGENET1K_V1
        )
        in_features = model.classifier[0].in_features
        model.classifier = nn.Sequential(
            nn.Linear(in_features, num_classes), nn.Softmax(dim=1)
        )
    else:
        raise ValueError(f"不支持的架构: {architecture}")

    return model


def calculate_class_weights(dataset):
    """
    计算类别权重以处理类别不平衡
    """
    # 统计每个类别的样本数量
    class_counts = torch.tensor(
        [
            len([y for y in dataset.targets if y == i])
            for i in range(len(dataset.classes))
        ]
    )
    # 计算权重：样本数量越少，权重越大
    class_weights = 1.0 / class_counts.float()
    # 归一化权重
    class_weights = class_weights / class_weights.sum() * len(class_weights)

    logger.info(f"类别样本数: {class_counts.tolist()}")
    logger.info(f"类别权重: {class_weights.tolist()}")

    return class_weights.to(device)


def load_data(data_dir):
    """
    加载训练和验证数据，使用高级数据增强
    """
    # 高级数据增强
    data_transforms = {
        "train": transforms.Compose(
            [
                transforms.Resize((CONFIG["input_width"], CONFIG["input_height"])),
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.RandomVerticalFlip(p=0.1),
                transforms.ColorJitter(
                    brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1
                ),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        ),
        "val": transforms.Compose(
            [
                transforms.Resize((CONFIG["input_width"], CONFIG["input_height"])),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        ),
    }

    image_datasets = {
        x: datasets.ImageFolder(os.path.join(data_dir, x), data_transforms[x])
        for x in ["train", "val"]
    }

    dataloaders = {
        x: DataLoader(
            image_datasets[x],
            batch_size=CONFIG["batch_size"],
            shuffle=(x == "train"),
            num_workers=CONFIG["num_workers"],
            pin_memory=torch.cuda.is_available(),
            drop_last=(x == "train"),  # 训练时丢弃最后一个不完整的批次
        )
        for x in ["train", "val"]
    }

    dataset_sizes = {x: len(image_datasets[x]) for x in ["train", "val"]}
    class_names = image_datasets["train"].classes

    logger.info(f"类别数量: {len(class_names)}")
    logger.info(f"类别名称: {class_names}")
    logger.info(f"训练集大小: {dataset_sizes['train']}")
    logger.info(f"验证集大小: {dataset_sizes['val']}")

    return dataloaders, dataset_sizes, class_names


def train_model(
    model,
    dataloaders,
    dataset_sizes,
    criterion,
    optimizer,
    scheduler,
    class_weights,
    num_epochs=50,
):
    """
    训练模型，使用混合精度训练和早停
    """
    best_acc = 0.0
    best_model_wts = model.state_dict()
    scaler = GradScaler(device="cuda") if GradScaler is not None else None

    # 早停参数
    patience = 10
    no_improve_epochs = 0
    use_amp = scaler is not None

    for epoch in range(num_epochs):
        logger.info(f"Epoch {epoch + 1}/{num_epochs}")
        logger.info("-" * 10)

        # 每个epoch都有训练和验证阶段
        for phase in ["train", "val"]:
            if phase == "train":
                model.train()  # 训练模式
            else:
                model.eval()  # 验证模式

            running_loss = 0.0
            running_corrects = torch.tensor(0, device=device)

            # 遍历数据
            for inputs, labels in dataloaders[phase]:
                inputs = inputs.to(device)
                labels = labels.to(device)

                # 清零梯度
                optimizer.zero_grad()

                # 前向传播
                with torch.set_grad_enabled(phase == "train"):
                    # 混合精度上下文
                    if use_amp:
                        with autocast(device_type="cuda"):
                            outputs = model(inputs)
                            _, preds = torch.max(outputs, 1)
                            loss = criterion(outputs, labels)
                    else:
                        outputs = model(inputs)
                        _, preds = torch.max(outputs, 1)
                        loss = criterion(outputs, labels)

                    # 反向传播和优化
                    if phase == "train":
                        if use_amp:
                            scaler.scale(loss).backward()
                            scaler.step(optimizer)
                            scaler.update()
                        else:
                            loss.backward()
                            optimizer.step()

                # 统计损失和准确率
                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)

            if phase == "train":
                scheduler.step()

            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = running_corrects.double() / dataset_sizes[phase]

            logger.info(f"{phase} Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}")

            # 深拷贝最优模型
            if phase == "val" and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_model_wts = model.state_dict().copy()
                no_improve_epochs = 0
                logger.info(f"找到更好的模型! 验证准确率: {best_acc:.4f}")
            elif phase == "val":
                no_improve_epochs += 1

        # 早停检查
        if no_improve_epochs >= patience:
            logger.info(f"验证集准确率在{patience}个epoch内没有提升，提前停止训练")
            break

    logger.info(f"Best val Acc: {best_acc:.4f}")

    # 加载最佳模型权重
    model.load_state_dict(best_model_wts)
    return model


def export_to_onnx(model, output_path, input_width=80, input_height=55):
    """
    将模型导出为ONNX格式，使用最新ONNX版本

    Args:
        model: PyTorch模型
        output_path: ONNX输出路径
        input_width: 输入图像宽度
        input_height: 输入图像高度
    """
    model.eval()

    # 创建模型输入张量
    dummy_input = torch.randn(1, 3, input_height, input_width, device=device)

    # 动态轴配置
    dynamic_axes = {"input": {0: "batch_size"}, "output": {0: "batch_size"}}

    # 使用PyTorch内置的ONNX导出功能
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,  # 存储训练后的参数权重
        opset_version=17,  # 使用最新的ONNX版本
        do_constant_folding=True,  # 执行常量折叠以优化
        input_names=["input"],  # 模型输入名称
        output_names=["output"],  # 模型输出名称
        dynamic_axes=dynamic_axes,  # 动态轴，允许批次大小变化
        verbose=False,
    )

    logger.info(f"模型已导出到 {output_path}")


def main():
    # 数据集路径
    data_dir = "img/dataset/sinner_avatar"

    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"数据集路径不存在: {data_dir}")

    # 加载数据
    dataloaders, dataset_sizes, class_names = load_data(data_dir)
    num_classes = len(class_names)

    # 计算类别权重
    class_weights = calculate_class_weights(dataloaders["train"].dataset)

    # 创建模型
    model = create_model(num_classes, CONFIG["model_architecture"])
    model = model.to(device)

    # 定义损失函数、优化器和学习率调度器
    criterion = nn.CrossEntropyLoss(
        weight=class_weights, label_smoothing=CONFIG["label_smoothing"]
    )
    optimizer = optim.AdamW(
        model.parameters(),
        lr=CONFIG["learning_rate"],
        weight_decay=CONFIG["weight_decay"],
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=CONFIG["epochs"], eta_min=1e-6
    )

    # 开始训练
    logger.info("开始训练...")
    logger.info(f"配置: {CONFIG}")
    model = train_model(
        model,
        dataloaders,
        dataset_sizes,
        criterion,
        optimizer,
        scheduler,
        class_weights,
        num_epochs=CONFIG["epochs"],
    )

    # 确保模型保存目录存在
    model_save_dir = "ai/model/sinner_avatar"
    os.makedirs(model_save_dir, exist_ok=True)

    # 导出为ONNX格式
    onnx_path = os.path.join(model_save_dir, "best_model.onnx")
    export_to_onnx(
        model,
        onnx_path,
        input_width=CONFIG["input_width"],
        input_height=CONFIG["input_height"],
    )

    # 保存类别标签到子文件夹
    classes_path = os.path.join(model_save_dir, "classes.txt")
    with open(classes_path, "w", encoding="utf-8") as f:
        for i, class_name in enumerate(class_names):
            f.write(f"{i} {class_name}\n")

    # 保存训练配置
    config_path = os.path.join(model_save_dir, "training_config.json")
    import json

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(
            {"config": CONFIG, "class_names": class_names, "num_classes": num_classes},
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.info("训练完成，模型已保存!")


if __name__ == "__main__":
    main()

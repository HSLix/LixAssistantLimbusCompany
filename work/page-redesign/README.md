# 队伍与镜牢页面调整

确认日期：2026-11-14。

## 已确认边界

星光强化保存每张卡的目标档位：0 不选、1 +、2 ++。本次仅页面交互和配置保存，不接入工作流，不推断费用、可购买条件和前置关系。

队伍页分为罪人编队和镜牢偏好；镜牢页分为运行与队伍、星光强化和结算设置。保留原有队伍选择弹窗及兼容字段。当前代码有十种流派和“不选”，全部保留。饰品序号代表游戏右侧上、中、下位置，而非饰品身份。

## 配置

- 队伍页保持 PAGE_ID、teams、active_team、sinners、gift_keyword、gift_slot_order。
- 镜牢页保持 PAGE_ID、reward_mode、mirror_team、mirror_teams。
- 新增 star_levels：以 mirror/page.py 的 STAR_CARDS 稳定键保存十个 0/1/2 整数；缺失和非法值恢复为 0。
- 星光图片保存在 mirror/assets/stars/，由 context.resource_path 读取。
- 星光中文标题是界面译名，稳定键使用对应英文名称；未声称为游戏官方中文译名。

## 检查

从仓库根目录运行：

```
QT_QPA_PLATFORM=offscreen .venv/bin/python work/page-redesign/check_pages.py
```

中英文交互、旧格式恢复、保存重载、罪人调整顺序、饰品移除重编号、星光档位互斥与非法值恢复、队伍选择弹窗取消隔离检查通过。已检查页面截图。未运行真实模型、游戏或 Windows 原生界面。

originals/ 保留修改前的两个页面；pages/ 为修改后完整页面包（luxcavation 未改）。修改仅写入用户指定的 Downloads 页面包，不安装到应用数据目录，也不修改内置示例。

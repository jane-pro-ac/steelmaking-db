# Scripts 目录

本目录包含用于开发、调试和手动验证的脚本工具。

## 可用脚本

### test_cancel.py

**用途：** 手动验证取消（cancel）和回炉（rework）事件的生成功能。

**功能：**
- 设置较高的取消/回炉事件概率（15%）
- 初始化模拟器并生成测试数据
- 查询并显示：
  - 所有被取消的操作（proc_status = 3）
  - 所有取消事件（G12007, G13008, G15008, G16015）
  - 所有回炉事件（G13007, G15007）
  - 验证取消操作是否有对应的取消事件

**前置条件：**
- PostgreSQL 数据库运行中
- 已配置数据库连接（.env 或环境变量）
- 数据库中存在必要的表结构

**运行方法：**

```bash
# 在项目根目录运行
poetry run python scripts/test_cancel.py
```

或者：

```bash
# 激活虚拟环境后运行
poetry shell
python scripts/test_cancel.py
```

**预期输出示例：**

```
Initialization complete!

Found 3 canceled operations:
  Heat 2412180001, Proc G12, Device G120
  Heat 2412180002, Proc G13, Device G131
  Heat 2412180003, Proc G16, Device G162

Found 3 cancel events:
  G12007: Heat 2412180001, Proc G12, Msg: 炉次取消，原因：设备故障
  G13008: Heat 2412180002, Proc G13, Msg: 炉次取消，原因：质量问题
  G16015: Heat 2412180003, Proc G16, Msg: 开浇取消，原因：设备异常

Found 2 rework events:
  G13007: Heat 2412180004, Proc G13, Msg: 炉次回炉，需要重新精炼
  G15007: Heat 2412180005, Proc G15, Msg: 炉次回炉，成分不合格

Canceled operations with their cancel events:
  Heat 2412180001 Proc G12: Cancel event = Yes
  Heat 2412180002 Proc G13: Cancel event = Yes
  Heat 2412180003 Proc G16: Cancel event = Yes

Done!
```

**注意事项：**
- 此脚本会清空并重新生成数据库中的操作、事件和预警数据
- 仅用于开发和测试环境，**不要在生产环境运行**
- 取消/回炉事件概率在脚本中设置为 15%，高于默认值（2-3%）

**环境变量配置：**

脚本内部会覆盖以下环境变量：
- `CANCEL_EVENT_PROBABILITY=0.15` （取消事件概率 15%）
- `REWORK_EVENT_PROBABILITY=0.15` （回炉事件概率 15%）

如需修改概率，直接编辑脚本中的值即可。

## 添加新脚本

在此目录添加新的开发脚本时，请：

1. 使用描述性的文件名（如 `verify_warnings.py`, `check_timing_constraints.py`）
2. 在文件顶部添加 docstring 说明用途
3. 确保脚本可以独立运行
4. 更新本 README 文档
5. 脚本不会被 pytest 自动收集（已配置在 `pyproject.toml` 中）

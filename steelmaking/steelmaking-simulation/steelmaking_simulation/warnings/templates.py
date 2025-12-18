"""Warning templates for steelmaking processes."""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional


WARNING_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "BOF": [
        { "msg": "检测到氧枪压力波动", "code": "BOF-01", "level": 2 },
        { "msg": "转炉煤气温度快速上升", "code": "BOF-02", "level": 2 },
        { "msg": "冷却水流量低于下限", "code": "BOF-03", "level": 1 },
        { "msg": "铁水硅超标，需调整造渣剂加入量", "code": "BOF-04", "level": 3 },
        { "msg": "炉口火焰异常，存在喷溅风险", "code": "BOF-05", "level": 1 },
        { "msg": "炉内压力异常升高", "code": "BOF-06", "level": 1 },
        { "msg": "吹炼时长超出工艺上限", "code": "BOF-07", "level": 2 },
        { "msg": "底吹气体流量不足", "code": "BOF-08", "level": 2 },
        { "msg": "终点碳含量偏高", "code": "BOF-09", "level": 3 },
        { "msg": "终点温度偏低", "code": "BOF-10", "level": 3 }
    ],
    "LF": [
        { "msg": "氩搅拌压力不稳定", "code": "LF-01", "level": 2 },
        { "msg": "钢包温度下降超过目标", "code": "LF-02", "level": 3 },
        { "msg": "合金加入机堵料", "code": "LF-03", "level": 2 },
        { "msg": "电极消耗高于预期", "code": "LF-04", "level": 4 },
        { "msg": "电极升降异常", "code": "LF-05", "level": 1 },
        { "msg": "升温速率低于工艺要求", "code": "LF-06", "level": 3 },
        { "msg": "精炼时间超限", "code": "LF-07", "level": 2 },
        { "msg": "合金加入量偏差超限", "code": "LF-08", "level": 3 },
        { "msg": "钢水成分偏离目标范围", "code": "LF-09", "level": 3 },
        { "msg": "炉盖未按时关闭", "code": "LF-10", "level": 2 }
    ],
    "CCM": [
        { "msg": "结晶器液位振荡超出范围", "code": "CCM-01", "level": 2 },
        { "msg": "二冷水压力偏低", "code": "CCM-02", "level": 1 },
        { "msg": "中间包温度偏移", "code": "CCM-03", "level": 3 },
        { "msg": "拉速波动", "code": "CCM-04", "level": 3 },
        { "msg": "结晶器漏钢风险", "code": "CCM-05", "level": 1 },
        { "msg": "结晶器液位控制失稳", "code": "CCM-06", "level": 2 },
        { "msg": "钢水过热度不足", "code": "CCM-07", "level": 3 },
        { "msg": "铸坯壳厚增长异常", "code": "CCM-08", "level": 2 },
        { "msg": "振动频率偏离设定值", "code": "CCM-09", "level": 2 },
        { "msg": "拉坯中断风险", "code": "CCM-10", "level": 1 }
    ],
    "COMMON": [
        { "msg": "传感器信号噪声过高", "code": "W-100", "level": 4 },
        { "msg": "请人工检查工艺参数", "code": "W-101", "level": 4 },
        { "msg": "数据采集延迟", "code": "W-102", "level": 4 },
        { "msg": "关键工艺参数缺失", "code": "W-103", "level": 2 },
        { "msg": "时间戳异常跳变", "code": "W-104", "level": 4 },
        { "msg": "设备通讯中断", "code": "W-105", "level": 1 },
        { "msg": "数据重复上报", "code": "W-106", "level": 4 },
        { "msg": "报警规则未命中配置", "code": "W-107", "level": 4 },
        { "msg": "模型计算结果异常", "code": "W-108", "level": 3 },
        { "msg": "系统时钟不同步", "code": "W-109", "level": 2 }
    ],
}


@dataclass(frozen=True)
class WarningPayload:
    """Warning data payload."""
    warning_code: Optional[str]
    warning_msg: str
    warning_level: int

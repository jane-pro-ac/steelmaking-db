"""Event generation logic for steelmaking operations.

This module generates realistic event sequences for each steelmaking process (BOF, LF, RH, CCM)
following the constraints defined in steelmaking/event_code_constraints.md.

Event sequences are generated to:
1. Start with the appropriate starting events (钢包到达, 处理开始, 炉次开始)
2. Include realistic middle events (加料, 测温, 取样, etc.) in valid sequences
3. End with the appropriate ending events (炉次结束, 处理结束, 钢包离开)

Special Events (取消/回炉):
- 取消 (cancel): Stops current operation and marks all subsequent operations as canceled
- 回炉 (rework): Operation continues normally to completion but signals need for rework

Support by process:
- BOF: G12007 炉次取消 only
- LF: G13007 炉次回炉, G13008 炉次取消
- RH: G15007 炉次回炉, G15008 炉次取消
- CCM: G16015 炉次开浇取消 only
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


class SpecialEventType(Enum):
    """Types of special events that affect operation flow."""
    NONE = auto()      # Normal event
    CANCEL = auto()    # 取消 - cancels current and subsequent operations
    REWORK = auto()    # 回炉 - operation continues but flags for rework


# Event code definitions by process
# Each entry: (event_code, event_name, param1, param2, param3, param4)
EVENT_CODES: Dict[str, List[Tuple[str, str, str, str, str, str]]] = {
    "BOF": [
        ("G12001", "钢包到达", "", "钢包号", "", ""),
        ("G12002", "钢包离开", "钢水重量", "钢包号", "", ""),
        ("G12003", "处理开始", "", "", "", ""),
        ("G12004", "处理结束", "", "", "", ""),
        ("G12005", "炉次开始", "", "", "", ""),
        ("G12006", "炉次结束", "", "", "", ""),
        ("G12007", "炉次取消", "", "", "", ""),
        ("G12008", "加料", "物料名称", "料仓号", "加料重量", ""),
        ("G12009", "钢水取样", "", "", "", ""),
        ("G12010", "收到钢水化验", "", "", "", ""),
        ("G12011", "钢渣取样", "", "", "", ""),
        ("G12012", "收到钢渣化验", "", "", "", ""),
        ("G12013", "钢水测温", "测量值", "", "", ""),
        ("G12014", "钢水定氢", "测量值", "", "", ""),
        ("G12015", "钢水定氧", "测量值", "", "", ""),
        ("G12016", "钢水定碳", "测量值", "", "", ""),
        ("G12017", "加废钢", "物料名称", "料篮号", "废钢重量", ""),
        ("G12018", "兑铁水", "铁包号", "铁水重量", "", ""),
        ("G12019", "合金配料下发", "", "", "", ""),
        ("G12020", "造渣料配料下发", "", "", "", ""),
        ("G12021", "氧枪喷吹开始", "", "", "", ""),
        ("G12022", "氧枪喷吹结束", "气体类型", "消耗量", "", ""),
        ("G12023", "扒渣开始", "", "", "", ""),
        ("G12024", "扒渣结束", "", "", "", ""),
        ("G12025", "出钢开始", "", "", "", ""),
        ("G12026", "出钢结束", "钢水重量", "钢包号", "", ""),
        ("G12027", "钢包底吹开始", "", "", "", ""),
        ("G12028", "钢包底吹结束", "气体类型", "消耗量", "", ""),
    ],
    "LF": [
        ("G13001", "钢包到达", "钢水重量", "钢包号", "", ""),
        ("G13002", "钢包离开", "钢水重量", "钢包号", "", ""),
        ("G13003", "处理开始", "", "", "", ""),
        ("G13004", "处理结束", "", "", "", ""),
        ("G13005", "炉次开始", "", "", "", ""),
        ("G13006", "炉次结束", "", "", "", ""),
        ("G13007", "炉次回炉", "", "", "", ""),
        ("G13008", "炉次取消", "", "", "", ""),
        ("G13009", "加料", "物料名称", "料仓号", "加料重量", ""),
        ("G13010", "喂丝", "物料名称", "料仓号", "加料重量", ""),
        ("G13011", "钢水取样", "", "", "", ""),
        ("G13012", "收到钢水化验", "", "", "", ""),
        ("G13013", "钢渣取样", "", "", "", ""),
        ("G13014", "收到钢渣化验", "", "", "", ""),
        ("G13015", "钢水测温", "测量值", "", "", ""),
        ("G13016", "钢水定氢", "测量值", "", "", ""),
        ("G13017", "钢水定氧", "测量值", "", "", ""),
        ("G13018", "软吹开始", "", "", "", ""),
        ("G13019", "软吹结束", "气体类型", "消耗量", "", ""),
        ("G13020", "变压器换挡", "档位", "", "", ""),
        ("G13021", "电流换挡", "档位", "", "", ""),
        ("G13022", "通电开始", "", "", "", ""),
        ("G13023", "通电结束", "电耗", "", "", ""),
        ("G13024", "吹氩开始", "", "", "", ""),
        ("G13025", "吹氩结束", "气体类型", "消耗量", "", ""),
    ],
    "RH": [
        ("G15001", "钢包到达", "钢水重量", "钢包号", "", ""),
        ("G15002", "钢包离开", "钢水重量", "钢包号", "", ""),
        ("G15003", "处理开始", "", "", "", ""),
        ("G15004", "处理结束", "", "", "", ""),
        ("G15005", "炉次开始(顶升到位)", "", "", "", ""),
        ("G15006", "炉次结束(顶升结束)", "", "", "", ""),
        ("G15007", "炉次回炉", "", "", "", ""),
        ("G15008", "炉次取消", "", "", "", ""),
        ("G15009", "加料", "物料名称", "料仓号", "加料重量", ""),
        ("G15010", "喂丝", "物料名称", "料仓号", "加料重量", ""),
        ("G15011", "钢水取样", "", "", "", ""),
        ("G15012", "收到钢水化验", "", "", "", ""),
        ("G15013", "钢渣取样", "", "", "", ""),
        ("G15014", "收到钢渣化验", "", "", "", ""),
        ("G15015", "钢水测温", "测量值", "", "", ""),
        ("G15016", "钢水定氢", "测量值", "", "", ""),
        ("G15017", "钢水定氧", "测量值", "", "", ""),
        ("G15018", "软吹开始", "", "", "", ""),
        ("G15019", "软吹结束", "气体类型", "消耗量", "", ""),
        ("G15020", "底搅拌开始", "", "", "", ""),
        ("G15021", "底搅拌结束", "气体类型", "消耗量", "", ""),
        ("G15022", "开始抽真空", "", "", "", ""),
        ("G15023", "达到高真空", "", "", "", ""),
        ("G15024", "真空结束（破空）", "", "", "", ""),
        ("G15025", "氩气换挡", "档位", "", "", ""),
    ],
    "CCM": [
        ("G16001", "中包加料", "物料名称", "加料重量", "", ""),
        ("G16002", "中包测温", "温度值", "", "", ""),
        ("G16003", "中包开浇", "中包重量", "", "", ""),
        ("G16004", "中包停浇", "中包重量", "", "", ""),
        ("G16005", "中包热换", "", "", "", ""),
        ("G16006", "大包加料", "物料名称", "加料重量", "", ""),
        ("G16007", "大包测温", "温度值", "", "", ""),
        ("G16008", "炉次到受包位", "中包重量", "大包重量", "", ""),
        ("G16009", "炉次到浇注位", "中包重量", "大包重量", "", ""),
        ("G16010", "炉次开浇", "中包重量", "大包重量", "", ""),
        ("G16011", "炉次停浇", "中包重量", "大包重量", "", ""),
        ("G16012", "炉次吊走", "", "", "", ""),
        ("G16013", "炉次切割完成", "", "", "", ""),
        ("G16014", "炉次喷号完成", "", "", "", ""),
        ("G16015", "炉次开浇取消", "", "", "", ""),
        ("G16016", "铸流开浇", "", "", "", ""),
        ("G16017", "铸流停浇", "", "", "", ""),
        ("G16018", "铸坯产生", "", "", "", ""),
        ("G16019", "拉尾坯开始", "中包重量", "", "", ""),
        ("G16020", "拉尾坯结束", "", "", "", ""),
        ("G16021", "开始切割", "", "", "", ""),
        ("G16022", "切割完成", "", "", "", ""),
    ],
}

# Process code to process name mapping
PROC_CD_TO_NAME: Dict[str, str] = {
    "G12": "BOF",
    "G13": "LF",
    "G15": "RH",
    "G16": "CCM",
}


@dataclass
class EventSequenceConfig:
    """Configuration for event sequence generation.
    
    This defines the starting, ending, and middle (loop) events for each process,
    as well as paired events that must occur together.
    """
    # Events that must occur in order at the start
    start_sequence: List[str] = field(default_factory=list)
    
    # Events that must occur in order at the end
    end_sequence: List[str] = field(default_factory=list)
    
    # Events that can occur in the middle (loop region), with weights
    middle_events: List[Tuple[str, float]] = field(default_factory=list)
    
    # Paired events: (start_code, end_code) - must occur together
    paired_events: List[Tuple[str, str]] = field(default_factory=list)
    
    # Events that should follow a specific event (e.g., 取样 -> 收到化验)
    follow_up_events: Dict[str, str] = field(default_factory=dict)
    
    # Special events (cancel/rework)
    # cancel_event: Event that cancels current operation + subsequent operations
    cancel_event: Optional[str] = None
    # rework_event: Event that flags operation for rework but continues to completion
    rework_event: Optional[str] = None
    # Shortened end sequence after cancel (e.g., just 钢包离开)
    cancel_end_sequence: List[str] = field(default_factory=list)


# Event sequence configurations for each process
EVENT_SEQUENCE_CONFIGS: Dict[str, EventSequenceConfig] = {
    "BOF": EventSequenceConfig(
        start_sequence=["G12001", "G12003", "G12005"],  # 钢包到达 -> 处理开始 -> 炉次开始
        end_sequence=[
            "G12025", "G12026",  # 出钢开始 -> 出钢结束
            "G12027", "G12028",  # 钢包底吹开始 -> 钢包底吹结束
            "G12006", "G12004", "G12002",  # 炉次结束 -> 处理结束 -> 钢包离开
        ],
        middle_events=[
            ("G12017", 0.8),   # 加废钢 - high probability
            ("G12018", 0.8),   # 兑铁水 - high probability
            ("G12008", 0.9),   # 加料 - very high probability
            ("G12019", 0.5),   # 合金配料下发
            ("G12020", 0.5),   # 造渣料配料下发
            ("G12021", 0.95),  # 氧枪喷吹开始 (paired)
            ("G12009", 0.7),   # 钢水取样 (has follow-up)
            ("G12011", 0.4),   # 钢渣取样 (has follow-up)
            ("G12013", 0.8),   # 钢水测温
            ("G12014", 0.3),   # 钢水定氢
            ("G12015", 0.3),   # 钢水定氧
            ("G12016", 0.5),   # 钢水定碳
            ("G12023", 0.4),   # 扒渣开始 (paired)
        ],
        paired_events=[
            ("G12021", "G12022"),  # 氧枪喷吹开始/结束
            ("G12023", "G12024"),  # 扒渣开始/结束
        ],
        follow_up_events={
            "G12009": "G12010",  # 钢水取样 -> 收到钢水化验
            "G12011": "G12012",  # 钢渣取样 -> 收到钢渣化验
        },
        # BOF only has cancel (炉次取消), no rework
        cancel_event="G12007",
        rework_event=None,
        cancel_end_sequence=["G12004", "G12002"],  # 处理结束 -> 钢包离开 (skip 出钢/底吹/炉次结束)
    ),
    "LF": EventSequenceConfig(
        start_sequence=["G13001", "G13003", "G13005"],  # 钢包到达 -> 处理开始 -> 炉次开始
        end_sequence=["G13006", "G13004", "G13002"],     # 炉次结束 -> 处理结束 -> 钢包离开
        middle_events=[
            ("G13009", 0.9),   # 加料
            ("G13010", 0.7),   # 喂丝
            ("G13022", 0.95),  # 通电开始 (paired)
            ("G13020", 0.4),   # 变压器换挡
            ("G13021", 0.4),   # 电流换挡
            ("G13024", 0.6),   # 吹氩开始 (paired)
            ("G13018", 0.5),   # 软吹开始 (paired)
            ("G13011", 0.7),   # 钢水取样 (has follow-up)
            ("G13013", 0.3),   # 钢渣取样 (has follow-up)
            ("G13015", 0.8),   # 钢水测温
            ("G13016", 0.2),   # 钢水定氢
            ("G13017", 0.3),   # 钢水定氧
        ],
        paired_events=[
            ("G13022", "G13023"),  # 通电开始/结束
            ("G13024", "G13025"),  # 吹氩开始/结束
            ("G13018", "G13019"),  # 软吹开始/结束
        ],
        follow_up_events={
            "G13011": "G13012",  # 钢水取样 -> 收到钢水化验
            "G13013": "G13014",  # 钢渣取样 -> 收到钢渣化验
        },
        # LF has both cancel (炉次取消) and rework (炉次回炉)
        cancel_event="G13008",
        rework_event="G13007",
        cancel_end_sequence=["G13004", "G13002"],  # 处理结束 -> 钢包离开 (skip 炉次结束)
    ),
    "RH": EventSequenceConfig(
        start_sequence=["G15001", "G15003", "G15005"],  # 钢包到达 -> 处理开始 -> 炉次开始(顶升到位)
        end_sequence=["G15006", "G15004", "G15002"],     # 炉次结束(顶升结束) -> 处理结束 -> 钢包离开
        middle_events=[
            ("G15022", 0.95),  # 开始抽真空 (part of vacuum sequence)
            ("G15009", 0.8),   # 加料
            ("G15010", 0.6),   # 喂丝
            ("G15018", 0.5),   # 软吹开始 (paired)
            ("G15020", 0.4),   # 底搅拌开始 (paired)
            ("G15025", 0.3),   # 氩气换挡
            ("G15011", 0.6),   # 钢水取样 (has follow-up)
            ("G15013", 0.3),   # 钢渣取样 (has follow-up)
            ("G15015", 0.8),   # 钢水测温
            ("G15016", 0.3),   # 钢水定氢
            ("G15017", 0.3),   # 钢水定氧
        ],
        paired_events=[
            ("G15018", "G15019"),  # 软吹开始/结束
            ("G15020", "G15021"),  # 底搅拌开始/结束
        ],
        follow_up_events={
            "G15011": "G15012",  # 钢水取样 -> 收到钢水化验
            "G15013": "G15014",  # 钢渣取样 -> 收到钢渣化验
            "G15022": "G15023",  # 开始抽真空 -> 达到高真空
            "G15023": "G15024",  # 达到高真空 -> 真空结束（破空）
        },
        # RH has both cancel (炉次取消) and rework (炉次回炉)
        cancel_event="G15008",
        rework_event="G15007",
        cancel_end_sequence=["G15004", "G15002"],  # 处理结束 -> 钢包离开 (skip 炉次结束)
    ),
    "CCM": EventSequenceConfig(
        start_sequence=["G16008", "G16009", "G16010"],  # 炉次到受包位 -> 炉次到浇注位 -> 炉次开浇
        end_sequence=["G16011", "G16012", "G16013", "G16014"],  # 炉次停浇 -> 炉次吊走 -> 炉次切割完成 -> 炉次喷号完成
        middle_events=[
            ("G16006", 0.7),   # 大包加料
            ("G16007", 0.8),   # 大包测温
            ("G16001", 0.5),   # 中包加料
            ("G16002", 0.6),   # 中包测温
            ("G16016", 0.4),   # 铸流开浇 (paired)
            ("G16018", 0.6),   # 铸坯产生
            ("G16019", 0.3),   # 拉尾坯开始 (has follow-up)
            ("G16021", 0.5),   # 开始切割 (paired)
        ],
        paired_events=[
            ("G16016", "G16017"),  # 铸流开浇/停浇
            ("G16021", "G16022"),  # 开始切割/切割完成
        ],
        follow_up_events={
            "G16019": "G16020",  # 拉尾坯开始 -> 拉尾坯结束
        },
        # CCM only has cancel (炉次开浇取消), no rework
        cancel_event="G16015",
        rework_event=None,
        cancel_end_sequence=["G16012"],  # 炉次吊走 (skip normal ending)
    ),
}


class EventMessageGenerator:
    """Generates realistic Chinese event messages based on event parameters."""
    
    # Sample values for different parameter types
    LADLE_NUMBERS = ["LP-01", "LP-02", "LP-03", "LP-04", "LP-05", "LP-06", "LP-07", "LP-08"]
    HOT_METAL_LADLE_NUMBERS = ["TB-01", "TB-02", "TB-03", "TB-04", "TB-05", "TB-06"]
    SCRAP_BASKET_NUMBERS = ["LB-01", "LB-02", "LB-03", "LB-04", "LB-05"]
    BIN_NUMBERS = ["1#", "2#", "3#", "4#", "5#", "6#", "7#", "8#"]
    
    # Material names
    SCRAP_MATERIALS = ["重废", "轻废", "生铁", "废钢", "返回钢"]
    ALLOY_MATERIALS = ["硅铁", "锰铁", "硅锰合金", "铝块", "钒铁", "钼铁", "铬铁"]
    SLAG_MATERIALS = ["石灰", "萤石", "轻烧白云石", "合成�ite"]
    WIRE_MATERIALS = ["硅钙线", "铝线", "钛线", "硼线", "碳线"]
    TUNDISH_MATERIALS = ["覆盖剂", "保护渣", "引流砂"]
    LADLE_ADDITIVES = ["脱氧剂", "增碳剂", "精炼剂"]
    
    GAS_TYPES = ["氩气", "氮气", "氧气"]
    GEAR_POSITIONS = ["1档", "2档", "3档", "4档", "5档", "6档"]
    
    @classmethod
    def generate_message(cls, event_code: str, event_name: str, 
                        param1: str, param2: str, param3: str, param4: str) -> str:
        """Generate a realistic Chinese event message based on event parameters."""
        
        # Default message if no parameters
        if not any([param1, param2, param3, param4]):
            return f"执行{event_name}操作"
        
        # Generate specific messages based on event type
        parts = [f"执行{event_name}操作"]
        
        if event_code in ("G12017", "G12008", "G13009", "G15009"):  # 加废钢/加料
            if param1:  # 物料名称
                material = cls._get_material_for_event(event_code)
                parts.append(f"，物料名称[{material}]")
            if param2:  # 料篮号/料仓号
                if "料篮" in param2:
                    parts.append(f"，料篮号[{random.choice(cls.SCRAP_BASKET_NUMBERS)}]")
                else:
                    parts.append(f"，料仓号[{random.choice(cls.BIN_NUMBERS)}]")
            if param3:  # 废钢重量/加料重量
                weight = round(random.uniform(0.5, 15.0), 1)
                parts.append(f"，重量[{weight} 吨]")
        
        elif event_code in ("G13010", "G15010"):  # 喂丝
            material = random.choice(cls.WIRE_MATERIALS)
            parts.append(f"，物料名称[{material}]")
            parts.append(f"，料仓号[{random.choice(cls.BIN_NUMBERS)}]")
            length = random.randint(50, 500)
            parts.append(f"，喂丝长度[{length} m]")
        
        elif event_code == "G12018":  # 兑铁水
            parts.append(f"，铁包号[{random.choice(cls.HOT_METAL_LADLE_NUMBERS)}]")
            weight = round(random.uniform(80, 120), 1)
            parts.append(f"，铁水重量[{weight} 吨]")
        
        elif event_code in ("G12001", "G13001", "G15001"):  # 钢包到达
            ladle = random.choice(cls.LADLE_NUMBERS)
            if param1:  # 钢水重量 (LF/RH)
                weight = round(random.uniform(80, 150), 1)
                parts.append(f"，钢水重量[{weight} 吨]")
            parts.append(f"，钢包号[{ladle}]")
        
        elif event_code in ("G12002", "G13002", "G15002"):  # 钢包离开
            weight = round(random.uniform(80, 150), 1)
            parts.append(f"，钢水重量[{weight} 吨]")
            parts.append(f"，钢包号[{random.choice(cls.LADLE_NUMBERS)}]")
        
        elif event_code == "G12026":  # 出钢结束
            weight = round(random.uniform(100, 160), 1)
            parts.append(f"，钢水重量[{weight} 吨]")
            parts.append(f"，钢包号[{random.choice(cls.LADLE_NUMBERS)}]")
        
        elif event_code in ("G12013", "G13015", "G15015"):  # 钢水测温
            temp = random.randint(1550, 1700)
            parts.append(f"，温度[{temp}℃]")
        
        elif event_code in ("G12014", "G13016", "G15016"):  # 钢水定氢
            h_value = round(random.uniform(1.0, 5.0), 2)
            parts.append(f"，氢含量[{h_value} ppm]")
        
        elif event_code in ("G12015", "G13017", "G15017"):  # 钢水定氧
            o_value = round(random.uniform(10, 100), 1)
            parts.append(f"，氧含量[{o_value} ppm]")
        
        elif event_code == "G12016":  # 钢水定碳
            c_value = round(random.uniform(0.02, 0.10), 3)
            parts.append(f"，碳含量[{c_value}%]")
        
        elif event_code in ("G12022", "G12028", "G13019", "G13025", "G15019", "G15021"):  # 气体消耗
            gas = random.choice(cls.GAS_TYPES)
            consumption = random.randint(50, 500)
            parts.append(f"，气体类型[{gas}]")
            parts.append(f"，消耗量[{consumption} Nm³]")
        
        elif event_code == "G13023":  # 通电结束
            power = random.randint(200, 800)
            parts.append(f"，电耗[{power} kWh]")
        
        elif event_code in ("G13020", "G13021", "G15025"):  # 换挡
            parts.append(f"，档位[{random.choice(cls.GEAR_POSITIONS)}]")
        
        elif event_code in ("G16001", "G16006"):  # 中包/大包加料
            if "中包" in event_name:
                material = random.choice(cls.TUNDISH_MATERIALS)
            else:
                material = random.choice(cls.LADLE_ADDITIVES)
            weight = round(random.uniform(5, 50), 1)
            parts.append(f"，物料名称[{material}]")
            parts.append(f"，加料重量[{weight} kg]")
        
        elif event_code in ("G16002", "G16007"):  # 中包/大包测温
            temp = random.randint(1520, 1580)
            parts.append(f"，温度[{temp}℃]")
        
        elif event_code in ("G16003", "G16004", "G16008", "G16009", "G16010", "G16011"):  # 中包/炉次相关
            tundish_weight = round(random.uniform(15, 35), 1)
            parts.append(f"，中包重量[{tundish_weight} 吨]")
            if "大包" in event_name or event_code in ("G16008", "G16009", "G16010", "G16011"):
                ladle_weight = round(random.uniform(80, 150), 1)
                parts.append(f"，大包重量[{ladle_weight} 吨]")
        
        elif event_code == "G16019":  # 拉尾坯开始
            tundish_weight = round(random.uniform(5, 15), 1)
            parts.append(f"，中包重量[{tundish_weight} 吨]")
        
        return "".join(parts)
    
    @classmethod
    def _get_material_for_event(cls, event_code: str) -> str:
        """Get appropriate material type based on event code."""
        if event_code == "G12017":  # 加废钢
            return random.choice(cls.SCRAP_MATERIALS)
        elif event_code in ("G12008", "G13009", "G15009"):  # 加料
            material_pool = cls.ALLOY_MATERIALS + cls.SLAG_MATERIALS
            return random.choice(material_pool)
        return "物料"


@dataclass
class Event:
    """Represents a single steelmaking event."""
    heat_no: int
    pro_line_cd: str
    proc_cd: str
    device_no: str
    event_code: str
    event_name: str
    event_msg: str
    event_time_start: datetime
    event_time_end: datetime
    extra: Optional[Dict[str, Any]] = None
    special_event_type: SpecialEventType = SpecialEventType.NONE


class EventGenerator:
    """Generates realistic event sequences for steelmaking operations."""
    
    def __init__(
        self,
        min_events_per_operation: int = 8,
        max_events_per_operation: int = 20,
        cancel_probability: float = 0.0,
        rework_probability: float = 0.0,
    ):
        self.min_events = min_events_per_operation
        self.max_events = max_events_per_operation
        self.cancel_probability = cancel_probability
        self.rework_probability = rework_probability
        
        # Build lookup for event codes
        self._event_lookup: Dict[str, Dict[str, Tuple[str, str, str, str, str, str]]] = {}
        for process, events in EVENT_CODES.items():
            self._event_lookup[process] = {code: (code, name, p1, p2, p3, p4) 
                                          for code, name, p1, p2, p3, p4 in events}
    
    def get_process_name(self, proc_cd: str) -> Optional[str]:
        """Convert process code to process name."""
        return PROC_CD_TO_NAME.get(proc_cd)
    
    def generate_event_sequence(
        self,
        heat_no: int,
        pro_line_cd: str,
        proc_cd: str,
        device_no: str,
        start_time: datetime,
        end_time: datetime,
        force_cancel: bool = False,
        force_rework: bool = False,
    ) -> List[Event]:
        """Generate a valid event sequence for an operation.
        
        Args:
            heat_no: Heat number
            pro_line_cd: Production line code
            proc_cd: Process code (G12, G13, G15, G16)
            device_no: Device number
            start_time: Operation start time
            end_time: Operation end time
            force_cancel: If True, force a cancel event (if available for this process)
            force_rework: If True, force a rework event (if available for this process)
            
        Returns:
            List of Event objects in chronological order
        """
        process_name = self.get_process_name(proc_cd)
        if not process_name:
            return []
        
        config = EVENT_SEQUENCE_CONFIGS.get(process_name)
        if not config:
            return []
        
        # Determine if we should trigger special events
        should_cancel = force_cancel or (
            config.cancel_event and random.random() < self.cancel_probability
        )
        should_rework = not should_cancel and (
            force_rework or (config.rework_event and random.random() < self.rework_probability)
        )
        
        # Generate event codes sequence with special event consideration
        event_codes, special_event_index, special_event_type = self._generate_event_code_sequence_with_special(
            process_name, config, should_cancel, should_rework
        )
        
        # Calculate event times
        total_duration = (end_time - start_time).total_seconds()
        if total_duration <= 0 or len(event_codes) == 0:
            return []
        
        # Distribute events across the operation duration
        events: List[Event] = []
        num_events = len(event_codes)
        
        # Reserve time for start and end sequences
        start_seq_len = len(config.start_sequence)
        # End sequence length depends on whether we're canceling
        if should_cancel and config.cancel_end_sequence:
            # +1 for the cancel event itself
            end_seq_len = len(config.cancel_end_sequence)
        else:
            end_seq_len = len(config.end_sequence)
        
        middle_len = max(0, num_events - start_seq_len - end_seq_len - (1 if special_event_index is not None else 0))
        
        # Allocate 10% of time for start sequence, 10% for end sequence, 80% for middle
        start_duration = total_duration * 0.10
        end_duration = total_duration * 0.10
        middle_duration = total_duration * 0.80
        
        for i, event_code in enumerate(event_codes):
            # Calculate event time
            if i < start_seq_len:
                # Start sequence events
                segment_progress = i / max(start_seq_len, 1)
                event_time = start_time + timedelta(seconds=start_duration * segment_progress)
            elif i >= num_events - end_seq_len:
                # End sequence events
                end_idx = i - (num_events - end_seq_len)
                segment_progress = end_idx / max(end_seq_len, 1)
                event_time = start_time + timedelta(seconds=start_duration + middle_duration + end_duration * segment_progress)
            else:
                # Middle events - randomize within the middle duration
                middle_idx = i - start_seq_len
                base_progress = middle_idx / max(middle_len, 1)
                jitter = random.uniform(-0.05, 0.05)
                segment_progress = max(0, min(1, base_progress + jitter))
                event_time = start_time + timedelta(seconds=start_duration + middle_duration * segment_progress)
            
            # Ensure events are strictly after the previous event
            if events and event_time <= events[-1].event_time_start:
                event_time = events[-1].event_time_start + timedelta(seconds=random.uniform(1, 10))
            
            # Ensure we don't exceed end_time
            if event_time >= end_time:
                event_time = end_time - timedelta(seconds=(num_events - i) * 2)
            
            # Get event details
            event_info = self._event_lookup[process_name].get(event_code)
            if not event_info:
                continue
            
            code, name, p1, p2, p3, p4 = event_info
            msg = EventMessageGenerator.generate_message(code, name, p1, p2, p3, p4)
            
            # Determine if this is a special event
            event_special_type = SpecialEventType.NONE
            if i == special_event_index:
                event_special_type = special_event_type
            
            event = Event(
                heat_no=heat_no,
                pro_line_cd=pro_line_cd,
                proc_cd=proc_cd,
                device_no=device_no,
                event_code=event_code,
                event_name=name,
                event_msg=msg,
                event_time_start=event_time,
                event_time_end=event_time,  # Same as start for now
                special_event_type=event_special_type,
            )
            events.append(event)
        
        # Sort events by time to ensure proper order
        events.sort(key=lambda e: e.event_time_start)
        
        return events
    
    def _generate_event_code_sequence_with_special(
        self,
        process_name: str,
        config: EventSequenceConfig,
        should_cancel: bool,
        should_rework: bool,
    ) -> Tuple[List[str], Optional[int], SpecialEventType]:
        """Generate event codes with potential special events.
        
        Returns:
            Tuple of (event_codes, special_event_index, special_event_type)
        """
        sequence: List[str] = []
        special_event_index: Optional[int] = None
        special_event_type = SpecialEventType.NONE
        
        # Add start sequence
        sequence.extend(config.start_sequence)
        
        # Generate middle events
        num_middle = random.randint(
            max(0, self.min_events - len(config.start_sequence) - len(config.end_sequence)),
            max(0, self.max_events - len(config.start_sequence) - len(config.end_sequence))
        )
        
        # If canceling, reduce middle events and insert cancel event
        if should_cancel and config.cancel_event:
            # Cancel happens somewhere in the middle, typically after some events
            num_middle = max(1, num_middle // 2)
        
        pending_pairs: List[str] = []
        pending_followups: List[str] = []
        pair_start_to_end = dict(config.paired_events)
        
        middle_generated = 0
        attempts = 0
        max_attempts = num_middle * 3
        
        while middle_generated < num_middle and attempts < max_attempts:
            attempts += 1
            
            if pending_followups and random.random() < 0.7:
                followup = pending_followups.pop(0)
                sequence.append(followup)
                if followup in config.follow_up_events:
                    pending_followups.append(config.follow_up_events[followup])
                middle_generated += 1
                continue
            
            event, weight = random.choice(config.middle_events)
            
            if random.random() > weight:
                continue
            
            if event in pair_start_to_end:
                if len(pending_pairs) >= 2:
                    continue
                sequence.append(event)
                pending_pairs.append(pair_start_to_end[event])
                middle_generated += 1
            else:
                sequence.append(event)
                middle_generated += 1
            
            if event in config.follow_up_events:
                pending_followups.append(config.follow_up_events[event])
            
            if pending_pairs and random.random() < 0.4:
                end_event = pending_pairs.pop(0)
                sequence.append(end_event)
                middle_generated += 1
        
        # Close remaining pairs before special events
        sequence.extend(pending_pairs)
        sequence.extend(pending_followups)
        
        # Insert special event if needed
        if should_cancel and config.cancel_event:
            special_event_index = len(sequence)
            special_event_type = SpecialEventType.CANCEL
            sequence.append(config.cancel_event)
            # Use shortened end sequence for cancel
            sequence.extend(config.cancel_end_sequence or [])
        elif should_rework and config.rework_event:
            special_event_index = len(sequence)
            special_event_type = SpecialEventType.REWORK
            sequence.append(config.rework_event)
            # Rework continues to normal end sequence
            sequence.extend(config.end_sequence)
        else:
            # Normal end sequence
            sequence.extend(config.end_sequence)
        
        return sequence, special_event_index, special_event_type
    
    def generate_events_for_operation(
        self,
        operation: Dict[str, Any],
        force_cancel: bool = False,
        force_rework: bool = False,
    ) -> List[Event]:
        """Generate events for an operation dictionary.
        
        Args:
            operation: Dictionary with operation data including:
                - heat_no, pro_line_cd, proc_cd, device_no
                - real_start_time (or plan_start_time), real_end_time (or plan_end_time)
            force_cancel: If True, force a cancel event
            force_rework: If True, force a rework event
                
        Returns:
            List of Event objects
        """
        start_time = operation.get("real_start_time") or operation.get("plan_start_time")
        end_time = operation.get("real_end_time") or operation.get("plan_end_time")
        
        if not start_time or not end_time:
            return []
        
        return self.generate_event_sequence(
            heat_no=operation["heat_no"],
            pro_line_cd=operation["pro_line_cd"],
            proc_cd=operation["proc_cd"],
            device_no=operation["device_no"],
            start_time=start_time,
            end_time=end_time,
            force_cancel=force_cancel,
            force_rework=force_rework,
        )


@dataclass
class EventSequenceResult:
    """Result of generating an event sequence, including special event info."""
    events: List[Event]
    has_cancel: bool = False
    has_rework: bool = False
    cancel_event_time: Optional[datetime] = None
    rework_event_time: Optional[datetime] = None
    
    @classmethod
    def from_events(cls, events: List[Event]) -> "EventSequenceResult":
        """Create result from a list of events, detecting special events."""
        has_cancel = False
        has_rework = False
        cancel_time = None
        rework_time = None
        
        for e in events:
            if e.special_event_type == SpecialEventType.CANCEL:
                has_cancel = True
                cancel_time = e.event_time_start
            elif e.special_event_type == SpecialEventType.REWORK:
                has_rework = True
                rework_time = e.event_time_start
        
        return cls(
            events=events,
            has_cancel=has_cancel,
            has_rework=has_rework,
            cancel_event_time=cancel_time,
            rework_event_time=rework_time,
        )

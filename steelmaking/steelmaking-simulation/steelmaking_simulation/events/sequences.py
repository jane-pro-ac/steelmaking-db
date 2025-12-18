"""Event sequence configurations for steelmaking processes."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


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

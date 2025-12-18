"""Event message generation for steelmaking operations."""

import random
from typing import List


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

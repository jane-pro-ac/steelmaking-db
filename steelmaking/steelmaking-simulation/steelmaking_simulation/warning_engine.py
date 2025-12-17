"""Warning generation and seeding logic."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol

from .config import SimulationConfig
from .config import PRO_LINE_CD


class _ProcessNameResolver(Protocol):
    def __call__(self, proc_cd: str) -> Optional[str]: ...


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
    warning_code: Optional[str]
    warning_msg: str
    warning_level: int


class WarningEngine:
    """Produces warnings both historically (init) and real-time (tick)."""

    def __init__(self, *, db, config: SimulationConfig, get_process_name: _ProcessNameResolver, logger):
        self.db = db
        self.config = config
        self.get_process_name = get_process_name
        self.logger = logger

    def random_warning_level(self) -> int:
        return random.choices([1, 2, 3, 4], weights=[0.1, 0.2, 0.35, 0.35], k=1)[0]

    def get_warning_templates(self, proc_cd: str) -> List[Dict[str, Any]]:
        proc_name = self.get_process_name(proc_cd)
        templates = WARNING_TEMPLATES.get(proc_name, [])
        return templates + WARNING_TEMPLATES["COMMON"]

    def build_warning_payload(self, proc_cd: str) -> WarningPayload:
        templates = self.get_warning_templates(proc_cd)
        template = random.choice(templates) if templates else {"msg": "Process warning", "level": 4}
        warning_level = template.get("level") or self.random_warning_level()
        warning_code = template.get("code")
        if warning_code and random.random() < 0.3:
            warning_code = None
        return WarningPayload(
            warning_code=warning_code,
            warning_msg=template["msg"],
            warning_level=warning_level,
        )

    def random_warning_duration_seconds(self) -> float:
        roll = random.random()
        if roll < 0.8:
            return random.uniform(1, 10)
        if roll < 0.95:
            return random.uniform(10, 60)
        return random.uniform(60, 180)

    @staticmethod
    def _operation_window(operation: Dict[str, Any]):
        start = operation.get("real_start_time") or operation.get("plan_start_time")
        end = operation.get("real_end_time") or operation.get("plan_end_time")
        return start, end

    def seed_historical_warnings_for_completed_operation(
        self,
        *,
        operation_id: Optional[int],
        heat_no: int,
        proc_cd: str,
        device_no: str,
        crew_cd: str,
        window_start: datetime,
        window_end: datetime,
    ) -> None:
        if (
            self.config.max_warnings_per_operation <= 0
            or window_start is None
            or window_end is None
            or window_end <= window_start
        ):
            return

        if random.random() >= self.config.seed_warning_probability_per_completed_operation:
            return

        if self.config.max_warnings_per_operation <= 2:
            count = random.randint(1, self.config.max_warnings_per_operation)
        else:
            count = random.choices(
                population=list(range(1, self.config.max_warnings_per_operation + 1)),
                weights=[0.55, 0.25]
                + [0.20 / (self.config.max_warnings_per_operation - 2)] * (self.config.max_warnings_per_operation - 2),
                k=1,
            )[0]

        total_seconds = (window_end - window_start).total_seconds()
        if total_seconds <= 1:
            return

        segment = total_seconds / (count + 1)
        starts: List[datetime] = []
        for i in range(1, count + 1):
            base = window_start + timedelta(seconds=segment * i)
            jitter = segment * 0.15
            start = base + timedelta(seconds=random.uniform(-jitter, jitter))
            start = max(window_start, min(start, window_end))
            starts.append(start)
        starts.sort()

        for start in starts:
            duration_seconds = self.random_warning_duration_seconds()
            end = min(start + timedelta(seconds=duration_seconds), window_end)
            if end <= start:
                continue

            payload = self.build_warning_payload(proc_cd)
            self.db.insert_warning(
                heat_no=heat_no,
                pro_line_cd=PRO_LINE_CD,
                proc_cd=proc_cd,
                device_no=device_no,
                warning_code=payload.warning_code,
                warning_msg=payload.warning_msg,
                warning_level=payload.warning_level,
                warning_time_start=start,
                warning_time_end=end,
                extra={"operation_id": operation_id, "crew_cd": crew_cd},
            )

    def should_emit_warning_now(self, operation: Dict[str, Any], now: datetime) -> bool:
        max_warnings = self.config.max_warnings_per_operation
        if max_warnings <= 0:
            return False

        window_start, window_end = self._operation_window(operation)
        if not window_start or not window_end:
            return False

        count = self.db.get_operation_warning_count(
            heat_no=operation["heat_no"],
            proc_cd=operation["proc_cd"],
            device_no=operation["device_no"],
            window_start=window_start,
            window_end=window_end,
        )
        if count >= max_warnings:
            return False

        last_end = self.db.get_operation_last_warning_end_time(
            heat_no=operation["heat_no"],
            proc_cd=operation["proc_cd"],
            device_no=operation["device_no"],
            window_start=window_start,
            window_end=window_end,
        )
        if last_end is not None:
            op_start = window_start
            op_end = window_end
            if op_start and op_end and op_end > op_start:
                target_spacing = (op_end - op_start).total_seconds() / (max_warnings + 1)
                min_spacing = max(30.0, target_spacing * 0.7)
            else:
                min_spacing = 60.0
            if (now - last_end).total_seconds() < min_spacing:
                return False

        return random.random() < self.config.warning_probability_per_tick

    def create_realtime_warning_for_operation(self, operation: Dict[str, Any], now: datetime) -> None:
        payload = self.build_warning_payload(operation["proc_cd"])
        duration_seconds = self.random_warning_duration_seconds()
        warn_start = now
        warn_end = now + timedelta(seconds=duration_seconds)

        warn_id = self.db.insert_warning(
            heat_no=operation["heat_no"],
            pro_line_cd=operation["pro_line_cd"],
            proc_cd=operation["proc_cd"],
            device_no=operation["device_no"],
            warning_code=payload.warning_code,
            warning_msg=payload.warning_msg,
            warning_level=payload.warning_level,
            warning_time_start=warn_start,
            warning_time_end=warn_end,
            extra={"operation_id": operation["id"], "crew_cd": operation["crew_cd"]},
        )
        self.logger.info(
            "Created warning %s for op %s heat %s device %s (%s) %s-%s",
            warn_id,
            operation["id"],
            operation["heat_no"],
            operation["device_no"],
            operation["proc_cd"],
            warn_start,
            warn_end,
        )

    def tick_realtime_warnings(self, now: datetime) -> None:
        for op in self.db.get_active_operations():
            if not op.get("real_start_time"):
                continue
            if op.get("plan_end_time") and now > op["plan_end_time"]:
                continue
            if self.should_emit_warning_now(op, now):
                self.create_realtime_warning_for_operation(op, now)

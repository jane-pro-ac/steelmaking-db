"""Heat creation (BOF -> LF -> CCM planned operations)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .config import EQUIPMENT, PROCESS_FLOW, PRO_LINE_CD, ProcessStatus, SimulationConfig
from .time_utils import CST


@dataclass(frozen=True)
class HeatPlanContext:
    db: Any
    config: SimulationConfig
    scheduler: Any
    generate_heat_no: Any
    get_random_steel_grade: Any
    get_random_crew: Any
    get_random_duration: Any
    get_random_transfer_gap: Any
    aligned_device: Any
    logger: Any


class HeatPlanner:
    """Creates a new heat and inserts operations when scheduling succeeds."""

    def __init__(self, ctx: HeatPlanContext):
        self.ctx = ctx

    def create_new_heat(self) -> Optional[int]:
        steel_grade = self.ctx.get_random_steel_grade()
        crew_cd = self.ctx.get_random_crew()
        now = datetime.now(CST)

        planned: List[Dict[str, Any]] = []

        bof_duration = self.ctx.get_random_duration()
        bof_slot = self.ctx.scheduler.find_slot(
            process_name="BOF",
            desired_start=now,
            latest_start=now,
            duration=bof_duration,
            devices=EQUIPMENT["BOF"]["devices"],
        )
        if not bof_slot:
            self.ctx.logger.debug("No available BOF slot to start now; skipping new heat creation")
            return None

        bof_device = bof_slot.device_no
        planned.append(
            {
                "process_name": "BOF",
                "proc_cd": EQUIPMENT["BOF"]["proc_cd"],
                "device_no": bof_device,
                "plan_start": bof_slot.plan_start,
                "plan_end": bof_slot.plan_end,
                "status": ProcessStatus.ACTIVE,
                "real_start": bof_slot.plan_start,
                "real_end": None,
            }
        )

        prev_end = bof_slot.plan_end
        for process_name in PROCESS_FLOW[1:]:
            proc_info = EQUIPMENT[process_name]
            proc_cd = proc_info["proc_cd"]
            duration = self.ctx.get_random_duration()

            transfer_offset = self.ctx.get_random_transfer_gap()
            desired_start = prev_end + transfer_offset
            latest_start = prev_end + timedelta(minutes=self.ctx.config.max_transfer_gap_minutes)

            preferred_device: Optional[str] = None
            if random.random() < self.ctx.config.aligned_route_probability:
                preferred_device = self.ctx.aligned_device(bof_device, process_name)

            slot = None
            if preferred_device:
                slot = self.ctx.scheduler.find_slot(
                    process_name=process_name,
                    desired_start=desired_start,
                    latest_start=latest_start,
                    duration=duration,
                    devices=[preferred_device],
                )

            if not slot:
                slot = self.ctx.scheduler.find_slot(
                    process_name=process_name,
                    desired_start=desired_start,
                    latest_start=latest_start,
                    duration=duration,
                    devices=proc_info["devices"],
                )

            if not slot:
                self.ctx.logger.debug(
                    "No available slot for %s within transfer window; skipping new heat creation",
                    process_name,
                )
                return None

            planned.append(
                {
                    "process_name": process_name,
                    "proc_cd": proc_cd,
                    "device_no": slot.device_no,
                    "plan_start": slot.plan_start,
                    "plan_end": slot.plan_end,
                    "status": ProcessStatus.PENDING,
                    "real_start": None,
                    "real_end": None,
                }
            )
            prev_end = slot.plan_end

        heat_no = self.ctx.generate_heat_no()
        self.ctx.logger.info("Creating new heat %s with steel grade %s", heat_no, steel_grade["code"])

        for entry in planned:
            self.ctx.db.insert_operation(
                heat_no=heat_no,
                pro_line_cd=PRO_LINE_CD,
                proc_cd=entry["proc_cd"],
                device_no=entry["device_no"],
                crew_cd=crew_cd,
                stl_grd_id=steel_grade["id"],
                stl_grd_cd=steel_grade["code"],
                proc_status=entry["status"],
                plan_start_time=entry["plan_start"],
                plan_end_time=entry["plan_end"],
                real_start_time=entry["real_start"],
                real_end_time=entry["real_end"],
            )
            self.ctx.logger.info(
                "  Created %s operation on %s, status: %s",
                entry["process_name"],
                entry["device_no"],
                entry["status"],
            )

        return heat_no


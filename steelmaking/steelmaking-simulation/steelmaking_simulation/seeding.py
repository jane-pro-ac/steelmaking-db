"""Initialization seeding logic for operations and historical warnings."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .config import EQUIPMENT, PROCESS_FLOW, PRO_LINE_CD, ProcessStatus, SimulationConfig
from .warning_engine import WarningEngine


@dataclass(frozen=True)
class SeedContext:
    db: any
    config: SimulationConfig
    warnings: WarningEngine
    generate_heat_no: any
    get_random_steel_grade: any
    get_random_crew: any
    get_random_duration: any
    logger: any


class OperationSeeder:
    """Seeds demo data on startup while enforcing all constraints."""

    def __init__(self, ctx: SeedContext):
        self.ctx = ctx

    def reset_demo_data(self, now: datetime) -> None:
        self.ctx.logger.info("Resetting demo data: clearing table and seeding past/future operations")
        self.ctx.db.clear_operations()
        self.seed_initial_timeline(now)

    def seed_initial_timeline(self, now: datetime) -> None:
        min_rest = self.ctx.config.min_rest_duration_minutes
        max_rest = self.ctx.config.max_rest_duration_minutes

        # Keep a bounded horizon; enough to provide completed, active, and pending.
        span_past = timedelta(minutes=max_rest * max(self.ctx.config.seed_past_heats, 4) + 180)
        span_future = timedelta(minutes=max_rest * max(self.ctx.config.seed_future_heats, 4) + 120)

        start_time = now - span_past
        end_time = now + span_future

        bof_devices = EQUIPMENT["BOF"]["devices"]
        lf_devices = EQUIPMENT["LF"]["devices"]
        ccm_devices = EQUIPMENT["CCM"]["devices"]

        for line_idx, bof_device in enumerate(bof_devices):
            lf_device = lf_devices[line_idx] if line_idx < len(lf_devices) else lf_devices[0]
            ccm_device = ccm_devices[line_idx] if line_idx < len(ccm_devices) else ccm_devices[0]

            last_end_bof: Optional[datetime] = None
            last_end_lf: Optional[datetime] = None
            last_end_ccm: Optional[datetime] = None

            cursor = start_time
            while cursor <= end_time:
                heat_no = self.ctx.generate_heat_no()
                steel_grade = self.ctx.get_random_steel_grade()
                crew_cd = self.ctx.get_random_crew()

                inserted = False
                for _attempt in range(30):
                    bof_rest = timedelta(minutes=random.randint(min_rest, max_rest))
                    bof_start = cursor if last_end_bof is None else max(cursor, last_end_bof + bof_rest)
                    bof_duration = self.ctx.get_random_duration()
                    bof_end = bof_start + bof_duration
                    if bof_start > end_time:
                        break

                    lf_duration = self.ctx.get_random_duration()
                    lf_earliest = bof_end + timedelta(minutes=self.ctx.config.min_transfer_gap_minutes)
                    lf_latest = bof_end + timedelta(minutes=self.ctx.config.max_transfer_gap_minutes)
                    if last_end_lf is not None:
                        lf_earliest = max(lf_earliest, last_end_lf + timedelta(minutes=min_rest))
                        lf_latest = min(lf_latest, last_end_lf + timedelta(minutes=max_rest))
                    if lf_earliest > lf_latest:
                        continue
                    lf_start = lf_earliest + timedelta(
                        seconds=random.uniform(0, (lf_latest - lf_earliest).total_seconds())
                    )
                    lf_end = lf_start + lf_duration

                    ccm_duration = self.ctx.get_random_duration()
                    ccm_earliest = lf_end + timedelta(minutes=self.ctx.config.min_transfer_gap_minutes)
                    ccm_latest = lf_end + timedelta(minutes=self.ctx.config.max_transfer_gap_minutes)
                    if last_end_ccm is not None:
                        ccm_earliest = max(ccm_earliest, last_end_ccm + timedelta(minutes=min_rest))
                        ccm_latest = min(ccm_latest, last_end_ccm + timedelta(minutes=max_rest))
                    if ccm_earliest > ccm_latest:
                        continue
                    ccm_start = ccm_earliest + timedelta(
                        seconds=random.uniform(0, (ccm_latest - ccm_earliest).total_seconds())
                    )
                    ccm_end = ccm_start + ccm_duration

                    stages = [
                        ("BOF", EQUIPMENT["BOF"]["proc_cd"], bof_device, bof_start, bof_end),
                        ("LF", EQUIPMENT["LF"]["proc_cd"], lf_device, lf_start, lf_end),
                        ("CCM", EQUIPMENT["CCM"]["proc_cd"], ccm_device, ccm_start, ccm_end),
                    ]

                    for _name, proc_cd, device_no, plan_start, plan_end in stages:
                        if plan_end <= now:
                            proc_status = ProcessStatus.COMPLETED
                            real_start = plan_start
                            real_end = plan_end
                        elif plan_start <= now < plan_end:
                            proc_status = ProcessStatus.ACTIVE
                            real_start = plan_start
                            real_end = None
                        else:
                            proc_status = ProcessStatus.PENDING
                            real_start = None
                            real_end = None

                        operation_id = self.ctx.db.insert_operation(
                            heat_no=heat_no,
                            pro_line_cd=PRO_LINE_CD,
                            proc_cd=proc_cd,
                            device_no=device_no,
                            crew_cd=crew_cd,
                            stl_grd_id=steel_grade["id"],
                            stl_grd_cd=steel_grade["code"],
                            proc_status=proc_status,
                            plan_start_time=plan_start,
                            plan_end_time=plan_end,
                            real_start_time=real_start,
                            real_end_time=real_end,
                        )

                        if proc_status == ProcessStatus.COMPLETED:
                            self.ctx.warnings.seed_historical_warnings_for_completed_operation(
                                operation_id=operation_id,
                                heat_no=heat_no,
                                proc_cd=proc_cd,
                                device_no=device_no,
                                crew_cd=crew_cd,
                                window_start=plan_start,
                                window_end=plan_end,
                            )

                    last_end_bof = bof_end
                    last_end_lf = lf_end
                    last_end_ccm = ccm_end
                    cursor = bof_end + timedelta(minutes=random.randint(min_rest, max_rest))
                    inserted = True
                    break

                if not inserted:
                    cursor += timedelta(minutes=max_rest)

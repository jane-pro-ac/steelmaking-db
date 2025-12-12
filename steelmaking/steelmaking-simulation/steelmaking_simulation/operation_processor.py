"""Runtime processing of active and pending operations."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .config import EQUIPMENT, PROCESS_FLOW, ProcessStatus, SimulationConfig
from .time_utils import CST


@dataclass(frozen=True)
class OperationProcessorContext:
    db: Any
    config: SimulationConfig
    scheduler: Any
    get_process_name: Any
    is_device_available: Any
    get_random_transfer_gap: Any
    aligned_device: Any
    logger: Any


class OperationProcessor:
    def __init__(self, ctx: OperationProcessorContext):
        self.ctx = ctx

    def process_active_operations(self) -> None:
        active_ops = self.ctx.db.get_active_operations()
        now = datetime.now(CST)

        for op in active_ops:
            if op.get("real_start_time"):
                elapsed = now - op["real_start_time"]
                min_duration = timedelta(minutes=self.ctx.config.min_operation_duration)

                if elapsed >= min_duration:
                    max_duration = timedelta(minutes=self.ctx.config.max_operation_duration)
                    if elapsed >= max_duration:
                        should_complete = True
                    else:
                        progress = (elapsed - min_duration) / (max_duration - min_duration)
                        should_complete = random.random() < (0.3 + 0.7 * progress)

                    if should_complete:
                        self._complete_operation(op, now)

    def _complete_operation(self, operation: Dict[str, Any], completion_time: datetime) -> None:
        self.ctx.logger.info(
            "Completing operation %s for heat %s (%s)",
            operation["id"],
            operation["heat_no"],
            operation["proc_cd"],
        )

        self.ctx.db.update_operation_status(
            operation_id=operation["id"],
            proc_status=ProcessStatus.COMPLETED,
            real_end_time=completion_time,
        )

        heat_ops = self.ctx.db.get_heat_operations(operation["heat_no"])
        next_op = next((op for op in heat_ops if op["proc_status"] == ProcessStatus.PENDING), None)
        if not next_op:
            return

        proc_name = self.ctx.get_process_name(next_op["proc_cd"])
        if not proc_name:
            return

        planned_duration = next_op["plan_end_time"] - next_op["plan_start_time"]
        transfer_offset = self.ctx.get_random_transfer_gap()
        desired_start = completion_time + transfer_offset
        latest_start = completion_time + timedelta(minutes=self.ctx.config.max_transfer_gap_minutes)

        bof_proc_cd = EQUIPMENT["BOF"]["proc_cd"]
        bof_device = None
        for heat_op in heat_ops:
            if heat_op["proc_cd"] == bof_proc_cd:
                bof_device = heat_op["device_no"]
                break

        preferred_device: Optional[str] = None
        if bof_device and random.random() < self.ctx.config.aligned_route_probability:
            preferred_device = self.ctx.aligned_device(bof_device, proc_name)

        slot = None
        if preferred_device:
            slot = self.ctx.scheduler.find_slot(
                process_name=proc_name,
                desired_start=desired_start,
                latest_start=latest_start,
                duration=planned_duration,
                devices=[preferred_device],
                exclude_operation_id=next_op["id"],
            )
        if not slot:
            slot = self.ctx.scheduler.find_slot(
                process_name=proc_name,
                desired_start=desired_start,
                latest_start=latest_start,
                duration=planned_duration,
                devices=EQUIPMENT[proc_name]["devices"],
                exclude_operation_id=next_op["id"],
            )
        if not slot:
            self.ctx.logger.debug("No available slot to schedule next operation %s", next_op["id"])
            return

        if slot.plan_start != next_op["plan_start_time"] or slot.plan_end != next_op["plan_end_time"]:
            self.ctx.db.update_operation_plan_times(next_op["id"], slot.plan_start, slot.plan_end)
        if slot.device_no != next_op["device_no"]:
            self.ctx.db.update_operation_status(
                operation_id=next_op["id"],
                proc_status=next_op["proc_status"],
                device_no=slot.device_no,
            )

        now = datetime.now(CST)
        if now >= slot.plan_start:
            device_to_use = slot.device_no if self.ctx.is_device_available(slot.device_no) else None
            if device_to_use:
                self.ctx.logger.info("Starting next operation %s (%s) on %s", next_op["id"], next_op["proc_cd"], device_to_use)
                self.ctx.db.update_operation_status(
                    operation_id=next_op["id"],
                    proc_status=ProcessStatus.ACTIVE,
                    real_start_time=now,
                    device_no=device_to_use,
                )
            else:
                self.ctx.logger.debug("No available device for next operation, will retry later")

    def process_pending_operations(self) -> None:
        pending_ops = self.ctx.db.get_pending_operations()
        now = datetime.now(CST)

        for op in pending_ops:
            heat_ops = self.ctx.db.get_heat_operations(op["heat_no"])

            current_proc_idx = None
            for i, proc_name in enumerate(PROCESS_FLOW):
                if EQUIPMENT[proc_name]["proc_cd"] == op["proc_cd"]:
                    current_proc_idx = i
                    break

            if current_proc_idx is None:
                continue

            if current_proc_idx == 0:
                # First stage (BOF) has no predecessor; start when plan time arrives.
                if now < op["plan_start_time"]:
                    continue

                duration = op["plan_end_time"] - op["plan_start_time"]
                desired_start = max(op["plan_start_time"], now)

                # Prefer the planned device, but allow cross-device reassignment if blocked.
                slot = self.ctx.scheduler.find_slot(
                    process_name="BOF",
                    desired_start=desired_start,
                    latest_start=None,
                    duration=duration,
                    devices=[op["device_no"]],
                    exclude_operation_id=op["id"],
                )
                if not slot:
                    slot = self.ctx.scheduler.find_slot(
                        process_name="BOF",
                        desired_start=desired_start,
                        latest_start=None,
                        duration=duration,
                        devices=EQUIPMENT["BOF"]["devices"],
                        exclude_operation_id=op["id"],
                    )
                if not slot:
                    self.ctx.logger.debug("No available slot for pending BOF operation %s, will retry", op["id"])
                    continue

                if slot.plan_start != op["plan_start_time"] or slot.plan_end != op["plan_end_time"]:
                    self.ctx.db.update_operation_plan_times(op["id"], slot.plan_start, slot.plan_end)
                if slot.device_no != op["device_no"]:
                    self.ctx.db.update_operation_status(operation_id=op["id"], proc_status=op["proc_status"], device_no=slot.device_no)

                if now < slot.plan_start:
                    continue

                device_no = slot.device_no
                if not self.ctx.is_device_available(device_no):
                    self.ctx.logger.debug("Device %s not free for pending BOF operation %s, will retry", device_no, op["id"])
                    continue

                self.ctx.logger.info("Starting BOF operation %s for heat %s (%s) on %s", op["id"], op["heat_no"], op["proc_cd"], device_no)
                self.ctx.db.update_operation_status(
                    operation_id=op["id"],
                    proc_status=ProcessStatus.ACTIVE,
                    real_start_time=now,
                    device_no=device_no,
                )
                continue

            prev_proc_name = PROCESS_FLOW[current_proc_idx - 1]
            prev_proc_cd = EQUIPMENT[prev_proc_name]["proc_cd"]
            prev_op = next((h for h in heat_ops if h["proc_cd"] == prev_proc_cd), None)

            if not (prev_op and prev_op["proc_status"] == ProcessStatus.COMPLETED and prev_op["real_end_time"]):
                continue

            proc_name = PROCESS_FLOW[current_proc_idx]
            min_ready_time = prev_op["real_end_time"] + timedelta(minutes=self.ctx.config.min_transfer_gap_minutes)
            max_ready_time = prev_op["real_end_time"] + timedelta(minutes=self.ctx.config.max_transfer_gap_minutes)
            scheduled_start = max(op["plan_start_time"], min_ready_time)
            duration = op["plan_end_time"] - op["plan_start_time"]

            slot = self.ctx.scheduler.find_slot(
                process_name=proc_name,
                desired_start=scheduled_start,
                latest_start=max_ready_time,
                duration=duration,
                devices=EQUIPMENT[proc_name]["devices"],
                exclude_operation_id=op["id"],
            )
            if not slot:
                self.ctx.logger.debug("No available slot for pending operation %s, will retry", op["id"])
                continue

            if slot.plan_start != op["plan_start_time"] or slot.plan_end != op["plan_end_time"]:
                self.ctx.db.update_operation_plan_times(op["id"], slot.plan_start, slot.plan_end)
            if slot.device_no != op["device_no"]:
                self.ctx.db.update_operation_status(operation_id=op["id"], proc_status=op["proc_status"], device_no=slot.device_no)

            if now < slot.plan_start:
                continue

            device_no = slot.device_no
            if not self.ctx.is_device_available(device_no):
                self.ctx.logger.debug("Device %s not free for pending operation %s, will retry", device_no, op["id"])
                continue

            self.ctx.logger.info("Starting pending operation %s for heat %s (%s) on %s", op["id"], op["heat_no"], op["proc_cd"], device_no)
            self.ctx.db.update_operation_status(
                operation_id=op["id"],
                proc_status=ProcessStatus.ACTIVE,
                real_start_time=now,
                device_no=device_no,
            )

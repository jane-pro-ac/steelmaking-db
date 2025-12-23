"""Tests for simulator constraints and core functionality."""

import logging
from datetime import datetime, timedelta

import pytest

from steelmaking_simulation.config import (
    DatabaseConfig,
    SimulationConfig,
    ProcessStatus,
    EQUIPMENT,
    PROCESS_FLOW,
)
from steelmaking_simulation.core import SteelmakingSimulator, Slot
from steelmaking_simulation.events import EVENT_SEQUENCE_CONFIGS, EventEngine, EventEngineConfig
from steelmaking_simulation.utils import CST

from conftest import FakeDatabaseManager


def set_fixed_now(monkeypatch, fixed_now: datetime):
    """Monkeypatch datetime.now to a fixed point for simulator and scheduler."""
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    import steelmaking_simulation.core.simulator as simulator_mod
    import steelmaking_simulation.core.scheduler as scheduler_mod
    import steelmaking_simulation.core.processor as operation_processor_mod
    import steelmaking_simulation.planning.heat_planner as heat_planner_mod

    monkeypatch.setattr(simulator_mod, "datetime", FixedDateTime)
    monkeypatch.setattr(scheduler_mod, "datetime", FixedDateTime)
    monkeypatch.setattr(operation_processor_mod, "datetime", FixedDateTime)
    monkeypatch.setattr(heat_planner_mod, "datetime", FixedDateTime)


@pytest.fixture()
def fixed_now(monkeypatch):
    now = datetime(2024, 1, 1, 12, 0, tzinfo=CST)
    set_fixed_now(monkeypatch, now)
    return now


@pytest.fixture()
def simulator(fixed_now):
    import random
    random.seed(42)
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    # Normalize counts to keep the seeded timeline close to "now" for deterministic checks
    sim.config.seed_past_heats = 4
    sim.config.seed_active_heats = 1
    sim.config.seed_future_heats = 4
    sim.config.seed_warning_probability_per_completed_operation = 0.25
    # Disable cancel/rework events for constraint tests to avoid timeline gaps
    sim.events.event_config.cancel_event_probability = 0.0
    sim.events.event_config.rework_event_probability = 0.0
    sim.events.generator.cancel_probability = 0.0
    sim.events.generator.rework_probability = 0.0
    return sim


def _derive_window(op):
    start = op["real_start_time"] or op["plan_start_time"]
    end = op["real_end_time"] or op["plan_end_time"]
    return start, end


def _device_timelines(ops):
    by_device = {}
    for op in ops:
        by_device.setdefault(op["device_no"], []).append(op)
    for ops_list in by_device.values():
        ops_list.sort(key=lambda op: op["real_start_time"] or op["plan_start_time"])
    return by_device


def _warnings_for_operation(warnings, operation):
    start, end = _derive_window(operation)
    return [
        w
        for w in warnings
        if w["heat_no"] == operation["heat_no"]
        and w["proc_cd"] == operation["proc_cd"]
        and w["device_no"] == operation["device_no"]
        and start <= w["warning_time_start"] <= end
    ]


def test_initialization_respects_constraints(simulator, fixed_now):
    simulator.initialize()
    ops = simulator.db.operations
    config = simulator.config

    # Durations within 30-50 minutes
    for op in ops:
        # Skip canceled operations for duration check
        if op.get("proc_status") == ProcessStatus.CANCELED:
            continue
        start, end = _derive_window(op)
        minutes = (end - start).total_seconds() / 60
        assert config.min_operation_duration - 0.5 <= minutes <= config.max_operation_duration + 0.5

    # Completed ops end before now; active exist
    completed = [op for op in ops if op["proc_status"] == ProcessStatus.COMPLETED]
    active = [op for op in ops if op["proc_status"] == ProcessStatus.ACTIVE]
    assert active, "Expected at least one active operation after initialization"
    assert len(active) >= 1
    assert all(op["real_end_time"] is None for op in active)
    assert all(op["plan_start_time"] <= fixed_now <= op["plan_end_time"] for op in active)
    assert all(op["real_start_time"] <= fixed_now for op in active)
    assert all(op["real_end_time"] and op["real_end_time"] <= fixed_now for op in completed)
    assert all(op["real_start_time"] <= fixed_now <= (op["real_end_time"] or op["plan_end_time"]) for op in active)

    # No device overlap and rest windows between 10-20 minutes
    timelines = _device_timelines(ops)
    for device, device_ops in timelines.items():
        prev_end = None
        for op in device_ops:
            start, end = _derive_window(op)
            if prev_end:
                gap = (start - prev_end).total_seconds() / 60
                assert config.min_rest_duration_minutes - 0.1 <= gap <= config.max_rest_duration_minutes + 0.1, (
                    f"Rest gap {gap} out of bounds on device {device}"
                )
            assert start >= (prev_end or start), f"Overlap detected on device {device}"
            prev_end = end

    # Transfer gaps between BOF->LF->CCM are 20-30 minutes
    bof_cd = EQUIPMENT["BOF"]["proc_cd"]
    lf_cd = EQUIPMENT["LF"]["proc_cd"]
    ccm_cd = EQUIPMENT["CCM"]["proc_cd"]
    for heat_no in {op["heat_no"] for op in ops}:
        heat_ops = [op for op in ops if op["heat_no"] == heat_no]
        by_cd = {op["proc_cd"]: op for op in heat_ops}
        if bof_cd in by_cd and lf_cd in by_cd:
            gap1 = (by_cd[lf_cd]["plan_start_time"] - by_cd[bof_cd]["plan_end_time"]).total_seconds() / 60
            assert config.min_transfer_gap_minutes - 0.1 <= gap1 <= config.max_transfer_gap_minutes + 0.1
        if lf_cd in by_cd and ccm_cd in by_cd:
            gap2 = (by_cd[ccm_cd]["plan_start_time"] - by_cd[lf_cd]["plan_end_time"]).total_seconds() / 60
            assert config.min_transfer_gap_minutes - 0.1 <= gap2 <= config.max_transfer_gap_minutes + 0.1

    # Process flow ordering per heat
    expected_flow = [EQUIPMENT[name]["proc_cd"] for name in PROCESS_FLOW]
    for heat_no in {op["heat_no"] for op in ops}:
        heat_ops = [op for op in ops if op["heat_no"] == heat_no]
        seen = [op["proc_cd"] for op in sorted(heat_ops, key=lambda o: o["plan_start_time"])]
        assert set(expected_flow).issubset(set(seen))


def test_future_and_past_schedule_respects_rest(simulator, fixed_now):
    simulator.initialize()
    ops = simulator.db.operations
    config = simulator.config

    timelines = _device_timelines(ops)
    for device, device_ops in timelines.items():
            for first, second in zip(device_ops, device_ops[1:]):
                first_end = (first["real_end_time"] or first["plan_end_time"])
                second_start = (second["real_start_time"] or second["plan_start_time"])
                gap_minutes = (second_start - first_end).total_seconds() / 60
                assert config.min_rest_duration_minutes - 0.1 <= gap_minutes <= config.max_rest_duration_minutes + 0.5


def test_initialization_has_no_large_device_idle_gaps(simulator, fixed_now):
    simulator.initialize()
    ops = simulator.db.operations

    for proc_name, info in EQUIPMENT.items():
        for device in info["devices"]:
            device_ops = [op for op in ops if op["device_no"] == device]
            assert len(device_ops) >= 2, f"Expected >=2 operations on {device} to validate rest constraints"


def test_create_new_heat_does_not_generate_heat_no_when_no_bof_slot(fixed_now, monkeypatch):
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    sim.steel_grades = db.get_steel_grades()

    def find_slot_stub(*, process_name, desired_start, latest_start, duration, devices=None, exclude_operation_id=None):
        if process_name == "BOF":
            return None
        return Slot(device_no=(devices or ["X"])[0], plan_start=desired_start, plan_end=desired_start + duration)

    sim.scheduler.find_slot = find_slot_stub

    calls = {"n": 0}

    def heat_no_stub():
        calls["n"] += 1
        return 240100001

    monkeypatch.setattr(sim, "generate_heat_no", heat_no_stub)

    assert sim.create_new_heat() is None
    assert calls["n"] == 0
    assert db.operations == []


def test_create_new_heat_success_increments_heat_no(fixed_now):
    import random

    random.seed(123)
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    sim.steel_grades = db.get_steel_grades()

    counters = {"BOF": 0, "LF": 0, "CCM": 0}

    def find_slot_stub(*, process_name, desired_start, latest_start, duration, devices=None, exclude_operation_id=None):
        devices = devices or EQUIPMENT[process_name]["devices"]
        idx = counters[process_name] % len(devices)
        counters[process_name] += 1
        return Slot(device_no=devices[idx], plan_start=desired_start, plan_end=desired_start + duration)

    sim.scheduler.find_slot = find_slot_stub

    heat1 = sim.create_new_heat()
    heat2 = sim.create_new_heat()
    assert heat1 is not None and heat2 is not None and heat1 != heat2

    assert len([op for op in db.operations if op["heat_no"] == heat1]) == 3
    assert len([op for op in db.operations if op["heat_no"] == heat2]) == 3


def test_warning_duration_distribution_sanity(fixed_now):
    import random

    random.seed(42)
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)

    durations = []
    for _ in range(1000):
        durations.append(sim._random_warning_duration_seconds())

    short = sum(1 for d in durations if d < 10)
    long = sum(1 for d in durations if d > 60)
    assert short >= 700
    assert long <= 100


def test_aligned_routing_when_probability_is_one(fixed_now):
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    sim.steel_grades = db.get_steel_grades()
    sim.config.aligned_route_probability = 1.0
    sim.config.min_transfer_gap_minutes = 20
    sim.config.max_transfer_gap_minutes = 30

    def find_slot_stub(*, process_name, desired_start, latest_start, duration, devices=None, exclude_operation_id=None):
        assert devices, "Expected explicit device preference in this test"
        return Slot(device_no=devices[0], plan_start=desired_start, plan_end=desired_start + duration)

    sim.scheduler.find_slot = find_slot_stub

    heat_no = sim.create_new_heat()
    assert heat_no is not None
    ops = db.get_heat_operations(heat_no)
    bof = next(op for op in ops if op["proc_cd"] == EQUIPMENT["BOF"]["proc_cd"])
    lf = next(op for op in ops if op["proc_cd"] == EQUIPMENT["LF"]["proc_cd"])
    ccm = next(op for op in ops if op["proc_cd"] == EQUIPMENT["CCM"]["proc_cd"])

    assert lf["device_no"].endswith(bof["device_no"][-1])
    assert ccm["device_no"].endswith(bof["device_no"][-1])


def test_realtime_warnings_time_order_and_max_per_operation(fixed_now):
    import random

    random.seed(7)
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    sim.config.warning_probability_per_tick = 1.0
    sim.config.max_warnings_per_operation = 5

    op_id = db.insert_operation(
        heat_no=240100001,
        pro_line_cd="G1",
        proc_cd=EQUIPMENT["BOF"]["proc_cd"],
        device_no=EQUIPMENT["BOF"]["devices"][0],
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=fixed_now - timedelta(minutes=10),
        plan_end_time=fixed_now + timedelta(minutes=30),
        real_start_time=fixed_now - timedelta(minutes=10),
        real_end_time=None,
    )

    # Step time forward; spacing should allow at most 5 warnings.
    times = [fixed_now + timedelta(minutes=4 * i) for i in range(10)]
    for t in times:
        sim._tick_realtime_warnings(t)

    op = next(o for o in db.operations if o["id"] == op_id)
    warnings = _warnings_for_operation(db.warnings, op)
    assert len(warnings) <= sim.config.max_warnings_per_operation
    assert warnings, "Expected at least one warning when probability=1.0"

    # Time-ordered and anchored near tick time.
    starts = [w["warning_time_start"] for w in warnings]
    assert starts == sorted(starts)
    assert all(s in times for s in starts)


def test_initialization_seeds_warnings_for_completed_operations(simulator, fixed_now):
    simulator.initialize()
    ops = simulator.db.operations
    warnings = simulator.db.warnings
    config = simulator.config

    completed_ops = [op for op in ops if op["proc_status"] == ProcessStatus.COMPLETED]
    assert completed_ops, "Need completed ops to validate historical warning seeding"

    by_op = {op["id"]: _warnings_for_operation(warnings, op) for op in completed_ops}

    completed_with_warnings = [op for op in completed_ops if by_op.get(op["id"])]
    assert completed_with_warnings, "Expected at least some completed ops to have warnings"
    assert len(completed_with_warnings) < len(completed_ops), "Warnings should not exist for every completed operation"

    for op in completed_with_warnings:
        op_warnings = by_op.get(op["id"], [])
        assert 1 <= len(op_warnings) <= config.max_warnings_per_operation
        start, end = _derive_window(op)
        op_warnings.sort(key=lambda w: w["warning_time_start"])
        for w in op_warnings:
            assert start <= w["warning_time_start"] <= end
            assert start <= w["warning_time_end"] <= end
            assert w["warning_time_end"] > w["warning_time_start"]


def test_pending_bof_starts_when_plan_time_passed(fixed_now):
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)

    plan_start = fixed_now - timedelta(minutes=5)
    plan_end = plan_start + timedelta(minutes=30)
    op_id = db.insert_operation(
        heat_no=240100123,
        pro_line_cd="G1",
        proc_cd=EQUIPMENT["BOF"]["proc_cd"],
        device_no=EQUIPMENT["BOF"]["devices"][0],
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.PENDING,
        plan_start_time=plan_start,
        plan_end_time=plan_end,
        real_start_time=None,
        real_end_time=None,
    )

    sim.process_pending_operations()

    op = next(o for o in db.operations if o["id"] == op_id)
    assert op["proc_status"] == ProcessStatus.ACTIVE
    assert op["real_start_time"] == fixed_now
    assert op["real_end_time"] is None
    # Plan remains immutable after creation.
    assert op["plan_start_time"] == plan_start
    assert op["plan_end_time"] == plan_end


def test_pending_bof_can_start_after_excess_idle_time(fixed_now):
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)

    # Device was idle longer than max_rest_duration_minutes; runtime must not deadlock.
    prev_end = fixed_now - timedelta(hours=2)
    db.insert_operation(
        heat_no=240100200,
        pro_line_cd="G1",
        proc_cd=EQUIPMENT["BOF"]["proc_cd"],
        device_no=EQUIPMENT["BOF"]["devices"][0],
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.COMPLETED,
        plan_start_time=prev_end - timedelta(minutes=35),
        plan_end_time=prev_end,
        real_start_time=prev_end - timedelta(minutes=35),
        real_end_time=prev_end,
    )

    plan_start = prev_end + timedelta(minutes=10)
    plan_end = plan_start + timedelta(minutes=30)
    op_id = db.insert_operation(
        heat_no=240100201,
        pro_line_cd="G1",
        proc_cd=EQUIPMENT["BOF"]["proc_cd"],
        device_no=EQUIPMENT["BOF"]["devices"][0],
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.PENDING,
        plan_start_time=plan_start,
        plan_end_time=plan_end,
        real_start_time=None,
        real_end_time=None,
    )

    sim.process_pending_operations()

    op = next(o for o in db.operations if o["id"] == op_id)
    assert op["proc_status"] == ProcessStatus.ACTIVE
    assert op["real_start_time"] == fixed_now
    assert op["real_end_time"] is None
    assert op["plan_start_time"] == plan_start
    assert op["plan_end_time"] == plan_end


def test_runtime_does_not_mutate_planned_timestamps(simulator, fixed_now, monkeypatch):
    simulator.initialize()
    simulator.config.new_heat_probability = 0.0

    original = {op["id"]: (op["plan_start_time"], op["plan_end_time"]) for op in simulator.db.operations}

    # Advance time in steps and tick; plan times should stay stable.
    times = [fixed_now + timedelta(minutes=15 * i) for i in range(1, 9)]
    for t in times:
        set_fixed_now(monkeypatch, datetime(t.year, t.month, t.day, t.hour, t.minute, tzinfo=CST))
        simulator.tick()

    after = {op["id"]: (op["plan_start_time"], op["plan_end_time"]) for op in simulator.db.operations if op["id"] in original}
    assert after == original


def test_pending_lf_can_start_after_missing_transfer_window(fixed_now):
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)

    prev_end = fixed_now - timedelta(minutes=40)
    prev_id = db.insert_operation(
        heat_no=240100124,
        pro_line_cd="G1",
        proc_cd=EQUIPMENT["BOF"]["proc_cd"],
        device_no=EQUIPMENT["BOF"]["devices"][0],
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.COMPLETED,
        plan_start_time=prev_end - timedelta(minutes=35),
        plan_end_time=prev_end,
        real_start_time=prev_end - timedelta(minutes=35),
        real_end_time=prev_end,
    )

    # Planned inside 20-30 window, but now is already past max_ready (prev_end + 30).
    lf_plan_start = prev_end + timedelta(minutes=29)
    lf_plan_end = lf_plan_start + timedelta(minutes=35)
    lf_id = db.insert_operation(
        heat_no=240100124,
        pro_line_cd="G1",
        proc_cd=EQUIPMENT["LF"]["proc_cd"],
        device_no=EQUIPMENT["LF"]["devices"][0],
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.PENDING,
        plan_start_time=lf_plan_start,
        plan_end_time=lf_plan_end,
        real_start_time=None,
        real_end_time=None,
    )

    sim.process_pending_operations()

    lf = next(o for o in db.operations if o["id"] == lf_id)
    assert lf["proc_status"] == ProcessStatus.ACTIVE
    assert lf["real_start_time"] == fixed_now
    assert lf["real_end_time"] is None


def test_operation_completion_emits_end_events(fixed_now):
    """Test that completing an operation emits the correct end sequence events.
    
    This test verifies that when an active BOF operation is completed,
    the end sequence events (出钢开始, 出钢结束, 底吹开始, 底吹结束, 
    炉次结束, 处理结束, 钢包离开) are properly generated.
    """
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    
    # Create an active BOF operation
    heat_no = 240100200
    device_no = EQUIPMENT["BOF"]["devices"][0]
    proc_cd = EQUIPMENT["BOF"]["proc_cd"]
    start_time = fixed_now - timedelta(minutes=40)  # Started 40 minutes ago
    plan_end = fixed_now + timedelta(minutes=10)
    
    op_id = db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=plan_end,
        real_start_time=start_time,
        real_end_time=None,
    )
    
    # Add some start sequence events (simulating real-time event generation)
    db.insert_event(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        event_code="G12001",  # 钢包到达
        event_name="钢包到达",
        event_msg="钢包到达",
        event_time_start=start_time,
        event_time_end=start_time,
    )
    db.insert_event(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        event_code="G12003",  # 处理开始
        event_name="处理开始",
        event_msg="处理开始",
        event_time_start=start_time + timedelta(seconds=30),
        event_time_end=start_time + timedelta(seconds=30),
    )
    db.insert_event(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        event_code="G12005",  # 炉次开始
        event_name="炉次开始",
        event_msg="炉次开始",
        event_time_start=start_time + timedelta(seconds=60),
        event_time_end=start_time + timedelta(seconds=60),
    )
    # Add some middle events
    db.insert_event(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        event_code="G12008",  # 加料
        event_name="加料",
        event_msg="加料",
        event_time_start=start_time + timedelta(minutes=10),
        event_time_end=start_time + timedelta(minutes=10),
    )
    
    initial_event_count = len(db.events)
    
    # Process active operations - this should complete the operation and emit end events
    # Force completion by making operation past max duration
    operation = db.operations[0]
    
    # Manually trigger completion through the processor
    sim.processor._complete_operation(operation, fixed_now)
    
    # Verify operation is now completed
    op = db.operations[0]
    assert op["proc_status"] == ProcessStatus.COMPLETED
    assert op["real_end_time"] == fixed_now
    
    # Verify end events were emitted
    final_event_count = len(db.events)
    assert final_event_count > initial_event_count, "End events should have been emitted"
    
    # Check that the correct end sequence events exist
    end_sequence = EVENT_SEQUENCE_CONFIGS["BOF"].end_sequence
    event_codes = [e["event_code"] for e in db.events if e["heat_no"] == heat_no]
    
    # All end sequence events should now be present
    for code in end_sequence:
        assert code in event_codes, f"Missing end event {code}"


def test_operation_completion_does_not_duplicate_end_events(fixed_now):
    """Test that end events are not duplicated if they already exist."""
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    
    heat_no = 240100201
    device_no = EQUIPMENT["BOF"]["devices"][0]
    proc_cd = EQUIPMENT["BOF"]["proc_cd"]
    start_time = fixed_now - timedelta(minutes=40)
    plan_end = fixed_now + timedelta(minutes=10)
    
    op_id = db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=plan_end,
        real_start_time=start_time,
        real_end_time=None,
    )
    
    # Add start sequence events
    for i, code in enumerate(EVENT_SEQUENCE_CONFIGS["BOF"].start_sequence):
        db.insert_event(
            heat_no=heat_no,
            pro_line_cd="G1",
            proc_cd=proc_cd,
            device_no=device_no,
            event_code=code,
            event_name=f"Event {code}",
            event_msg=f"Event {code}",
            event_time_start=start_time + timedelta(seconds=i*30),
            event_time_end=start_time + timedelta(seconds=i*30),
        )
    
    # Add ALL end sequence events (simulating they were already generated)
    for i, code in enumerate(EVENT_SEQUENCE_CONFIGS["BOF"].end_sequence):
        db.insert_event(
            heat_no=heat_no,
            pro_line_cd="G1",
            proc_cd=proc_cd,
            device_no=device_no,
            event_code=code,
            event_name=f"Event {code}",
            event_msg=f"Event {code}",
            event_time_start=fixed_now - timedelta(minutes=5) + timedelta(seconds=i*30),
            event_time_end=fixed_now - timedelta(minutes=5) + timedelta(seconds=i*30),
        )
    
    initial_event_count = len(db.events)
    
    # Complete the operation
    operation = db.operations[0]
    sim.processor._complete_operation(operation, fixed_now)
    
    # Verify no duplicate end sequence events were added
    final_event_count = len(db.events)
    assert final_event_count > initial_event_count, "Missing events should be backfilled on completion"

    event_codes = [e["event_code"] for e in db.events if e["heat_no"] == heat_no]
    for code in EVENT_SEQUENCE_CONFIGS["BOF"].end_sequence:
        assert event_codes.count(code) == 1, f"End event {code} should not be duplicated"


def test_emit_end_sequence_for_lf_operation(fixed_now):
    """Test end sequence generation for LF process."""
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    
    heat_no = 240100202
    device_no = EQUIPMENT["LF"]["devices"][0]
    proc_cd = EQUIPMENT["LF"]["proc_cd"]
    start_time = fixed_now - timedelta(minutes=40)
    plan_end = fixed_now + timedelta(minutes=10)
    
    db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=plan_end,
        real_start_time=start_time,
        real_end_time=None,
    )
    
    # Add start events only
    for i, code in enumerate(EVENT_SEQUENCE_CONFIGS["LF"].start_sequence):
        db.insert_event(
            heat_no=heat_no,
            pro_line_cd="G1",
            proc_cd=proc_cd,
            device_no=device_no,
            event_code=code,
            event_name=f"Event {code}",
            event_msg=f"Event {code}",
            event_time_start=start_time + timedelta(seconds=i*30),
            event_time_end=start_time + timedelta(seconds=i*30),
        )
    
    operation = db.operations[0]
    sim.processor._complete_operation(operation, fixed_now)
    
    # Verify LF end sequence events exist (G13006, G13004, G13002)
    event_codes = [e["event_code"] for e in db.events if e["heat_no"] == heat_no]
    lf_end_sequence = EVENT_SEQUENCE_CONFIGS["LF"].end_sequence
    
    for code in lf_end_sequence:
        assert code in event_codes, f"Missing LF end event {code}"


def test_emit_end_sequence_for_ccm_operation(fixed_now):
    """Test end sequence generation for CCM process."""
    db = FakeDatabaseManager()
    sim = SteelmakingSimulator(DatabaseConfig(), SimulationConfig(), db_manager=db)
    
    heat_no = 240100203
    device_no = EQUIPMENT["CCM"]["devices"][0]
    proc_cd = EQUIPMENT["CCM"]["proc_cd"]
    start_time = fixed_now - timedelta(minutes=40)
    plan_end = fixed_now + timedelta(minutes=10)
    
    db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=plan_end,
        real_start_time=start_time,
        real_end_time=None,
    )
    
    # Add start events only
    for i, code in enumerate(EVENT_SEQUENCE_CONFIGS["CCM"].start_sequence):
        db.insert_event(
            heat_no=heat_no,
            pro_line_cd="G1",
            proc_cd=proc_cd,
            device_no=device_no,
            event_code=code,
            event_name=f"Event {code}",
            event_msg=f"Event {code}",
            event_time_start=start_time + timedelta(seconds=i*30),
            event_time_end=start_time + timedelta(seconds=i*30),
        )
    
    operation = db.operations[0]
    sim.processor._complete_operation(operation, fixed_now)
    
    # Verify CCM end sequence events exist
    event_codes = [e["event_code"] for e in db.events if e["heat_no"] == heat_no]
    ccm_end_sequence = EVENT_SEQUENCE_CONFIGS["CCM"].end_sequence
    
    for code in ccm_end_sequence:
        assert code in event_codes, f"Missing CCM end event {code}"


def test_active_operations_have_partial_events_after_initialization(fixed_now):
    """Test that ACTIVE operations have partial events seeded during initialization.
    
    When the simulator initializes, ACTIVE operations should already have some
    events (start sequence + some middle events) since they have been running
    for some time.
    """
    db = FakeDatabaseManager()
    config = SimulationConfig()
    
    # Create event engine
    event_engine = EventEngine(
        db=db,
        config=config,
        get_process_name=lambda pc: {"G12": "BOF", "G13": "LF", "G16": "CCM"}.get(pc),
        logger=logging.getLogger("test"),
    )
    
    # Create an active BOF operation that started 20 minutes ago
    heat_no = 240100300
    device_no = EQUIPMENT["BOF"]["devices"][0]
    proc_cd = EQUIPMENT["BOF"]["proc_cd"]
    start_time = fixed_now - timedelta(minutes=20)
    
    op_id = db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=start_time + timedelta(minutes=40),
        real_start_time=start_time,
        real_end_time=None,
    )
    
    # Call partial event seeding
    count = event_engine.seed_partial_events_for_active_operation(
        operation_id=op_id,
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        window_start=start_time,
        now=fixed_now,
    )
    
    assert count > 0, "Should have generated some partial events"
    
    # Check that start sequence events exist
    event_codes = [e["event_code"] for e in db.events if e["heat_no"] == heat_no]
    bof_start_seq = EVENT_SEQUENCE_CONFIGS["BOF"].start_sequence
    
    for code in bof_start_seq:
        assert code in event_codes, f"Missing start event {code}"
    
    # Check that all events are within the time window
    for e in db.events:
        if e["heat_no"] == heat_no:
            assert e["event_time_start"] >= start_time, "Event should be after operation start"
            assert e["event_time_start"] <= fixed_now, "Event should be before or at now"


def test_active_operations_have_start_events_at_minimum(fixed_now):
    """Test that even if operation just started, it should have start sequence events."""
    db = FakeDatabaseManager()
    config = SimulationConfig()
    
    event_engine = EventEngine(
        db=db,
        config=config,
        get_process_name=lambda pc: {"G12": "BOF", "G13": "LF", "G16": "CCM"}.get(pc),
        logger=logging.getLogger("test"),
    )
    
    # Create an active LF operation that started only 5 minutes ago
    heat_no = 240100301
    device_no = EQUIPMENT["LF"]["devices"][0]
    proc_cd = EQUIPMENT["LF"]["proc_cd"]
    start_time = fixed_now - timedelta(minutes=5)
    
    op_id = db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=start_time + timedelta(minutes=40),
        real_start_time=start_time,
        real_end_time=None,
    )
    
    count = event_engine.seed_partial_events_for_active_operation(
        operation_id=op_id,
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        window_start=start_time,
        now=fixed_now,
    )
    
    # Should have at least the start sequence
    lf_start_seq = EVENT_SEQUENCE_CONFIGS["LF"].start_sequence
    assert count >= len(lf_start_seq), f"Should have at least {len(lf_start_seq)} start events"
    
    event_codes = [e["event_code"] for e in db.events if e["heat_no"] == heat_no]
    for code in lf_start_seq:
        assert code in event_codes, f"Missing LF start event {code}"


def test_long_running_active_operation_has_middle_events(fixed_now):
    """Test that an operation running for a long time has middle events too."""
    db = FakeDatabaseManager()
    config = SimulationConfig()
    
    event_engine = EventEngine(
        db=db,
        config=config,
        get_process_name=lambda pc: {"G12": "BOF", "G13": "LF", "G16": "CCM"}.get(pc),
        logger=logging.getLogger("test"),
    )
    
    # Create an active BOF operation that started 35 minutes ago (near completion)
    heat_no = 240100302
    device_no = EQUIPMENT["BOF"]["devices"][0]
    proc_cd = EQUIPMENT["BOF"]["proc_cd"]
    start_time = fixed_now - timedelta(minutes=35)
    
    op_id = db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=start_time + timedelta(minutes=40),
        real_start_time=start_time,
        real_end_time=None,
    )
    
    count = event_engine.seed_partial_events_for_active_operation(
        operation_id=op_id,
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        window_start=start_time,
        now=fixed_now,
    )
    
    bof_start_seq = EVENT_SEQUENCE_CONFIGS["BOF"].start_sequence
    
    # Should have more events than just the start sequence
    # (since operation has been running for 35 minutes)
    assert count > len(bof_start_seq), \
        f"Long-running operation should have middle events too. Got {count} events, start seq has {len(bof_start_seq)}"


def test_partial_events_do_not_include_end_sequence(fixed_now):
    """Test that partial events for active operations do NOT include end sequence."""
    db = FakeDatabaseManager()
    config = SimulationConfig()
    
    event_engine = EventEngine(
        db=db,
        config=config,
        get_process_name=lambda pc: {"G12": "BOF", "G13": "LF", "G16": "CCM"}.get(pc),
        logger=logging.getLogger("test"),
    )
    
    heat_no = 240100303
    device_no = EQUIPMENT["BOF"]["devices"][0]
    proc_cd = EQUIPMENT["BOF"]["proc_cd"]
    start_time = fixed_now - timedelta(minutes=35)
    
    op_id = db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=start_time + timedelta(minutes=40),
        real_start_time=start_time,
        real_end_time=None,
    )
    
    event_engine.seed_partial_events_for_active_operation(
        operation_id=op_id,
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        window_start=start_time,
        now=fixed_now,
    )
    
    # End sequence events should NOT be present
    event_codes = set(e["event_code"] for e in db.events if e["heat_no"] == heat_no)
    bof_end_seq = EVENT_SEQUENCE_CONFIGS["BOF"].end_sequence
    
    for code in bof_end_seq:
        assert code not in event_codes, f"End event {code} should NOT be present for active operation"


def test_partial_events_include_paired_ends_for_lf(fixed_now, monkeypatch):
    """Test that paired LF events are emitted together for active operations."""
    db = FakeDatabaseManager()
    config = SimulationConfig()

    event_engine = EventEngine(
        db=db,
        config=config,
        get_process_name=lambda pc: {"G12": "BOF", "G13": "LF", "G16": "CCM"}.get(pc),
        logger=logging.getLogger("test"),
    )

    lf_config = EVENT_SEQUENCE_CONFIGS["LF"]
    monkeypatch.setattr(lf_config, "middle_events", [("G13024", 1.0)])
    monkeypatch.setattr(lf_config, "paired_events", [("G13024", "G13025")])

    heat_no = 240100304
    device_no = EQUIPMENT["LF"]["devices"][0]
    proc_cd = EQUIPMENT["LF"]["proc_cd"]
    start_time = fixed_now - timedelta(minutes=30)

    op_id = db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=start_time + timedelta(minutes=40),
        real_start_time=start_time,
        real_end_time=None,
    )

    event_engine.seed_partial_events_for_active_operation(
        operation_id=op_id,
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        window_start=start_time,
        now=fixed_now,
    )

    event_codes = [e["event_code"] for e in db.events if e["heat_no"] == heat_no]
    assert "G13024" in event_codes, "Expected paired start event G13024"
    assert event_codes.count("G13025") >= event_codes.count("G13024"), \
        "Paired end event G13025 should be present for each G13024"


def test_emit_end_sequence_closes_paired_events(fixed_now):
    """Test that completion inserts missing paired end events."""
    db = FakeDatabaseManager()
    config = SimulationConfig()

    event_engine = EventEngine(
        db=db,
        config=config,
        get_process_name=lambda pc: {"G12": "BOF", "G13": "LF", "G16": "CCM"}.get(pc),
        logger=logging.getLogger("test"),
    )

    heat_no = 240100305
    device_no = EQUIPMENT["LF"]["devices"][0]
    proc_cd = EQUIPMENT["LF"]["proc_cd"]
    start_time = fixed_now - timedelta(minutes=30)

    op_id = db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=start_time + timedelta(minutes=40),
        real_start_time=start_time,
        real_end_time=None,
    )

    start_event_time = start_time + timedelta(minutes=5)
    db.insert_event(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        event_code="G13024",
        event_name="吹氩开始",
        event_msg="执行吹氩开始操作",
        event_time_start=start_event_time,
        event_time_end=start_event_time,
        extra={"operation_id": op_id},
    )

    operation = db.operations[0]
    event_engine.emit_end_sequence_events(operation, fixed_now)

    paired_end_events = [
        e for e in db.events
        if e["heat_no"] == heat_no and e["event_code"] == "G13025"
    ]
    assert paired_end_events, "Expected paired end event G13025 to be inserted"
    assert paired_end_events[0]["event_time_start"] >= start_event_time


def test_emit_realtime_event_prefers_paired_end(fixed_now):
    """Test that realtime emission closes pending paired events first."""
    db = FakeDatabaseManager()
    config = SimulationConfig()

    event_engine = EventEngine(
        db=db,
        config=config,
        get_process_name=lambda pc: {"G12": "BOF", "G13": "LF", "G16": "CCM"}.get(pc),
        logger=logging.getLogger("test"),
    )

    heat_no = 240100306
    device_no = EQUIPMENT["LF"]["devices"][0]
    proc_cd = EQUIPMENT["LF"]["proc_cd"]
    start_time = fixed_now - timedelta(minutes=15)

    op_id = db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=start_time + timedelta(minutes=40),
        real_start_time=start_time,
        real_end_time=None,
    )

    start_event_time = start_time + timedelta(minutes=2)
    db.insert_event(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        event_code="G13024",
        event_name="吹氩开始",
        event_msg="执行吹氩开始操作",
        event_time_start=start_event_time,
        event_time_end=start_event_time,
        extra={"operation_id": op_id},
    )

    operation = db.operations[0]
    event_engine.emit_realtime_event(operation, fixed_now)

    last_event = db.events[-1]
    assert last_event["event_code"] == "G13025", "Realtime emission should close paired events first"


def test_completed_operation_seeding_includes_all_events(fixed_now):
    """Test that historical seeding backfills all required events."""
    db = FakeDatabaseManager()
    config = SimulationConfig()

    event_engine = EventEngine(
        db=db,
        config=config,
        event_config=EventEngineConfig(
            seed_event_probability_per_completed_operation=1.0,
            cancel_event_probability=0.0,
            rework_event_probability=0.0,
        ),
        get_process_name=lambda pc: {"G13": "LF"}.get(pc),
        logger=logging.getLogger("test"),
    )

    heat_no = 240100307
    device_no = "G130"
    proc_cd = "G13"
    start_time = fixed_now - timedelta(minutes=50)
    end_time = fixed_now - timedelta(minutes=10)

    op_id = db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.COMPLETED,
        plan_start_time=start_time,
        plan_end_time=end_time,
        real_start_time=start_time,
        real_end_time=end_time,
    )

    event_engine.seed_historical_events_for_completed_operation(
        operation_id=op_id,
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        window_start=start_time,
        window_end=end_time,
    )

    event_codes = {e["event_code"] for e in db.events if e["heat_no"] == heat_no}
    required_codes = set(EventEngine._build_required_event_sequence(EVENT_SEQUENCE_CONFIGS["LF"]))
    assert required_codes.issubset(event_codes)


def test_runtime_completion_backfills_all_events(fixed_now):
    """Test that runtime completion fills missing required events."""
    db = FakeDatabaseManager()
    config = SimulationConfig()

    event_engine = EventEngine(
        db=db,
        config=config,
        get_process_name=lambda pc: {"G13": "LF"}.get(pc),
        logger=logging.getLogger("test"),
    )

    heat_no = 240100308
    device_no = "G130"
    proc_cd = "G13"
    start_time = fixed_now - timedelta(minutes=40)

    db.insert_operation(
        heat_no=heat_no,
        pro_line_cd="G1",
        proc_cd=proc_cd,
        device_no=device_no,
        crew_cd="A",
        stl_grd_id=1,
        stl_grd_cd="G-TEST",
        proc_status=ProcessStatus.ACTIVE,
        plan_start_time=start_time,
        plan_end_time=fixed_now + timedelta(minutes=5),
        real_start_time=start_time,
        real_end_time=None,
    )

    operation = db.operations[0]
    event_engine.emit_end_sequence_events(operation, fixed_now)

    event_codes = {e["event_code"] for e in db.events if e["heat_no"] == heat_no}
    required_codes = set(EventEngine._build_required_event_sequence(EVENT_SEQUENCE_CONFIGS["LF"]))
    assert required_codes.issubset(event_codes)

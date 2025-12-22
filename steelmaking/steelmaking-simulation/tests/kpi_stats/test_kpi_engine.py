"""Unit tests for the KPI stats engine module."""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import pytest

from steelmaking_simulation.kpi_stats import KpiStatsEngine, KpiStatsEngineConfig
from steelmaking_simulation.config import SimulationConfig, ProcessStatus, EQUIPMENT
from steelmaking_simulation.utils import CST


# Sample KPI definitions for testing
SAMPLE_KPI_DEFINITIONS = {
    "G12": [
        {
            "kpi_code": "BOF_PROC_T_PV",
            "kpi_name": "温度当前值",
            "unit": "℃",
            "int_digits": 4,
            "decimal_digits": 0,
            "upper_limit": Decimal("1800"),
            "lower_limit": Decimal("1200"),
        },
        {
            "kpi_code": "BOF_PROC_O2_RATE_PV",
            "kpi_name": "吹氧流量当前值",
            "unit": "Nm3/min",
            "int_digits": 5,
            "decimal_digits": 0,
            "upper_limit": Decimal("10000"),
            "lower_limit": Decimal("0"),
        },
        {
            "kpi_code": "BOF_PROC_O2_TOTAL",
            "kpi_name": "累计吹氧量",
            "unit": "Nm3",
            "int_digits": 6,
            "decimal_digits": 0,
            "upper_limit": Decimal("200000"),
            "lower_limit": Decimal("0"),
        },
    ],
    "G13": [
        {
            "kpi_code": "LF_PROC_T_PV",
            "kpi_name": "温度当前值",
            "unit": "℃",
            "int_digits": 4,
            "decimal_digits": 0,
            "upper_limit": Decimal("1800"),
            "lower_limit": Decimal("1200"),
        },
        {
            "kpi_code": "LF_ENER_POWER_PV",
            "kpi_name": "功率当前值",
            "unit": "MW",
            "int_digits": 2,
            "decimal_digits": 2,
            "upper_limit": Decimal("80"),
            "lower_limit": Decimal("0"),
        },
    ],
}


class TestKpiStatsEngine:
    """Tests for KpiStatsEngine."""

    @pytest.fixture
    def fake_db(self):
        """Create a fake database for testing."""
        from tests.conftest import FakeDatabaseManager
        db = FakeDatabaseManager()
        # Set up KPI definitions
        for proc_cd, definitions in SAMPLE_KPI_DEFINITIONS.items():
            db.set_kpi_definitions(proc_cd, definitions)
        return db

    @pytest.fixture
    def sim_config(self):
        return SimulationConfig(
            interval=2,
            min_operation_duration=30,
            max_operation_duration=50,
        )

    @pytest.fixture
    def kpi_config(self):
        return KpiStatsEngineConfig(
            seed_kpi_stats_probability=1.0,  # Always seed for testing
            min_samples_per_operation=3,
            max_samples_per_operation=5,
            kpi_probability_per_tick=1.0,  # Always emit for testing
            min_sample_interval_seconds=0,  # No minimum interval for testing
            max_realtime_samples_per_operation=10,
        )

    @pytest.fixture
    def engine(self, fake_db, sim_config, kpi_config):
        def get_process_name(proc_cd):
            for name, info in EQUIPMENT.items():
                if info["proc_cd"] == proc_cd:
                    return name
            return None
        
        return KpiStatsEngine(
            db=fake_db,
            config=sim_config,
            kpi_config=kpi_config,
            get_process_name=get_process_name,
            logger=logging.getLogger(__name__),
        )

    def test_load_kpi_definitions(self, engine, fake_db):
        """Test loading KPI definitions from database."""
        engine.load_kpi_definitions()
        
        assert "G12" in engine._kpi_definitions_cache
        assert "G13" in engine._kpi_definitions_cache
        assert len(engine._kpi_definitions_cache["G12"]) == 3
        assert len(engine._kpi_definitions_cache["G13"]) == 2

    def test_get_kpi_definitions(self, engine):
        """Test getting KPI definitions for a process code."""
        definitions = engine.get_kpi_definitions("G12")
        
        assert len(definitions) == 3
        assert definitions[0]["kpi_code"] == "BOF_PROC_T_PV"

    def test_get_kpi_definitions_caches(self, engine):
        """Test that get_kpi_definitions caches results."""
        # First call - should fetch from DB
        definitions1 = engine.get_kpi_definitions("G12")
        
        # Second call - should use cache
        definitions2 = engine.get_kpi_definitions("G12")
        
        assert definitions1 == definitions2
        assert "G12" in engine._kpi_definitions_cache

    def test_seed_historical_kpi_stats_for_completed_operation(self, engine, fake_db):
        """Test seeding historical KPI stats for a completed operation."""
        now = datetime.now(CST)
        window_start = now - timedelta(minutes=40)
        window_end = now - timedelta(minutes=10)
        
        count = engine.seed_historical_kpi_stats_for_completed_operation(
            operation_id=1,
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            window_start=window_start,
            window_end=window_end,
        )
        
        # Should have inserted stats (num_samples * num_kpis)
        assert count > 0
        assert len(fake_db.kpi_stats) == count
        
        # Verify the stats
        for stat in fake_db.kpi_stats:
            assert stat["heat_no"] == 2412000001
            assert stat["pro_line_cd"] == "G1"
            assert stat["proc_cd"] == "G12"
            assert stat["device_no"] == "G120"
            assert window_start <= stat["sample_time"] <= window_end

    def test_seed_historical_kpi_stats_invalid_window(self, engine, fake_db):
        """Test that invalid window returns 0."""
        now = datetime.now(CST)
        
        # End before start
        count = engine.seed_historical_kpi_stats_for_completed_operation(
            operation_id=1,
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            window_start=now,
            window_end=now - timedelta(minutes=10),
        )
        
        assert count == 0
        assert len(fake_db.kpi_stats) == 0

    def test_seed_historical_kpi_stats_unknown_proc_cd(self, engine, fake_db):
        """Test that unknown proc_cd returns 0."""
        now = datetime.now(CST)
        
        count = engine.seed_historical_kpi_stats_for_completed_operation(
            operation_id=1,
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G99",  # Unknown
            device_no="G990",
            window_start=now - timedelta(minutes=40),
            window_end=now - timedelta(minutes=10),
        )
        
        assert count == 0

    def test_seed_partial_kpi_stats_for_active_operation(self, engine, fake_db):
        """Test seeding partial KPI stats for an active operation."""
        now = datetime.now(CST)
        window_start = now - timedelta(minutes=20)
        
        count = engine.seed_partial_kpi_stats_for_active_operation(
            operation_id=1,
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            window_start=window_start,
            now=now,
        )
        
        assert count > 0
        
        # Check operation state was initialized
        assert 1 in engine._operation_states
        state = engine._operation_states[1]
        assert state.heat_no == 2412000001
        assert state.proc_cd == "G12"
        assert state.sample_count > 0

    def test_tick_realtime_kpi_stats(self, engine, fake_db):
        """Test real-time KPI stats generation during tick."""
        now = datetime.now(CST)
        start_time = now - timedelta(minutes=15)
        
        # Add an active operation
        fake_db.insert_operation(
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            crew_cd="A",
            stl_grd_id=1,
            stl_grd_cd="G-TEST",
            proc_status=ProcessStatus.ACTIVE,
            plan_start_time=start_time,
            plan_end_time=start_time + timedelta(minutes=40),
            real_start_time=start_time,
        )
        
        # Run tick
        engine.tick_realtime_kpi_stats(now)
        
        # Should have generated stats
        assert len(fake_db.kpi_stats) > 0
        
        for stat in fake_db.kpi_stats:
            assert stat["heat_no"] == 2412000001
            assert stat["proc_cd"] == "G12"
            assert stat["sample_time"] == now

    def test_tick_respects_max_samples(self, engine, fake_db):
        """Test that tick respects max_realtime_samples_per_operation."""
        now = datetime.now(CST)
        start_time = now - timedelta(minutes=15)
        
        # Add an active operation
        op_id = fake_db.insert_operation(
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            crew_cd="A",
            stl_grd_id=1,
            stl_grd_cd="G-TEST",
            proc_status=ProcessStatus.ACTIVE,
            plan_start_time=start_time,
            plan_end_time=start_time + timedelta(minutes=40),
            real_start_time=start_time,
        )
        
        # Override max samples to a small number
        engine.kpi_config.max_realtime_samples_per_operation = 2
        
        # Run multiple ticks
        for i in range(5):
            engine.tick_realtime_kpi_stats(now + timedelta(seconds=i * 60))
        
        # Should have stopped at max samples
        state = engine._operation_states.get(op_id)
        assert state is not None
        assert state.sample_count <= 2

    def test_cleanup_completed_operation(self, engine, fake_db):
        """Test cleaning up state for completed operation."""
        now = datetime.now(CST)
        
        # Seed partial stats to create state
        engine.seed_partial_kpi_stats_for_active_operation(
            operation_id=1,
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            window_start=now - timedelta(minutes=20),
            now=now,
        )
        
        assert 1 in engine._operation_states
        
        # Clean up
        engine.cleanup_completed_operation(1)
        
        assert 1 not in engine._operation_states

    def test_generate_sample_times(self, engine):
        """Test sample time generation."""
        now = datetime.now(CST)
        start = now - timedelta(minutes=30)
        end = now
        
        times = engine._generate_sample_times(start, end, 5)
        
        assert len(times) == 5
        # Should be sorted
        assert times == sorted(times)
        # All within range
        for t in times:
            assert start <= t <= end

    def test_generate_sample_times_single(self, engine):
        """Test sample time generation with single sample."""
        now = datetime.now(CST)
        start = now - timedelta(minutes=30)
        end = now
        
        times = engine._generate_sample_times(start, end, 1)
        
        assert len(times) == 1
        assert start <= times[0] <= end

    def test_generate_sample_times_zero(self, engine):
        """Test sample time generation with zero samples."""
        now = datetime.now(CST)
        
        times = engine._generate_sample_times(now - timedelta(minutes=30), now, 0)
        
        assert times == []


class TestKpiStatsEngineConfig:
    """Tests for KpiStatsEngineConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = KpiStatsEngineConfig()
        
        assert config.seed_kpi_stats_probability == 0.95
        assert config.min_samples_per_operation == 5
        assert config.max_samples_per_operation == 15
        assert config.kpi_probability_per_tick == 0.4
        assert config.min_sample_interval_seconds == 30
        assert config.max_realtime_samples_per_operation == 50
        assert config.out_of_range_probability == 0.05
        assert config.out_of_range_factor == 0.15

    def test_custom_values(self):
        """Test custom configuration values."""
        config = KpiStatsEngineConfig(
            seed_kpi_stats_probability=0.8,
            min_samples_per_operation=3,
            max_samples_per_operation=10,
        )
        
        assert config.seed_kpi_stats_probability == 0.8
        assert config.min_samples_per_operation == 3
        assert config.max_samples_per_operation == 10


class TestKpiStatsIntegration:
    """Integration tests for KPI stats generation."""

    @pytest.fixture
    def fake_db(self):
        """Create a fake database for testing."""
        from tests.conftest import FakeDatabaseManager
        db = FakeDatabaseManager()
        for proc_cd, definitions in SAMPLE_KPI_DEFINITIONS.items():
            db.set_kpi_definitions(proc_cd, definitions)
        return db

    @pytest.fixture
    def sim_config(self):
        return SimulationConfig(interval=2)

    @pytest.fixture
    def engine(self, fake_db, sim_config):
        def get_process_name(proc_cd):
            for name, info in EQUIPMENT.items():
                if info["proc_cd"] == proc_cd:
                    return name
            return None
        
        return KpiStatsEngine(
            db=fake_db,
            config=sim_config,
            get_process_name=get_process_name,
            logger=logging.getLogger(__name__),
        )

    def test_full_operation_lifecycle(self, engine, fake_db):
        """Test KPI stats generation through full operation lifecycle."""
        now = datetime.now(CST)
        
        # 1. Seed partial stats for active operation
        start_time = now - timedelta(minutes=20)
        
        count1 = engine.seed_partial_kpi_stats_for_active_operation(
            operation_id=1,
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            window_start=start_time,
            now=now,
        )
        
        assert count1 > 0
        initial_count = len(fake_db.kpi_stats)
        
        # 2. Add active operation to DB
        fake_db.insert_operation(
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            crew_cd="A",
            stl_grd_id=1,
            stl_grd_cd="G-TEST",
            proc_status=ProcessStatus.ACTIVE,
            plan_start_time=start_time,
            plan_end_time=start_time + timedelta(minutes=40),
            real_start_time=start_time,
        )
        
        # 3. Simulate a few ticks
        tick_time = now + timedelta(seconds=60)
        engine.tick_realtime_kpi_stats(tick_time)
        
        assert len(fake_db.kpi_stats) > initial_count
        
        # 4. Clean up on completion
        engine.cleanup_completed_operation(1)
        
        assert 1 not in engine._operation_states

    def test_multiple_processes(self, engine, fake_db):
        """Test KPI stats for multiple process types."""
        now = datetime.now(CST)
        start_time = now - timedelta(minutes=30)
        end_time = now - timedelta(minutes=5)
        
        # Seed for BOF (G12)
        count_bof = engine.seed_historical_kpi_stats_for_completed_operation(
            operation_id=1,
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            window_start=start_time,
            window_end=end_time,
        )
        
        # Seed for LF (G13)
        count_lf = engine.seed_historical_kpi_stats_for_completed_operation(
            operation_id=2,
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G13",
            device_no="G130",
            window_start=end_time,
            window_end=now,
        )
        
        assert count_bof > 0
        assert count_lf > 0
        
        # Verify different KPI codes for each process
        bof_codes = {s["kpi_code"] for s in fake_db.kpi_stats if s["proc_cd"] == "G12"}
        lf_codes = {s["kpi_code"] for s in fake_db.kpi_stats if s["proc_cd"] == "G13"}
        
        assert "BOF_PROC_T_PV" in bof_codes
        assert "LF_PROC_T_PV" in lf_codes
        assert bof_codes != lf_codes

"""Unit tests for the KPI value generator module."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from steelmaking_simulation.kpi_stats import KpiValueGenerator, KpiStat
from steelmaking_simulation.utils import CST


class TestKpiValueGenerator:
    """Tests for KpiValueGenerator."""

    @pytest.fixture
    def generator(self):
        return KpiValueGenerator(
            out_of_range_probability=0.05,
            out_of_range_factor=0.15,
        )

    def test_generate_value_with_limits(self, generator):
        """Test basic value generation with upper and lower limits."""
        kpi_def = {
            "kpi_code": "TEST_KPI",
            "int_digits": 4,
            "decimal_digits": 2,
            "upper_limit": Decimal("1800"),
            "lower_limit": Decimal("1200"),
        }
        
        for _ in range(100):
            value = generator.generate_value(kpi_def, progress=0.5)
            assert value is not None
            # Most values should be within range (allowing for occasional out-of-range)
            # We don't assert strictly within range due to out_of_range_probability
            assert isinstance(value, Decimal)

    def test_generate_value_respects_decimal_digits(self, generator):
        """Test that generated values respect decimal_digits setting."""
        kpi_def = {
            "kpi_code": "TEST_KPI",
            "int_digits": 4,
            "decimal_digits": 0,
            "upper_limit": Decimal("100"),
            "lower_limit": Decimal("0"),
        }
        
        for _ in range(20):
            value = generator.generate_value(kpi_def, progress=0.5)
            assert value is not None
            # Value should be a whole number (0 decimal places)
            assert value == value.to_integral_value()

    def test_generate_value_with_decimal_places(self, generator):
        """Test value generation with multiple decimal places."""
        kpi_def = {
            "kpi_code": "TEST_PCT",
            "int_digits": 1,
            "decimal_digits": 4,
            "upper_limit": Decimal("0.2"),
            "lower_limit": Decimal("0"),
        }
        
        for _ in range(20):
            value = generator.generate_value(kpi_def, progress=0.5)
            assert value is not None
            # Check that value has at most 4 decimal places
            str_val = str(value)
            if "." in str_val:
                decimal_part = str_val.split(".")[1]
                assert len(decimal_part) <= 4

    def test_generate_value_none_limits(self, generator):
        """Test that None is returned when both limits are None."""
        kpi_def = {
            "kpi_code": "TEST_KPI",
            "int_digits": 4,
            "decimal_digits": 2,
            "upper_limit": None,
            "lower_limit": None,
        }
        
        value = generator.generate_value(kpi_def, progress=0.5)
        assert value is None

    def test_generate_value_temperature_kpi(self, generator):
        """Test temperature KPI value generation patterns."""
        kpi_def = {
            "kpi_code": "BOF_PROC_T_PV",
            "int_digits": 4,
            "decimal_digits": 0,
            "upper_limit": Decimal("1800"),
            "lower_limit": Decimal("1200"),
        }
        
        values = []
        for _ in range(50):
            value = generator.generate_value(kpi_def, progress=0.5)
            assert value is not None
            values.append(float(value))
        
        # Temperature values should be mostly within working range
        avg = sum(values) / len(values)
        assert 1200 <= avg <= 1800

    def test_generate_value_cumulative_kpi(self, generator):
        """Test cumulative KPI increases with progress."""
        kpi_def = {
            "kpi_code": "BOF_PROC_O2_TOTAL",
            "int_digits": 6,
            "decimal_digits": 0,
            "upper_limit": Decimal("200000"),
            "lower_limit": Decimal("0"),
        }
        
        # Generate values at different progress levels
        values_early = [float(generator.generate_value(kpi_def, progress=0.1)) for _ in range(20)]
        values_late = [float(generator.generate_value(kpi_def, progress=0.9)) for _ in range(20)]
        
        # Average of late values should generally be higher
        avg_early = sum(values_early) / len(values_early)
        avg_late = sum(values_late) / len(values_late)
        assert avg_late > avg_early

    def test_generate_value_deviation_kpi(self, generator):
        """Test deviation KPI values are centered around 0."""
        kpi_def = {
            "kpi_code": "BOF_PROC_T_DEV",
            "int_digits": 3,
            "decimal_digits": 0,
            "upper_limit": Decimal("200"),
            "lower_limit": Decimal("-200"),
        }
        
        values = [float(generator.generate_value(kpi_def, progress=0.5)) for _ in range(100)]
        avg = sum(values) / len(values)
        
        # Deviation values should be centered near 0
        assert -50 < avg < 50

    def test_generate_value_with_previous_value(self, generator):
        """Test that previous_value influences generated value."""
        kpi_def = {
            "kpi_code": "BOF_PROC_T_PV",
            "int_digits": 4,
            "decimal_digits": 0,
            "upper_limit": Decimal("1800"),
            "lower_limit": Decimal("1200"),
        }
        
        previous_value = Decimal("1500")
        values = [
            float(generator.generate_value(kpi_def, progress=0.5, previous_value=previous_value))
            for _ in range(50)
        ]
        
        avg = sum(values) / len(values)
        # Values should tend towards the previous value
        assert abs(avg - 1500) < 200

    def test_generate_stats_for_operation(self, generator):
        """Test generating stats for all KPIs in an operation."""
        kpi_definitions = [
            {
                "kpi_code": "BOF_PROC_T_PV",
                "int_digits": 4,
                "decimal_digits": 0,
                "upper_limit": Decimal("1800"),
                "lower_limit": Decimal("1200"),
            },
            {
                "kpi_code": "BOF_PROC_O2_RATE_PV",
                "int_digits": 5,
                "decimal_digits": 0,
                "upper_limit": Decimal("10000"),
                "lower_limit": Decimal("0"),
            },
        ]
        
        sample_time = datetime.now(CST)
        
        stats = generator.generate_stats_for_operation(
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            kpi_definitions=kpi_definitions,
            sample_time=sample_time,
            progress=0.5,
        )
        
        assert len(stats) == 2
        
        for stat in stats:
            assert isinstance(stat, KpiStat)
            assert stat.heat_no == 2412000001
            assert stat.pro_line_cd == "G1"
            assert stat.proc_cd == "G12"
            assert stat.device_no == "G120"
            assert stat.sample_time == sample_time
            assert stat.stat_value is not None

    def test_kpi_stat_to_dict(self):
        """Test KpiStat.to_dict() method."""
        sample_time = datetime.now(CST)
        stat = KpiStat(
            heat_no=2412000001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            kpi_code="BOF_PROC_T_PV",
            stat_value=Decimal("1550"),
            sample_time=sample_time,
            extra={"operation_id": 1},
        )
        
        d = stat.to_dict()
        
        assert d["heat_no"] == 2412000001
        assert d["pro_line_cd"] == "G1"
        assert d["proc_cd"] == "G12"
        assert d["device_no"] == "G120"
        assert d["kpi_code"] == "BOF_PROC_T_PV"
        assert d["stat_value"] == Decimal("1550")
        assert d["sample_time"] == sample_time
        assert d["extra"] == {"operation_id": 1}


class TestKpiValueGeneratorOutOfRange:
    """Tests for out-of-range value generation."""

    def test_out_of_range_values_generated(self):
        """Test that out-of-range values are occasionally generated."""
        # High probability to ensure we see out-of-range values
        generator = KpiValueGenerator(
            out_of_range_probability=0.5,  # 50% chance
            out_of_range_factor=0.2,
        )
        
        kpi_def = {
            "kpi_code": "TEST_KPI",
            "int_digits": 4,
            "decimal_digits": 2,
            "upper_limit": Decimal("100"),
            "lower_limit": Decimal("0"),
        }
        
        out_of_range_count = 0
        total = 100
        
        for _ in range(total):
            value = generator.generate_value(kpi_def, progress=0.5)
            if value is not None and (value < 0 or value > 100):
                out_of_range_count += 1
        
        # Should have some out-of-range values
        assert out_of_range_count > 0

    def test_zero_out_of_range_probability(self):
        """Test that no out-of-range values with 0 probability."""
        generator = KpiValueGenerator(
            out_of_range_probability=0.0,  # Never
            out_of_range_factor=0.2,
        )
        
        kpi_def = {
            "kpi_code": "TEST_KPI",
            "int_digits": 4,
            "decimal_digits": 2,
            "upper_limit": Decimal("100"),
            "lower_limit": Decimal("0"),
        }
        
        for _ in range(100):
            value = generator.generate_value(kpi_def, progress=0.5)
            if value is not None:
                assert 0 <= value <= 100


class TestKpiValueGeneratorEdgeCases:
    """Edge case tests for KpiValueGenerator."""

    @pytest.fixture
    def generator(self):
        return KpiValueGenerator()

    def test_narrow_range(self, generator):
        """Test value generation with very narrow range."""
        kpi_def = {
            "kpi_code": "TEST_KPI",
            "int_digits": 1,
            "decimal_digits": 2,
            "upper_limit": Decimal("1.01"),
            "lower_limit": Decimal("1.00"),
        }
        
        for _ in range(20):
            value = generator.generate_value(kpi_def, progress=0.5)
            assert value is not None

    def test_only_upper_limit(self, generator):
        """Test value generation with only upper limit."""
        kpi_def = {
            "kpi_code": "TEST_KPI",
            "int_digits": 4,
            "decimal_digits": 0,
            "upper_limit": Decimal("1000"),
            "lower_limit": None,
        }
        
        for _ in range(20):
            value = generator.generate_value(kpi_def, progress=0.5)
            assert value is not None

    def test_only_lower_limit(self, generator):
        """Test value generation with only lower limit."""
        kpi_def = {
            "kpi_code": "TEST_KPI",
            "int_digits": 4,
            "decimal_digits": 0,
            "upper_limit": None,
            "lower_limit": Decimal("0"),
        }
        
        for _ in range(20):
            value = generator.generate_value(kpi_def, progress=0.5)
            assert value is not None

    def test_progress_boundaries(self, generator):
        """Test value generation at progress boundaries."""
        kpi_def = {
            "kpi_code": "BOF_PROC_O2_TOTAL",
            "int_digits": 6,
            "decimal_digits": 0,
            "upper_limit": Decimal("200000"),
            "lower_limit": Decimal("0"),
        }
        
        # Progress = 0
        value_start = generator.generate_value(kpi_def, progress=0.0)
        assert value_start is not None
        
        # Progress = 1
        value_end = generator.generate_value(kpi_def, progress=1.0)
        assert value_end is not None

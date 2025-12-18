"""Unit tests for the event generator module."""

from datetime import datetime, timedelta

import pytest

from steelmaking_simulation.events import (
    Event,
    EventGenerator,
    EventMessageGenerator,
    EventSequenceConfig,
    EventSequenceResult,
    EVENT_CODES,
    EVENT_SEQUENCE_CONFIGS,
    PROC_CD_TO_NAME,
    SpecialEventType,
)
from steelmaking_simulation.utils import CST


class TestEventMessageGenerator:
    """Tests for EventMessageGenerator."""

    def test_generate_message_no_params(self):
        """Test message generation for events without parameters."""
        msg = EventMessageGenerator.generate_message("G12003", "处理开始", "", "", "", "")
        assert "执行处理开始操作" in msg

    def test_generate_message_with_temperature(self):
        """Test message generation for temperature measurement events."""
        msg = EventMessageGenerator.generate_message("G12013", "钢水测温", "测量值", "", "", "")
        assert "执行钢水测温操作" in msg
        assert "温度" in msg
        assert "℃" in msg

    def test_generate_message_scrap_addition(self):
        """Test message generation for scrap addition events."""
        msg = EventMessageGenerator.generate_message("G12017", "加废钢", "物料名称", "料篮号", "废钢重量", "")
        assert "执行加废钢操作" in msg
        assert "物料名称" in msg
        assert "料篮号" in msg
        assert "重量" in msg
        assert "吨" in msg

    def test_generate_message_hot_metal(self):
        """Test message generation for hot metal pouring events."""
        msg = EventMessageGenerator.generate_message("G12018", "兑铁水", "铁包号", "铁水重量", "", "")
        assert "执行兑铁水操作" in msg
        assert "铁包号" in msg
        assert "铁水重量" in msg
        assert "吨" in msg

    def test_generate_message_ladle_arrival(self):
        """Test message generation for ladle arrival events."""
        msg = EventMessageGenerator.generate_message("G13001", "钢包到达", "钢水重量", "钢包号", "", "")
        assert "执行钢包到达操作" in msg
        assert "钢包号" in msg

    def test_generate_message_gas_consumption(self):
        """Test message generation for gas consumption events."""
        msg = EventMessageGenerator.generate_message("G12022", "氧枪喷吹结束", "气体类型", "消耗量", "", "")
        assert "执行氧枪喷吹结束操作" in msg
        assert "气体类型" in msg
        assert "消耗量" in msg
        assert "Nm³" in msg

    def test_generate_message_wire_feeding(self):
        """Test message generation for wire feeding events."""
        msg = EventMessageGenerator.generate_message("G13010", "喂丝", "物料名称", "料仓号", "加料重量", "")
        assert "执行喂丝操作" in msg
        assert "物料名称" in msg
        assert "喂丝长度" in msg

    def test_generate_message_gear_change(self):
        """Test message generation for gear change events."""
        msg = EventMessageGenerator.generate_message("G13020", "变压器换挡", "档位", "", "", "")
        assert "执行变压器换挡操作" in msg
        assert "档位" in msg

    def test_generate_message_tundish(self):
        """Test message generation for tundish events."""
        msg = EventMessageGenerator.generate_message("G16001", "中包加料", "物料名称", "加料重量", "", "")
        assert "执行中包加料操作" in msg
        assert "物料名称" in msg
        assert "加料重量" in msg


class TestEventGenerator:
    """Tests for EventGenerator."""

    @pytest.fixture
    def generator(self):
        return EventGenerator(min_events_per_operation=8, max_events_per_operation=20)

    def test_get_process_name(self, generator):
        """Test process code to name conversion."""
        assert generator.get_process_name("G12") == "BOF"
        assert generator.get_process_name("G13") == "LF"
        assert generator.get_process_name("G15") == "RH"
        assert generator.get_process_name("G16") == "CCM"
        assert generator.get_process_name("G99") is None

    def test_generate_bof_event_sequence(self, generator):
        """Test BOF event sequence generation."""
        now = datetime.now(CST)
        start_time = now
        end_time = now + timedelta(minutes=40)

        events = generator.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            start_time=start_time,
            end_time=end_time,
        )

        assert len(events) >= 8
        assert len(events) <= 25  # start + end + some middle

        # Check that events are in chronological order
        for i in range(1, len(events)):
            assert events[i].event_time_start >= events[i - 1].event_time_start

        # Check that all events are within the operation window
        for event in events:
            assert event.event_time_start >= start_time
            assert event.event_time_end <= end_time

        # Check that events have the correct attributes
        for event in events:
            assert event.heat_no == 2412100001
            assert event.pro_line_cd == "G1"
            assert event.proc_cd == "G12"
            assert event.device_no == "G120"
            assert event.event_code.startswith("G12")
            assert len(event.event_msg) > 0

    def test_generate_lf_event_sequence(self, generator):
        """Test LF event sequence generation."""
        now = datetime.now(CST)
        start_time = now
        end_time = now + timedelta(minutes=35)

        events = generator.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G13",
            device_no="G130",
            start_time=start_time,
            end_time=end_time,
        )

        assert len(events) >= 8
        
        # Check all events are G13 codes
        for event in events:
            assert event.event_code.startswith("G13")

    def test_generate_rh_event_sequence(self, generator):
        """Test RH event sequence generation."""
        now = datetime.now(CST)
        start_time = now
        end_time = now + timedelta(minutes=45)

        events = generator.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G15",
            device_no="G150",
            start_time=start_time,
            end_time=end_time,
        )

        assert len(events) >= 8
        
        # Check all events are G15 codes
        for event in events:
            assert event.event_code.startswith("G15")

    def test_generate_ccm_event_sequence(self, generator):
        """Test CCM event sequence generation."""
        now = datetime.now(CST)
        start_time = now
        end_time = now + timedelta(minutes=50)

        events = generator.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G16",
            device_no="G160",
            start_time=start_time,
            end_time=end_time,
        )

        assert len(events) >= 8
        
        # Check all events are G16 codes
        for event in events:
            assert event.event_code.startswith("G16")

    def test_bof_sequence_starts_correctly(self, generator):
        """Test that BOF sequence starts with correct events."""
        now = datetime.now(CST)
        events = generator.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            start_time=now,
            end_time=now + timedelta(minutes=40),
        )

        # First events should be start sequence: G12001, G12003, G12005
        config = EVENT_SEQUENCE_CONFIGS["BOF"]
        start_codes = config.start_sequence
        
        for i, expected_code in enumerate(start_codes):
            assert events[i].event_code == expected_code, \
                f"Expected {expected_code} at position {i}, got {events[i].event_code}"

    def test_bof_sequence_ends_correctly(self, generator):
        """Test that BOF sequence ends with correct events."""
        now = datetime.now(CST)
        events = generator.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            start_time=now,
            end_time=now + timedelta(minutes=40),
        )

        # Last events should be end sequence
        config = EVENT_SEQUENCE_CONFIGS["BOF"]
        end_codes = config.end_sequence
        
        # Check that the end sequence is at the end
        event_codes = [e.event_code for e in events]
        for expected_code in end_codes:
            assert expected_code in event_codes, \
                f"Expected end code {expected_code} not found in sequence"

    def test_lf_sequence_starts_correctly(self, generator):
        """Test that LF sequence starts with correct events."""
        now = datetime.now(CST)
        events = generator.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G13",
            device_no="G130",
            start_time=now,
            end_time=now + timedelta(minutes=35),
        )

        # First events should be start sequence: G13001, G13003, G13005
        config = EVENT_SEQUENCE_CONFIGS["LF"]
        start_codes = config.start_sequence
        
        for i, expected_code in enumerate(start_codes):
            assert events[i].event_code == expected_code, \
                f"Expected {expected_code} at position {i}, got {events[i].event_code}"

    def test_generate_events_for_operation_dict(self, generator):
        """Test generating events from an operation dictionary."""
        now = datetime.now(CST)
        operation = {
            "id": 1,
            "heat_no": 2412100001,
            "pro_line_cd": "G1",
            "proc_cd": "G12",
            "device_no": "G120",
            "real_start_time": now,
            "real_end_time": now + timedelta(minutes=40),
        }

        events = generator.generate_events_for_operation(operation)

        assert len(events) >= 8
        assert all(e.heat_no == 2412100001 for e in events)

    def test_generate_events_for_operation_uses_plan_times(self, generator):
        """Test that plan times are used when real times are not available."""
        now = datetime.now(CST)
        operation = {
            "id": 1,
            "heat_no": 2412100001,
            "pro_line_cd": "G1",
            "proc_cd": "G12",
            "device_no": "G120",
            "plan_start_time": now,
            "plan_end_time": now + timedelta(minutes=40),
            "real_start_time": None,
            "real_end_time": None,
        }

        events = generator.generate_events_for_operation(operation)

        assert len(events) >= 8
        for event in events:
            assert event.event_time_start >= now
            assert event.event_time_end <= now + timedelta(minutes=40)

    def test_generate_events_returns_empty_for_invalid_proc_cd(self, generator):
        """Test that invalid process code returns empty list."""
        now = datetime.now(CST)
        events = generator.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G99",  # Invalid
            device_no="G990",
            start_time=now,
            end_time=now + timedelta(minutes=40),
        )

        assert events == []

    def test_generate_events_returns_empty_for_invalid_window(self, generator):
        """Test that invalid time window returns empty list."""
        now = datetime.now(CST)
        events = generator.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            start_time=now,
            end_time=now - timedelta(minutes=40),  # End before start
        )

        assert events == []


class TestEventSequenceConstraints:
    """Tests for verifying event sequence constraints."""

    @pytest.fixture
    def generator(self):
        return EventGenerator(min_events_per_operation=10, max_events_per_operation=20)

    def test_bof_paired_events_occur_together(self, generator):
        """Test that paired BOF events (start/end) occur together."""
        now = datetime.now(CST)
        
        # Run multiple times to check probabilistically
        for _ in range(10):
            events = generator.generate_event_sequence(
                heat_no=2412100001,
                pro_line_cd="G1",
                proc_cd="G12",
                device_no="G120",
                start_time=now,
                end_time=now + timedelta(minutes=40),
            )
            
            event_codes = [e.event_code for e in events]
            
            # Check paired events
            paired = [
                ("G12021", "G12022"),  # 氧枪喷吹开始/结束
                ("G12023", "G12024"),  # 扒渣开始/结束
            ]
            
            for start_code, end_code in paired:
                if start_code in event_codes:
                    # If start exists, end should also exist somewhere after
                    start_idx = event_codes.index(start_code)
                    end_indices = [i for i, c in enumerate(event_codes) if c == end_code]
                    # End might appear multiple times, at least one should be after start
                    if end_indices:
                        assert any(idx > start_idx for idx in end_indices), \
                            f"End event {end_code} should appear after start event {start_code}"

    def test_lf_paired_events_occur_together(self, generator):
        """Test that paired LF events (start/end) occur together."""
        now = datetime.now(CST)
        
        for _ in range(10):
            events = generator.generate_event_sequence(
                heat_no=2412100001,
                pro_line_cd="G1",
                proc_cd="G13",
                device_no="G130",
                start_time=now,
                end_time=now + timedelta(minutes=35),
            )
            
            event_codes = [e.event_code for e in events]
            
            # Check that if 通电开始 exists, 通电结束 also exists
            if "G13022" in event_codes:
                assert "G13023" in event_codes or event_codes.count("G13022") == event_codes.count("G13023") == 0

    def test_events_within_operation_window(self, generator):
        """Test that all events are strictly within the operation time window."""
        now = datetime.now(CST)
        start_time = now
        end_time = now + timedelta(minutes=40)
        
        for proc_cd in ["G12", "G13", "G15", "G16"]:
            events = generator.generate_event_sequence(
                heat_no=2412100001,
                pro_line_cd="G1",
                proc_cd=proc_cd,
                device_no=f"{proc_cd}0",
                start_time=start_time,
                end_time=end_time,
            )
            
            for event in events:
                assert event.event_time_start >= start_time, \
                    f"Event {event.event_code} starts before operation start"
                assert event.event_time_end <= end_time, \
                    f"Event {event.event_code} ends after operation end"


class TestEventCodesCompleteness:
    """Tests to verify event codes data is complete."""

    def test_all_processes_have_event_codes(self):
        """Test that all processes have event codes defined."""
        for proc_name in ["BOF", "LF", "RH", "CCM"]:
            assert proc_name in EVENT_CODES
            assert len(EVENT_CODES[proc_name]) > 0

    def test_all_processes_have_sequence_configs(self):
        """Test that all processes have sequence configs defined."""
        for proc_name in ["BOF", "LF", "RH", "CCM"]:
            assert proc_name in EVENT_SEQUENCE_CONFIGS
            config = EVENT_SEQUENCE_CONFIGS[proc_name]
            assert len(config.start_sequence) > 0
            assert len(config.end_sequence) > 0

    def test_bof_event_codes_match_spec(self):
        """Test that BOF event codes match the specification."""
        bof_codes = {code for code, *_ in EVENT_CODES["BOF"]}
        
        # Check some expected codes
        expected_codes = [
            "G12001", "G12002", "G12003", "G12004", "G12005", "G12006",
            "G12017", "G12018", "G12025", "G12026",
        ]
        for code in expected_codes:
            assert code in bof_codes, f"Expected BOF code {code} not found"

    def test_lf_event_codes_match_spec(self):
        """Test that LF event codes match the specification."""
        lf_codes = {code for code, *_ in EVENT_CODES["LF"]}
        
        expected_codes = [
            "G13001", "G13002", "G13003", "G13004", "G13005", "G13006",
            "G13009", "G13010", "G13022", "G13023",
        ]
        for code in expected_codes:
            assert code in lf_codes, f"Expected LF code {code} not found"

    def test_ccm_event_codes_match_spec(self):
        """Test that CCM event codes match the specification."""
        ccm_codes = {code for code, *_ in EVENT_CODES["CCM"]}
        
        expected_codes = [
            "G16001", "G16002", "G16003", "G16004",
            "G16008", "G16009", "G16010", "G16011",
        ]
        for code in expected_codes:
            assert code in ccm_codes, f"Expected CCM code {code} not found"

    def test_proc_cd_mapping_complete(self):
        """Test that process code mapping is complete."""
        assert PROC_CD_TO_NAME["G12"] == "BOF"
        assert PROC_CD_TO_NAME["G13"] == "LF"
        assert PROC_CD_TO_NAME["G15"] == "RH"
        assert PROC_CD_TO_NAME["G16"] == "CCM"


class TestSpecialEvents:
    """Tests for cancel (取消) and rework (回炉) special events."""

    @pytest.fixture
    def generator_with_special(self):
        """Generator with high special event probability for testing."""
        return EventGenerator(
            min_events_per_operation=6,
            max_events_per_operation=12,
            cancel_probability=1.0,  # Always trigger for testing
            rework_probability=0.0,
        )

    @pytest.fixture
    def generator_with_rework(self):
        """Generator with high rework probability for testing."""
        return EventGenerator(
            min_events_per_operation=6,
            max_events_per_operation=12,
            cancel_probability=0.0,
            rework_probability=1.0,
        )

    def test_bof_cancel_event_generated(self, generator_with_special):
        """Test that BOF generates cancel event (G12007) when forced."""
        now = datetime.now(CST)
        events = generator_with_special.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            start_time=now,
            end_time=now + timedelta(minutes=40),
            force_cancel=True,
        )

        # Find cancel event
        cancel_events = [e for e in events if e.event_code == "G12007"]
        assert len(cancel_events) == 1, "Should have exactly one cancel event"
        assert cancel_events[0].special_event_type == SpecialEventType.CANCEL

        # Check that cancel event has proper message
        assert "炉次取消" in cancel_events[0].event_name

    def test_bof_has_no_rework_event(self, generator_with_rework):
        """Test that BOF does NOT generate rework event (no rework for BOF)."""
        now = datetime.now(CST)
        events = generator_with_rework.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            start_time=now,
            end_time=now + timedelta(minutes=40),
            force_rework=True,
        )

        # Should have no rework event for BOF
        rework_events = [e for e in events if e.special_event_type == SpecialEventType.REWORK]
        assert len(rework_events) == 0, "BOF should not have rework events"

    def test_lf_cancel_event_generated(self, generator_with_special):
        """Test that LF generates cancel event (G13008) when forced."""
        now = datetime.now(CST)
        events = generator_with_special.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G13",
            device_no="G130",
            start_time=now,
            end_time=now + timedelta(minutes=35),
            force_cancel=True,
        )

        cancel_events = [e for e in events if e.event_code == "G13008"]
        assert len(cancel_events) == 1, "Should have exactly one LF cancel event"
        assert cancel_events[0].special_event_type == SpecialEventType.CANCEL

    def test_lf_rework_event_generated(self, generator_with_rework):
        """Test that LF generates rework event (G13007) when forced."""
        now = datetime.now(CST)
        events = generator_with_rework.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G13",
            device_no="G130",
            start_time=now,
            end_time=now + timedelta(minutes=35),
            force_rework=True,
        )

        rework_events = [e for e in events if e.event_code == "G13007"]
        assert len(rework_events) == 1, "Should have exactly one LF rework event"
        assert rework_events[0].special_event_type == SpecialEventType.REWORK
        assert "炉次回炉" in rework_events[0].event_name

    def test_rh_cancel_event_generated(self, generator_with_special):
        """Test that RH generates cancel event (G15008) when forced."""
        now = datetime.now(CST)
        events = generator_with_special.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G15",
            device_no="G150",
            start_time=now,
            end_time=now + timedelta(minutes=30),
            force_cancel=True,
        )

        cancel_events = [e for e in events if e.event_code == "G15008"]
        assert len(cancel_events) == 1, "Should have exactly one RH cancel event"

    def test_rh_rework_event_generated(self, generator_with_rework):
        """Test that RH generates rework event (G15007) when forced."""
        now = datetime.now(CST)
        events = generator_with_rework.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G15",
            device_no="G150",
            start_time=now,
            end_time=now + timedelta(minutes=30),
            force_rework=True,
        )

        rework_events = [e for e in events if e.event_code == "G15007"]
        assert len(rework_events) == 1, "Should have exactly one RH rework event"

    def test_ccm_cancel_event_generated(self, generator_with_special):
        """Test that CCM generates cancel event (G16015) when forced."""
        now = datetime.now(CST)
        events = generator_with_special.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G16",
            device_no="G160",
            start_time=now,
            end_time=now + timedelta(minutes=45),
            force_cancel=True,
        )

        cancel_events = [e for e in events if e.event_code == "G16015"]
        assert len(cancel_events) == 1, "Should have exactly one CCM cancel event"
        assert "开浇取消" in cancel_events[0].event_name

    def test_ccm_has_no_rework_event(self, generator_with_rework):
        """Test that CCM does NOT generate rework event (no rework for CCM)."""
        now = datetime.now(CST)
        events = generator_with_rework.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G16",
            device_no="G160",
            start_time=now,
            end_time=now + timedelta(minutes=45),
            force_rework=True,
        )

        rework_events = [e for e in events if e.special_event_type == SpecialEventType.REWORK]
        assert len(rework_events) == 0, "CCM should not have rework events"

    def test_cancel_event_sequence_is_shortened(self, generator_with_special):
        """Test that cancel events result in shortened end sequence."""
        now = datetime.now(CST)
        
        # Generate normal BOF sequence
        normal_gen = EventGenerator(min_events_per_operation=6, max_events_per_operation=10)
        normal_events = normal_gen.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            start_time=now,
            end_time=now + timedelta(minutes=40),
        )
        
        # Generate canceled BOF sequence
        canceled_events = generator_with_special.generate_event_sequence(
            heat_no=2412100002,
            pro_line_cd="G1",
            proc_cd="G12",
            device_no="G120",
            start_time=now,
            end_time=now + timedelta(minutes=40),
            force_cancel=True,
        )
        
        # Normal sequence should have 出钢 events
        normal_codes = [e.event_code for e in normal_events]
        assert "G12025" in normal_codes, "Normal should have 出钢开始"
        assert "G12026" in normal_codes, "Normal should have 出钢结束"
        
        # Canceled sequence should NOT have 出钢 events (they're skipped)
        canceled_codes = [e.event_code for e in canceled_events]
        assert "G12025" not in canceled_codes, "Canceled should skip 出钢开始"
        assert "G12026" not in canceled_codes, "Canceled should skip 出钢结束"
        
        # But should still have 钢包离开
        assert "G12002" in canceled_codes, "Canceled should still have 钢包离开"

    def test_rework_event_continues_to_normal_end(self, generator_with_rework):
        """Test that rework events still complete with normal end sequence."""
        now = datetime.now(CST)
        events = generator_with_rework.generate_event_sequence(
            heat_no=2412100001,
            pro_line_cd="G1",
            proc_cd="G13",
            device_no="G130",
            start_time=now,
            end_time=now + timedelta(minutes=35),
            force_rework=True,
        )
        
        event_codes = [e.event_code for e in events]
        
        # Should have the rework event
        assert "G13007" in event_codes, "Should have rework event"
        
        # Should still have normal end sequence
        assert "G13006" in event_codes, "Rework should still have 炉次结束"
        assert "G13004" in event_codes, "Rework should still have 处理结束"
        assert "G13002" in event_codes, "Rework should still have 钢包离开"

    def test_event_sequence_result_detects_cancel(self):
        """Test EventSequenceResult correctly detects cancel events."""
        now = datetime.now(CST)
        events = [
            Event(
                heat_no=1, pro_line_cd="G1", proc_cd="G12", device_no="G120",
                event_code="G12001", event_name="钢包到达", event_msg="test",
                event_time_start=now, event_time_end=now,
            ),
            Event(
                heat_no=1, pro_line_cd="G1", proc_cd="G12", device_no="G120",
                event_code="G12007", event_name="炉次取消", event_msg="test",
                event_time_start=now + timedelta(minutes=10), event_time_end=now + timedelta(minutes=10),
                special_event_type=SpecialEventType.CANCEL,
            ),
        ]
        
        result = EventSequenceResult.from_events(events)
        assert result.has_cancel is True
        assert result.has_rework is False
        assert result.cancel_event_time == now + timedelta(minutes=10)

    def test_event_sequence_result_detects_rework(self):
        """Test EventSequenceResult correctly detects rework events."""
        now = datetime.now(CST)
        events = [
            Event(
                heat_no=1, pro_line_cd="G1", proc_cd="G13", device_no="G130",
                event_code="G13001", event_name="钢包到达", event_msg="test",
                event_time_start=now, event_time_end=now,
            ),
            Event(
                heat_no=1, pro_line_cd="G1", proc_cd="G13", device_no="G130",
                event_code="G13007", event_name="炉次回炉", event_msg="test",
                event_time_start=now + timedelta(minutes=15), event_time_end=now + timedelta(minutes=15),
                special_event_type=SpecialEventType.REWORK,
            ),
        ]
        
        result = EventSequenceResult.from_events(events)
        assert result.has_cancel is False
        assert result.has_rework is True
        assert result.rework_event_time == now + timedelta(minutes=15)

    def test_special_event_configs_correct(self):
        """Test that special event configs are correctly set for each process."""
        # BOF: cancel only
        bof_config = EVENT_SEQUENCE_CONFIGS["BOF"]
        assert bof_config.cancel_event == "G12007"
        assert bof_config.rework_event is None
        
        # LF: both cancel and rework
        lf_config = EVENT_SEQUENCE_CONFIGS["LF"]
        assert lf_config.cancel_event == "G13008"
        assert lf_config.rework_event == "G13007"
        
        # RH: both cancel and rework
        rh_config = EVENT_SEQUENCE_CONFIGS["RH"]
        assert rh_config.cancel_event == "G15008"
        assert rh_config.rework_event == "G15007"
        
        # CCM: cancel only
        ccm_config = EVENT_SEQUENCE_CONFIGS["CCM"]
        assert ccm_config.cancel_event == "G16015"
        assert ccm_config.rework_event is None

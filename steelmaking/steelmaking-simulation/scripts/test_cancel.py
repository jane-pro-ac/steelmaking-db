#!/usr/bin/env python
"""Test script to verify cancel/rework event generation."""

import os
os.environ["CANCEL_EVENT_PROBABILITY"] = "0.15"
os.environ["REWORK_EVENT_PROBABILITY"] = "0.15"

from steelmaking_simulation.config import DatabaseConfig, SimulationConfig
from steelmaking_simulation.simulator import SteelmakingSimulator
import psycopg2
from psycopg2.extras import RealDictCursor

# Create simulator and initialize (this seeds data)
db_config = DatabaseConfig()
sim_config = SimulationConfig()
sim_config.seed_past_heats = 5
sim_config.seed_future_heats = 2

simulator = SteelmakingSimulator(db_config, sim_config)
simulator.initialize()
print("Initialization complete!")

# Check for canceled operations
conn = psycopg2.connect(db_config.connection_string)
with conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        SELECT heat_no, proc_cd, proc_status, device_no, 
               plan_start_time, plan_end_time, real_end_time
        FROM steelmaking.steelmaking_operation
        WHERE proc_status = 3
        ORDER BY heat_no, plan_start_time
    """)
    canceled = cur.fetchall()
    print(f"\nFound {len(canceled)} canceled operations:")
    for op in canceled[:15]:
        print(f"  Heat {op['heat_no']}, Proc {op['proc_cd']}, Device {op['device_no']}")

# Check for cancel events
with conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        SELECT event_code, event_msg, heat_no, proc_cd
        FROM steelmaking.steelmaking_event
        WHERE event_code IN ('G12007', 'G13008', 'G15008', 'G16015')
        ORDER BY event_time_start
    """)
    cancel_events = cur.fetchall()
    print(f"\nFound {len(cancel_events)} cancel events:")
    for evt in cancel_events[:15]:
        print(f"  {evt['event_code']}: Heat {evt['heat_no']}, Proc {evt['proc_cd']}, Msg: {evt['event_msg']}")

# Check for rework events
with conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        SELECT event_code, event_msg, heat_no, proc_cd
        FROM steelmaking.steelmaking_event
        WHERE event_code IN ('G13007', 'G15007')
        ORDER BY event_time_start
    """)
    rework_events = cur.fetchall()
    print(f"\nFound {len(rework_events)} rework events:")
    for evt in rework_events[:15]:
        print(f"  {evt['event_code']}: Heat {evt['heat_no']}, Proc {evt['proc_cd']}, Msg: {evt['event_msg']}")

# Verify that canceled operations have matching cancel events
with conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        SELECT o.heat_no, o.proc_cd, 
               e.event_code as cancel_event_code
        FROM steelmaking.steelmaking_operation o
        LEFT JOIN steelmaking.steelmaking_event e 
            ON o.heat_no = e.heat_no 
            AND o.proc_cd = e.proc_cd
            AND e.event_code IN ('G12007', 'G13008', 'G15008', 'G16015')
        WHERE o.proc_status = 3
        ORDER BY o.heat_no
        LIMIT 10
    """)
    results = cur.fetchall()
    print(f"\nCanceled operations with their cancel events:")
    for r in results:
        has_cancel = "Yes" if r['cancel_event_code'] else "No"
        print(f"  Heat {r['heat_no']} Proc {r['proc_cd']}: Cancel event = {has_cancel}")

conn.close()
simulator.db.close()
print("\nDone!")

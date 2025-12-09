Here is the example steelmaking operation data:

```json
{
  "heat_no": 25200122, // 炉次号，25年-2-第00122炉
  "pro_line_cd": "G1", // 产线代码 永远都是G1-代表着炼钢产线
  "proc_cd": "G12", // 工序代码 G12-BOF工序 G13-LF工序 G15-RH工序 G16-CCM工序
  "device_no": "G120", // 设备座次号 G120-代表着1#转炉 G130-代表着1#LF G150-代表着1#RH G160-代表着1#CCM G121-代表着2#转炉 以此类推
  "steel_grade_id": 1, // 钢种ID 对应steel_grade表的id
  "stl_grd_cd": "C001", // 钢种代码 对应steel_grade表的stl_grd_cd
  "proc_status": 0, // 工序状态 0-completed 1-active 2-pending
  "plan_start_time": "2025-12-07 14:40:00+08", // 计划开始时间
  "plan_end_time": "2025-12-07 15:00:00+08", // 计划结束时间
  "real_start_time": "2025-12-07 14:43:23+08", // 实际开始时间
  "real_end_time": "2025-12-07 15:04:45+08", // 实际结束时间
}```

# Base Rule
- All operation duration should be between 10 to 30 minutes.
- The gap between different operations for the same heat_no should be between 1 to 10 minutes.
- When the proc_status is 'completed', both real_start_time and real_end_time must be provided.
- When the proc_status is 'active', only real_start_time must be provided, and real_end_time should be null.
- When the proc_status is 'pending', both real_start_time and real_end_time should be null.
- Know current date time for generating realistic timestamps.
- Understand the steelmaking process flow to ensure logical sequencing of operations. BOF -> LF -> RH -> CCM. 
    - For this data, only generate for BOF, LF and CCM. This is BOF -> LF -> CCM flow.
    - In one process flow, caution the status in the sequence. For example, if BOF is completed, LF can be active or pending, but not completed.
- The factory has 3 BOF (G120, G121, G122), 3 LF (G130, G131, G132), 3 CCM (G160, G161, G162) units.
- Steel grade codes (stl_grd_cd) should be realistic and correspond to existing entries in the steel_grade table. You need to random select from existing steel grades.

# Tasks
- Write a python program that can simulate the factory steelmaking operations data based on the above rules.
- The program should fully simulate the steelmaking operations by inserting and updating the steelmaking_operation table.
- The program should be running continuously to simulate real-time data generation. The program will not terminate except manual stop.
- The program should strictly follow the base rules when generating data.
- The program should use poetry to manage dependencies.
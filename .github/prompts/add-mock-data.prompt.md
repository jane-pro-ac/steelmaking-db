---
agent: 'agent'
model: 'Claude Sonnet 4.5'
tools:
  ['edit', 'runNotebooks', 'search', 'new', 'runCommands', 'runTasks', 'chrome-devtools/*', 'postgres-mcp/*', 'usages', 'vscodeAPI', 'problems', 'changes', 'testFailure', 'openSimpleBrowser', 'fetch', 'githubRepo', 'extensions', 'todos', 'runSubagent']
description: 'Add mocking data for steelmaking warning.'
---

For now the simulation only seeds data into the `steelmaking_operation` table. Now you need to extend the simulation to also seed data into the `steelmaking_warning` table.

# Base Information
- This `steelmaking_warning` table (You can check the schema in `steelmaking/steelmaking_warning.sql`) is intended to store warning events that occur during steelmaking operations. 
- One warning should be associated with one operation in the `steelmaking_operation` table via the foreign key `operation_id`. But it also has redundant columns `heat_no`, `pro_line_cd`, `proc_cd`, `device_no` and `crew_cd` for easier querying. So when seeding warnings, you need to fill in these columns as well.
- The `warning_level` column indicates the severity of the warning, with 1 being the highest severity and 4 being the lowest.
- The warning code is optional, but the warning message is required. You need to come up with some realistic warning messages that could occur during steelmaking operations.
- The warning time is now split into `warning_time_start` and `warning_time_end`, representing the start and end time of the warning event.
  - The `warning_time_start` should be within the operation's actual start and end time.
  - The `warning_time_end` should be after the `warning_time_start` but before the operation's actual end time.
- Each operation can have zero or more warnings associated with it.

# Tasks
1. On startup, truncates warnings/operations, seeds completed flows within the last 12 hours and planned flows within the next 12 hours. Each heat uses one random crew and steel grade. So when seeding the past completed operations, you need to randomly decide whether to create warnings for each operation. If you decide to create warnings, you can create between 1 to 5 warnings for that operation. Make sure the warning times are within the operation's actual start and end time.
2. During the tick loop, when processing active operations, you also need to randomly decide whether to create warnings for the operation. If you decide to create warnings, you can create between 1 to 5 warnings for that operation. Make sure the warning times are within the operation's actual start and end time.
3. The pending operations do not have actual start and end times yet, so you do not need to create warnings for them.
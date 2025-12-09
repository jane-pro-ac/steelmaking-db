CREATE SCHEMA IF NOT EXISTS steelmaking;

CREATE TABLE steelmaking.steelmaking_operation (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    heat_no          BIGINT NOT NULL,              -- 炉次号
    pro_line_cd      TEXT NOT NULL,              -- 产线代码
    proc_cd          TEXT NOT NULL,              -- 工序代码
    device_no        TEXT NOT NULL,              -- 设备座次号

    steel_grade_id   BIGINT REFERENCES base.steel_grade(id),
    stl_grd_cd       TEXT,                       -- 冗余钢种代码，可选

    proc_status      SMALLINT NOT NULL,          -- 0: completed, 1: active, 2: pending
    CONSTRAINT chk_proc_status CHECK (proc_status IN (0, 1, 2)),

    plan_start_time  TIMESTAMPTZ NOT NULL,
    plan_end_time    TIMESTAMPTZ NOT NULL,
    real_start_time  TIMESTAMPTZ,
    real_end_time    TIMESTAMPTZ,

    extra            JSONB,

    CONSTRAINT uq_heat_proc_device UNIQUE (heat_no, proc_cd, device_no)
);

-- 1. BOF + 实绩时间（过去）
CREATE INDEX idx_op_bof_real_time
    ON steelmaking.steelmaking_operation (real_start_time, heat_no)
    WHERE proc_cd = 'G12' AND real_start_time IS NOT NULL;

-- 2. BOF + 计划时间（未来）
CREATE INDEX idx_op_bof_plan_time
    ON steelmaking.steelmaking_operation (plan_start_time, heat_no)
    WHERE proc_cd = 'G12'
      AND real_start_time IS NULL
      AND plan_start_time IS NOT NULL;

-- 3. 炉次全流程
CREATE INDEX idx_op_heat_proc_time
    ON steelmaking.steelmaking_operation (heat_no, proc_cd, real_start_time);
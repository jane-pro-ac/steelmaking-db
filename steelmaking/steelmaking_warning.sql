CREATE TABLE steelmaking.steelmaking_warning (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    heat_no       BIGINT NOT NULL,
    pro_line_cd   TEXT NOT NULL,
    proc_cd       TEXT NOT NULL,
    device_no     TEXT NOT NULL,

    warning_code  TEXT,
    warning_msg   TEXT NOT NULL,
    warning_level SMALLINT NOT NULL,
    CONSTRAINT chk_warning_level CHECK (warning_level IN (1, 2, 3, 4)),  -- 1: high, 2: medium high, 3: medium low, 4: low
    warning_time_start  TIMESTAMPTZ NOT NULL,
    warning_time_end       TIMESTAMPTZ NOT NULL,

    extra         JSONB
);

CREATE INDEX idx_stlmk_warn_heat_device
    ON steelmaking.steelmaking_warning (heat_no, device_no);
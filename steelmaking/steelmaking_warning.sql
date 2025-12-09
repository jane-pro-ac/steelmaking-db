CREATE TABLE steelmaking.steelmaking_warning (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    operation_id  BIGINT REFERENCES steelmaking.steelmaking_operation(id),

    heat_no       TEXT NOT NULL,
    pro_line_cd   TEXT NOT NULL,
    proc_cd       TEXT NOT NULL,
    device_no     TEXT NOT NULL,

    warning_code  TEXT,
    warning_msg   TEXT NOT NULL,
    warning_time  TIMESTAMPTZ NOT NULL,

    extra         JSONB
);

CREATE INDEX idx_warn_heat_device_time
    ON steelmaking.steelmaking_warning (heat_no, device_no, warning_time DESC);
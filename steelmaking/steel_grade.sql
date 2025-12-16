CREATE SCHEMA IF NOT EXISTS base;

CREATE TABLE base.steel_grade (
    id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stl_grd_cd    TEXT NOT NULL UNIQUE,   -- 钢种代码
    stl_grd_nm    TEXT NOT NULL           -- 钢种名称
);

CREATE INDEX idx_steel_grade_code
    ON base.steel_grade (stl_grd_cd);
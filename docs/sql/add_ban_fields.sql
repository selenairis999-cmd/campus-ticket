-- 分级处置封禁机制：sys_user 增加封禁信息字段
-- 执行方式：mysql -uroot -p campus_ticket < add_ban_fields.sql
-- status 语义沿用现有约定：1=正常（注册默认值），0=封禁

ALTER TABLE sys_user
  ADD COLUMN ban_expire_time DATETIME NULL COMMENT '封禁截止时间，NULL表示永久（仅status=0时有效），到期自动视为解封' AFTER role,
  ADD COLUMN ban_reason VARCHAR(200) NULL COMMENT '封禁原因留痕（在线命中/离线检出/人工研判）' AFTER ban_expire_time;

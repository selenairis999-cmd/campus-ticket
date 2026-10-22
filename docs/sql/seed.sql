-- ============================================================
-- 校园票务与智能分析系统 演示种子数据
-- 依赖：先执行 docs/sql/schema.sql 建表
-- 执行：mysql -uroot -p campus_ticket < docs/sql/seed.sql
-- 说明：所有账号初始密码均为 123456（库中存 BCrypt 哈希，非明文）。
--       种子数据仅为演示/答辩用，正式部署请修改密码或删除演示账号。
-- 可重复执行（INSERT ... ON DUPLICATE KEY UPDATE，username 为唯一键）。
-- ============================================================

SET NAMES utf8mb4;

-- ------------------------------------------------------------
-- 演示账号：4 种角色各至少 1 个
-- role：0 管理员 / 1 学生 / 2 组织者 / 3 核销员
-- 密码哈希为 BCrypt(cost=12)，明文口令：123456
-- ------------------------------------------------------------
INSERT INTO `sys_user` (`username`, `password`, `name`, `phone`, `status`, `role`) VALUES
('admin',       '$2a$12$lX3.2NIDXLgVvZAVq9gZ2O2.YxOXwqD5JFtKKHbsC2gFg7Tm7wU7a', '管理员',  '13800000000', 1, 0),
('zhangsan',    '$2a$12$lX3.2NIDXLgVvZAVq9gZ2O2.YxOXwqD5JFtKKHbsC2gFg7Tm7wU7a', '张三',    '13900000001', 1, 2),
('student01',   '$2a$12$lX3.2NIDXLgVvZAVq9gZ2O2.YxOXwqD5JFtKKHbsC2gFg7Tm7wU7a', '李同学',  '13900000002', 1, 1),
('organizer01', '$2a$12$lX3.2NIDXLgVvZAVq9gZ2O2.YxOXwqD5JFtKKHbsC2gFg7Tm7wU7a', '王组织',  '13900000003', 1, 2),
('checker01',   '$2a$12$lX3.2NIDXLgVvZAVq9gZ2O2.YxOXwqD5JFtKKHbsC2gFg7Tm7wU7a', '核销员',  '13900000004', 1, 3)
ON DUPLICATE KEY UPDATE `password` = VALUES(`password`), `name` = VALUES(`name`),
                        `phone` = VALUES(`phone`), `role` = VALUES(`role`), `status` = 1;

-- ------------------------------------------------------------
-- 演示活动（由 organizer01 发布，抢票窗口覆盖"现在"之后，便于立即演示抢票）
-- 注意：抢票结束时间必须晚于当前时间，否则活动无法发布/抢票会被时间窗拦截。
--       若演示时间已过期，请自行调整下列时间或通过组织者页面新建活动。
-- ------------------------------------------------------------
INSERT INTO `activity`
  (`id`, `title`, `description`, `location`, `start_time`, `end_time`,
   `sign_start_time`, `sign_end_time`, `organizer_id`, `status`,
   `total_stock`, `remain_stock`, `version`)
VALUES
  (1, '校园歌手大赛决赛', '一年一度的校园歌手大赛决赛，欢迎各位同学到场观赛。', '大学生活动中心报告厅',
   '2026-11-20 19:00:00', '2026-11-20 21:30:00',
   '2026-11-01 09:00:00', '2026-11-20 18:00:00',
   (SELECT id FROM sys_user WHERE username = 'organizer01'), 0, 100, 100, 0)
ON DUPLICATE KEY UPDATE `title` = VALUES(`title`);

-- 票种：与活动库存同步（活动库存 = 其下所有票种库存之和）
INSERT INTO `ticket` (`id`, `activity_id`, `ticket_name`, `total_stock`, `remain_stock`, `version`) VALUES
  (1, 1, '普通票', 80, 80, 0),
  (2, 1, '前排票', 20, 20, 0)
ON DUPLICATE KEY UPDATE `total_stock` = VALUES(`total_stock`),
                        `remain_stock` = VALUES(`remain_stock`);

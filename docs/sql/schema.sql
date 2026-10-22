-- ============================================================
-- 校园票务与智能分析系统 数据库建表脚本
-- 数据库：campus_ticket（MySQL 8.0，字符集 utf8mb4）
-- 执行方式：
--   mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS campus_ticket DEFAULT CHARACTER SET utf8mb4;"
--   mysql -uroot -p campus_ticket < docs/sql/schema.sql
-- 说明：本项目共 8 张核心表，与 docs/diagrams/er/ 下的实体图一一对应。
--       本脚本由实际运行库 SHOW CREATE TABLE 导出后整理，可重复执行（IF NOT EXISTS）。
-- ============================================================

SET NAMES utf8mb4;

-- ------------------------------------------------------------
-- 表 1/8：sys_user 系统用户表
-- role：0 管理员 / 1 学生 / 2 组织者 / 3 核销员
-- status：1 正常 / 0 封禁（封禁到期后由业务层视为解封，不改写 status）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sys_user` (
  `id`             bigint(20)   NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username`       varchar(50)  NOT NULL COMMENT '用户名/学号',
  `password`       varchar(100) NOT NULL COMMENT '密码（BCrypt 哈希，非明文）',
  `name`           varchar(50)  NOT NULL COMMENT '真实姓名',
  `phone`          varchar(20)  DEFAULT NULL COMMENT '手机号（用于找回密码）',
  `status`         tinyint(4)   DEFAULT '1' COMMENT '状态 1正常 0封禁',
  `role`           tinyint(4)   DEFAULT '1' COMMENT '角色：0管理员 1学生 2组织者 3核销员',
  `ban_expire_time` datetime    DEFAULT NULL COMMENT '封禁截止时间，NULL表示永久（仅status=0时有效），到期自动视为解封',
  `ban_reason`     varchar(200) DEFAULT NULL COMMENT '封禁原因留痕（在线命中/离线检出/人工研判）',
  `create_time`    datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='系统用户表';

-- ------------------------------------------------------------
-- 表 2/8：activity 校园活动表
-- version 为活动级乐观锁版本号，由条件 UPDATE 维护
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `activity` (
  `id`              bigint(20)   NOT NULL AUTO_INCREMENT COMMENT '活动ID',
  `title`           varchar(200) NOT NULL COMMENT '活动标题',
  `description`     text         COMMENT '活动详情',
  `location`        varchar(200) DEFAULT NULL COMMENT '活动地点',
  `start_time`      datetime     NOT NULL COMMENT '活动开始时间',
  `end_time`        datetime     NOT NULL COMMENT '活动结束时间',
  `sign_start_time` datetime     NOT NULL COMMENT '抢票开始时间',
  `sign_end_time`   datetime     NOT NULL COMMENT '抢票结束时间',
  `organizer_id`    bigint(20)   NOT NULL COMMENT '组织者用户ID',
  `status`          tinyint(4)   DEFAULT '0' COMMENT '状态 0未开始 1进行中 2已结束',
  `total_stock`     int(11)      NOT NULL DEFAULT '0' COMMENT '总库存（由其下所有票种库存之和派生）',
  `remain_stock`    int(11)      NOT NULL DEFAULT '0' COMMENT '剩余库存',
  `version`         int(11)      DEFAULT '0' COMMENT '乐观锁版本号',
  `create_time`     datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='校园活动表';

-- ------------------------------------------------------------
-- 表 3/8：ticket 活动票务表 / 票种表
-- 注意：本表是"票种"而非电子票，电子票见 eticket
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `ticket` (
  `id`           bigint(20)   NOT NULL AUTO_INCREMENT COMMENT '票种ID',
  `activity_id`  bigint(20)   NOT NULL COMMENT '关联活动ID',
  `ticket_name`  varchar(100) NOT NULL COMMENT '票种名称',
  `total_stock`  int(11)      NOT NULL COMMENT '总库存',
  `remain_stock` int(11)      NOT NULL COMMENT '剩余库存',
  `version`      int(11)      DEFAULT '0' COMMENT '乐观锁版本号',
  `create_time`  datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='活动票务表（票种）';

-- ------------------------------------------------------------
-- 表 4/8：ticket_order 抢票订单表
-- 一人一票判重依据：user_id + activity_id
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `ticket_order` (
  `id`          bigint(20)   NOT NULL AUTO_INCREMENT COMMENT '订单ID',
  `user_id`     bigint(20)   NOT NULL COMMENT '用户ID',
  `activity_id` bigint(20)   NOT NULL COMMENT '活动ID',
  `ticket_name` varchar(100) DEFAULT NULL COMMENT '票种名称',
  `create_time` datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_user_activity` (`user_id`,`activity_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='抢票订单表';

-- ------------------------------------------------------------
-- 表 5/8：eticket 电子票表
-- qr_content 保存出票时的静态票号；动态二维码在请求接口时实时生成，不回写本表
-- status：0 未使用 / 1 已核销 / 2 已作废
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `eticket` (
  `id`          bigint(20)   NOT NULL AUTO_INCREMENT COMMENT '主键',
  `order_id`    bigint(20)   NOT NULL COMMENT '关联订单ID',
  `user_id`     bigint(20)   NOT NULL COMMENT '用户ID',
  `activity_id` bigint(20)   NOT NULL COMMENT '活动ID',
  `ticket_code` varchar(64)  NOT NULL COMMENT '唯一票号',
  `qr_content`  varchar(255) DEFAULT NULL COMMENT '出票时写入的静态票号；动态二维码在请求接口时实时生成，不回写本表',
  `status`      tinyint(4)   DEFAULT '0' COMMENT '状态：0未使用 1已核销 2已作废',
  `ticket_name` varchar(100) DEFAULT NULL COMMENT '票种名称',
  `create_time` datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `used_time`   datetime     DEFAULT NULL COMMENT '核销时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ticket_code` (`ticket_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='电子票表';

-- ------------------------------------------------------------
-- 表 6/8：checkin_record 核销记录表
-- 一次核销一条记录，ticket_code 冗余便于按票号追溯
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `checkin_record` (
  `id`          bigint(20)   NOT NULL AUTO_INCREMENT COMMENT '主键',
  `ticket_id`   bigint(20)   NOT NULL COMMENT '电子票ID',
  `activity_id` bigint(20)   NOT NULL COMMENT '活动ID',
  `user_id`     bigint(20)   NOT NULL COMMENT '持票人ID',
  `ticket_code` varchar(64)  NOT NULL COMMENT '票号',
  `ticket_name` varchar(100) DEFAULT NULL COMMENT '票种名称',
  `checker_id`  bigint(20)   NOT NULL COMMENT '核销员ID',
  `create_time` datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '核销时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='核销记录表';

-- ------------------------------------------------------------
-- 表 7/8：activity_comment 活动评论表
-- parent_id：0 主评，>0 追评所属主评ID
-- sentiment：模型回填的预测标签 0差评 1中评 2好评 9无意义
-- sentiment_label：造数/人工标注的真实标签，仅离线实验使用
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `activity_comment` (
  `id`              bigint(20)   NOT NULL AUTO_INCREMENT COMMENT '主键',
  `activity_id`     bigint(20)   NOT NULL COMMENT '活动ID',
  `user_id`         bigint(20)   NOT NULL COMMENT '评论用户ID',
  `username`        varchar(50)  NOT NULL COMMENT '用户名',
  `content`         varchar(500) NOT NULL COMMENT '评论内容',
  `sentiment`       tinyint(4)   DEFAULT NULL COMMENT '情感：0差评 1中评 2好评 9无意义（定时任务模型回填）',
  `sentiment_label` tinyint(4)   DEFAULT NULL COMMENT '真实标签（造数/人工标注，仅离线实验用）',
  `parent_id`       bigint(20)   NOT NULL DEFAULT '0' COMMENT '主评ID，0=主评论，>0=追评所属主评ID',
  `create_time`     datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '评论时间',
  PRIMARY KEY (`id`),
  KEY `idx_activity` (`activity_id`),
  KEY `idx_sentiment_null` (`sentiment`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='活动评论表（方案三情感分析）';

-- ------------------------------------------------------------
-- 表 8/8：grab_log 抢票请求日志表
-- create_time 为 datetime(3)，毫秒精度是离线"请求间隔"特征的前提
-- result 枚举：SUCCESS / STOCK_EMPTY / VERSION_CONFLICT / TIME_WINDOW
--              / ACTIVITY_ENDED / DUPLICATE / RISK_BLOCKED / BANNED / ERROR
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `grab_log` (
  `id`          bigint(20)   NOT NULL AUTO_INCREMENT,
  `user_id`     bigint(20)   NOT NULL COMMENT '抢票用户ID',
  `username`    varchar(50)  NOT NULL COMMENT '用户名（冗余，便于离线分析直接出报告）',
  `activity_id` bigint(20)   NOT NULL COMMENT '活动ID',
  `ip`          varchar(50)  DEFAULT NULL COMMENT '客户端IP',
  `user_agent`  varchar(500) DEFAULT NULL COMMENT '浏览器UA',
  `result`      varchar(30)  NOT NULL COMMENT 'SUCCESS/STOCK_EMPTY/VERSION_CONFLICT/TIME_WINDOW/ACTIVITY_ENDED/DUPLICATE/RISK_BLOCKED/BANNED/ERROR',
  `create_time` datetime(3)  NOT NULL COMMENT '请求时间（毫秒精度，间隔特征依赖它）',
  PRIMARY KEY (`id`),
  KEY `idx_user_time` (`user_id`,`create_time`),
  KEY `idx_activity` (`activity_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='抢票请求日志（成功+失败都记，风控数据源）';

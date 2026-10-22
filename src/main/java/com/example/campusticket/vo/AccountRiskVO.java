package com.example.campusticket.vo;

import lombok.Data;
import java.time.LocalDateTime;

/** 单个账号的抢票行为聚合（风控嫌疑分析用） */
@Data
public class AccountRiskVO {
    private String username;     // 用户名
    private Long userId;         // 用户ID
    private Long totalRequests;  // 总请求数
    private Long successCount;   // 成功次数
    private Long blockedCount;   // 被风控拦截次数
    private Boolean suspect;     // 是否嫌疑账号（Java 侧判定）
    private Boolean banned;      // 是否处于封禁中（管理端处置用）
    private LocalDateTime banExpireTime; // 封禁截止时间：NULL 表示永久
}

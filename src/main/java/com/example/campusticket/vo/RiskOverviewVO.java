package com.example.campusticket.vo;

import lombok.Data;
import java.util.List;

/** 风控总览：统计卡片 + 嫌疑账号排行（分页） */
@Data
public class RiskOverviewVO {
    private long totalRequests;              // 抢票日志总数
    private long successCount;               // 成功次数
    private long blockedCount;               // 被风控拦截次数
    private long conflictCount;              // 乐观锁冲突次数
    private long bannedCount;                // 当前封禁中账号数
    private String successRate;              // 成功率（如 "87.5%"）
    /** 当前页的嫌疑账号（被拦截过 或 请求数超阈值），按请求量倒序 */
    private List<AccountRiskVO> suspectAccounts;
    private long suspectTotal;               // 嫌疑账号总数（分页用）
    private long suspectPageNum;             // 当前页码
    private long suspectPageSize;            // 每页条数
    private long suspectPages;               // 总页数
}

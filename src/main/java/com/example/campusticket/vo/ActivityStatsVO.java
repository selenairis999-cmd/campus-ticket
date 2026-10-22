package com.example.campusticket.vo;

import lombok.Data;

/** 活动出勤统计数据 */
@Data
public class ActivityStatsVO {
    private Long activityId;
    private String activityTitle;
    private Integer totalStock;   // 总库存
    private Integer remainStock;  // 剩余库存
    private Long soldCount;       // 已售出票数
    private Long checkedCount;    // 已核销（实际入场）人数
    private String attendanceRate;// 出勤率，如 "100.0%"
}

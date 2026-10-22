package com.example.campusticket.vo;

import lombok.Data;
import java.util.List;

/** 离线检测运行结果：报告行 + 脚本控制台输出 */
@Data
public class OfflineAnalysisResultVO {
    private Long activityId;       // 本次分析的活动
    private int analyzedUsers;     // 参与检测的用户数
    private int anomalyCount;      // 孤立森林判为异常的账号数
    private List<OfflineAnomalyVO> rows; // 按异常分升序（越负越异常，排最前）
    private String console;        // 三步脚本的控制台输出（审计/调试用）
}

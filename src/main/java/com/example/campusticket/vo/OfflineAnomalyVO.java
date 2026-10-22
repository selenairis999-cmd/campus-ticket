package com.example.campusticket.vo;

import lombok.Data;

/** 离线检测报告中的单个账号行（anomaly_report.csv 的结构化映射） */
@Data
public class OfflineAnomalyVO {
    private String username;      // 用户名
    private double ifScore;       // 孤立森林异常分，越负越异常
    private boolean ifAnomaly;    // 孤立森林判定：true=异常
    private boolean sigAnomaly;   // 3σ 统计基线判定：true=命中
    private int reqCount;         // 总请求数
    private double intervalMean;  // 请求间隔均值（ms）
    private double intervalMin;   // 请求间隔最小值（ms）
    private double conflictRate;  // 乐观锁冲突率
    private String top3Features;  // 偏离最大的 3 个特征及 z 值（可解释性）
}

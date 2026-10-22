package com.example.campusticket.vo;

import lombok.Data;

@Data
public class SentimentStatsVO {
    private Long activityId;
    private Integer total;        // 评论总数
    private Integer posCount;     // 好评数
    private Integer neuCount;     // 中评数
    private Integer negCount;     // 差评数
    private String positiveRate;  // 好评率，如 "87.5"
}

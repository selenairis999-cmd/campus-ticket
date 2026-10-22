package com.example.campusticket.vo;

import lombok.Data;

@Data
public class CommentRankVO {
    private Long activityId;
    private String title;
    private Integer total;       // 已分析评论数
    private Integer posCount;
    private Integer neuCount;
    private Integer negCount;
    private String positiveRate; // 好评率（后端算好，如 "87.5%"）
}

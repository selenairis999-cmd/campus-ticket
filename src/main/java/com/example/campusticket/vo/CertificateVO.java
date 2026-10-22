package com.example.campusticket.vo;

import lombok.Data;
import java.time.LocalDateTime;

/** 电子签到证书数据 */
@Data
public class CertificateVO {
    private String certificateNo;        // 证书编号
    private String studentName;          // 学生姓名
    private String activityTitle;        // 活动名称
    private String location;             // 活动地点
    private LocalDateTime activityStartTime; // 活动开始时间
    private LocalDateTime activityEndTime;   // 活动结束时间
    private LocalDateTime checkinTime;       // 核销（签到）时间
}

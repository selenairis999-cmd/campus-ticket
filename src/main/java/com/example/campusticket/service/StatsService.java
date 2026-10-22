package com.example.campusticket.service;

import com.example.campusticket.common.Result;
import com.example.campusticket.vo.ActivityStatsVO;
import com.example.campusticket.vo.CertificateVO;

public interface StatsService {
    /** 活动出勤统计（组织者/管理员） */
    Result<ActivityStatsVO> activityStats(Long activityId, Long userId);
    /** 生成签到证书（学生，自己的已核销票） */
    Result<CertificateVO> certificate(Long ticketId, Long userId);
}

package com.example.campusticket.controller;

import com.example.campusticket.annotation.RequireRole;
import com.example.campusticket.common.Result;
import com.example.campusticket.common.UserContext;
import com.example.campusticket.common.UserRole;
import com.example.campusticket.service.StatsService;
import com.example.campusticket.vo.ActivityStatsVO;
import com.example.campusticket.vo.CertificateVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/stats")
public class StatsController {

    @Autowired
    private StatsService statsService;

    /** 活动出勤统计：组织者/管理员 */
    @GetMapping("/activity")
    @RequireRole({UserRole.ORGANIZER, UserRole.ADMIN})
    public Result<ActivityStatsVO> activityStats(@RequestParam Long activityId) {
        return statsService.activityStats(activityId, UserContext.get().getId());
    }

    /** 生成签到证书：学生（自己的已核销票） */
    @GetMapping("/certificate")
    @RequireRole(UserRole.STUDENT)
    public Result<CertificateVO> certificate(@RequestParam Long ticketId) {
        return statsService.certificate(ticketId, UserContext.get().getId());
    }
}

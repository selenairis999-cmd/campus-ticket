package com.example.campusticket.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.annotation.RequireRole;
import com.example.campusticket.common.Result;
import com.example.campusticket.common.UserContext;
import com.example.campusticket.common.UserRole;
import com.example.campusticket.entity.CheckinRecord;
import com.example.campusticket.service.CheckinService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/checkin")
public class CheckinController {

    @Autowired
    private CheckinService checkinService;

    /** 扫码核销：仅核销员 */
    @PostMapping("/verify")
    @RequireRole(UserRole.CHECKER)
    public Result<String> verify(@RequestParam String qrContent) {
        return checkinService.verify(qrContent, UserContext.get().getId());
    }

    /** 核销记录查询：核销员可见全部，组织者仅可见本组织活动 */
    @GetMapping("/records")
    @RequireRole({UserRole.CHECKER, UserRole.ORGANIZER})
    public Result<Page<CheckinRecord>> records(@RequestParam(required = false) Long activityId,
                                               @RequestParam(defaultValue = "1") long pageNum,
                                               @RequestParam(defaultValue = "10") long pageSize) {
        return checkinService.records(activityId, pageNum, pageSize, UserContext.get());
    }
}

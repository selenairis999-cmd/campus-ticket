package com.example.campusticket.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.annotation.RequireRole;
import com.example.campusticket.common.Result;
import com.example.campusticket.common.UserContext;
import com.example.campusticket.common.UserRole;
import com.example.campusticket.entity.Ticket;
import com.example.campusticket.service.TicketService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/ticket")
public class TicketController {

    @Autowired
    private TicketService ticketService;

    /** 我的票券列表：学生（分页） */
    @GetMapping("/myList")
    @RequireRole(UserRole.STUDENT)
    public Result<Page<Ticket>> myList(@RequestParam(defaultValue = "1") Integer pageNum,
                                       @RequestParam(defaultValue = "10") Integer pageSize) {
        return ticketService.myTickets(UserContext.get().getId(), pageNum, pageSize);
    }

    /** 票券详情：学生 */
    @GetMapping("/detail")
    @RequireRole(UserRole.STUDENT)
    public Result<Ticket> detail(@RequestParam Long ticketId) {
        return ticketService.getTicket(ticketId, UserContext.get().getId());
    }

    /** 获取动态二维码（学生）：前端每 3 秒调用一次实现刷新 */
    @GetMapping("/qrcode")
    @RequireRole(UserRole.STUDENT)
    public Result<String> qrcode(@RequestParam Long ticketId) {
        return ticketService.dynamicQrCode(ticketId, UserContext.get().getId());
    }

    /** 删除已过期的票（学生）：活动已结束且未核销的票可从"我的票券"移除 */
    @PostMapping("/delete")
    @RequireRole(UserRole.STUDENT)
    public Result<String> delete(@RequestParam Long ticketId) {
        return ticketService.deleteExpiredTicket(ticketId, UserContext.get().getId());
    }

}

package com.example.campusticket.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.common.Result;
import com.example.campusticket.entity.Ticket;

public interface TicketService {
    /** 我的票券列表（分页） */
    Result<Page<Ticket>> myTickets(Long userId, Integer pageNum, Integer pageSize);
    /** 票券详情（校验只能看自己的） */
    Result<Ticket> getTicket(Long ticketId, Long userId);
    /** 获取动态二维码内容（学生自己的未使用票） */
    Result<String> dynamicQrCode(Long ticketId, Long userId);
    /** 删除已过期且未核销的票（校验归属：只能删自己的；校验过期：活动结束时间已过） */
    Result<String> deleteExpiredTicket(Long ticketId, Long userId);

}

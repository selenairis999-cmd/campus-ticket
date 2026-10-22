package com.example.campusticket.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.common.Result;
import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.Ticket;
import com.example.campusticket.mapper.ActivityMapper;
import com.example.campusticket.mapper.TicketMapper;
import com.example.campusticket.service.TicketService;
import com.example.campusticket.common.QrCodeUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class TicketServiceImpl implements TicketService {

    @Autowired
    private TicketMapper ticketMapper;

    @Autowired
    private ActivityMapper activityMapper;

    @Override
    public Result<Page<Ticket>> myTickets(Long userId, Integer pageNum, Integer pageSize) {
        if (pageNum == null || pageNum < 1) pageNum = 1;
        if (pageSize == null || pageSize < 1) pageSize = 10;
        LambdaQueryWrapper<Ticket> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Ticket::getUserId, userId)
                .orderByDesc(Ticket::getCreateTime); // 最新的票排前面
        Page<Ticket> page = ticketMapper.selectPage(new Page<>(pageNum, pageSize), wrapper);
        // 联表填充活动开始时间和活动名称（前端直接展示）
        List<Ticket> tickets = page.getRecords();
        if (!tickets.isEmpty()) {
            List<Long> activityIds = tickets.stream().map(Ticket::getActivityId).distinct().collect(Collectors.toList());
            Map<Long, Activity> activityMap = activityMapper.selectBatchIds(activityIds).stream()
                    .collect(Collectors.toMap(Activity::getId, a -> a));
            tickets.forEach(t -> {
                Activity a = activityMap.get(t.getActivityId());
                if (a != null) {
                    t.setActivityStartTime(a.getStartTime());
                    t.setActivityEndTime(a.getEndTime());
                    t.setActivityTitle(a.getTitle());
                }
            });
        }
        return Result.success(page);
    }

    @Override
    public Result<Ticket> getTicket(Long ticketId, Long userId) {
        Ticket ticket = ticketMapper.selectById(ticketId);
        if (ticket == null) {
            return Result.error("票券不存在");
        }
        // 只能查看自己的票（防越权）
        if (!ticket.getUserId().equals(userId)) {
            return Result.error("无权查看他人票券");
        }
        return Result.success(ticket);
    }

    @Autowired
    private QrCodeUtil qrCodeUtil;

    @Override
    public Result<String> dynamicQrCode(Long ticketId, Long userId) {
        Ticket ticket = ticketMapper.selectById(ticketId);
        if (ticket == null) {
            return Result.error("票券不存在");
        }
        // 只能获取自己的票
        if (!ticket.getUserId().equals(userId)) {
            return Result.error("无权操作他人票券");
        }
        // 已核销/已作废的票不能生成二维码
        if (ticket.getStatus() != 0) {
            return Result.error("该票已核销或已作废");
        }
        // 活动已结束的票视为过期，不能生成入场二维码
        Activity activity = activityMapper.selectById(ticket.getActivityId());
        if (activity != null && activity.getEndTime() != null
                && !activity.getEndTime().isAfter(java.time.LocalDateTime.now())) {
            return Result.error("活动已结束，该票已过期");
        }
        // 每次调用都生成新的时间戳+签名，保证"一次一码、秒级变化"
        return Result.success(qrCodeUtil.build(ticket.getTicketCode()));
    }

    @Override
    public Result<String> deleteExpiredTicket(Long ticketId, Long userId) {
        Ticket ticket = ticketMapper.selectById(ticketId);
        if (ticket == null) {
            return Result.error("票券不存在");
        }
        // 只能删自己的票（防越权）
        if (!ticket.getUserId().equals(userId)) {
            return Result.error("无权操作他人票券");
        }
        // 已核销/已作废的票不允许删除（保留证书入口）
        if (ticket.getStatus() != 0) {
            return Result.error("仅已过期的未使用票可删除");
        }
        // 只有活动已结束（票已过期）才允许删除
        Activity activity = activityMapper.selectById(ticket.getActivityId());
        if (activity == null || activity.getEndTime() == null
                || activity.getEndTime().isAfter(java.time.LocalDateTime.now())) {
            return Result.error("活动未结束，票不可删除");
        }
        ticketMapper.deleteById(ticket.getId());
        return Result.success("已删除过期票");
    }

}

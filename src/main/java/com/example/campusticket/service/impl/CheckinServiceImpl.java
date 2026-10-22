package com.example.campusticket.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.common.QrCodeUtil;
import com.example.campusticket.common.Result;
import com.example.campusticket.common.UserRole;
import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.CheckinRecord;
import com.example.campusticket.entity.SysUser;
import com.example.campusticket.entity.Ticket;
import com.example.campusticket.mapper.ActivityMapper;
import com.example.campusticket.mapper.CheckinRecordMapper;
import com.example.campusticket.mapper.SysUserMapper;
import com.example.campusticket.mapper.TicketMapper;
import com.example.campusticket.service.CheckinService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;


import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
public class CheckinServiceImpl implements CheckinService {

    @Autowired
    private TicketMapper ticketMapper;

    @Autowired
    private ActivityMapper activityMapper;

    @Autowired
    private CheckinRecordMapper checkinRecordMapper;

    @Autowired
    private SysUserMapper sysUserMapper;

    @Autowired
    private QrCodeUtil qrCodeUtil;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result<String> verify(String qrContent, Long checkerId) {
        // 0. 解析并校验动态码：签名校验 + 3秒时效校验（静态票号会被拒绝）
        String ticketCode;
        try {
            ticketCode = qrCodeUtil.verify(qrContent);
        } catch (RuntimeException e) {
            return Result.error(e.getMessage());
        }

        // 1. 按票号查电子票
        LambdaQueryWrapper<Ticket> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Ticket::getTicketCode, ticketCode);
        Ticket ticket = ticketMapper.selectOne(wrapper);
        if (ticket == null) {
            return Result.error("票券不存在");
        }

        // 2. 防重复入场：只有 status=0（未使用）的票才能核销
        if (ticket.getStatus() != 0) {
            if (ticket.getStatus() == 1) {
                return Result.error("该票已核销，请勿重复入场");
            }
            return Result.error("该票已作废");
        }

        // 3. 活动校验：活动必须存在、未被手动结束，且在验票时间窗口内
        //    窗口 = 活动开始前 1 小时 ～ 活动结束（提前 1 小时放票入场，给观众缓冲时间）
        Activity activity = activityMapper.selectById(ticket.getActivityId());
        if (activity == null) {
            return Result.error("活动不存在");
        }
        LocalDateTime now = LocalDateTime.now();
        if (activity.getStatus() != null && activity.getStatus() == 2) {
            return Result.error("活动已结束，无法核销");
        }
        if (activity.getStartTime() != null && now.isBefore(activity.getStartTime().minusHours(1))) {
            return Result.error("活动未开始，可在开始前1小时起验票入场");
        }
        if (activity.getEndTime() != null && !now.isBefore(activity.getEndTime())) {
            return Result.error("活动已结束，该票已过期，无法核销");
        }

        // 4. 标记电子票为已核销（带 status=0 条件：并发核销时只有一个请求能成功，防止重复入场）
        int rows = ticketMapper.update(null, new LambdaUpdateWrapper<Ticket>()
                .eq(Ticket::getId, ticket.getId())
                .eq(Ticket::getStatus, 0)
                .set(Ticket::getStatus, 1)
                .set(Ticket::getUsedTime, LocalDateTime.now()));
        if (rows == 0) {
            return Result.error("该票已核销，请勿重复入场");
        }


        // 5. 写核销记录（谁核销的、什么时候）
        CheckinRecord record = new CheckinRecord();
        record.setTicketId(ticket.getId());
        record.setActivityId(ticket.getActivityId());
        record.setUserId(ticket.getUserId());
        record.setTicketCode(ticket.getTicketCode());
        record.setTicketName(ticket.getTicketName());
        record.setCheckerId(checkerId);
        record.setCreateTime(LocalDateTime.now());
        checkinRecordMapper.insert(record);

        return Result.success("核销成功");
    }

    @Override
    public Result<Page<CheckinRecord>> records(Long activityId, long pageNum, long pageSize, SysUser user) {
        LambdaQueryWrapper<CheckinRecord> wrapper = new LambdaQueryWrapper<>();
        if (activityId != null) {
            wrapper.eq(CheckinRecord::getActivityId, activityId);
        }
        // 组织者仅可见本组织活动的核销记录
        if (user != null && user.getRole() != null && user.getRole() == UserRole.ORGANIZER) {
            wrapper.inSql(CheckinRecord::getActivityId,
                    "SELECT id FROM activity WHERE organizer_id = " + user.getId());
        }
        wrapper.orderByDesc(CheckinRecord::getCreateTime);
        Page<CheckinRecord> page = new Page<>(pageNum, pageSize);
        checkinRecordMapper.selectPage(page, wrapper);
        fillNames(page.getRecords());
        return Result.success(page);
    }

    /** 回填展示字段：活动名称、持票人姓名、核销员姓名（按 ID 批量查询，避免 N+1） */
    private void fillNames(List<CheckinRecord> list) {
        if (list == null || list.isEmpty()) {
            return;
        }
        Set<Long> actIds = list.stream().map(CheckinRecord::getActivityId).collect(Collectors.toSet());
        Set<Long> holderIds = list.stream().map(CheckinRecord::getUserId).collect(Collectors.toSet());
        Set<Long> checkerIds = list.stream().map(CheckinRecord::getCheckerId).collect(Collectors.toSet());

        Map<Long, Activity> actMap = activityMapper.selectBatchIds(actIds).stream()
                .collect(Collectors.toMap(Activity::getId, Function.identity()));
        Map<Long, SysUser> holderMap = sysUserMapper.selectBatchIds(holderIds).stream()
                .collect(Collectors.toMap(SysUser::getId, Function.identity()));
        Map<Long, SysUser> checkerMap = sysUserMapper.selectBatchIds(checkerIds).stream()
                .collect(Collectors.toMap(SysUser::getId, Function.identity()));

        for (CheckinRecord r : list) {
            Activity a = actMap.get(r.getActivityId());
            if (a != null) {
                r.setActivityTitle(a.getTitle());
            }
            SysUser h = holderMap.get(r.getUserId());
            if (h != null) {
                r.setUserName(displayName(h));
            }
            SysUser c = checkerMap.get(r.getCheckerId());
            if (c != null) {
                r.setCheckerName(displayName(c));
            }
        }
    }

    /** 优先展示真实姓名，未填写时回退登录账号 */
    private String displayName(SysUser u) {
        return (u.getName() != null && !u.getName().isEmpty()) ? u.getName() : u.getUsername();
    }
}

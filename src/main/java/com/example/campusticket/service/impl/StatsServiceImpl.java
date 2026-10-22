package com.example.campusticket.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.campusticket.common.Result;
import com.example.campusticket.common.UserRole;
import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.CheckinRecord;
import com.example.campusticket.entity.SysUser;
import com.example.campusticket.entity.Ticket;
import com.example.campusticket.entity.TicketOrder;
import com.example.campusticket.mapper.ActivityMapper;
import com.example.campusticket.mapper.CheckinRecordMapper;
import com.example.campusticket.mapper.SysUserMapper;
import com.example.campusticket.mapper.TicketMapper;
import com.example.campusticket.mapper.TicketOrderMapper;
import com.example.campusticket.service.StatsService;
import com.example.campusticket.vo.ActivityStatsVO;
import com.example.campusticket.vo.CertificateVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class StatsServiceImpl implements StatsService {

    @Autowired
    private ActivityMapper activityMapper;

    @Autowired
    private TicketOrderMapper ticketOrderMapper;

    @Autowired
    private CheckinRecordMapper checkinRecordMapper;

    @Autowired
    private TicketMapper ticketMapper;

    @Autowired
    private SysUserMapper sysUserMapper;

    @Override
    public Result<ActivityStatsVO> activityStats(Long activityId, Long userId) {
        Activity activity = activityMapper.selectById(activityId);
        if (activity == null) {
            return Result.error("活动不存在");
        }
        // 权限：管理员 或 该活动的组织者 才能看统计
        SysUser user = sysUserMapper.selectById(userId);
        if (user.getRole() != UserRole.ADMIN && !activity.getOrganizerId().equals(userId)) {
            return Result.error("无权限查看该活动统计");
        }

        // 已售出 = ticket_order 表中该活动的订单数
        Long soldCount = ticketOrderMapper.selectCount(
                new LambdaQueryWrapper<TicketOrder>().eq(TicketOrder::getActivityId, activityId));
        // 已核销 = checkin_record 表中该活动的记录数
        Long checkedCount = checkinRecordMapper.selectCount(
                new LambdaQueryWrapper<CheckinRecord>().eq(CheckinRecord::getActivityId, activityId));

        ActivityStatsVO vo = new ActivityStatsVO();
        vo.setActivityId(activity.getId());
        vo.setActivityTitle(activity.getTitle());
        vo.setTotalStock(activity.getTotalStock());
        vo.setRemainStock(activity.getRemainStock());
        vo.setSoldCount(soldCount);
        vo.setCheckedCount(checkedCount);
        // 出勤率 = 已核销 / 已售出（售出为 0 时按 0 处理，避免除零）
        double rate = soldCount == 0 ? 0.0 : checkedCount * 100.0 / soldCount;
        vo.setAttendanceRate(String.format("%.1f%%", rate));
        return Result.success(vo);
    }

    @Override
    public Result<CertificateVO> certificate(Long ticketId, Long userId) {
        Ticket ticket = ticketMapper.selectById(ticketId);
        if (ticket == null) {
            return Result.error("票券不存在");
        }
        // 只能生成自己的证书
        if (!ticket.getUserId().equals(userId)) {
            return Result.error("无权查看他人证书");
        }
        // 必须已核销入场才能生成签到证书
        if (ticket.getStatus() != 1) {
            return Result.error("该票未核销，无法生成签到证书");
        }

        SysUser student = sysUserMapper.selectById(ticket.getUserId());
        Activity activity = activityMapper.selectById(ticket.getActivityId());

        CertificateVO vo = new CertificateVO();
        // 证书编号规则：CERT + 活动ID + 票号，全局唯一
        vo.setCertificateNo("CERT-" + activity.getId() + "-" + ticket.getTicketCode());
        vo.setStudentName(student.getName());
        vo.setActivityTitle(activity.getTitle());
        vo.setLocation(activity.getLocation());
        vo.setActivityStartTime(activity.getStartTime());
        vo.setActivityEndTime(activity.getEndTime());
        vo.setCheckinTime(ticket.getUsedTime());
        return Result.success(vo);
    }
}

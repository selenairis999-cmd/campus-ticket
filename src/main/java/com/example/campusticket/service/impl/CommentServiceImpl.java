package com.example.campusticket.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.common.UserContext;
import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.ActivityComment;
import com.example.campusticket.entity.SysUser;
import com.example.campusticket.entity.Ticket;
import com.example.campusticket.entity.TicketOrder;
import com.example.campusticket.mapper.ActivityCommentMapper;
import com.example.campusticket.mapper.ActivityMapper;
import com.example.campusticket.mapper.TicketMapper;
import com.example.campusticket.mapper.TicketOrderMapper;
import com.example.campusticket.service.CommentService;
import com.example.campusticket.vo.SentimentStatsVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Service
public class CommentServiceImpl implements CommentService {

    @Autowired
    private ActivityCommentMapper commentMapper;

    @Autowired
    private ActivityMapper activityMapper;

    @Autowired
    private TicketOrderMapper ticketOrderMapper;

    @Autowired
    private TicketMapper ticketMapper;

    @Override
    public Page<ActivityComment> listByActivity(Long activityId, Integer pageNum, Integer pageSize) {
        LambdaQueryWrapper<ActivityComment> qw = new LambdaQueryWrapper<>();
        qw.eq(ActivityComment::getActivityId, activityId)
                // 追评紧跟其主评：按"组"倒序（新主评在前），组内主评在前、追评按时间正序
                .last("ORDER BY IF(parent_id > 0, parent_id, id) DESC, parent_id ASC, id ASC");
        return commentMapper.selectPage(new Page<>(pageNum, pageSize), qw);
    }

    @Override
    public SentimentStatsVO stats(Long activityId) {
        QueryWrapper<ActivityComment> qw = new QueryWrapper<>();
        qw.select("sentiment", "count(*) as cnt")
                .eq("activity_id", activityId)
                .groupBy("sentiment");
        List<Map<String, Object>> maps = commentMapper.selectMaps(qw);

        int pos = 0, neu = 0, neg = 0, pending = 0;
        for (Map<String, Object> m : maps) {
            Object sv = m.get("sentiment");
            int c = ((Number) m.get("cnt")).intValue();
            if (sv == null) {            // 待离线分析的评论，不计入情感分布
                pending += c;
                continue;
            }
            int s = ((Number) sv).intValue();
            if (s == 9) continue;        // 无效评论（纯标点/超短，9/17 新增），不计入统计
            if (s == 2) pos += c;
            else if (s == 1) neu += c;
            else neg += c;
        }
        int analyzed = pos + neu + neg;
        int total = analyzed + pending;
        SentimentStatsVO vo = new SentimentStatsVO();
        vo.setActivityId(activityId);
        vo.setTotal(total);              // 评论总数（含待分析）
        vo.setPosCount(pos);
        vo.setNeuCount(neu);
        vo.setNegCount(neg);
        // 好评率 = 好评 / 已分析评论数（待分析的不参与）
        vo.setPositiveRate(analyzed == 0 ? "0.0" : String.format("%.1f", pos * 100.0 / analyzed));
        return vo;
    }


    @Override
    public String addComment(Long activityId, String content, Long parentId) {
        if (activityId == null || content == null || content.isBlank()) {
            return "评论内容不能为空";
        }
        if (content.length() > 200) {
            return "评论不能超过200字";
        }
        Activity activity = activityMapper.selectById(activityId);
        if (activity == null) {
            return "活动不存在";
        }
        SysUser user = UserContext.get();
        boolean isFollow = parentId != null && parentId > 0;

        // 已核销（到场）票数 = 可发主评次数（一张已核销票一次评价）
        Long ticketCount = ticketMapper.selectCount(
                new LambdaQueryWrapper<Ticket>()
                        .eq(Ticket::getUserId, user.getId())
                        .eq(Ticket::getActivityId, activityId)
                        .eq(Ticket::getStatus, 1));
        if (ticketCount == null || ticketCount == 0) {
            return "只有已到场核销（参加过活动）的用户才能评论";
        }

        if (isFollow) {
            // ---- 追评：校验主评存在、归属本人、追评次数 < 2 ----
            ActivityComment parent = commentMapper.selectById(parentId);
            if (parent == null || !parent.getActivityId().equals(activityId)) {
                return "被追评的评论不存在";
            }
            if (!parent.getUserId().equals(user.getId())) {
                return "只能追评自己的评论";
            }
            if (parent.getParentId() != null && parent.getParentId() > 0) {
                return "只能对主评论追评";
            }
            Long followCount = commentMapper.selectCount(
                    new LambdaQueryWrapper<ActivityComment>()
                            .eq(ActivityComment::getParentId, parentId));
            if (followCount != null && followCount >= 2) {
                return "每条评价最多追评2次";
            }
        } else {
            // ---- 主评：已发主评数 < 购票数 ----
            Long mainCount = commentMapper.selectCount(
                    new LambdaQueryWrapper<ActivityComment>()
                            .eq(ActivityComment::getActivityId, activityId)
                            .eq(ActivityComment::getUserId, user.getId())
                            .eq(ActivityComment::getParentId, 0L));
            if (mainCount != null && mainCount >= ticketCount) {
                return "评价次数已用完（每张票可评价1次）";
            }
        }

        ActivityComment c = new ActivityComment();
        c.setActivityId(activityId);
        c.setUserId(user.getId());
        c.setUsername(user.getUsername());
        c.setContent(content.trim());
        c.setParentId(isFollow ? parentId : 0L);
        c.setSentiment(null);            // 情感留空，离线模型分析后回填
        c.setCreateTime(LocalDateTime.now());
        commentMapper.insert(c);
        return null;
    }

    @Override
    public Map<String, Object> commentQuota(Long activityId) {
        SysUser user = UserContext.get();
        // 已核销（到场）票数
        Long ticketCount = ticketMapper.selectCount(
                new LambdaQueryWrapper<Ticket>()
                        .eq(Ticket::getUserId, user.getId())
                        .eq(Ticket::getActivityId, activityId)
                        .eq(Ticket::getStatus, 1));
        Long mainCount = commentMapper.selectCount(
                new LambdaQueryWrapper<ActivityComment>()
                        .eq(ActivityComment::getActivityId, activityId)
                        .eq(ActivityComment::getUserId, user.getId())
                        .eq(ActivityComment::getParentId, 0L));
        long remain = Math.max(0, (ticketCount == null ? 0 : ticketCount) - (mainCount == null ? 0 : mainCount));
        Map<String, Object> map = new java.util.HashMap<>();
        map.put("ticketCount", ticketCount == null ? 0 : ticketCount);
        map.put("mainCount", mainCount == null ? 0 : mainCount);
        map.put("remain", remain);
        return map;
    }
}

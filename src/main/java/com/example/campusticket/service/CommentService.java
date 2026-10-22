package com.example.campusticket.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.entity.ActivityComment;
import com.example.campusticket.vo.SentimentStatsVO;

import java.util.Map;

public interface CommentService {
    Page<ActivityComment> listByActivity(Long activityId, Integer pageNum, Integer pageSize);
    SentimentStatsVO stats(Long activityId);

    /**
     * 发表评论/追评（sentiment 留空，待离线模型分析回填）
     * 主评：parentId 为空或 0，次数上限=该用户该活动购票数
     * 追评：parentId 为主评ID，每条主评最多追评 2 次
     * @return null 表示成功，否则返回错误信息
     */
    String addComment(Long activityId, String content, Long parentId);

    /** 当前用户对该活动还能发几条主评（购票数 - 已发主评数） */
    Map<String, Object> commentQuota(Long activityId);
}

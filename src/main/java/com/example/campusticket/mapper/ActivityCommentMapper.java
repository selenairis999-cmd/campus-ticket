package com.example.campusticket.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.campusticket.entity.ActivityComment;
import com.example.campusticket.vo.CommentRankVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface ActivityCommentMapper extends BaseMapper<ActivityComment> {

    /** 各活动满意度排行（按好评数降序，仅统计已分析评论；已删除活动不显示） */
    @Select("SELECT c.activity_id AS activityId, a.title AS title, " +
            "COUNT(*) AS total, " +
            "SUM(CASE WHEN c.sentiment = 2 THEN 1 ELSE 0 END) AS posCount, " +
            "SUM(CASE WHEN c.sentiment = 1 THEN 1 ELSE 0 END) AS neuCount, " +
            "SUM(CASE WHEN c.sentiment = 0 THEN 1 ELSE 0 END) AS negCount " +
            "FROM activity_comment c INNER JOIN activity a ON c.activity_id = a.id " +
            "WHERE c.sentiment IS NOT NULL AND c.sentiment <> 9 " +
            "GROUP BY c.activity_id, a.title ORDER BY posCount DESC, total DESC")
    List<CommentRankVO> selectActivityRanking();
}

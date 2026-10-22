package com.example.campusticket.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("activity_comment")
public class ActivityComment {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long activityId;
    private Long userId;
    private String username;
    private String content;
    private Integer sentiment;   // 0差评 1中评 2好评（模型预测值）
    private Long parentId;       // 0=主评论；>0=追评，指向所属主评ID（限制每张票1条主评、每条主评追评2次）
    private LocalDateTime createTime;
}

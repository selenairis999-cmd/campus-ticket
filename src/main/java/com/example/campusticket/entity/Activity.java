package com.example.campusticket.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("activity")
public class Activity {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String title;            // 活动标题
    private String description;      // 活动详情
    private String location;         // 活动地点
    private LocalDateTime startTime; // 活动开始时间
    private LocalDateTime endTime;   // 活动结束时间
    private LocalDateTime signStartTime; // 抢票开始时间
    private LocalDateTime signEndTime;   // 抢票结束时间
    private Long organizerId;        // 组织者用户ID
    private Integer status;          // 状态 0未开始 1进行中 2已结束
    private Integer totalStock;      // 总库存
    private Integer remainStock;     // 剩余库存
    private Integer version;         // 乐观锁版本号
    private LocalDateTime createTime; // 创建时间
}

package com.example.campusticket.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("grab_log")
public class GrabLog {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long userId;          // 抢票用户ID
    private String username;      // 用户名（冗余）
    private Long activityId;      // 活动ID
    private String ip;            // 客户端IP
    private String userAgent;     // 浏览器UA
    private String result;        // SUCCESS/STOCK_EMPTY/...（见枚举注释）
    private LocalDateTime createTime; // 请求时间（毫秒精度）

    @TableField(exist = false)
    private String activityTitle; // 活动名称（联表填充，非表字段）
}

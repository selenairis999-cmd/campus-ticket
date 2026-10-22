package com.example.campusticket.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("eticket")
public class Ticket {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long orderId;      // 关联订单ID
    private Long userId;       // 持票人ID
    private Long activityId;   // 活动ID
    private String ticketName; // 票种名称（多票种）
    private String ticketCode; // 唯一票号
    private String qrContent;  // 二维码内容
    private Integer status;    // 0-未使用 1-已核销 2-已作废
    private LocalDateTime createTime;
    private LocalDateTime usedTime;
    @TableField(exist = false)
    private LocalDateTime activityStartTime; // 活动开始时间（联表填充，非表字段）
    @TableField(exist = false)
    private String activityTitle;            // 活动名称（联表填充，非表字段）
    @TableField(exist = false)
    private LocalDateTime activityEndTime;   // 活动结束时间（联表填充，非表字段；用于判断票是否过期）

}

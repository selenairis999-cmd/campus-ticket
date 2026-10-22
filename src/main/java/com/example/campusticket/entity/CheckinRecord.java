package com.example.campusticket.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("checkin_record")
public class CheckinRecord {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long ticketId;    // 电子票ID
    private Long activityId;  // 活动ID
    private Long userId;      // 持票人ID
    private String ticketCode;// 票号
    private String ticketName; // 票种名称（多票种）
    private Long checkerId;   // 核销员ID
    private LocalDateTime createTime; // 核销时间

    /** 以下为展示用冗余字段（不落库）：查询时按 ID 回填对应名称 */
    @TableField(exist = false)
    private String activityTitle; // 活动名称
    @TableField(exist = false)
    private String userName;      // 持票人姓名
    @TableField(exist = false)
    private String checkerName;   // 核销员姓名
}

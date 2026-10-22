package com.example.campusticket.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 票种实体 —— 映射数据库 ticket 表（票种/库存表，多票种功能）
 * 注意：不要和 entity/Ticket.java 混淆！Ticket 映射的是 eticket 表（电子票）
 */
@Data
@TableName("ticket")
public class TicketType {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long activityId;     // 关联活动
    private String ticketName;   // 票种名称（组织者自定义，如 普通票/前排票）
    private Integer totalStock;  // 该票种总库存
    private Integer remainStock; // 该票种剩余库存
    private Integer version;     // 乐观锁版本号（每票种独立）
    private LocalDateTime createTime;
}

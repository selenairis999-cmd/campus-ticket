package com.example.campusticket.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("sys_user")
public class SysUser {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String username;
    private String password;
    private String name;
    private String phone;
    private Integer status;    // 1=正常 0=封禁
    private Integer role;      // 角色：1学生 2组织者 3核销员 0管理员
    private LocalDateTime banExpireTime; // 封禁截止时间：NULL 表示永久（仅 status=0 时有意义），到期自动视为解封
    private String banReason;            // 封禁原因留痕（在线命中/离线检出/人工研判）
    private LocalDateTime createTime;

}

package com.example.campusticket.vo;

import lombok.Data;

/** 登录成功返回给前端的数据：令牌 + 用户基本信息 */
@Data
public class LoginVO {
    private String token;
    private Long userId;
    private String username;
    private String name;
    private Integer role;
}

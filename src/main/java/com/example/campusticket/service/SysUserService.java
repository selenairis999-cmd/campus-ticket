package com.example.campusticket.service;

import com.example.campusticket.entity.SysUser;

public interface SysUserService {
    /**
     * 登录校验
     */
    SysUser login(String username, String password);

    /**
     * 注册（默认学生角色）
     * @return null 表示成功，否则返回错误信息
     */
    String register(String username, String password, String name, String phone);

    /**
     * 忘记密码：校验用户名+手机号后重置
     * @return null 表示成功，否则返回错误信息
     */
    String resetPassword(String username, String phone, String newPassword);
}

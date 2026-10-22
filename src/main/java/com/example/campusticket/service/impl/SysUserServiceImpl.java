package com.example.campusticket.service.impl;

import cn.hutool.crypto.digest.BCrypt;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.campusticket.entity.SysUser;
import com.example.campusticket.mapper.SysUserMapper;
import com.example.campusticket.service.SysUserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.time.LocalDateTime;

@Service
public class SysUserServiceImpl implements SysUserService {

    @Autowired
    private SysUserMapper sysUserMapper;

    @Override
    public SysUser login(String username, String password) {
        // 根据用户名查询用户
        LambdaQueryWrapper<SysUser> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(SysUser::getUsername, username);
        SysUser user = sysUserMapper.selectOne(queryWrapper);

        // 用户不存在
        if (user == null) {
            return null;
        }

        // 校验密码：BCrypt 哈希比对（所有账号密码均以 BCrypt 哈希落库，不再兼容明文）
        String stored = user.getPassword();
        boolean ok;
        try {
            ok = stored != null && stored.startsWith("$2") && BCrypt.checkpw(password, stored);
        } catch (Exception e) {
            ok = false;
        }
        return ok ? user : null;
    }

    @Override
    public String register(String username, String password, String name, String phone) {
        // 参数非空校验
        if (username == null || username.isBlank() || password == null || password.isBlank()
                || name == null || name.isBlank() || phone == null || phone.isBlank()) {
            return "请填写完整信息";
        }
        // 用户名唯一
        LambdaQueryWrapper<SysUser> nameWrapper = new LambdaQueryWrapper<>();
        nameWrapper.eq(SysUser::getUsername, username);
        if (sysUserMapper.selectCount(nameWrapper) > 0) {
            return "用户名已存在";
        }
        // 手机号唯一
        LambdaQueryWrapper<SysUser> phoneWrapper = new LambdaQueryWrapper<>();
        phoneWrapper.eq(SysUser::getPhone, phone);
        if (sysUserMapper.selectCount(phoneWrapper) > 0) {
            return "该手机号已注册";
        }
        // 密码 BCrypt 加密后入库
        SysUser user = new SysUser();
        user.setUsername(username);
        user.setPassword(BCrypt.hashpw(password));
        user.setName(name);
        user.setPhone(phone);
        user.setRole(1);       // 默认学生
        user.setStatus(1);     // 启用
        user.setCreateTime(LocalDateTime.now());
        sysUserMapper.insert(user);
        return null;
    }

    @Override
    public String resetPassword(String username, String phone, String newPassword) {
        if (newPassword == null || newPassword.isBlank()) {
            return "请输入新密码";
        }
        // 按用户名查用户
        LambdaQueryWrapper<SysUser> queryWrapper = new LambdaQueryWrapper<>();
        queryWrapper.eq(SysUser::getUsername, username);
        SysUser user = sysUserMapper.selectOne(queryWrapper);
        if (user == null) {
            return "用户名不存在";
        }
        // 手机号必须匹配（防别人乱改）
        if (phone == null || !phone.equals(user.getPhone())) {
            return "手机号与注册信息不匹配";
        }
        // 新密码 BCrypt 加密后更新
        SysUser update = new SysUser();
        update.setId(user.getId());
        update.setPassword(BCrypt.hashpw(newPassword));
        sysUserMapper.updateById(update);
        return null;
    }
}

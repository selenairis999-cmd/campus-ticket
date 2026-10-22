package com.example.campusticket.controller;

import com.example.campusticket.common.JwtUtil;
import com.example.campusticket.common.Result;
import com.example.campusticket.entity.SysUser;
import com.example.campusticket.mapper.SysUserMapper;
import com.example.campusticket.risk.RiskService;
import com.example.campusticket.service.SysUserService;
import com.example.campusticket.vo.LoginVO;
import cn.hutool.jwt.JWT;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/auth")
public class LoginController {

    @Autowired
    private SysUserService sysUserService;

    @Autowired
    private SysUserMapper sysUserMapper;

    @Autowired
    private JwtUtil jwtUtil;

    @Autowired
    private RiskService riskService;

    @PostMapping("/login")
    public Result<LoginVO> login(@RequestParam String username, @RequestParam String password) {
        SysUser user = sysUserService.login(username, password);
        if (user == null) {
            return Result.error("用户名或密码错误");
        }
        // 封禁校验（R0 黑名单）：密码正确也拒绝登录，避免封禁形同虚设
        String banReason = riskService.checkBan(user.getId());
        if (banReason != null) {
            return Result.error(banReason);
        }
        // 登录成功，签发令牌
        String token = jwtUtil.generateToken(user.getId(), user.getRole());
        LoginVO vo = new LoginVO();
        vo.setToken(token);
        vo.setUserId(user.getId());
        vo.setUsername(user.getUsername());
        vo.setName(user.getName());
        vo.setRole(user.getRole());
        return Result.success(vo);
    }

    @PostMapping("/register")
    public Result<String> register(@RequestParam String username, @RequestParam String password,
                                   @RequestParam String name, @RequestParam String phone) {
        String err = sysUserService.register(username, password, name, phone);
        if (err != null) {
            return Result.error(err);
        }
        return Result.success("注册成功");
    }

    @PostMapping("/forgot")
    public Result<String> forgot(@RequestParam String username, @RequestParam String phone,
                                 @RequestParam String newPassword) {
        String err = sysUserService.resetPassword(username, phone, newPassword);
        if (err != null) {
            return Result.error(err);
        }
        return Result.success("密码重置成功");
    }

    /**
     * 令牌续期：用当前仍有效的 token 换取新 token（滑动过期）。
     * 前端在 token 临近过期（5 分钟内）时主动调用，避免用户操作中途被踢到登录页。
     * token 已过期或签名非法则返回 401，前端跳转登录。
     */
    @PostMapping("/refresh")
    public Result<LoginVO> refresh(HttpServletRequest request) {
        String token = request.getHeader("token");
        if (token == null || token.isBlank()) {
            return Result.error(401, "未登录");
        }
        try {
            JWT jwt = jwtUtil.parse(token);   // 校验签名 + 有效期，失败抛异常
            Long userId = ((Number) jwt.getPayload("userId")).longValue();
            SysUser user = sysUserMapper.selectById(userId);
            // 账号被删或已封禁 → 不续期
            if (user == null || user.getStatus() == null || user.getStatus() != 1) {
                return Result.error(401, "账号状态异常，请重新登录");
            }
            String newToken = jwtUtil.generateToken(user.getId(), user.getRole());
            LoginVO vo = new LoginVO();
            vo.setToken(newToken);
            vo.setUserId(user.getId());
            vo.setUsername(user.getUsername());
            vo.setName(user.getName());
            vo.setRole(user.getRole());
            return Result.success(vo);
        } catch (Exception e) {
            return Result.error(401, "登录已过期，请重新登录");
        }
    }
}

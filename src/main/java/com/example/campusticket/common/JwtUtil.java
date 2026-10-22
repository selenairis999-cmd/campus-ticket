package com.example.campusticket.common;

import cn.hutool.jwt.JWT;
import cn.hutool.jwt.JWTUtil;
import cn.hutool.jwt.JWTValidator;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.Date;

/**
 * JWT 工具类：生成与解析登录令牌
 * 原理：令牌携带 userId + role，用密钥签名防伪造，exp 过期时间防止长期有效被重放
 */
@Component
public class JwtUtil {

    @Value("${jwt.secret}")
    private String secret;

    /** 令牌有效期：2 小时 */
    private static final long EXPIRE = 2 * 60 * 60 * 1000L;

    /** 登录成功后生成令牌 */
    public String generateToken(Long userId, Integer role) {
        return JWT.create()
                .setPayload("userId", userId)
                .setPayload("role", role)
                .setExpiresAt(new Date(System.currentTimeMillis() + EXPIRE))
                .setKey(secret.getBytes())
                .sign();
    }

    /** 解析并校验令牌（签名 + 有效期），失败会抛异常 */
    public JWT parse(String token) {
        JWT jwt = JWTUtil.parseToken(token);
        jwt.setKey(secret.getBytes());
        if (!jwt.verify()) {
            throw new RuntimeException("Token 签名校验失败");
        }
        JWTValidator.of(token).validateDate(); // 校验是否过期
        return jwt;
    }

    /** 从令牌中取用户ID */
    public Long getUserId(String token) {
        Object uid = parse(token).getPayload("userId");
        return ((Number) uid).longValue();
    }

    /** 从令牌中取角色 */
    public Integer getRole(String token) {
        Object role = parse(token).getPayload("role");
        return ((Number) role).intValue();
    }
}

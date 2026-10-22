package com.example.campusticket.config;

import com.example.campusticket.annotation.RequireRole;
import com.example.campusticket.common.JwtUtil;
import com.example.campusticket.common.Result;
import com.example.campusticket.common.UserContext;
import com.example.campusticket.entity.SysUser;
import com.example.campusticket.mapper.SysUserMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * 登录鉴权 + 角色权限拦截器
 * 流程：取 token -> 解析用户 -> 封禁校验 -> 存入上下文 -> 校验角色注解
 */
@Component
public class AuthInterceptor implements HandlerInterceptor {

    /** 封禁提示中的解封时间格式（与 RiskService 保持一致） */
    private static final DateTimeFormatter BAN_TIME = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    @Autowired
    private JwtUtil jwtUtil;

    @Autowired
    private SysUserMapper sysUserMapper;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        // 接口判定：只有命中 Controller 方法的请求才需要鉴权；
        // 静态资源、SPA 页面回退（404 转发 /index.html）不是 HandlerMethod，直接放行
        // 修复：原先仅凭 "/api" 前缀标记鉴权，去掉前缀的裸路径可绕过登录与角色校验
        if (!(handler instanceof HandlerMethod)) {
            return true;
        }

        // 兜底放行：登录等 /auth/ 开头的接口不做鉴权
        if (request.getRequestURI().startsWith("/auth/")) {
            return true;
        }

        // 放行 /error：404 时 Spring 会内部转发到 /error，避免被误拦成 401
        if (request.getRequestURI().startsWith("/error")) {
            return true;
        }
        // 1. 从请求头取 token 并解析（失败说明未登录/过期/被篡改）
        String token = request.getHeader("token");
        Long userId;
        try {
            userId = jwtUtil.getUserId(token);
        } catch (Exception e) {
            return writeJson(response, 401, Result.error(401, "未登录或登录已过期"));
        }

        // 2. 查数据库拿最新用户信息（角色、状态以数据库为准，改角色后立即生效）
        SysUser user = sysUserMapper.selectById(userId);
        if (user == null) {
            return writeJson(response, 401, Result.error(401, "用户不存在"));
        }

        // 2.1 封禁校验：status=0 且未到期（ban_expire_time 为空表示永久）→ 拒绝全部业务接口。
        // 原先只在登录与抢票入口校验封禁，被踢下线的账号仍可持旧令牌浏览活动、查看票券与评论；
        // 这里复用已查出的用户对象，零额外查询开销。
        if (user.getStatus() != null && user.getStatus() != 1) {
            LocalDateTime expire = user.getBanExpireTime();
            if (expire == null || expire.isAfter(LocalDateTime.now())) {
                UserContext.clear();
                String reason = user.getBanReason() != null ? user.getBanReason() : "违规行为";
                String msg = expire == null
                        ? "账号已被永久封禁（原因：" + reason + "），如有疑问请联系管理员申诉"
                        : "账号已被封禁，解封时间：" + expire.format(BAN_TIME) + "（原因：" + reason + "）";
                return writeJson(response, 401, Result.error(401, msg));
            }
        }
        UserContext.set(user);

        // 3. 角色校验：方法上有 @RequireRole 才校验，没有则直接放行
        if (handler instanceof HandlerMethod) {
            HandlerMethod handlerMethod = (HandlerMethod) handler;
            RequireRole requireRole = handlerMethod.getMethodAnnotation(RequireRole.class);
            if (requireRole == null) {
                requireRole = handlerMethod.getBeanType().getAnnotation(RequireRole.class);
            }
            if (requireRole != null) {
                boolean allowed = false;
                for (int role : requireRole.value()) {
                    if (user.getRole() != null && user.getRole() == role) {
                        allowed = true;
                        break;
                    }
                }
                if (!allowed) {
                    UserContext.clear();
                    return writeJson(response, 403, Result.error(403, "无权限访问"));
                }
            }
        }
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        // 请求结束清空上下文，防止线程池复用导致串号
        UserContext.clear();
    }

    /** 输出统一格式的错误响应 */
    private boolean writeJson(HttpServletResponse response, int code, Result<?> result) throws IOException {
        response.setStatus(code);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(new ObjectMapper().writeValueAsString(result));
        return false;
    }
}

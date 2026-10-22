package com.example.campusticket.config;

import com.example.campusticket.annotation.RequireRole;
import com.example.campusticket.common.JwtUtil;
import com.example.campusticket.common.UserContext;
import com.example.campusticket.common.UserRole;
import com.example.campusticket.entity.SysUser;
import com.example.campusticket.mapper.SysUserMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.web.method.HandlerMethod;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.when;

/**
 * 登录鉴权与封禁拦截单元测试（覆盖 R0 黑名单与角色校验）
 * 核心回归点：被封禁账号持"仍然有效"的旧令牌访问任意业务接口都应被 401 拒绝，
 * 而不是只在登录与抢票入口校验。
 * 请求/响应用 Spring 的 Mock 实现（真实行为），只有 JwtUtil 与 SysUserMapper 用 Mockito 打桩。
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class AuthInterceptorTest {

    @Mock private JwtUtil jwtUtil;
    @Mock private SysUserMapper sysUserMapper;

    private AuthInterceptor interceptor;
    private MockHttpServletRequest request;
    private MockHttpServletResponse response;

    /** 供 HandlerMethod 解析的测试用控制器 */
    @SuppressWarnings("unused")
    static class SampleController {
        @RequireRole(UserRole.STUDENT)
        public void studentOnly() {
        }

        public void anyLoggedIn() {
        }

        @RequireRole({UserRole.CHECKER, UserRole.ORGANIZER})
        public void checkerOrOrganizer() {
        }
    }

    @BeforeEach
    void setUp() {
        interceptor = new AuthInterceptor();
        org.springframework.test.util.ReflectionTestUtils.setField(interceptor, "jwtUtil", jwtUtil);
        org.springframework.test.util.ReflectionTestUtils.setField(interceptor, "sysUserMapper", sysUserMapper);
        request = new MockHttpServletRequest();
        response = new MockHttpServletResponse();
    }

    @AfterEach
    void tearDown() {
        UserContext.clear();
    }

    private HandlerMethod handler(String method) throws Exception {
        return new HandlerMethod(new SampleController(), SampleController.class.getMethod(method));
    }

    private SysUser user(int role, int status) {
        SysUser u = new SysUser();
        u.setId(3L);
        u.setUsername("student01");
        u.setName("李同学");
        u.setRole(role);
        u.setStatus(status);
        return u;
    }

    /** 模拟"带一个仍有效的旧令牌"的请求 */
    private void stubToken(String token, Long userId) {
        request.setRequestURI("/activity/page");
        request.addHeader("token", token);
        when(jwtUtil.getUserId(token)).thenReturn(userId);
    }

    @Test
    @DisplayName("非 HandlerMethod（静态资源/SPA 回退）直接放行")
    void nonHandlerShouldPass() throws Exception {
        assertTrue(interceptor.preHandle(request, response, new Object()));
    }

    @Test
    @DisplayName("/auth/ 与 /error 前缀放行")
    void authAndErrorPathsShouldPass() throws Exception {
        request.setRequestURI("/auth/login");
        assertTrue(interceptor.preHandle(request, response, handler("anyLoggedIn")));

        request.setRequestURI("/error");
        assertTrue(interceptor.preHandle(request, response, handler("anyLoggedIn")));
    }

    @Test
    @DisplayName("无 token → 401 未登录或登录已过期")
    void missingTokenShouldReturn401() throws Exception {
        request.setRequestURI("/activity/page");
        when(jwtUtil.getUserId(null)).thenThrow(new RuntimeException("token 为空"));

        assertFalse(interceptor.preHandle(request, response, handler("anyLoggedIn")));
        assertEquals(401, response.getStatus());
        assertTrue(response.getContentAsString().contains("未登录或登录已过期"));
    }

    @Test
    @DisplayName("正常用户访问无角色注解接口 → 放行且上下文写入用户")
    void normalUserShouldPass() throws Exception {
        stubToken("valid-token", 3L);
        when(sysUserMapper.selectById(3L)).thenReturn(user(UserRole.STUDENT, 1));

        assertTrue(interceptor.preHandle(request, response, handler("anyLoggedIn")));
        assertNotNull(UserContext.get());
        assertEquals("student01", UserContext.get().getUsername());
    }

    @Test
    @DisplayName("用户不存在（已删除）→ 401")
    void deletedUserShouldReturn401() throws Exception {
        stubToken("valid-token", 3L);
        when(sysUserMapper.selectById(3L)).thenReturn(null);

        assertFalse(interceptor.preHandle(request, response, handler("anyLoggedIn")));
        assertEquals(401, response.getStatus());
        assertTrue(response.getContentAsString().contains("用户不存在"));
    }

    /**
     * P0 缺陷回归测试：修复前拦截器只校验 token 与角色，
     * 账号被封禁后其旧令牌仍可浏览活动、票券与评论。
     */
    @Test
    @DisplayName("【回归】封禁账号持旧令牌访问业务接口 → 401 账号已被封禁")
    void bannedUserWithOldTokenShouldBeRejected() throws Exception {
        stubToken("old-but-valid-token", 3L);
        SysUser banned = user(UserRole.STUDENT, 0);
        banned.setBanExpireTime(LocalDateTime.now().plusDays(7));
        banned.setBanReason("在线命中风控规则");
        when(sysUserMapper.selectById(3L)).thenReturn(banned);

        assertFalse(interceptor.preHandle(request, response, handler("anyLoggedIn")));
        assertEquals(401, response.getStatus());
        String body = response.getContentAsString();
        assertTrue(body.contains("账号已被封禁"), body);
        assertTrue(body.contains("在线命中风控规则"), body);
        assertNull(UserContext.get(), "被拦截时不应写入用户上下文");
    }

    @Test
    @DisplayName("永久封禁（ban_expire_time 为空）→ 401 且提示永久封禁")
    void permanentlyBannedUserShouldBeRejected() throws Exception {
        request.setRequestURI("/ticket/myList");
        request.addHeader("token", "old-token");
        when(jwtUtil.getUserId("old-token")).thenReturn(3L);
        SysUser banned = user(UserRole.STUDENT, 0);
        banned.setBanExpireTime(null);
        banned.setBanReason(null);
        when(sysUserMapper.selectById(3L)).thenReturn(banned);

        assertFalse(interceptor.preHandle(request, response, handler("anyLoggedIn")));
        assertEquals(401, response.getStatus());
        String body = response.getContentAsString();
        assertTrue(body.contains("账号已被永久封禁"), body);
        assertTrue(body.contains("违规行为"), "原因为空时应给出默认原因");
    }

    @Test
    @DisplayName("封禁已到期（ban_expire_time 已过）→ 放行，视为自动解封")
    void expiredBanShouldPass() throws Exception {
        stubToken("token", 3L);
        SysUser expired = user(UserRole.STUDENT, 0);
        expired.setBanExpireTime(LocalDateTime.now().minusMinutes(1));
        when(sysUserMapper.selectById(3L)).thenReturn(expired);

        assertTrue(interceptor.preHandle(request, response, handler("anyLoggedIn")));
    }

    @Test
    @DisplayName("角色不匹配 → 403 无权限访问")
    void wrongRoleShouldReturn403() throws Exception {
        request.setRequestURI("/risk/overview");
        request.addHeader("token", "token");
        when(jwtUtil.getUserId("token")).thenReturn(3L);
        when(sysUserMapper.selectById(3L)).thenReturn(user(UserRole.STUDENT, 1));

        assertFalse(interceptor.preHandle(request, response, handler("checkerOrOrganizer")));
        assertEquals(403, response.getStatus());
        assertTrue(response.getContentAsString().contains("无权限访问"));
        assertNull(UserContext.get());
    }

    @Test
    @DisplayName("角色匹配（多角色注解之一）→ 放行")
    void matchingRoleAmongManyShouldPass() throws Exception {
        request.setRequestURI("/checkin/records");
        request.addHeader("token", "token");
        when(jwtUtil.getUserId("token")).thenReturn(5L);
        SysUser checker = user(UserRole.CHECKER, 1);
        checker.setId(5L);
        when(sysUserMapper.selectById(5L)).thenReturn(checker);

        assertTrue(interceptor.preHandle(request, response, handler("checkerOrOrganizer")));
    }

    @Test
    @DisplayName("管理员(role=0) 访问管理员接口 → 放行")
    void adminShouldPass() throws Exception {
        request.setRequestURI("/comment/analyze");
        request.addHeader("token", "token");
        when(jwtUtil.getUserId("token")).thenReturn(1L);
        SysUser admin = user(UserRole.ADMIN, 1);
        admin.setId(1L);
        when(sysUserMapper.selectById(1L)).thenReturn(admin);

        assertTrue(interceptor.preHandle(request, response, handler("anyLoggedIn")));
    }

    @Test
    @DisplayName("请求结束后清空上下文，避免线程池复用串号")
    void afterCompletionShouldClearContext() throws Exception {
        stubToken("token", 3L);
        when(sysUserMapper.selectById(3L)).thenReturn(user(UserRole.STUDENT, 1));
        HandlerMethod handler = handler("anyLoggedIn");
        interceptor.preHandle(request, response, handler);
        assertNotNull(UserContext.get());

        interceptor.afterCompletion(request, response, handler, null);
        assertNull(UserContext.get());
    }

    @Test
    @DisplayName("角色以数据库为准：令牌里的角色被改后不影响鉴权结果")
    void roleShouldComeFromDatabase() throws Exception {
        request.setRequestURI("/checkin/records");
        request.addHeader("token", "token-claiming-admin");
        when(jwtUtil.getUserId("token-claiming-admin")).thenReturn(3L);
        // 令牌里 role=0，但数据库里该用户是学生 → 应以数据库为准被拒绝
        when(jwtUtil.getRole("token-claiming-admin")).thenReturn(UserRole.ADMIN);
        when(sysUserMapper.selectById(3L)).thenReturn(user(UserRole.STUDENT, 1));

        assertFalse(interceptor.preHandle(request, response, handler("checkerOrOrganizer")));
        assertEquals(403, response.getStatus());
    }
}

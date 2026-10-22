package com.example.campusticket.risk;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.example.campusticket.common.Result;
import com.example.campusticket.common.UserContext;
import com.example.campusticket.entity.GrabLog;
import com.example.campusticket.entity.SysUser;
import com.example.campusticket.mapper.GrabLogMapper;
import com.example.campusticket.mapper.SysUserMapper;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * 抢票风控门面：log（埋点）+ check（第3步接入拦截）
 * 原则：任何异常只打 warn，绝不向上抛——否则 @Transactional 抢票事务会被回滚
 */
@Slf4j
@Service
public class RiskService {

    @Autowired
    private GrabLogMapper grabLogMapper;

    @Autowired
    private RiskProperties riskProperties;

    @Autowired
    private RiskRuleEngine ruleEngine;

    @Autowired
    private SysUserMapper sysUserMapper;


    /** 埋点：记录一次抢票请求结果（成功/失败都记） */
    public void log(Long userId, Long activityId, String result) {
        try {
            GrabLog grabLog = new GrabLog();
            grabLog.setUserId(userId);
            SysUser user = UserContext.get();
            grabLog.setUsername(user != null ? user.getUsername() : null);
            grabLog.setActivityId(activityId);

            // 从当前请求线程取 IP/UA（Controller/Service 签名零改动）
            ServletRequestAttributes attrs =
                    (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
            if (attrs != null) {
                HttpServletRequest request = attrs.getRequest();
                grabLog.setIp(getClientIp(request));
                String ua = request.getHeader("User-Agent");
                grabLog.setUserAgent(ua != null && ua.length() > 500 ? ua.substring(0, 500) : ua);
            }

            grabLog.setResult(result);
            grabLog.setCreateTime(LocalDateTime.now());
            grabLogMapper.insert(grabLog);
        } catch (Exception e) {
            log.warn("风控日志写入失败: {}", e.getMessage());
        }
    }

    /**
     * 在线拦截判定：通过返回 null；命中返回拦截原因（并记 BANNED / RISK_BLOCKED 日志）
     * R0 黑名单（封禁账号）不受总开关控制、始终生效；R1/R2 受 enabled 开关控制
     * 风控异常 → 一律放行，不阻塞主流程
     */
    public String check(Long userId, Long activityId) {
        try {
            // R0 黑名单：封禁账号直接拒绝（限时到期自动放行）
            String banReason = checkBan(userId);
            if (banReason != null) {
                log(userId, activityId, "BANNED");
                return banReason;
            }
            if (!riskProperties.isEnabled()) {
                return null; // enabled=false：只记日志不拦截
            }
            String reason = ruleEngine.checkUser(userId, System.currentTimeMillis());
            if (reason != null) {
                log(userId, activityId, "RISK_BLOCKED");
                return reason;
            }
            // R2 同IP多账号（默认关，需 yml 打开 ip-rule-enabled）
            if (riskProperties.isIpRuleEnabled()) {
                ServletRequestAttributes attrs =
                        (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
                if (attrs != null) {
                    String ip = getClientIp(attrs.getRequest());
                    reason = ruleEngine.checkIp(ip, activityId, userId, System.currentTimeMillis());
                    if (reason != null) {
                        log(userId, activityId, "RISK_BLOCKED");
                        return reason;
                    }
                }
            }
            return null;
        } catch (Exception e) {
            log.warn("风控判定失败: {}", e.getMessage());
            return null;
        }
    }

    private String getClientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        if (ip != null && !ip.isEmpty() && !"unknown".equalsIgnoreCase(ip)) {
            return ip.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }

    // ==================== R0 黑名单：封禁判定与管理 ====================

    private static final DateTimeFormatter BAN_TIME = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    /**
     * 封禁判定（登录与抢票入口共用，不受风控总开关控制）
     * status=0 且（无截止时间 或 未到期）→ 封禁中，返回提示文案；否则 null 放行
     */
    public String checkBan(Long userId) {
        try {
            if (userId == null) {
                return null;
            }
            SysUser user = sysUserMapper.selectById(userId);
            if (user == null || user.getStatus() == null || user.getStatus() == 1) {
                return null;
            }
            LocalDateTime expire = user.getBanExpireTime();
            if (expire != null && expire.isBefore(LocalDateTime.now())) {
                return null; // 限时封禁到期，自动视为解封
            }
            String reason = StringUtils.hasText(user.getBanReason()) ? user.getBanReason() : "违规行为";
            if (expire == null) {
                return "账号已被永久封禁（原因：" + reason + "），如有疑问请联系管理员申诉";
            }
            return "账号已被封禁，解封时间：" + expire.format(BAN_TIME) + "（原因：" + reason + "）";
        } catch (Exception e) {
            log.warn("封禁判定失败: {}", e.getMessage());
            return null; // 判定异常不阻断主流程
        }
    }

    /** 封禁单个账号：days 为空或 ≤0 表示永久；管理员账号不允许封禁 */
    public Result<String> ban(Long userId, Integer days, String reason) {
        SysUser user = sysUserMapper.selectById(userId);
        if (user == null) {
            return Result.error("账号不存在");
        }
        if (user.getRole() != null && user.getRole() == 0) {
            return Result.error("不允许封禁管理员账号");
        }
        doBan(userId, days, reason);
        log.warn("封禁账号: userId={}, days={}, reason={}", userId, days, reason);
        return Result.success(days == null || days <= 0 ? "已永久封禁" : "已封禁 " + days + " 天");
    }

    /** 解封：恢复 status=1 并清空封禁信息（UpdateWrapper 显式 set，避免 MP 忽略 null 字段） */
    public Result<String> unban(Long userId) {
        SysUser user = sysUserMapper.selectById(userId);
        if (user == null) {
            return Result.error("账号不存在");
        }
        sysUserMapper.update(null, new LambdaUpdateWrapper<SysUser>()
                .eq(SysUser::getId, userId)
                .set(SysUser::getStatus, 1)
                .set(SysUser::getBanExpireTime, null)
                .set(SysUser::getBanReason, null));
        log.warn("解封账号: userId={}", userId);
        return Result.success("已解封");
    }

    /** 当前封禁名单（仅返回未到期的），密码字段置空防泄露 */
    public List<SysUser> listBanned() {
        List<SysUser> users = sysUserMapper.selectList(new LambdaQueryWrapper<SysUser>()
                .eq(SysUser::getStatus, 0)
                .and(w -> w.isNull(SysUser::getBanExpireTime)
                        .or().gt(SysUser::getBanExpireTime, LocalDateTime.now()))
                .orderByDesc(SysUser::getId));
        users.forEach(u -> u.setPassword(null));
        return users;
    }

    /** 批量封禁（离线检测报告导入）：按用户名封禁，返回结果说明 */
    public Result<String> banBatch(String usernamesRaw, Integer days, String reason) {
        if (!StringUtils.hasText(usernamesRaw)) {
            return Result.error("请输入要封禁的账号");
        }
        Set<String> names = new LinkedHashSet<>(Arrays.asList(usernamesRaw.split("[\\s,;，；]+")));
        names.removeIf(n -> !StringUtils.hasText(n));

        int banned = 0, skippedAdmin = 0;
        List<String> notFound = new ArrayList<>();
        for (String name : names) {
            SysUser user = sysUserMapper.selectOne(new LambdaQueryWrapper<SysUser>()
                    .eq(SysUser::getUsername, name));
            if (user == null) {
                notFound.add(name);
            } else if (user.getRole() != null && user.getRole() == 0) {
                skippedAdmin++;
            } else {
                doBan(user.getId(), days, reason);
                banned++;
            }
        }
        StringBuilder msg = new StringBuilder("成功封禁 " + banned + " 个账号");
        if (skippedAdmin > 0) {
            msg.append("，跳过管理员 ").append(skippedAdmin).append(" 个");
        }
        if (!notFound.isEmpty()) {
            msg.append("，未找到：").append(String.join("、", notFound));
        }
        log.warn("批量封禁: count={}, days={}, reason={}", banned, days, reason);
        return Result.success(msg.toString());
    }

    private void doBan(Long userId, Integer days, String reason) {
        boolean permanent = days == null || days <= 0;
        // UpdateWrapper 显式 set（永久时置 NULL）——updateById 会忽略 null 字段，限时改永久时清不掉旧到期时间
        sysUserMapper.update(null, new LambdaUpdateWrapper<SysUser>()
                .eq(SysUser::getId, userId)
                .set(SysUser::getStatus, 0)
                .set(SysUser::getBanExpireTime, permanent ? null : LocalDateTime.now().plusDays(days))
                .set(SysUser::getBanReason, StringUtils.hasText(reason) ? reason.trim() : "管理端人工封禁"));
    }
}

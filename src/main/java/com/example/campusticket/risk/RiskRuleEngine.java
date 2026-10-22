package com.example.campusticket.risk;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.concurrent.ConcurrentHashMap;

import java.util.Map;


/**
 * 在线规则引擎（单机简化实现，生产环境换 Redis 滑动窗口）
 * R1：单用户滑动窗口高频检测 + 惩罚名单
 */
@Component
public class RiskRuleEngine {

    @Autowired
    private RiskProperties properties;

    /** R1 窗口队列：u:{userId} -> 时间戳队列 */
    private final ConcurrentHashMap<String, Deque<Long>> userWindow = new ConcurrentHashMap<>();

    /** 惩罚名单：userId -> 解封时间戳(ms) */
    private final ConcurrentHashMap<Long, Long> punishList = new ConcurrentHashMap<>();

    /** R2 同IP同活动账号表：ip:{ip}:act:{activityId} -> {userId: 最后请求时间戳} */
    private final ConcurrentHashMap<String, Map<Long, Long>> ipAccounts = new ConcurrentHashMap<>();

    /**
     * 定时清理：每 5 分钟清除三个内存 Map 中的过期条目，防止长时间运行（含压测造数）导致内存泄漏。
     * 1) punishList：惩罚到期的条目
     * 2) userWindow：窗口外的时间戳；清理后队列为空则移除该用户 key
     * 3) ipAccounts：窗口外的账号；内层 map 为空则移除该 ip:activity key
     */
    @Scheduled(fixedDelay = 5 * 60 * 1000)
    public void cleanup() {
        long now = System.currentTimeMillis();
        long userWindowMs = properties.getUserWindowSeconds() * 1000;
        long ipWindowMs = properties.getIpWindowSeconds() * 1000;

        // 1) 惩罚名单：移除已到期
        punishList.entrySet().removeIf(e -> now >= e.getValue());

        // 2) 用户窗口队列：清掉窗口外时间戳，空队列移除 key
        userWindow.entrySet().removeIf(e -> {
            Deque<Long> dq = e.getValue();
            synchronized (dq) {
                while (!dq.isEmpty() && now - dq.peekFirst() > userWindowMs) {
                    dq.pollFirst();
                }
                return dq.isEmpty();
            }
        });

        // 3) IP 账号表：清掉窗口外账号，空 map 移除 key
        ipAccounts.entrySet().removeIf(e -> {
            Map<Long, Long> accounts = e.getValue();
            synchronized (accounts) {
                accounts.entrySet().removeIf(a -> now - a.getValue() > ipWindowMs);
                return accounts.isEmpty();
            }
        });
    }


    /**
     * R1 校验：通过返回 null，命中返回拦截原因
     */
    public String checkUser(Long userId, long now) {
        String key = "u:" + userId;
        Deque<Long> deque = userWindow.computeIfAbsent(key, k -> new ArrayDeque<>());
        synchronized (deque) { // 同一用户并发抢票时保证队列操作原子
            // 1) 惩罚名单校验放在锁内：若放在锁外，并发突发时后到的线程会在惩罚写入之前
            //    就读到 null 并继续走计数分支，而此时队列已被清空，它们会重新开始计数，
            //    导致 R1 限频被并发绕过（实测 20 并发约有 3~5 个请求逃逸）。
            Long unban = punishList.get(userId);
            if (unban != null) {
                if (now < unban) {
                    return "操作过于频繁，请稍后再试";
                }
                punishList.remove(userId); // 惩罚到期，解除
            }

            // 2) 滑动窗口计数
            long windowMs = properties.getUserWindowSeconds() * 1000;
            // 清理窗口外的旧时间戳
            while (!deque.isEmpty() && now - deque.peekFirst() > windowMs) {
                deque.pollFirst();
            }
            deque.addLast(now);
            if (deque.size() > properties.getUserMaxRequests()) {
                // 命中：进惩罚名单并清空计数（惩罚结束后重新计数）
                punishList.put(userId, now + properties.getUserPunishSeconds() * 1000);
                deque.clear();
                return "操作过于频繁，请稍后再试";
            }
        }
        return null; // 放行
    }

    /**
     * R2 校验：同IP同活动窗口内不同账号数超限即拦截（默认关，防NAT误杀）
     * 通过返回 null，命中返回拦截原因
     */
    public String checkIp(String ip, Long activityId, Long userId, long now) {
        String key = "ip:" + ip + ":act:" + activityId;
        Map<Long, Long> accounts = ipAccounts.computeIfAbsent(key, k -> new ConcurrentHashMap<>());
        synchronized (accounts) {
            long windowMs = properties.getIpWindowSeconds() * 1000;
            // 清理窗口外的账号（超时没再请求的移除）
            accounts.entrySet().removeIf(e -> now - e.getValue() > windowMs);
            accounts.put(userId, now);
            if (accounts.size() > properties.getIpMaxAccounts()) {
                return "检测到异常抢票行为";
            }
        }
        return null;
    }

}

package com.example.campusticket.risk;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 在线风控规则引擎单元测试（覆盖 R1/R2 与内存结构清理）
 * 不依赖 Spring 容器与数据库，直接构造引擎对象验证规则边界。
 */
class RiskRuleEngineTest {

    private RiskProperties properties;
    private RiskRuleEngine engine;

    @BeforeEach
    void setUp() {
        properties = new RiskProperties();
        properties.setUserWindowSeconds(10);
        properties.setUserMaxRequests(5);
        properties.setUserPunishSeconds(30);
        properties.setIpRuleEnabled(false);
        properties.setIpWindowSeconds(60);
        properties.setIpMaxAccounts(3);

        engine = new RiskRuleEngine();
        ReflectionTestUtils.setField(engine, "properties", properties);
    }

    @Test
    @DisplayName("R1：窗口内未超限应全部放行")
    void underLimitShouldPass() {
        long now = System.currentTimeMillis();
        for (int i = 0; i < 5; i++) {
            assertNull(engine.checkUser(1L, now + i), "第 " + (i + 1) + " 次请求应放行");
        }
    }

    @Test
    @DisplayName("R1：窗口内超过上限应拦截并给出提示")
    void overLimitShouldBlock() {
        long now = System.currentTimeMillis();
        for (int i = 0; i < 5; i++) {
            assertNull(engine.checkUser(1L, now + i));
        }
        assertEquals("操作过于频繁，请稍后再试", engine.checkUser(1L, now + 5));
    }

    @Test
    @DisplayName("R1：命中后进入惩罚名单，惩罚期内即使低频请求也被拦截")
    void punishListShouldBlockDuringPunishWindow() {
        long now = System.currentTimeMillis();
        for (int i = 0; i < 5; i++) {
            assertNull(engine.checkUser(1L, now + i));
        }
        assertNotNull(engine.checkUser(1L, now + 5));

        // 惩罚期内（30 秒）单次请求依然被拦截，且不重新计数
        assertNotNull(engine.checkUser(1L, now + 10_000));
        assertNotNull(engine.checkUser(1L, now + 29_000));

        // 惩罚到期后自动解除
        assertNull(engine.checkUser(1L, now + 31_000));
    }

    @Test
    @DisplayName("R1：窗口滑动后旧请求不再计数（10 秒窗口过期即放行）")
    void slidingWindowShouldExpire() {
        long now = System.currentTimeMillis();
        for (int i = 0; i < 5; i++) {
            assertNull(engine.checkUser(1L, now + i));
        }
        // 窗口外（>10s）再次请求：旧时间戳被清理，不应命中
        assertNull(engine.checkUser(1L, now + 11_000));
    }

    @Test
    @DisplayName("R1：不同用户互不影响")
    void usersAreIsolated() {
        long now = System.currentTimeMillis();
        for (int i = 0; i < 5; i++) {
            assertNull(engine.checkUser(1L, now + i));
        }
        assertNull(engine.checkUser(2L, now + 10), "用户 2 不应受用户 1 的计数影响");
    }

    @Test
    @DisplayName("R2：同 IP 同活动账号数超限应拦截")
    void ipRuleShouldBlock() {
        long now = System.currentTimeMillis();
        assertNull(engine.checkIp("10.0.0.1", 1L, 101L, now));
        assertNull(engine.checkIp("10.0.0.1", 1L, 102L, now));
        assertNull(engine.checkIp("10.0.0.1", 1L, 103L, now));
        assertEquals("检测到异常抢票行为", engine.checkIp("10.0.0.1", 1L, 104L, now));
    }

    @Test
    @DisplayName("R2：同一账号重复请求不重复计数，不同活动相互独立")
    void ipRuleCountsDistinctAccountsOnly() {
        long now = System.currentTimeMillis();
        for (int i = 0; i < 10; i++) {
            assertNull(engine.checkIp("10.0.0.1", 1L, 101L, now + i), "同一账号重复请求不应计数");
        }
        assertNull(engine.checkIp("10.0.0.1", 2L, 102L, now), "不同活动应独立计数");
    }

    @Test
    @DisplayName("并发下 R1 计数不丢失（同一用户 20 个并发请求应被拦截）")
    void concurrentCheckShouldNotLoseCount() throws Exception {
        int threads = 20;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(threads);
        AtomicInteger blocked = new AtomicInteger();

        long now = System.currentTimeMillis();
        for (int i = 0; i < threads; i++) {
            pool.submit(() -> {
                try {
                    start.await();
                    if (engine.checkUser(9L, now) != null) {
                        blocked.incrementAndGet();
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    done.countDown();
                }
            });
        }
        start.countDown();
        assertTrue(done.await(10, TimeUnit.SECONDS), "并发校验应在超时前完成");
        pool.shutdown();

        // 上限 5，故至少 15 个请求应被拦截
        assertTrue(blocked.get() >= 15, "应拦截至少 15 个请求，实际 " + blocked.get());
    }

    @Test
    @DisplayName("定时清理：过期惩罚、窗口外时间戳与 IP 记录都应被移除")
    @SuppressWarnings("unchecked")
    void cleanupShouldPurgeExpiredEntries() {
        long now = System.currentTimeMillis();
        for (int i = 0; i < 5; i++) {
            engine.checkUser(1L, now + i);
        }
        engine.checkUser(1L, now + 5);          // 进入惩罚名单
        engine.checkIp("10.0.0.1", 1L, 101L, now);

        // 把内部时间戳改成"很久以前"，模拟长时间运行后的过期状态
        ConcurrentHashMap<String, java.util.Deque<Long>> userWindow =
                (ConcurrentHashMap<String, java.util.Deque<Long>>) ReflectionTestUtils.getField(engine, "userWindow");
        long stale = now - 60 * 60 * 1000L;
        userWindow.get("u:1").clear();
        userWindow.get("u:1").addLast(stale);
        ConcurrentHashMap<Long, Long> punishList =
                (ConcurrentHashMap<Long, Long>) ReflectionTestUtils.getField(engine, "punishList");
        punishList.put(1L, stale);
        ConcurrentHashMap<String, Map<Long, Long>> ipAccounts =
                (ConcurrentHashMap<String, Map<Long, Long>>) ReflectionTestUtils.getField(engine, "ipAccounts");
        ipAccounts.get("ip:10.0.0.1:act:1").put(101L, stale);

        engine.cleanup();

        assertTrue(punishList.isEmpty(), "过期惩罚应被清理");
        assertTrue(userWindow.isEmpty(), "窗口外的用户队列应被移除");
        assertTrue(ipAccounts.isEmpty(), "窗口外的 IP 记录应被移除");
    }

    @Test
    @DisplayName("阈值可通过配置调整（窗口/上限/惩罚时长）")
    void thresholdsAreConfigurable() {
        properties.setUserMaxRequests(2);
        properties.setUserPunishSeconds(1);
        long now = System.currentTimeMillis();
        assertNull(engine.checkUser(7L, now));
        assertNull(engine.checkUser(7L, now + 1));
        assertNotNull(engine.checkUser(7L, now + 2), "超过新上限应被拦截");
        assertNull(engine.checkUser(7L, now + 2_000), "1 秒惩罚到期后应放行");
    }
}

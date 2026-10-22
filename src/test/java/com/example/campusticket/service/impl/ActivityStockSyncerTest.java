package com.example.campusticket.service.impl;

import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.TicketType;
import com.example.campusticket.mapper.ActivityMapper;
import com.example.campusticket.mapper.TicketTypeMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

import java.util.Arrays;
import java.util.Collections;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 活动库存同步器单元测试。
 *
 * <p>核心回归点：回写必须走带 version 条件的 CAS（{@code syncStock}）而不是整行覆写，
 * 否则并发抢票已扣减的活动级库存会被聚合快照抹掉，活动级余量虚高直至超卖。
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class ActivityStockSyncerTest {

    @Mock private ActivityMapper activityMapper;
    @Mock private TicketTypeMapper ticketTypeMapper;

    @InjectMocks private ActivityStockSyncer syncer;

    private static final Long ACTIVITY_ID = 1L;

    private Activity activity(int version) {
        Activity a = new Activity();
        a.setId(ACTIVITY_ID);
        a.setVersion(version);
        return a;
    }

    private TicketType type(int total, int remain) {
        TicketType t = new TicketType();
        t.setTotalStock(total);
        t.setRemainStock(remain);
        return t;
    }

    @Test
    @DisplayName("单次同步成功：聚合票种之和并带 version 做 CAS，不整行覆写")
    void syncOnceShouldAggregateAndCas() {
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(activity(7));
        when(ticketTypeMapper.selectList(any())).thenReturn(Arrays.asList(type(30, 20), type(20, 10)));
        when(activityMapper.syncStock(ACTIVITY_ID, 50, 30, 7)).thenReturn(1);

        assertTrue(syncer.syncOnce(ACTIVITY_ID));

        verify(activityMapper).syncStock(eq(ACTIVITY_ID), eq(50), eq(30), eq(7));
        verify(activityMapper, org.mockito.Mockito.never()).updateById(any());
    }

    @Test
    @DisplayName("活动已不存在：视为无须同步，返回 true 且不写库")
    void syncOnceShouldSkipWhenActivityMissing() {
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(null);

        assertTrue(syncer.syncOnce(ACTIVITY_ID));

        verify(activityMapper, org.mockito.Mockito.never()).syncStock(anyLong(), any(), any(), any());
    }

    @Test
    @DisplayName("重试：首次版本冲突，第二次读到新 version 后成功")
    void syncWithRetryShouldSucceedOnSecondAttempt() {
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(activity(7), activity(8));
        when(ticketTypeMapper.selectList(any())).thenReturn(Collections.singletonList(type(30, 20)));
        when(activityMapper.syncStock(ACTIVITY_ID, 30, 20, 7)).thenReturn(0);
        when(activityMapper.syncStock(ACTIVITY_ID, 30, 20, 8)).thenReturn(1);

        assertTrue(syncer.syncWithRetry(ACTIVITY_ID));

        // 关键：第二次用的是新读到的 version=8，而不是死磕旧的 7
        verify(activityMapper).syncStock(eq(ACTIVITY_ID), eq(30), eq(20), eq(7));
        verify(activityMapper).syncStock(eq(ACTIVITY_ID), eq(30), eq(20), eq(8));
    }

    @Test
    @DisplayName("连续冲突达上限：返回 false（由调用方决定回滚），不抛异常")
    void syncWithRetryShouldReturnFalseAfterMaxAttempts() {
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(activity(7));
        when(ticketTypeMapper.selectList(any())).thenReturn(Collections.singletonList(type(30, 20)));
        when(activityMapper.syncStock(anyLong(), any(), any(), any())).thenReturn(0);

        assertFalse(syncer.syncWithRetry(ACTIVITY_ID));

        verify(activityMapper, times(20)).syncStock(anyLong(), any(), any(), any());
    }
}

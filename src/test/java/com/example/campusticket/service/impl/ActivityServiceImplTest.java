package com.example.campusticket.service.impl;

import com.example.campusticket.common.BusinessException;
import com.example.campusticket.common.Result;
import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.ActivityComment;
import com.example.campusticket.entity.CheckinRecord;
import com.example.campusticket.entity.Ticket;
import com.example.campusticket.entity.TicketOrder;
import com.example.campusticket.entity.TicketType;
import com.example.campusticket.mapper.ActivityCommentMapper;
import com.example.campusticket.mapper.ActivityMapper;
import com.example.campusticket.mapper.CheckinRecordMapper;
import com.example.campusticket.mapper.TicketMapper;
import com.example.campusticket.mapper.TicketOrderMapper;
import com.example.campusticket.mapper.TicketTypeMapper;
import com.example.campusticket.risk.RiskService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 抢票流程单元测试（对应论文 4.4.1 节与表2 抢票用例）
 * 核心回归点：票种库存已扣减后，活动总库存扣减失败必须"抛异常触发回滚"，
 * 而不是 return Result.error —— 后者不会回滚事务，会造成库存泄漏。
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class ActivityServiceImplTest {

    @Mock private ActivityMapper activityMapper;
    @Mock private TicketOrderMapper ticketOrderMapper;
    @Mock private TicketMapper ticketMapper;
    @Mock private TicketTypeMapper ticketTypeMapper;
    @Mock private CheckinRecordMapper checkinRecordMapper;
    @Mock private ActivityCommentMapper activityCommentMapper;
    @Mock private RiskService riskService;
    @Mock private ActivityStockSyncer activityStockSyncer;

    @InjectMocks private ActivityServiceImpl activityService;

    private static final Long USER_ID = 3L;
    private static final Long ACTIVITY_ID = 1L;
    private static final Long TICKET_TYPE_ID = 11L;

    private Activity openActivity(int remainStock, int version) {
        Activity activity = new Activity();
        activity.setId(ACTIVITY_ID);
        activity.setTitle("单元测试活动");
        activity.setOrganizerId(4L);
        activity.setStatus(1);
        activity.setTotalStock(100);
        activity.setRemainStock(remainStock);
        activity.setVersion(version);
        activity.setSignStartTime(LocalDateTime.now().minusHours(1));
        activity.setSignEndTime(LocalDateTime.now().plusHours(1));
        activity.setStartTime(LocalDateTime.now().plusDays(1));
        activity.setEndTime(LocalDateTime.now().plusDays(2));
        return activity;
    }

    private TicketType ticketType(int remainStock, int version) {
        TicketType type = new TicketType();
        type.setId(TICKET_TYPE_ID);
        type.setActivityId(ACTIVITY_ID);
        type.setTicketName("普通票");
        type.setTotalStock(100);
        type.setRemainStock(remainStock);
        type.setVersion(version);
        return type;
    }

    /** 常规放行场景：活动可抢、未重复购票、库存充足 */
    private void stubHappyPath(Activity activity, TicketType type) {
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(activity);
        when(ticketOrderMapper.selectCount(any())).thenReturn(0L);
        when(ticketTypeMapper.selectOne(any())).thenReturn(type);
    }

    @Test
    @DisplayName("抢票成功：双扣库存成功 → 生成订单与电子票，票号带 T 前缀")
    void grabSuccessShouldCreateOrderAndTicket() {
        stubHappyPath(openActivity(50, 3), ticketType(50, 3));
        when(ticketTypeMapper.deductStock(TICKET_TYPE_ID, 3)).thenReturn(1);
        when(activityMapper.deductStock(ACTIVITY_ID, 3)).thenReturn(1);

        Result<String> result = activityService.grabTicket(USER_ID, ACTIVITY_ID, null);

        assertEquals(200, result.getCode());
        assertEquals("抢票成功", result.getData());
        verify(ticketOrderMapper).insert(any(TicketOrder.class));
        verify(ticketMapper).insert(any(Ticket.class));
        verify(riskService).log(USER_ID, ACTIVITY_ID, "SUCCESS");
    }

    @Test
    @DisplayName("电子票落库时票号与 qrContent 一致，状态为未使用(0)")
    void issuedTicketShouldBeUnusedAndCarryCode() {
        stubHappyPath(openActivity(50, 3), ticketType(50, 3));
        when(ticketTypeMapper.deductStock(TICKET_TYPE_ID, 3)).thenReturn(1);
        when(activityMapper.deductStock(ACTIVITY_ID, 3)).thenReturn(1);

        activityService.grabTicket(USER_ID, ACTIVITY_ID, null);

        org.mockito.ArgumentCaptor<Ticket> captor = org.mockito.ArgumentCaptor.forClass(Ticket.class);
        verify(ticketMapper).insert(captor.capture());
        Ticket ticket = captor.getValue();
        assertNotNull(ticket.getTicketCode());
        assertTrue(ticket.getTicketCode().startsWith("T"), "票号应以 T 开头");
        assertEquals(ticket.getTicketCode(), ticket.getQrContent(), "出票时 qr_content 写入静态票号");
        assertEquals(0, ticket.getStatus(), "新票状态应为 0 未使用");
    }

    /**
     * P0 缺陷回归测试：修复前此处是 return Result.error(...)，事务不回滚，
     * 结果是"票种库存被扣掉、却没有订单与电子票"。修复后必须抛 BusinessException。
     */
    @Test
    @DisplayName("【回归】票种已扣、活动扣减失败 → 抛 BusinessException 触发回滚，不生成订单")
    void activityDeductFailureMustThrowToRollback() {
        stubHappyPath(openActivity(50, 3), ticketType(50, 3));
        when(ticketTypeMapper.deductStock(TICKET_TYPE_ID, 3)).thenReturn(1);
        when(activityMapper.deductStock(ACTIVITY_ID, 3)).thenReturn(0); // 活动行版本已变

        BusinessException e = assertThrows(BusinessException.class,
                () -> activityService.grabTicket(USER_ID, ACTIVITY_ID, null));

        assertEquals("VERSION_CONFLICT", e.getLogResult());
        assertEquals("抢票失败，请重试", e.getMessage());
        verify(ticketOrderMapper, never()).insert(any(TicketOrder.class));
        verify(ticketMapper, never()).insert(any(Ticket.class));
    }

    @Test
    @DisplayName("票种扣减失败（版本冲突）→ 抛 BusinessException，未写入任何数据")
    void ticketTypeDeductFailureShouldThrow() {
        stubHappyPath(openActivity(50, 3), ticketType(50, 3));
        when(ticketTypeMapper.deductStock(TICKET_TYPE_ID, 3)).thenReturn(0);

        BusinessException e = assertThrows(BusinessException.class,
                () -> activityService.grabTicket(USER_ID, ACTIVITY_ID, null));

        assertEquals("VERSION_CONFLICT", e.getLogResult());
        verify(activityMapper, never()).deductStock(anyLong(), any());
        verify(ticketOrderMapper, never()).insert(any(TicketOrder.class));
    }

    @Test
    @DisplayName("活动不存在 → 返回业务错误并记录 ERROR")
    void missingActivityShouldReturnError() {
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(null);

        Result<String> result = activityService.grabTicket(USER_ID, ACTIVITY_ID, null);

        assertEquals(500, result.getCode());
        assertEquals("活动不存在", result.getMsg());
        verify(riskService).log(USER_ID, ACTIVITY_ID, "ERROR");
    }

    @Test
    @DisplayName("活动已结束(status=2) → 拒绝抢票")
    void endedActivityShouldBeRejected() {
        Activity activity = openActivity(50, 3);
        activity.setStatus(2);
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(activity);

        Result<String> result = activityService.grabTicket(USER_ID, ACTIVITY_ID, null);

        assertEquals("活动已结束，无法抢票", result.getMsg());
        verify(riskService).log(USER_ID, ACTIVITY_ID, "ACTIVITY_ENDED");
        verify(ticketTypeMapper, never()).deductStock(anyLong(), any());
    }

    @Test
    @DisplayName("抢票未开始 / 已结束 → 时间窗校验拦截")
    void signWindowShouldBeEnforced() {
        Activity notStarted = openActivity(50, 3);
        notStarted.setSignStartTime(LocalDateTime.now().plusHours(2));
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(notStarted);
        assertEquals("抢票尚未开始", activityService.grabTicket(USER_ID, ACTIVITY_ID, null).getMsg());

        Activity expired = openActivity(50, 3);
        expired.setSignEndTime(LocalDateTime.now().minusHours(2));
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(expired);
        assertEquals("抢票已结束", activityService.grabTicket(USER_ID, ACTIVITY_ID, null).getMsg());
    }

    @Test
    @DisplayName("一人一票：已有订单 → 拒绝并记录 DUPLICATE")
    void duplicateOrderShouldBeRejected() {
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(openActivity(50, 3));
        when(ticketOrderMapper.selectCount(any())).thenReturn(1L);

        Result<String> result = activityService.grabTicket(USER_ID, ACTIVITY_ID, null);

        assertEquals("您已抢过该活动的门票，每人限购一张", result.getMsg());
        verify(riskService).log(USER_ID, ACTIVITY_ID, "DUPLICATE");
        verify(ticketTypeMapper, never()).deductStock(anyLong(), any());
    }

    @Test
    @DisplayName("票种已抢完 → 库存预检拦截，不进入扣减")
    void soldOutTicketTypeShouldBeRejected() {
        stubHappyPath(openActivity(50, 3), ticketType(0, 3));

        Result<String> result = activityService.grabTicket(USER_ID, ACTIVITY_ID, null);

        assertEquals("该票种已抢完", result.getMsg());
        verify(riskService).log(USER_ID, ACTIVITY_ID, "STOCK_EMPTY");
        verify(ticketTypeMapper, never()).deductStock(anyLong(), any());
    }

    @Test
    @DisplayName("活动总库存为 0 → 预检拦截（P0 修复后该判断前移到写操作之前）")
    void soldOutActivityShouldBeRejectedBeforeAnyWrite() {
        stubHappyPath(openActivity(0, 3), ticketType(50, 3));

        Result<String> result = activityService.grabTicket(USER_ID, ACTIVITY_ID, null);

        assertEquals("门票已抢完", result.getMsg());
        verify(ticketTypeMapper, never()).deductStock(anyLong(), any());
        verify(ticketOrderMapper, never()).insert(any(TicketOrder.class));
    }

    @Test
    @DisplayName("指定票种不属于该活动 → 拒绝")
    void mismatchedTicketTypeShouldBeRejected() {
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(openActivity(50, 3));
        when(ticketOrderMapper.selectCount(any())).thenReturn(0L);
        TicketType other = ticketType(50, 3);
        other.setActivityId(999L);
        when(ticketTypeMapper.selectById(TICKET_TYPE_ID)).thenReturn(other);

        Result<String> result = activityService.grabTicket(USER_ID, ACTIVITY_ID, TICKET_TYPE_ID);

        assertEquals("票种不存在", result.getMsg());
        verify(ticketTypeMapper, never()).deductStock(anyLong(), any());
    }

    @Test
    @DisplayName("乐观锁条件更新使用读到的 version（活动与票种各自独立）")
    void deductShouldUseReadVersion() {
        stubHappyPath(openActivity(50, 7), ticketType(50, 9));
        when(ticketTypeMapper.deductStock(TICKET_TYPE_ID, 9)).thenReturn(1);
        when(activityMapper.deductStock(ACTIVITY_ID, 7)).thenReturn(1);

        activityService.grabTicket(USER_ID, ACTIVITY_ID, null);

        verify(ticketTypeMapper).deductStock(eq(TICKET_TYPE_ID), eq(9));
        verify(activityMapper).deductStock(eq(ACTIVITY_ID), eq(7));
    }

    // ---------- 活动删除级联清理（P3） ----------

    @Test
    @DisplayName("删除活动：票种/订单/电子票/核销记录/评论一并清理，grab_log 保留")
    void deleteActivityShouldCascadeCleanup() {
        Activity db = openActivity(50, 3);
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(db);
        when(ticketTypeMapper.delete(any())).thenReturn(2);
        when(ticketOrderMapper.delete(any())).thenReturn(5);
        when(ticketMapper.delete(any())).thenReturn(5);
        when(checkinRecordMapper.delete(any())).thenReturn(3);
        when(activityCommentMapper.delete(any())).thenReturn(4);

        Result<String> result = activityService.deleteActivity(ACTIVITY_ID, 4L);

        assertEquals(200, result.getCode());
        assertTrue(result.getData().contains("活动删除成功"));
        assertTrue(result.getData().contains("评论 4 条"));
        verify(ticketTypeMapper).delete(any());
        verify(ticketOrderMapper).delete(any());
        verify(ticketMapper).delete(any());
        verify(checkinRecordMapper).delete(any());
        verify(activityCommentMapper).delete(any());
        verify(activityMapper).deleteById(ACTIVITY_ID);
    }

    @Test
    @DisplayName("删除他人活动 → 拒绝且不做任何清理")
    void deleteOthersActivityShouldBeRejected() {
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(openActivity(50, 3));

        Result<String> result = activityService.deleteActivity(ACTIVITY_ID, 999L);

        assertEquals("只能删除自己发布的活动", result.getMsg());
        verify(activityMapper, never()).deleteById(anyLong());
        verify(ticketTypeMapper, never()).delete(any());
        verify(ticketOrderMapper, never()).delete(any());
        verify(ticketMapper, never()).delete(any());
        verify(checkinRecordMapper, never()).delete(any());
        verify(activityCommentMapper, never()).delete(any());
    }

    // ---------- 票种增改删后的活动库存回写（委托给独立事务的 ActivityStockSyncer） ----------

    @Test
    @DisplayName("票种增改删后回写活动库存：委托 ActivityStockSyncer 执行带 version 的 CAS 同步")
    void syncActivityStockShouldDelegateToSyncer() {
        Activity act = openActivity(50, 7);
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(act);
        TicketType db = ticketType(50, 9);
        when(ticketTypeMapper.selectById(TICKET_TYPE_ID)).thenReturn(db);
        when(activityStockSyncer.syncWithRetry(ACTIVITY_ID)).thenReturn(true);

        activityService.updateTicketType(TICKET_TYPE_ID, "普通票", 60, 4L);

        // 回写必须交给独立事务的同步器（否则 REPEATABLE-READ 下重试读不到新 version）
        verify(activityStockSyncer).syncWithRetry(eq(ACTIVITY_ID));
        // 绝不能再退回整行覆写
        verify(activityMapper, never()).updateById(any());
    }

    @Test
    @DisplayName("同步器全部重试失败：抛 BusinessException 触发回滚，不留两层库存不一致")
    void syncActivityStockShouldThrowWhenSyncerFails() {
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(openActivity(50, 7));
        when(ticketTypeMapper.selectById(TICKET_TYPE_ID)).thenReturn(ticketType(50, 9));
        when(activityStockSyncer.syncWithRetry(ACTIVITY_ID)).thenReturn(false);

        BusinessException ex = assertThrows(BusinessException.class,
                () -> activityService.updateTicketType(TICKET_TYPE_ID, "普通票", 60, 4L));
        assertEquals("VERSION_CONFLICT", ex.getLogResult());
    }

    @Test
    @DisplayName("新增票种后同样触发活动库存同步")
    void createTicketTypeShouldAlsoSyncActivityStock() {
        when(activityMapper.selectById(ACTIVITY_ID)).thenReturn(openActivity(50, 7));
        when(activityStockSyncer.syncWithRetry(ACTIVITY_ID)).thenReturn(true);

        activityService.createTicketType(ACTIVITY_ID, "前排票", 20, 4L);

        verify(activityStockSyncer).syncWithRetry(eq(ACTIVITY_ID));
    }
}

package com.example.campusticket.service.impl;

import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import com.example.campusticket.common.QrCodeUtil;
import com.example.campusticket.common.Result;
import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.CheckinRecord;
import com.example.campusticket.entity.SysUser;
import com.example.campusticket.entity.Ticket;
import com.example.campusticket.mapper.ActivityMapper;
import com.example.campusticket.mapper.CheckinRecordMapper;
import com.example.campusticket.mapper.SysUserMapper;
import com.example.campusticket.mapper.TicketMapper;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 核销流程单元测试（对应论文表3 核销用例与 5.5 节）
 * 覆盖：动态码校验、防重复入场、验票时间窗（活动开始前 1 小时 ～ 活动结束）、
 * 并发核销只有一个请求成功。
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class CheckinServiceImplTest {

    @Mock private TicketMapper ticketMapper;
    @Mock private ActivityMapper activityMapper;
    @Mock private CheckinRecordMapper checkinRecordMapper;
    @Mock private SysUserMapper sysUserMapper;

    @InjectMocks private CheckinServiceImpl checkinService;

    private QrCodeUtil qrCodeUtil;

    private static final Long CHECKER_ID = 5L;
    private static final String TICKET_CODE = "T20261013001";
    private static final String SECRET = "unit-test-secret";

    @BeforeEach
    void setUp() {
        qrCodeUtil = new QrCodeUtil();
        ReflectionTestUtils.setField(qrCodeUtil, "secret", SECRET);
        ReflectionTestUtils.setField(checkinService, "qrCodeUtil", qrCodeUtil);
    }

    /**
     * 纯 Mockito 单元测试没有 Spring 容器，MyBatis-Plus 的 LambdaQueryWrapper 需要
     * 实体元信息缓存（TableInfoHelper）才能把方法引用解析成列名，否则报
     * "can not find lambda cache for this entity"。这里手动初始化一次。
     */
    @BeforeAll
    static void initTableInfo() {
        MapperBuilderAssistant assistant = new MapperBuilderAssistant(new MybatisConfiguration(), "");
        TableInfoHelper.initTableInfo(assistant, Ticket.class);
        TableInfoHelper.initTableInfo(assistant, Activity.class);
        TableInfoHelper.initTableInfo(assistant, CheckinRecord.class);
        TableInfoHelper.initTableInfo(assistant, SysUser.class);
    }

    private String freshQr() {
        return qrCodeUtil.build(TICKET_CODE);
    }

    private Ticket unusedTicket() {
        Ticket ticket = new Ticket();
        ticket.setId(100L);
        ticket.setTicketCode(TICKET_CODE);
        ticket.setActivityId(1L);
        ticket.setUserId(3L);
        ticket.setTicketName("普通票");
        ticket.setStatus(0);
        return ticket;
    }

    /** 活动处于可验票窗口内：开始前 1 小时 ~ 结束时间 */
    private Activity checkableActivity() {
        Activity activity = new Activity();
        activity.setId(1L);
        activity.setTitle("单元测试活动");
        activity.setStatus(1);
        activity.setStartTime(LocalDateTime.now().plusMinutes(30));
        activity.setEndTime(LocalDateTime.now().plusHours(3));
        return activity;
    }

    private void stubTicketAndActivity(Ticket ticket, Activity activity) {
        when(ticketMapper.selectOne(any())).thenReturn(ticket);
        when(activityMapper.selectById(ticket.getActivityId())).thenReturn(activity);
    }

    @Test
    @DisplayName("核销成功：票置为已核销并写入核销记录")
    void verifySuccessShouldMarkTicketAndWriteRecord() {
        stubTicketAndActivity(unusedTicket(), checkableActivity());
        when(ticketMapper.update(any(), any())).thenReturn(1);

        Result<String> result = checkinService.verify(freshQr(), CHECKER_ID);

        assertEquals(200, result.getCode());
        assertEquals("核销成功", result.getData());
        verify(ticketMapper).update(any(), any());
        verify(checkinRecordMapper).insert(any(CheckinRecord.class));
    }

    @Test
    @DisplayName("静态票号（非动态码）应被拒绝")
    void staticTicketCodeShouldBeRejected() {
        Result<String> result = checkinService.verify(TICKET_CODE, CHECKER_ID);

        assertEquals("二维码格式错误，请使用动态二维码", result.getMsg());
        verify(ticketMapper, never()).update(any(), any());
    }

    @Test
    @DisplayName("票券不存在 → 拒绝")
    void unknownTicketShouldBeRejected() {
        when(ticketMapper.selectOne(any())).thenReturn(null);

        assertEquals("票券不存在", checkinService.verify(freshQr(), CHECKER_ID).getMsg());
        verify(checkinRecordMapper, never()).insert(any(CheckinRecord.class));
    }

    @Test
    @DisplayName("已核销的票再次扫码 → 拒绝重复入场")
    void alreadyUsedTicketShouldBeRejected() {
        Ticket used = unusedTicket();
        used.setStatus(1);
        when(ticketMapper.selectOne(any())).thenReturn(used);

        assertEquals("该票已核销，请勿重复入场", checkinService.verify(freshQr(), CHECKER_ID).getMsg());
        verify(ticketMapper, never()).update(any(), any());
    }

    @Test
    @DisplayName("已作废的票 → 拒绝")
    void voidedTicketShouldBeRejected() {
        Ticket voided = unusedTicket();
        voided.setStatus(2);
        when(ticketMapper.selectOne(any())).thenReturn(voided);

        assertEquals("该票已作废", checkinService.verify(freshQr(), CHECKER_ID).getMsg());
    }

    @Test
    @DisplayName("活动已结束(status=2) → 拒绝核销")
    void endedActivityShouldBeRejected() {
        Activity ended = checkableActivity();
        ended.setStatus(2);
        stubTicketAndActivity(unusedTicket(), ended);

        assertEquals("活动已结束，无法核销", checkinService.verify(freshQr(), CHECKER_ID).getMsg());
    }

    @Test
    @DisplayName("活动开始前 1 小时之外 → 拒绝核销")
    void tooEarlyShouldBeRejected() {
        Activity early = checkableActivity();
        early.setStartTime(LocalDateTime.now().plusHours(2));
        stubTicketAndActivity(unusedTicket(), early);

        assertEquals("活动未开始，可在开始前1小时起验票入场", checkinService.verify(freshQr(), CHECKER_ID).getMsg());
        verify(ticketMapper, never()).update(any(), any());
    }

    @Test
    @DisplayName("活动结束时间已过 → 拒绝核销")
    void expiredActivityShouldBeRejected() {
        Activity expired = checkableActivity();
        expired.setEndTime(LocalDateTime.now().minusMinutes(1));
        stubTicketAndActivity(unusedTicket(), expired);

        assertEquals("活动已结束，该票已过期，无法核销", checkinService.verify(freshQr(), CHECKER_ID).getMsg());
    }

    /**
     * 并发核销保护：条件更新 WHERE status=0 影响 0 行说明票已被别的请求核销。
     */
    @Test
    @DisplayName("并发核销：条件更新影响 0 行 → 拒绝并提示重复入场")
    void concurrentCheckinShouldFailOnZeroRows() {
        stubTicketAndActivity(unusedTicket(), checkableActivity());
        when(ticketMapper.update(any(), any())).thenReturn(0);

        assertEquals("该票已核销，请勿重复入场", checkinService.verify(freshQr(), CHECKER_ID).getMsg());
        verify(checkinRecordMapper, never()).insert(any(CheckinRecord.class));
    }

    @Test
    @DisplayName("活动不存在 → 拒绝核销")
    void missingActivityShouldBeRejected() {
        when(ticketMapper.selectOne(any())).thenReturn(unusedTicket());
        when(activityMapper.selectById(1L)).thenReturn(null);

        assertEquals("活动不存在", checkinService.verify(freshQr(), CHECKER_ID).getMsg());
    }
}

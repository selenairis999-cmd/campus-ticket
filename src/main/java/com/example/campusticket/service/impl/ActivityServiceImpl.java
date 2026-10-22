package com.example.campusticket.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.common.BusinessException;
import com.example.campusticket.common.Result;
import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.ActivityComment;
import com.example.campusticket.entity.CheckinRecord;
import com.example.campusticket.entity.TicketOrder;
import com.example.campusticket.mapper.ActivityCommentMapper;
import com.example.campusticket.mapper.ActivityMapper;
import com.example.campusticket.mapper.CheckinRecordMapper;
import com.example.campusticket.mapper.TicketOrderMapper;
import com.example.campusticket.service.ActivityService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

import com.example.campusticket.entity.Ticket;
import com.example.campusticket.mapper.TicketMapper;

import com.example.campusticket.entity.TicketType;
import com.example.campusticket.mapper.TicketTypeMapper;

import com.example.campusticket.risk.RiskService;

@Service
public class ActivityServiceImpl implements ActivityService {

    @Autowired
    private ActivityMapper activityMapper;

    @Autowired
    private TicketOrderMapper ticketOrderMapper;

    @Autowired
    private TicketMapper ticketMapper;

    @Autowired
    private RiskService riskService;

    @Autowired
    private TicketTypeMapper ticketTypeMapper;

    @Autowired
    private CheckinRecordMapper checkinRecordMapper;

    @Autowired
    private ActivityCommentMapper activityCommentMapper;

    @Autowired
    private ActivityStockSyncer activityStockSyncer;


    /** 抢票：活动/时间窗校验 → 一人一票查重 → 按票种扣库存（乐观锁）
     *  → 扣活动总库存（乐观锁）→ 生成订单 + 电子票（同一事务，任一步失败整体回滚）
     *  ticketId 为空时取该活动第一个票种（默认普通票），不传参数行为与之前完全一致。
     *  注意：风控在线拦截由调用方（ActivityController#grabTicket）在进入本方法前完成，
     *  这样乐观锁重试不会被重复计入 R1 单用户滑动窗口。 */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result<String> grabTicket(Long userId, Long activityId, Long ticketId) {
        Activity activity = activityMapper.selectById(activityId);
        if (activity == null) {
            riskService.log(userId, activityId, "ERROR");
            return Result.error("活动不存在");
        }

        // 校验活动状态与抢票时间窗
        LocalDateTime now = LocalDateTime.now();
        if (activity.getStatus() != null && activity.getStatus() == 2) {
            riskService.log(userId, activityId, "ACTIVITY_ENDED");
            return Result.error("活动已结束，无法抢票");
        }
        if (activity.getSignStartTime() != null && now.isBefore(activity.getSignStartTime())) {
            riskService.log(userId, activityId, "TIME_WINDOW");
            return Result.error("抢票尚未开始");
        }
        if (activity.getSignEndTime() != null && now.isAfter(activity.getSignEndTime())) {
            riskService.log(userId, activityId, "TIME_WINDOW");
            return Result.error("抢票已结束");
        }

        // 一人一票：同一用户对同一活动限购一张（防止多设备共用账号抢多张票）
        Long exists = ticketOrderMapper.selectCount(new LambdaQueryWrapper<TicketOrder>()
                .eq(TicketOrder::getUserId, userId)
                .eq(TicketOrder::getActivityId, activityId));
        if (exists != null && exists > 0) {
            riskService.log(userId, activityId, "DUPLICATE");
            return Result.error("您已抢过该活动的门票，每人限购一张");
        }

        // 票种定位：不传 ticketId → 该活动第一个票种（默认普通票）
        TicketType ticketType;
        if (ticketId == null) {
            ticketType = ticketTypeMapper.selectOne(new LambdaQueryWrapper<TicketType>()
                    .eq(TicketType::getActivityId, activityId)
                    .orderByAsc(TicketType::getId).last("LIMIT 1"));
        } else {
            ticketType = ticketTypeMapper.selectById(ticketId);
            if (ticketType == null || !ticketType.getActivityId().equals(activityId)) {
                riskService.log(userId, activityId, "ERROR");
                return Result.error("票种不存在");
            }
        }
        if (ticketType == null || ticketType.getRemainStock() <= 0) {
            riskService.log(userId, activityId, "STOCK_EMPTY");
            return Result.error("该票种已抢完");
        }

        // 活动级库存预检：放在任何写操作之前，售罄时无需进入事务提交/回滚流程（同时避免空指针）
        if (activity.getRemainStock() == null || activity.getRemainStock() <= 0) {
            riskService.log(userId, activityId, "STOCK_EMPTY");
            return Result.error("门票已抢完");
        }

        // 双扣第一步：扣票种库存（乐观锁条件更新，未命中即 0 行）
        // 冲突同样抛 BusinessException：此时尚未写入任何数据，回滚是空操作，
        // 但可让 Controller 层的重试逻辑统一处理（见 ActivityController#grabTicket）。
        int ticketCount = ticketTypeMapper.deductStock(ticketType.getId(), ticketType.getVersion());
        if (ticketCount == 0) {
            throw new BusinessException("抢票失败，请重试", "VERSION_CONFLICT");
        }

        // 双扣第二步：扣活动总库存（乐观锁条件更新）
        // 【关键】票种库存此刻已扣减成功，此分支若失败必须回滚，否则会出现
        // “票种库存被扣掉、却没有生成订单与电子票”的库存泄漏。
        // 因此这里抛 BusinessException（而非 return Result.error）触发 @Transactional 回滚；
        // 埋点在事务外由 Controller 补记，避免随回滚一起丢失。
        int updateCount = activityMapper.deductStock(activityId, activity.getVersion());
        if (updateCount == 0) {
            throw new BusinessException("抢票失败，请重试", "VERSION_CONFLICT");
        }

        // 生成订单 + 电子票（带票种名）
        TicketOrder order = new TicketOrder();
        order.setUserId(userId);
        order.setActivityId(activityId);
        order.setTicketName(ticketType.getTicketName());
        ticketOrderMapper.insert(order);

        Ticket ticket = new Ticket();
        ticket.setOrderId(order.getId());
        ticket.setUserId(userId);
        ticket.setActivityId(activityId);
        ticket.setTicketName(ticketType.getTicketName());
        String code = "T" + System.currentTimeMillis() + (int) (Math.random() * 9000 + 1000);
        ticket.setTicketCode(code);
        ticket.setQrContent(code);
        ticket.setStatus(0);
        ticket.setCreateTime(LocalDateTime.now());
        ticketMapper.insert(ticket);

        // 成功埋点与抢票在同一事务内提交：二者要么都成功、要么一起回滚，
        // 不会出现"日志记了成功、订单却没落库"的错配。
        riskService.log(userId, activityId, "SUCCESS");
        return Result.success("抢票成功");
    }



    @Override
    @Transactional(rollbackFor = Exception.class)   // ← 加上事务注解，活动+票种同生共死
    public Result<String> createActivity(Activity activity, Long organizerId) {
        if (activity.getSignStartTime() == null || activity.getSignEndTime() == null
                || activity.getStartTime() == null || activity.getEndTime() == null) {
            return Result.error("活动时间不能为空");
        }
        if (!activity.getSignStartTime().isBefore(activity.getSignEndTime())) {
            return Result.error("抢票开始时间必须早于抢票结束时间");
        }
        if (!activity.getSignEndTime().isBefore(activity.getStartTime())) {
            return Result.error("抢票结束时间必须早于活动开始时间");
        }
        if (!activity.getSignEndTime().isAfter(LocalDateTime.now())) {
            return Result.error("抢票结束时间必须晚于当前时间，不能发布已结束的活动");
        }
        if (!activity.getStartTime().isBefore(activity.getEndTime())) {
            return Result.error("活动开始时间必须早于活动结束时间");
        }
        if (activity.getTotalStock() == null || activity.getTotalStock() <= 0) {
            return Result.error("库存必须大于0");
        }

        activity.setId(null);
        activity.setOrganizerId(organizerId);
        activity.setRemainStock(activity.getTotalStock());
        activity.setVersion(0);
        activity.setStatus(0);
        activity.setCreateTime(LocalDateTime.now());

        activityMapper.insert(activity);

        // 发布活动时自动创建默认票种"普通票"（库存=活动库存），ticket 表从此真正用起来
        TicketType defaultTicket = new TicketType();
        defaultTicket.setActivityId(activity.getId());
        defaultTicket.setTicketName("普通票");
        defaultTicket.setTotalStock(activity.getTotalStock());
        defaultTicket.setRemainStock(activity.getTotalStock());
        defaultTicket.setVersion(0);
        defaultTicket.setCreateTime(LocalDateTime.now());
        ticketTypeMapper.insert(defaultTicket);

        return Result.success("活动发布成功");
    }

    @Override
    public Result<String> updateActivity(Activity activity, Long organizerId) {
        Activity db = activityMapper.selectById(activity.getId());
        if (db == null) {
            return Result.error("活动不存在");
        }
        if (!db.getOrganizerId().equals(organizerId)) {
            return Result.error("只能修改自己发布的活动");
        }
        activity.setOrganizerId(organizerId);
        // 活动库存由其下所有票种库存之和决定，编辑活动时不直接修改 totalStock/remainStock；
        // 如需调整库存，请通过票种管理（增/改/删票种）操作，系统会自动同步到活动表
        activity.setTotalStock(db.getTotalStock());
        activity.setRemainStock(db.getRemainStock());
        activity.setVersion(db.getVersion());
        activity.setCreateTime(db.getCreateTime());

        activityMapper.updateById(activity);
        return Result.success("活动修改成功");
    }

    @Override
    public Result<String> changeStatus(Long activityId, Integer status, Long organizerId) {
        Activity db = activityMapper.selectById(activityId);
        if (db == null) {
            return Result.error("活动不存在");
        }
        if (!db.getOrganizerId().equals(organizerId)) {
            return Result.error("只能操作自己发布的活动");
        }
        Activity update = new Activity();
        update.setId(activityId);
        update.setStatus(status);
        activityMapper.updateById(update);
        return Result.success("状态更新成功");
    }

    /** 删除活动：连同该活动的票种、订单、电子票、核销记录与评论一并清理（同一事务）。
     *  原实现只执行 activityMapper.deleteById，会留下订单/电子票/核销记录/评论等孤儿数据：
     *  学生的"我的票券"里仍能看到已删除活动的票、组织者核销记录里仍能查到该活动的记录、
     *  评论排行里也会残留该活动的评论。grab_log 作为风控审计日志保留不删（与 7.2 节一致）。 */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result<String> deleteActivity(Long activityId, Long organizerId) {
        Activity db = activityMapper.selectById(activityId);
        if (db == null) {
            return Result.error("活动不存在");
        }
        if (!db.getOrganizerId().equals(organizerId)) {
            return Result.error("只能删除自己发布的活动");
        }

        // 先删下游数据，再删活动本身，避免出现指向已删除活动的孤儿记录
        int ticketCount = ticketMapper.delete(new LambdaQueryWrapper<Ticket>()
                .eq(Ticket::getActivityId, activityId));
        int orderCount = ticketOrderMapper.delete(new LambdaQueryWrapper<TicketOrder>()
                .eq(TicketOrder::getActivityId, activityId));
        int checkinCount = checkinRecordMapper.delete(new LambdaQueryWrapper<CheckinRecord>()
                .eq(CheckinRecord::getActivityId, activityId));
        int commentCount = activityCommentMapper.delete(new LambdaQueryWrapper<ActivityComment>()
                .eq(ActivityComment::getActivityId, activityId));
        int typeCount = ticketTypeMapper.delete(new LambdaQueryWrapper<TicketType>()
                .eq(TicketType::getActivityId, activityId));

        activityMapper.deleteById(activityId);

        return Result.success(String.format(
                "活动删除成功（同时清理票种 %d、订单 %d、电子票 %d、核销记录 %d、评论 %d 条）",
                typeCount, orderCount, ticketCount, checkinCount, commentCount));
    }

    @Override
    public Result<Activity> getActivity(Long activityId) {
        Activity activity = activityMapper.selectById(activityId);
        if (activity == null) {
            return Result.error("活动不存在");
        }
        return Result.success(activity);
    }

    @Override
    public Result<List<Activity>> listActivities() {
        return Result.success(activityMapper.selectList(null));
    }

    @Override
    public Result<Page<Activity>> pageActivities(long pageNum, long pageSize, String keyword) {
        LambdaQueryWrapper<Activity> wrapper = new LambdaQueryWrapper<>();
        if (keyword != null && !keyword.trim().isEmpty()) {
            wrapper.like(Activity::getTitle, keyword);
        }
        wrapper.orderByDesc(Activity::getCreateTime);
        Page<Activity> page = new Page<>(pageNum, pageSize);
        activityMapper.selectPage(page, wrapper);
        return Result.success(page);
    }

    // ===== 多票种管理（功能12） =====

    @Override
    public Result<List<TicketType>> listTicketTypes(Long activityId) {
        return Result.success(ticketTypeMapper.selectList(new LambdaQueryWrapper<TicketType>()
                .eq(TicketType::getActivityId, activityId)
                .orderByAsc(TicketType::getId)));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)   // 票种写入与活动库存回写必须同事务，否则回写失败会留下不一致
    public Result<String> createTicketType(Long activityId, String ticketName, Integer totalStock, Long organizerId) {
        Activity activity = activityMapper.selectById(activityId);
        if (activity == null) {
            return Result.error("活动不存在");
        }
        if (!activity.getOrganizerId().equals(organizerId)) {
            return Result.error("只能操作自己发布的活动");
        }
        if (ticketName == null || ticketName.trim().isEmpty()) {
            return Result.error("票种名称不能为空");
        }
        if (totalStock == null || totalStock <= 0) {
            return Result.error("库存必须大于0");
        }
        Long exists = ticketTypeMapper.selectCount(new LambdaQueryWrapper<TicketType>()
                .eq(TicketType::getActivityId, activityId)
                .eq(TicketType::getTicketName, ticketName.trim()));
        if (exists != null && exists > 0) {
            return Result.error("该活动已存在同名票种");
        }
        TicketType tt = new TicketType();
        tt.setActivityId(activityId);
        tt.setTicketName(ticketName.trim());
        tt.setTotalStock(totalStock);
        tt.setRemainStock(totalStock);
        tt.setVersion(0);
        tt.setCreateTime(LocalDateTime.now());
        ticketTypeMapper.insert(tt);
        syncActivityStock(activityId);   // 同步活动总库存 = 各票种库存之和
        return Result.success("票种添加成功");
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result<String> updateTicketType(Long ticketTypeId, String ticketName, Integer totalStock, Long organizerId) {
        TicketType db = ticketTypeMapper.selectById(ticketTypeId);
        if (db == null) {
            return Result.error("票种不存在");
        }
        Activity activity = activityMapper.selectById(db.getActivityId());
        if (activity == null || !activity.getOrganizerId().equals(organizerId)) {
            return Result.error("只能操作自己发布的活动");
        }
        if (ticketName == null || ticketName.trim().isEmpty()) {
            return Result.error("票种名称不能为空");
        }
        if (totalStock == null || totalStock <= 0) {
            return Result.error("库存必须大于0");
        }
        int sold = db.getTotalStock() - db.getRemainStock();
        if (totalStock < sold) {
            return Result.error("新库存不能小于已售数量(" + sold + ")");
        }
        TicketType update = new TicketType();
        update.setId(ticketTypeId);
        update.setTicketName(ticketName.trim());
        update.setTotalStock(totalStock);
        update.setRemainStock(totalStock - sold);   // 剩余联动：新总库存 - 已售
        ticketTypeMapper.updateById(update);
        syncActivityStock(db.getActivityId());      // 同步活动总库存
        return Result.success("票种修改成功");
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Result<String> deleteTicketType(Long ticketTypeId, Long organizerId) {
        TicketType db = ticketTypeMapper.selectById(ticketTypeId);
        if (db == null) {
            return Result.error("票种不存在");
        }
        Activity activity = activityMapper.selectById(db.getActivityId());
        if (activity == null || !activity.getOrganizerId().equals(organizerId)) {
            return Result.error("只能操作自己发布的活动");
        }
        Long count = ticketTypeMapper.selectCount(new LambdaQueryWrapper<TicketType>()
                .eq(TicketType::getActivityId, db.getActivityId()));
        if (count != null && count <= 1) {
            return Result.error("至少保留一个票种");
        }
        if (db.getRemainStock() < db.getTotalStock()) {
            return Result.error("该票种已有售出，不能删除");
        }
        ticketTypeMapper.deleteById(ticketTypeId);
        syncActivityStock(db.getActivityId());      // 同步活动总库存
        return Result.success("票种删除成功");
    }

    /**
     * 同步活动库存：activity.totalStock / remainStock = 其下所有票种 totalStock / remainStock 之和。
     * 保证抢票时"票种级 + 活动级"双乐观锁的两层库存始终一致，避免超卖或误拒绝。
     *
     * <p>实现委托给 {@link ActivityStockSyncer}：那里用 REQUIRES_NEW 让每次重试
     * 都在新事务中读到并发已提交的最新 version。若重试循环留在本类事务内，
     * MySQL REPEATABLE-READ 会固定快照，导致 CAS 永远命中旧版本、重试形同虚设。</p>
     *
     * <p>失败时抛 BusinessException 触发调用方事务回滚：宁可让组织者这次改票种失败，
     * 也不能留下"票种已改、活动两层库存却没跟上"的不一致状态。</p>
     */
    private void syncActivityStock(Long activityId) {
        if (!activityStockSyncer.syncWithRetry(activityId)) {
            throw new BusinessException("活动库存同步失败，请重试", "VERSION_CONFLICT");
        }
    }

}

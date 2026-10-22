package com.example.campusticket.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.TicketType;
import com.example.campusticket.mapper.ActivityMapper;
import com.example.campusticket.mapper.TicketTypeMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 活动两层库存的一致性回写器（票种库存之和 → activity.total_stock / remain_stock）。
 *
 * <p>单独抽成一个 Bean 而不是留在 {@code ActivityServiceImpl} 的私有方法里，
 * 是因为必须让 Spring 事务代理生效：本类被 {@code @Transactional} 的票种增/改/删调用，
 * 若重试循环留在调用方同一个事务内，MySQL 默认 REPEATABLE-READ 会让快照固定在
 * 事务第一次读上 —— 后续反复 selectById 拿到的永远是同一个旧 version，
 * CAS 永远不会成功。这里用 REQUIRES_NEW 让每次尝试都在新事务里读到并发已提交的新版本。</p>
 */
@Component
public class ActivityStockSyncer {

    /** 重试上限。每次失败都开新事务重读，因此有限次即可收敛。 */
    private static final int MAX_ATTEMPTS = 20;

    @Autowired
    private ActivityMapper activityMapper;

    @Autowired
    private TicketTypeMapper ticketTypeMapper;

    /**
     * 单次尝试：读活动 version → 聚合票种库存 → 带 version 条件 CAS 回写。
     *
     * @return true 表示已同步成功（或活动已不存在，无须同步）
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW, rollbackFor = Exception.class)
    public boolean syncOnce(Long activityId) {
        Activity db = activityMapper.selectById(activityId);
        if (db == null) {
            return true;
        }
        List<TicketType> types = ticketTypeMapper.selectList(
                new LambdaQueryWrapper<TicketType>().eq(TicketType::getActivityId, activityId));
        int totalStock = types.stream().mapToInt(TicketType::getTotalStock).sum();
        int remainStock = types.stream().mapToInt(TicketType::getRemainStock).sum();
        return activityMapper.syncStock(activityId, totalStock, remainStock, db.getVersion()) > 0;
    }

    /**
     * 重试直到成功。全部失败时返回 false，由调用方决定回滚还是报错。
     *
     * <p>注意：这里刻意不抛异常。调用方（票种增/改/删）自身处在事务中，
     * 本方法每次尝试都是一个独立事务；若在此抛出，会把已成功提交的票种写入
     * 与"未同步的活动库存"一起留在外面，反而更难判断。返回布尔值更清晰。</p>
     */
    public boolean syncWithRetry(Long activityId) {
        for (int attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
            if (syncOnce(activityId)) {
                return true;
            }
            try {
                Thread.sleep(Math.min(2 + attempt * 2L, 20L));
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        return false;
    }
}

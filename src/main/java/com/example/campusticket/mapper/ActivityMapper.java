package com.example.campusticket.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.campusticket.entity.Activity;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface ActivityMapper extends BaseMapper<Activity> {

    /**
     * 乐观锁扣减库存
     */
    @Update("UPDATE activity SET remain_stock = remain_stock - 1, version = version + 1 " +
            "WHERE id = #{activityId} AND version = #{version} AND remain_stock > 0")
    int deductStock(@Param("activityId") Long activityId, @Param("version") Integer version);

    /**
     * 乐观锁回写活动两层库存（票种增/改/删后同步用）。
     * 必须带 version 条件：若期间有抢票事务推进了版本，本次回写返回 0 行，
     * 调用方据此重读重算，避免用陈旧聚合值覆盖并发扣减的结果。
     */
    @Update("UPDATE activity SET total_stock = #{totalStock}, remain_stock = #{remainStock}, " +
            "version = version + 1 " +
            "WHERE id = #{activityId} AND version = #{version}")
    int syncStock(@Param("activityId") Long activityId,
                  @Param("totalStock") Integer totalStock,
                  @Param("remainStock") Integer remainStock,
                  @Param("version") Integer version);
}

package com.example.campusticket.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.campusticket.entity.TicketType;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface TicketTypeMapper extends BaseMapper<TicketType> {

    /** 票种乐观锁扣库存（等价 activity 的 deductStock，每个票种独立版本号） */
    @Update("UPDATE ticket SET remain_stock = remain_stock - 1, version = version + 1 " +
            "WHERE id = #{id} AND version = #{version} AND remain_stock > 0")
    int deductStock(@Param("id") Long id, @Param("version") Integer version);
}

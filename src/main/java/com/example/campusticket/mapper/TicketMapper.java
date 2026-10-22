package com.example.campusticket.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.campusticket.entity.Ticket;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface TicketMapper extends BaseMapper<Ticket> {
}

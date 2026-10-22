package com.example.campusticket.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.common.Result;
import com.example.campusticket.entity.Activity;

import java.util.List;
import com.example.campusticket.entity.TicketType;

public interface ActivityService {
    Result<String> grabTicket(Long userId, Long activityId, Long ticketId);
    Result<String> createActivity(Activity activity, Long organizerId);   // 发布活动
    Result<String> updateActivity(Activity activity, Long organizerId);   // 编辑活动
    Result<String> changeStatus(Long activityId, Integer status, Long organizerId); // 上下架
    Result<String> deleteActivity(Long activityId, Long organizerId);     // 删除活动
    Result<Activity> getActivity(Long activityId);                        // 活动详情
    Result<List<Activity>> listActivities();                              // 活动列表
    Result<Page<Activity>> pageActivities(long pageNum, long pageSize, String keyword); // 分页查询
    Result<List<TicketType>> listTicketTypes(Long activityId);                       // 活动票种列表
    Result<String> createTicketType(Long activityId, String ticketName, Integer totalStock, Long organizerId); // 新增票种
    Result<String> updateTicketType(Long ticketTypeId, String ticketName, Integer totalStock, Long organizerId); // 编辑票种
    Result<String> deleteTicketType(Long ticketTypeId, Long organizerId);             // 删除票种

}

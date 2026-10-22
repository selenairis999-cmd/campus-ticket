package com.example.campusticket.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.common.Result;
import com.example.campusticket.entity.CheckinRecord;
import com.example.campusticket.entity.SysUser;

public interface CheckinService {
    /** 扫码核销：核销员传入动态二维码内容（票号.时间戳.签名） */
    Result<String> verify(String qrContent, Long checkerId);

    /** 核销记录分页查询（可按活动筛选；组织者仅可见本组织活动的记录） */
    Result<Page<CheckinRecord>> records(Long activityId, long pageNum, long pageSize, SysUser user);
}

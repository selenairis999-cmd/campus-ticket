package com.example.campusticket.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.example.campusticket.entity.GrabLog;
import com.example.campusticket.vo.AccountRiskVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface GrabLogMapper extends BaseMapper<GrabLog> {

    /** 按用户聚合抢票行为（总请求/成功/被拦次数），按请求量倒序 */
    @Select("SELECT username, user_id AS userId, COUNT(*) AS totalRequests, " +
            "SUM(CASE WHEN result = 'SUCCESS' THEN 1 ELSE 0 END) AS successCount, " +
            "SUM(CASE WHEN result = 'RISK_BLOCKED' THEN 1 ELSE 0 END) AS blockedCount " +
            "FROM grab_log GROUP BY username, user_id ORDER BY totalRequests DESC")
    List<AccountRiskVO> selectAccountRisk();

    /**
     * 嫌疑账号排行的分页查询：只取「被拦截过 或 请求数超过阈值」的账号。
     * 排序规则与页面展示一致：先按总请求量倒序，再按用户名升序保证顺序稳定（翻页不跳行）。
     * <p>SQL 里用 HAVING 而不是让 Java 过滤，是为了让 total 与当前页数据口径一致——
     * 否则分页总数会把正常账号也算进去，页码会虚高。
     */
    @Select("SELECT username, user_id AS userId, COUNT(*) AS totalRequests, " +
            "SUM(CASE WHEN result = 'SUCCESS' THEN 1 ELSE 0 END) AS successCount, " +
            "SUM(CASE WHEN result = 'RISK_BLOCKED' THEN 1 ELSE 0 END) AS blockedCount " +
            "FROM grab_log GROUP BY username, user_id " +
            "HAVING SUM(CASE WHEN result = 'RISK_BLOCKED' THEN 1 ELSE 0 END) > 0 " +
            "   OR COUNT(*) > #{suspectThreshold} " +
            "ORDER BY totalRequests DESC, username ASC")
    IPage<AccountRiskVO> selectSuspectAccountPage(IPage<AccountRiskVO> page,
                                                  @Param("suspectThreshold") long suspectThreshold);
}

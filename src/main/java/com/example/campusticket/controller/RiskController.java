package com.example.campusticket.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.annotation.RequireRole;
import com.example.campusticket.common.Result;
import com.example.campusticket.common.UserRole;
import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.GrabLog;
import com.example.campusticket.entity.SysUser;
import com.example.campusticket.mapper.ActivityMapper;
import com.example.campusticket.mapper.GrabLogMapper;
import com.example.campusticket.risk.OfflineAnalysisService;
import com.example.campusticket.risk.RiskService;
import com.example.campusticket.vo.AccountRiskVO;
import com.example.campusticket.vo.OfflineAnalysisResultVO;
import com.example.campusticket.vo.RiskOverviewVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/risk")
public class RiskController {

    @Autowired
    private GrabLogMapper grabLogMapper;

    @Autowired
    private ActivityMapper activityMapper;

    @Autowired
    private RiskService riskService;

    @Autowired
    private OfflineAnalysisService offlineAnalysisService;

    /** 嫌疑账号判定阈值：请求数超过该值即视为嫌疑（页面标题与 SQL 共用同一口径） */
    private static final long SUSPECT_REQUEST_THRESHOLD = 50;

    /** 风控总览：统计卡片 + 嫌疑账号排行（分页，仅管理员） */
    @GetMapping("/overview")
    @RequireRole(UserRole.ADMIN)
    public Result<RiskOverviewVO> overview(@RequestParam(defaultValue = "1") long pageNum,
                                           @RequestParam(defaultValue = "10") long pageSize) {
        RiskOverviewVO vo = new RiskOverviewVO();
        long total = grabLogMapper.selectCount(null);
        long success = grabLogMapper.selectCount(new LambdaQueryWrapper<GrabLog>().eq(GrabLog::getResult, "SUCCESS"));
        long blocked = grabLogMapper.selectCount(new LambdaQueryWrapper<GrabLog>().eq(GrabLog::getResult, "RISK_BLOCKED"));
        long conflict = grabLogMapper.selectCount(new LambdaQueryWrapper<GrabLog>().eq(GrabLog::getResult, "VERSION_CONFLICT"));
        vo.setTotalRequests(total);
        vo.setSuccessCount(success);
        vo.setBlockedCount(blocked);
        vo.setConflictCount(conflict);
        vo.setSuccessRate(total == 0 ? "0.0%" : String.format("%.1f%%", success * 100.0 / total));
        // 嫌疑判定：被拦截过 或 请求量明显异常。过滤与分页都下推到 SQL，
        // 保证 total 与当前页口径一致（否则页码会按「全部账号」虚高）
        Page<AccountRiskVO> page = new Page<>(pageNum, pageSize);
        IPage<AccountRiskVO> riskPage =
                grabLogMapper.selectSuspectAccountPage(page, SUSPECT_REQUEST_THRESHOLD);
        List<AccountRiskVO> list = riskPage.getRecords();
        // 封禁信息：一次查出当前封禁名单，回填到嫌疑账号行 + 统计卡片
        Map<Long, SysUser> bannedMap = riskService.listBanned().stream()
                .collect(Collectors.toMap(SysUser::getId, Function.identity()));
        vo.setBannedCount(bannedMap.size());
        for (AccountRiskVO a : list) {
            a.setSuspect(a.getBlockedCount() != null && a.getBlockedCount() > 0
                    || a.getTotalRequests() != null && a.getTotalRequests() > SUSPECT_REQUEST_THRESHOLD);
            SysUser banned = bannedMap.get(a.getUserId());
            a.setBanned(banned != null);
            a.setBanExpireTime(banned != null ? banned.getBanExpireTime() : null);
        }
        vo.setSuspectAccounts(list);
        vo.setSuspectTotal(riskPage.getTotal());
        vo.setSuspectPageNum(riskPage.getCurrent());
        vo.setSuspectPageSize(riskPage.getSize());
        vo.setSuspectPages(riskPage.getPages());
        return Result.success(vo);
    }

    // ==================== 分级处置：封禁管理（仅管理员） ====================

    /** 封禁单个账号：days 为空或 0 表示永久封禁，否则为限时天数 */
    @PostMapping("/ban")
    @RequireRole(UserRole.ADMIN)
    public Result<String> ban(@RequestParam Long userId,
                              @RequestParam(required = false) Integer days,
                              @RequestParam(required = false) String reason) {
        return riskService.ban(userId, days, reason);
    }

    /** 解封账号 */
    @PostMapping("/unban")
    @RequireRole(UserRole.ADMIN)
    public Result<String> unban(@RequestParam Long userId) {
        return riskService.unban(userId);
    }

    /** 当前封禁名单（限时到期的不返回） */
    @GetMapping("/banned")
    @RequireRole(UserRole.ADMIN)
    public Result<List<SysUser>> banned() {
        return Result.success(riskService.listBanned());
    }

    /** 批量封禁：粘贴离线检测报告中的异常账号（换行/逗号分隔） */
    @PostMapping("/ban-batch")
    @RequireRole(UserRole.ADMIN)
    public Result<String> banBatch(@RequestParam String usernames,
                                   @RequestParam(required = false) Integer days,
                                   @RequestParam(required = false) String reason) {
        return riskService.banBatch(usernames, days, reason);
    }

    // ==================== 离线检测调度（仅管理员） ====================

    /** 可分析的活动列表：有抢票日志的活动 + 日志量（检测弹窗下拉数据源） */
    @GetMapping("/analysis-activities")
    @RequireRole(UserRole.ADMIN)
    public Result<List<Map<String, Object>>> analysisActivities() {
        return Result.success(offlineAnalysisService.analyzableActivities());
    }

    /** 运行离线检测：按活动串跑 导出→特征工程→孤立森林，返回结构化报告（需数秒，前端已放宽超时） */
    @PostMapping("/run-offline-analysis")
    @RequireRole(UserRole.ADMIN)
    public Result<OfflineAnalysisResultVO> runOfflineAnalysis(@RequestParam Long activityId) {
        return Result.success(offlineAnalysisService.run(activityId));
    }

    /** 抢票日志分页查询（可按用户名/结果筛选） */
    @GetMapping("/records")
    @RequireRole(UserRole.ADMIN)
    public Result<Page<GrabLog>> records(@RequestParam(defaultValue = "1") long pageNum,
                                         @RequestParam(defaultValue = "10") long pageSize,
                                         @RequestParam(required = false) String username,
                                         @RequestParam(required = false) String result) {
        Page<GrabLog> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<GrabLog> qw = new LambdaQueryWrapper<GrabLog>()
                .eq(StringUtils.hasText(username), GrabLog::getUsername, username)
                .eq(StringUtils.hasText(result), GrabLog::getResult, result)
                .orderByDesc(GrabLog::getId);
        grabLogMapper.selectPage(page, qw);
        fillActivityTitle(page.getRecords());
        return Result.success(page);
    }

    /** 回填活动名称（按 ID 批量查询，避免 N+1） */
    private void fillActivityTitle(List<GrabLog> list) {
        if (list == null || list.isEmpty()) {
            return;
        }
        Set<Long> actIds = list.stream().map(GrabLog::getActivityId).collect(Collectors.toSet());
        Map<Long, Activity> actMap = activityMapper.selectBatchIds(actIds).stream()
                .collect(Collectors.toMap(Activity::getId, Function.identity()));
        for (GrabLog g : list) {
            Activity a = actMap.get(g.getActivityId());
            if (a != null) {
                g.setActivityTitle(a.getTitle());
            }
        }
    }
}

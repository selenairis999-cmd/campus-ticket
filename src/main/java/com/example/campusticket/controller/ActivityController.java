package com.example.campusticket.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.campusticket.annotation.RequireRole;
import com.example.campusticket.common.BusinessException;
import com.example.campusticket.common.Result;
import com.example.campusticket.common.UserContext;
import com.example.campusticket.common.UserRole;
import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.TicketType;
import com.example.campusticket.risk.RiskService;
import com.example.campusticket.service.ActivityService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/activity")
public class ActivityController {

    @Autowired
    private ActivityService activityService;

    @Autowired
    private RiskService riskService;

    /** 抢票：只有学生可抢，userId 从登录态取
     *  乐观锁冲突（VERSION_CONFLICT）属于“读到的版本已过期”，并非库存不足：
     *  高并发下大量请求会在同一瞬间读到旧版本号而失败，若不重试就会出现
     *  “库存还有、请求却全部失败”的假售罄。这里做有限次重试（含短暂退避），
     *  重试耗尽才把失败返回给用户。
     *  风控校验只做一次，避免重试把同一请求重复计入 R1 滑动窗口。
     *  重试次数取值依据：库存与并发数接近时（如 50 并发抢 50 张）没有“售罄”这一
     *  终止信号，所有线程会持续争抢同一行，单次 CAS 命中概率随竞争加剧而下降。
     *  实测 8 次会有约 1/3 的请求在库存未售罄时误报失败；20 次在 100/200 并发下
     *  仍有 5~17 张票卖不出去；提高到 40 次后在 50/100/200 并发下均能把库存
     *  全部卖出且不超卖。次数再往上没有收益，只会拉长"售罄"请求的排队时间。 */
    private static final int GRAB_MAX_ATTEMPTS = 40;

    @PostMapping("/grab")
    @RequireRole(UserRole.STUDENT)
    public Result<String> grabTicket(@RequestParam Long activityId,
                                     @RequestParam(required = false) Long ticketId) {
        Long userId = UserContext.get().getId();

        // 风控在线拦截：命中直接返回，且不计入后续重试
        String riskReason = riskService.check(userId, activityId);
        if (riskReason != null) {
            return Result.error(riskReason);
        }

        String lastMessage = "抢票失败，请重试";
        for (int attempt = 1; attempt <= GRAB_MAX_ATTEMPTS; attempt++) {
            try {
                return activityService.grabTicket(userId, activityId, ticketId);
            } catch (BusinessException e) {
                // 事务已因 BusinessException 回滚，风控埋点必须在此补记（否则会随事务一起回滚丢失）
                lastMessage = e.getMessage();
                boolean retryable = "VERSION_CONFLICT".equals(e.getLogResult());
                if (!retryable || attempt == GRAB_MAX_ATTEMPTS) {
                    if (e.getLogResult() != null) {
                        riskService.log(userId, activityId, e.getLogResult());
                    }
                    return Result.error(e.getMessage());
                }
                // 版本冲突：退避后重试。退避必须"递增但有上限"：
                // 固定小退避（如 1~5ms）会让 200 个线程在整整 1 秒的售出期内
                // 反复争抢同一行，失败线程的高频重试反过来拖慢成功线程；
                // 线性无上限退避（早期 attempt*3ms）累计等待又能到 2.6 秒。
                // 这里取 min(2+2*attempt, 25)ms + 抖动，既打散线程又限制总等待。
                try {
                    long backoff = Math.min(2 + attempt * 2L, 25L);
                    Thread.sleep(backoff + (long) (Math.random() * 5));
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    return Result.error(e.getMessage());
                }
            }
        }
        return Result.error(lastMessage);
    }


    /** 发布活动：组织者 */
    @PostMapping("/create")
    @RequireRole(UserRole.ORGANIZER)
    public Result<String> create(@RequestBody Activity activity) {
        return activityService.createActivity(activity, UserContext.get().getId());
    }

    /** 编辑活动：组织者 */
    @PostMapping("/update")
    @RequireRole(UserRole.ORGANIZER)
    public Result<String> update(@RequestBody Activity activity) {
        return activityService.updateActivity(activity, UserContext.get().getId());
    }

    /** 变更活动状态：组织者（0未开始 1进行中 2已结束） */
    @PostMapping("/changeStatus")
    @RequireRole(UserRole.ORGANIZER)
    public Result<String> changeStatus(@RequestParam Long activityId, @RequestParam Integer status) {
        return activityService.changeStatus(activityId, status, UserContext.get().getId());
    }

    /** 删除活动：组织者 */
    @PostMapping("/delete")
    @RequireRole(UserRole.ORGANIZER)
    public Result<String> delete(@RequestParam Long activityId) {
        return activityService.deleteActivity(activityId, UserContext.get().getId());
    }

    /** 活动详情：登录即可看 */
    @GetMapping("/detail")
    public Result<Activity> detail(@RequestParam Long activityId) {
        return activityService.getActivity(activityId);
    }

    /** 活动列表：登录即可看 */
    @GetMapping("/list")
    public Result<List<Activity>> list() {
        return activityService.listActivities();
    }

    /** 分页查询：登录即可看，支持按标题模糊搜索 */
    @GetMapping("/page")
    public Result<Page<Activity>> page(@RequestParam(defaultValue = "1") long pageNum,
                                       @RequestParam(defaultValue = "10") long pageSize,
                                       @RequestParam(required = false) String keyword) {
        return activityService.pageActivities(pageNum, pageSize, keyword);
    }

    /** 活动票种列表（登录即可） */
    @GetMapping("/ticketTypes")
    public Result<List<TicketType>> ticketTypes(@RequestParam Long activityId) {
        return activityService.listTicketTypes(activityId);
    }

    /** 新增票种（组织者） */
    @PostMapping("/ticketType/create")
    @RequireRole(UserRole.ORGANIZER)
    public Result<String> createTicketType(@RequestParam Long activityId,
                                           @RequestParam String ticketName,
                                           @RequestParam Integer totalStock) {
        return activityService.createTicketType(activityId, ticketName, totalStock, UserContext.get().getId());
    }

    /** 编辑票种（组织者） */
    @PostMapping("/ticketType/update")
    @RequireRole(UserRole.ORGANIZER)
    public Result<String> updateTicketType(@RequestParam Long ticketTypeId,
                                           @RequestParam String ticketName,
                                           @RequestParam Integer totalStock) {
        return activityService.updateTicketType(ticketTypeId, ticketName, totalStock, UserContext.get().getId());
    }

    /** 删除票种（组织者） */
    @PostMapping("/ticketType/delete")
    @RequireRole(UserRole.ORGANIZER)
    public Result<String> deleteTicketType(@RequestParam Long ticketTypeId) {
        return activityService.deleteTicketType(ticketTypeId, UserContext.get().getId());
    }

}

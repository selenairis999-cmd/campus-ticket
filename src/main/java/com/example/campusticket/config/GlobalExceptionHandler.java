package com.example.campusticket.config;

import com.example.campusticket.common.BusinessException;
import com.example.campusticket.common.Result;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.Map;

/**
 * 全局异常处理器：将 Controller 层抛出的异常统一包装为 Result 返回前端，
 * 避免原始异常堆栈泄露给客户端，同时保证错误响应结构与正常接口一致。
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 静态资源/页面路径未命中（Spring 6.1+ 抛 NoResourceFoundException）。
     * <p>必须在 RuntimeException / Exception 兜底之前匹配：否则深链刷新（如直接访问
     * /admin/risk）会被兜底成 500 JSON，SPA 前端入口永远回退不到，用户刷新即白屏。
     * <p>/api 开头的接口仍返回 JSON；其余页面路径回退到 index.html 交给 Vue Router。
     * <p>是否接口请求以 ApiPrefixFilter 打的 isApiRequest 属性为准——该过滤器会把
     * /api 前缀从 getRequestURI() 里剥掉，直接看 URI 会漏判。
     */
    @ExceptionHandler(NoResourceFoundException.class)
    public Object handleNoResource(NoResourceFoundException e, HttpServletRequest request) {
        boolean isApi = "true".equals(request.getAttribute("isApiRequest"))
                || (request.getRequestURI() != null && request.getRequestURI().startsWith("/api"));
        if (isApi) {
            return ResponseEntity.status(404)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of("code", 404, "message", "接口不存在"));
        }
        // SPA 深链回退：交给前端路由，状态码保持 200
        return ResponseEntity.ok()
                .contentType(MediaType.TEXT_HTML)
                .body(new ClassPathResource("static/index.html"));
    }

    /** 业务异常：消息由开发者抛出时指定，可直接展示给用户 */
    @ExceptionHandler(IllegalStateException.class)
    public Result<Void> handleIllegalState(IllegalStateException e) {
        log.warn("[业务异常] {}", e.getMessage());
        return Result.error(500, e.getMessage());
    }

    /**
     * 需要触发事务回滚的业务失败（如抢票双扣库存第二步失败）。
     * 事务已由 @Transactional 回滚，这里只负责把消息转成统一的 Result 结构。
     */
    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusiness(BusinessException e) {
        log.warn("[业务回滚] {}", e.getMessage());
        return Result.error(500, e.getMessage());
    }

    /** 校验类运行时异常（二维码签名失败、Token 无效等），消息可直接展示 */
    @ExceptionHandler(RuntimeException.class)
    public Result<Void> handleRuntime(RuntimeException e) {
        log.warn("[运行时异常] {}", e.getMessage());
        return Result.error(500, e.getMessage());
    }

    /** 请求参数缺失（@RequestParam 必填项未传） */
    @ExceptionHandler(MissingServletRequestParameterException.class)
    public Result<Void> handleMissingParam(MissingServletRequestParameterException e) {
        String msg = "缺少必填参数：" + e.getParameterName();
        log.warn("[参数异常] {}", msg);
        return Result.error(500, msg);
    }

    /** 兜底：未预期异常，仅记录堆栈，返回通用提示，避免泄露内部信息 */
    @ExceptionHandler(Exception.class)
    public Result<Void> handleException(Exception e) {
        log.error("[系统异常]", e);
        return Result.error(500, "系统异常，请联系管理员");
    }
}

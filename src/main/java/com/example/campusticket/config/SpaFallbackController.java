package com.example.campusticket.config;

import jakarta.servlet.RequestDispatcher;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.boot.web.servlet.error.ErrorController;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.RequestMapping;

import java.util.Map;

@Controller
public class SpaFallbackController implements ErrorController {

    @RequestMapping("/error")
    public Object handleError(HttpServletRequest request, HttpServletResponse response) {
        String uri = (String) request.getAttribute(RequestDispatcher.ERROR_REQUEST_URI);
        Integer status = (Integer) request.getAttribute(RequestDispatcher.ERROR_STATUS_CODE);
        // /api 接口错误：返回 JSON，避免前端拿到 HTML
        if (uri != null && uri.startsWith("/api")) {
            int code = status == null ? 404 : status;
            return ResponseEntity.status(code)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of("code", code, "message", "接口不存在"));
        }
        // 页面路径（Vue history 路由）404：回退前端入口
        // 重置为 200：深链刷新/分享拿到的是正常页面，不应带 404 状态码
        if (status == null || status == 404) {
            response.setStatus(HttpServletResponse.SC_OK);
            return "forward:/index.html";
        }
        // 页面路径下的其他错误（如 500）：JSON 说明，状态码保持原样
        int code = status == null ? 500 : status;
        return ResponseEntity.status(code)
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("code", code, "message", "请求错误"));
    }
}

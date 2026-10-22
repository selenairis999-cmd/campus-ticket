package com.example.campusticket.config;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import org.springframework.stereotype.Component;
import java.io.IOException;

@Component
public class ApiPrefixFilter implements Filter {

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest req = (HttpServletRequest) request;
        String uri = req.getRequestURI();
        if (uri.startsWith("/api")) {
            request.setAttribute("isApiRequest", "true");   // 新增：标记这是接口请求
            chain.doFilter(new ApiPrefixRequestWrapper(req, uri.substring(4)), response);
        } else {
            chain.doFilter(request, response);
        }

    }

    static class ApiPrefixRequestWrapper extends HttpServletRequestWrapper {
        private final String newUri;
        ApiPrefixRequestWrapper(HttpServletRequest request, String newUri) {
            super(request);
            this.newUri = newUri;
        }
        @Override public String getRequestURI() { return newUri; }
        @Override public String getServletPath() { return newUri; }
        @Override public String getContextPath() { return ""; }
    }
}

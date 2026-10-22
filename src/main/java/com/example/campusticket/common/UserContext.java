package com.example.campusticket.common;

import com.example.campusticket.entity.SysUser;

/**
 * 当前登录用户上下文（ThreadLocal，每个请求线程独立，天然线程安全）
 */
public class UserContext {

    private static final ThreadLocal<SysUser> HOLDER = new ThreadLocal<>();

    public static void set(SysUser user) { HOLDER.set(user); }

    public static SysUser get() { return HOLDER.get(); }

    public static void clear() { HOLDER.remove(); }
}

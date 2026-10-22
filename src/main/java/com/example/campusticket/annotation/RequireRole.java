package com.example.campusticket.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 角色权限注解
 * 用法：@RequireRole(UserRole.ORGANIZER)                      只有组织者可访问
 *      @RequireRole({UserRole.ORGANIZER, UserRole.CHECKER})  多个角色均可访问
 */
@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
public @interface RequireRole {
    int[] value();
}

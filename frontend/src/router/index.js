import { createRouter, createWebHistory } from 'vue-router';

const routes = [
    { path: '/login', component: () => import('@/views/Login.vue') },
    { path: '/register', component: () => import('@/views/Register.vue') },
    { path: '/forgot', component: () => import('@/views/Forgot.vue') },
    { path: '/', redirect: '/student/activities' },
    { path: '/student/activities', component: () => import('@/views/student/ActivityList.vue'), meta: { roles: [0, 1] } },
    { path: '/student/tickets', component: () => import('@/views/student/MyTickets.vue'), meta: { roles: [1] } },
    { path: '/organizer/activities', component: () => import('@/views/organizer/ActivityManage.vue'), meta: { roles: [2] } },
    { path: '/organizer/stats', component: () => import('@/views/organizer/ActivityStats.vue'), meta: { roles: [0, 2] } },
    { path: '/organizer/records', component: () => import('@/views/organizer/CheckinRecords.vue'), meta: { roles: [2] } },
    { path: '/checker/checkin', component: () => import('@/views/checker/Checkin.vue'), meta: { roles: [3] } },
    { path: '/admin/risk', component: () => import('@/views/admin/RiskMonitor.vue'), meta: { roles: [0] } },
    { path: '/admin/sentiment', component: () => import('@/views/admin/SentimentCenter.vue'), meta: { roles: [0] } }

];

const router = createRouter({
    history: createWebHistory(),
    routes
});

// 全局守卫：未登录只能进登录页
router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('token');
    if (!['/login', '/register', '/forgot'].includes(to.path) && !token) {
        next('/login');
        return;
    }

    // 角色守卫：路由声明了 roles 就校验当前用户角色，不符回登录页
    if (to.meta.roles) {
        let user = null;
        try {
            const raw = localStorage.getItem('user');
            if (raw && raw !== 'undefined') user = JSON.parse(raw);
        } catch (e) {}
        const role = user ? user.role : null;
        if (role === null || !to.meta.roles.includes(role)) {
            next('/login');
            return;
        }
    }
    next();
});


export default router;

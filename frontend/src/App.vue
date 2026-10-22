<template>
  <div class="app">
    <el-header class="header">
      <div class="left">
        <span class="title">校园活动票务系统</span>
        <el-menu v-if="user && menus.length" class="nav" mode="horizontal"
                 :default-active="route.path" :ellipsis="false" router
                 background-color="#409eff" text-color="#fff" active-text-color="#ffd04b">
          <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">{{ m.label }}</el-menu-item>
        </el-menu>
      </div>
      <span v-if="user" class="right">
        <span class="hello">{{ user.name }}（{{ roleName }}）</span>
        <el-button link style="color:#fff" @click="logout">退出登录</el-button>
      </span>
    </el-header>
    <router-view />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';

const router = useRouter();
const route = useRoute();

const loadUser = () => {
  try {
    const raw = localStorage.getItem('user');
    if (raw && raw !== 'undefined') {
      return JSON.parse(raw);
    }
  } catch (e) {}
  return null;
};

const user = ref(loadUser());

watch(() => route.path, () => {
  user.value = loadUser();
});

const roleMap = { 0: '管理员', 1: '学生', 2: '组织者', 3: '核销员' };
const roleName = computed(() => (user.value ? roleMap[user.value.role] : ''));

// 各角色导航菜单（path 必须与 router/index.js 里注册的路由一致）
const menuMap = {
  0: [
    { label: '活动列表', path: '/student/activities' },
    { label: '出勤统计', path: '/organizer/stats' },
    { label: '风控监控', path: '/admin/risk' },
    { label: '情感分析', path: '/admin/sentiment' }
  ],


  1: [
    { label: '活动列表', path: '/student/activities' },
    { label: '我的票券', path: '/student/tickets' }
  ],

  2: [
    { label: '活动管理', path: '/organizer/activities' },
    { label: '出勤统计', path: '/organizer/stats' },
    { label: '核销记录', path: '/organizer/records' }
  ],

  3: [
    { label: '扫码核销', path: '/checker/checkin' }
  ]
};
const menus = computed(() => (user.value ? (menuMap[user.value.role] || []) : []));

const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  router.push('/login');
};
</script>

<style>
body { margin: 0; background: linear-gradient(135deg, #f0f7f4 0%, #e6f2ec 100%); min-height: 100vh; }
.app {
  min-height: 100vh; position: relative; overflow-x: hidden;
  background:
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1440' height='900' viewBox='0 0 1440 900'><line x1='-50' y1='780' x2='500' y2='230' stroke='%234caf78' stroke-width='1' opacity='0.18'/><line x1='150' y1='920' x2='750' y2='320' stroke='%234caf78' stroke-width='1' opacity='0.13'/><line x1='900' y1='-50' x2='1480' y2='530' stroke='%232e7d5a' stroke-width='1' opacity='0.12'/><circle cx='1180' cy='160' r='130' fill='none' stroke='%232e7d5a' stroke-width='1.5' opacity='0.18'/><circle cx='1180' cy='160' r='90' fill='none' stroke='%232e7d5a' stroke-width='1' opacity='0.12'/><circle cx='160' cy='700' r='90' fill='none' stroke='%232e7d5a' stroke-width='1.5' opacity='0.15'/><circle cx='160' cy='700' r='55' fill='none' stroke='%232e7d5a' stroke-width='1' opacity='0.1'/><circle cx='520' cy='120' r='3' fill='%234caf78' opacity='0.3'/><circle cx='640' cy='230' r='2' fill='%234caf78' opacity='0.25'/><circle cx='900' cy='680' r='3' fill='%234caf78' opacity='0.25'/><circle cx='1050' cy='520' r='2' fill='%234caf78' opacity='0.2'/><circle cx='320' cy='420' r='2.5' fill='%232e7d5a' opacity='0.2'/></svg>") center/cover no-repeat,
    linear-gradient(135deg, #f0f7f4 0%, #e6f2ec 100%);
}
.app::before {
  content: ''; position: fixed; top: -140px; right: -140px;
  width: 460px; height: 460px; border-radius: 50%;
  background: radial-gradient(circle, rgba(76, 175, 120, 0.20), transparent 70%);
  pointer-events: none; z-index: 0;
}
.app::after {
  content: ''; position: fixed; bottom: -160px; left: -120px;
  width: 520px; height: 520px; border-radius: 50%;
  background: radial-gradient(circle, rgba(46, 125, 90, 0.14), transparent 70%);
  pointer-events: none; z-index: 0;
}
.header {
  display: flex; align-items: center; justify-content: space-between;
  background: #2e7d5a; color: #fff; height: 56px; line-height: 56px;
  padding: 0 20px; position: relative; z-index: 1;
}
.left { display: flex; align-items: center; gap: 24px; }
.title { font-size: 18px; font-weight: bold; white-space: nowrap; }
.right { display: flex; align-items: center; gap: 12px; }
.nav { border-bottom: none; background: transparent !important; height: 56px; }
.nav :deep(.el-menu-item) {
  height: 56px; line-height: 56px; color: #fff; background: transparent;
}
.nav :deep(.el-menu-item:hover) { background: #3a9d6b !important; color: #fff !important; }
.nav :deep(.el-menu-item.is-active) { color: #ffd04b; border-bottom: 2px solid #ffd04b; }
</style>

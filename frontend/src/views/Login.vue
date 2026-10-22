<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2 class="title">校园活动票务系统</h2>
      <el-form @keyup.enter="login">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-button type="primary" style="width: 100%" :loading="loading" @click="login">登 录</el-button>
        <div class="tip">没有账号？<el-link type="primary" @click="goRegister">去注册</el-link>　|　<el-link type="primary" @click="goForgot">忘记密码？</el-link></div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import request from '@/utils/request';

const router = useRouter();
const form = reactive({ username: '', password: '' });
const loading = ref(false);

const login = async () => {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码');
    return;
  }
  loading.value = true;
  try {
    // 后端登录是 @RequestParam，所以用 params 传参
    const res = await request.post('/auth/login', null, { params: form });
    // 后端返回 {token, userId, username, name, role} —— 注意没有 user 对象
    localStorage.setItem('token', res.data.token);
    localStorage.setItem('user', JSON.stringify({
      id: res.data.userId,
      username: res.data.username,
      name: res.data.name,
      role: res.data.role
    }));
    // 按角色跳转到对应首页
    const role = res.data.role;
    if (role === 1) router.push('/student/activities');
    else if (role === 2) router.push('/organizer/activities');
    else if (role === 3) router.push('/checker/checkin');
    else router.push('/student/activities');
  } catch (e) {
    // 错误提示已由拦截器处理
  } finally {
    loading.value = false;
  }
};

const goRegister = () => router.push('/register');
const goForgot = () => router.push('/forgot');


</script>

<style scoped>
.login-page {
  height: 100vh; display: flex; align-items: center; justify-content: center;
  background:
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1440' height='900' viewBox='0 0 1440 900'><line x1='-50' y1='780' x2='500' y2='230' stroke='%234caf78' stroke-width='1' opacity='0.18'/><line x1='150' y1='920' x2='750' y2='320' stroke='%234caf78' stroke-width='1' opacity='0.13'/><line x1='900' y1='-50' x2='1480' y2='530' stroke='%232e7d5a' stroke-width='1' opacity='0.12'/><circle cx='1180' cy='160' r='130' fill='none' stroke='%232e7d5a' stroke-width='1.5' opacity='0.18'/><circle cx='1180' cy='160' r='90' fill='none' stroke='%232e7d5a' stroke-width='1' opacity='0.12'/><circle cx='160' cy='700' r='90' fill='none' stroke='%232e7d5a' stroke-width='1.5' opacity='0.15'/><circle cx='160' cy='700' r='55' fill='none' stroke='%232e7d5a' stroke-width='1' opacity='0.1'/><circle cx='520' cy='120' r='3' fill='%234caf78' opacity='0.3'/><circle cx='640' cy='230' r='2' fill='%234caf78' opacity='0.25'/><circle cx='900' cy='680' r='3' fill='%234caf78' opacity='0.25'/><circle cx='1050' cy='520' r='2' fill='%234caf78' opacity='0.2'/><circle cx='320' cy='420' r='2.5' fill='%232e7d5a' opacity='0.2'/></svg>") center/cover no-repeat,
    linear-gradient(135deg, #f0f7f4 0%, #e6f2ec 100%);
  position: relative; overflow: hidden;
}
.login-page::before {
  content: ''; position: absolute; top: -140px; right: -140px;
  width: 460px; height: 460px; border-radius: 50%;
  background: radial-gradient(circle, rgba(76, 175, 120, 0.22), transparent 70%);
}
.login-page::after {
  content: ''; position: absolute; bottom: -160px; left: -120px;
  width: 520px; height: 520px; border-radius: 50%;
  background: radial-gradient(circle, rgba(46, 125, 90, 0.15), transparent 70%);
}
.login-card {
  width: 380px; padding: 28px 24px; position: relative; z-index: 1;
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12);
}
.title { text-align: center; margin: 0 0 20px; color: #1f3d30; letter-spacing: 1px; }
.tip { margin-top: 12px; text-align: center; font-size: 14px; color: #666; }
.login-card :deep(.el-button--primary) {
  background: #2e7d5a; border-color: #2e7d5a;
}
.login-card :deep(.el-button--primary:hover) {
  background: #3a9d6b; border-color: #3a9d6b;
}
.login-card :deep(.el-link--primary) { color: #2e7d5a; }
.login-card :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #2e7d5a inset !important;
}
</style>

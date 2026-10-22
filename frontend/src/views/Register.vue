<template>
  <div class="register-page">
    <el-card class="register-card">
      <h2 class="title">注册学生账号</h2>
      <el-form @keyup.enter="register">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名（登录用）" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.name" placeholder="姓名" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.phone" placeholder="手机号（找回密码用）" maxlength="11" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.confirmPassword" type="password" placeholder="确认密码" show-password />
        </el-form-item>
        <el-button type="primary" style="width: 100%" :loading="loading" @click="register">注 册</el-button>
        <div class="tip">已有账号？<el-link type="primary" @click="goLogin">去登录</el-link></div>
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
const form = reactive({ username: '', name: '', phone: '', password: '', confirmPassword: '' });
const loading = ref(false);

const register = async () => {
  if (!form.username || !form.name || !form.phone || !form.password) {
    ElMessage.warning('请填写完整信息');
    return;
  }
  if (form.password !== form.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致');
    return;
  }
  if (!/^1\d{10}$/.test(form.phone)) {
    ElMessage.warning('请输入正确的11位手机号');
    return;
  }
  loading.value = true;
  try {
    // 后端是 @RequestParam，用 params 传参
    const res = await request.post('/auth/register', null, {
      params: { username: form.username, password: form.password, name: form.name, phone: form.phone }
    });
    ElMessage.success(res.data);
    router.push('/login');
  } catch (e) {
    // 错误提示已由拦截器处理
  } finally {
    loading.value = false;
  }
};

const goLogin = () => router.push('/login');
</script>

<style scoped>
.register-page {
  height: 100vh; display: flex; align-items: center; justify-content: center;
  background:
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='1440' height='900' viewBox='0 0 1440 900'><line x1='-50' y1='780' x2='500' y2='230' stroke='%234caf78' stroke-width='1' opacity='0.18'/><line x1='150' y1='920' x2='750' y2='320' stroke='%234caf78' stroke-width='1' opacity='0.13'/><line x1='900' y1='-50' x2='1480' y2='530' stroke='%232e7d5a' stroke-width='1' opacity='0.12'/><circle cx='1180' cy='160' r='130' fill='none' stroke='%232e7d5a' stroke-width='1.5' opacity='0.18'/><circle cx='1180' cy='160' r='90' fill='none' stroke='%232e7d5a' stroke-width='1' opacity='0.12'/><circle cx='160' cy='700' r='90' fill='none' stroke='%232e7d5a' stroke-width='1.5' opacity='0.15'/><circle cx='160' cy='700' r='55' fill='none' stroke='%232e7d5a' stroke-width='1' opacity='0.1'/><circle cx='520' cy='120' r='3' fill='%234caf78' opacity='0.3'/><circle cx='640' cy='230' r='2' fill='%234caf78' opacity='0.25'/><circle cx='900' cy='680' r='3' fill='%234caf78' opacity='0.25'/><circle cx='1050' cy='520' r='2' fill='%234caf78' opacity='0.2'/><circle cx='320' cy='420' r='2.5' fill='%232e7d5a' opacity='0.2'/></svg>") center/cover no-repeat,
    linear-gradient(135deg, #f0f7f4 0%, #e6f2ec 100%);
  position: relative; overflow: hidden;
}
.register-page::before {
  content: ''; position: absolute; top: -140px; right: -140px;
  width: 460px; height: 460px; border-radius: 50%;
  background: radial-gradient(circle, rgba(76, 175, 120, 0.22), transparent 70%);
}
.register-page::after {
  content: ''; position: absolute; bottom: -160px; left: -120px;
  width: 520px; height: 520px; border-radius: 50%;
  background: radial-gradient(circle, rgba(46, 125, 90, 0.15), transparent 70%);
}
.register-card {
  width: 400px; padding: 28px 24px; position: relative; z-index: 1;
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12);
}
.title { text-align: center; margin: 0 0 20px; color: #1f3d30; letter-spacing: 1px; }
.tip { margin-top: 12px; text-align: center; font-size: 14px; color: #666; }
.register-card :deep(.el-button--primary) { background: #2e7d5a; border-color: #2e7d5a; }
.register-card :deep(.el-button--primary:hover) { background: #3a9d6b; border-color: #3a9d6b; }
.register-card :deep(.el-link--primary) { color: #2e7d5a; }
.register-card :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px #2e7d5a inset !important; }
</style>

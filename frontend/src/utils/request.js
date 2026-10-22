import axios from 'axios';
import { ElMessage } from 'element-plus';
import router from '@/router';

const request = axios.create({
    baseURL: '/api',
    timeout: 10000
});

/** 解码 JWT payload，返回 exp（秒级时间戳），解析失败返回 0 */
function getTokenExpire(token) {
    try {
        const payload = token.split('.')[1];
        // base64url -> base64
        const b64 = payload.replace(/-/g, '+').replace(/_/g, '/');
        const json = decodeURIComponent(escape(atob(b64)));
        const obj = JSON.parse(json);
        return obj.exp ? obj.exp * 1000 : 0;   // JWT exp 是秒，转毫秒
    } catch (e) {
        return 0;
    }
}

/** 临近过期阈值：5 分钟 */
const REFRESH_THRESHOLD = 5 * 60 * 1000;

/** 进行中的刷新请求（并发去重，避免多个请求同时触发续期） */
let refreshPromise = null;

/** 主动续期：token 仍有效时换取新 token；失败返回 false */
function refreshToken() {
    if (refreshPromise) {
        return refreshPromise;
    }
    refreshPromise = request.post('/auth/refresh')
        .then(res => {
            const newToken = res.data?.token;
            if (newToken) {
                localStorage.setItem('token', newToken);
                // 同步更新本地缓存的用户信息（若有）
                const user = JSON.parse(localStorage.getItem('user') || '{}');
                if (res.data.username) user.username = res.data.username;
                if (res.data.name) user.name = res.data.name;
                if (res.data.role != null) user.role = res.data.role;
                localStorage.setItem('user', JSON.stringify(user));
            }
            return true;
        })
        .catch(() => false)
        .finally(() => { refreshPromise = null; });
    return refreshPromise;
}

// 请求拦截：自动带上登录 token；token 临近过期时先续期
request.interceptors.request.use(async config => {
    const token = localStorage.getItem('token');
    if (token) {
        // 续期接口本身不再触发续期判断，避免死循环
        if (!config.url.includes('/auth/refresh')) {
            const expire = getTokenExpire(token);
            const now = Date.now();
            if (expire > 0 && expire - now < REFRESH_THRESHOLD) {
                const ok = await refreshToken();
                if (ok) {
                    // 续期成功，用新 token 发送本次请求
                    config.headers['token'] = localStorage.getItem('token');
                    return config;
                }
                // 续期失败（token 已过期），继续发请求，由响应拦截器处理 401
            }
        }
        config.headers['token'] = localStorage.getItem('token');
    }
    return config;
});

// 响应拦截：统一处理 200/401/403
request.interceptors.response.use(
    response => {
        const res = response.data;
        if (res.code !== 200) {
            ElMessage.error(res.msg || '请求失败');
            return Promise.reject(new Error(res.msg));
        }
        return res;
    },
    error => {
        if (error.response) {
            if (error.response.status === 401) {
                ElMessage.error('登录已过期，请重新登录');
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                router.push('/login');
            } else if (error.response.status === 403) {
                ElMessage.error('无权限访问');
            } else {
                ElMessage.error(error.response.data?.msg || '请求失败');
            }
        } else {
            ElMessage.error('网络错误');
        }
        return Promise.reject(error);
    }
);

export default request;

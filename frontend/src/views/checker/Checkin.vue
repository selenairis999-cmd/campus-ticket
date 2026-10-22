<template>
  <div class="page">
    <!-- 模式切换：摄像头扫码 / 手动粘贴 -->
    <el-radio-group v-model="mode" class="mode-switch">
      <el-radio-button value="scan">摄像头扫码</el-radio-button>
      <el-radio-button value="manual">手动粘贴</el-radio-button>
    </el-radio-group>

    <!-- ① 摄像头扫码模式 -->
    <el-card v-if="mode === 'scan'" class="scan-card">
      <h3>扫码核销</h3>
      <p class="tip">对准学生手机上的动态二维码，识别后自动核销（3 秒动态码，扫码比粘贴快）</p>
      <div class="scanner">
        <video ref="videoRef" autoplay playsinline muted></video>
        <canvas ref="canvasRef" style="display: none"></canvas>
        <div v-if="!scanning" class="scan-placeholder">📷 摄像头未开启</div>
        <div v-else-if="!result.msg" class="scan-frame"></div>
      </div>
      <el-button v-if="!scanning" type="primary" size="large" class="big-btn" @click="startScan">开启摄像头</el-button>
      <el-button v-else type="danger" size="large" class="big-btn" @click="stopScan">停 止</el-button>
      <el-alert v-if="result.msg" :title="result.msg" :type="result.ok ? 'success' : 'error'"
                show-icon :closable="false" class="result-bar" />
      <el-button v-if="result.msg" type="success" size="large" class="big-btn" @click="resetScan">继续扫码</el-button>
    </el-card>

    <!-- ② 手动粘贴模式（扫码枪/不支持摄像头时兜底） -->
    <el-card v-else class="checkin-card">
      <h3>扫码核销</h3>
      <p class="tip">模拟扫码：把学生手机上的二维码内容粘贴到下方输入框（真实场景由扫码枪自动填充）</p>
      <el-input v-model="qrContent" type="textarea" :rows="3"
                placeholder="粘贴二维码内容，格式：票号.时间戳.签名" />
      <el-button type="primary" size="large" class="big-btn" :loading="checking" @click="verify">核 销</el-button>
      <el-alert v-if="result.msg" :title="result.msg" :type="result.ok ? 'success' : 'error'"
                show-icon :closable="false" class="result-bar" />
    </el-card>

    <!-- 核销记录 -->
    <el-card style="margin-top: 20px">
      <div class="toolbar">
        <span>核销记录</span>
        <el-select v-model="activityId" placeholder="全部活动" clearable style="width: 160px"
                   @change="loadRecords">
          <el-option v-for="a in activities" :key="a.id" :label="a.title" :value="a.id" />
        </el-select>
      </div>
      <div class="table-wrap">
        <el-table :data="records" v-loading="loading" size="small">
          <el-table-column prop="ticketCode" label="票号" width="200" />
          <el-table-column prop="activityTitle" label="活动" min-width="120" show-overflow-tooltip />
          <el-table-column prop="ticketName" label="票种" width="90" />
          <el-table-column prop="userName" label="持票人" width="90" />
          <el-table-column prop="checkerName" label="核销员" width="90" />
          <el-table-column label="核销时间" width="150">
            <template #default="{ row }">{{ fmt(row.createTime) }}</template>
          </el-table-column>
        </el-table>
      </div>
      <el-pagination v-model:current-page="pageNum" :total="total" layout="prev, pager, next"
                     @current-change="loadRecords" style="margin-top: 15px" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { ElMessage } from 'element-plus';
import jsQR from 'jsqr';
import request from '@/utils/request';

// —— 模式与手动输入 ——
const mode = ref('scan');
const qrContent = ref('');
const checking = ref(false);
const result = ref({ ok: false, msg: '' });

// —— 摄像头扫码状态 ——
const videoRef = ref(null);
const canvasRef = ref(null);
const scanning = ref(false);
let stream = null;
let rafId = null;
let lastDetected = '';
let lastDetectedTime = 0;

// —— 核销记录 ——
const records = ref([]);
const total = ref(0);
const pageNum = ref(1);
const activityId = ref(null);
const loading = ref(false);
const activities = ref([]);

const fmt = t => (t ? t.replace('T', ' ').slice(0, 16) : '');

// —— 摄像头扫码逻辑 ——
const startScan = async () => {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    ElMessage.error('当前环境不支持摄像头，请使用手动粘贴模式（需 HTTPS 或 localhost）');
    return;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment' } // 优先后置摄像头
    });
    videoRef.value.srcObject = stream;
    scanning.value = true;
    result.value = { ok: false, msg: '' };
    lastDetected = '';
    lastDetectedTime = 0;
    tick();
  } catch (e) {
    ElMessage.error('无法打开摄像头：' + (e && e.message ? e.message : '请检查权限设置'));
  }
};

const stopScan = () => {
  cancelAnimationFrame(rafId);
  if (stream) {
    stream.getTracks().forEach(t => t.stop());
    stream = null;
  }
  scanning.value = false;
};

const tick = () => {
  const video = videoRef.value;
  const canvas = canvasRef.value;
  if (!video || !canvas || video.readyState < 2) {
    rafId = requestAnimationFrame(tick);
    return;
  }
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const code = jsQR(img.data, img.width, img.height, { inversionAttempts: 'dontInvert' });
  if (code && code.data) {
    const now = Date.now();
    // 同一码 2 秒内不重复识别（动态码 3 秒过期，避免连续误触发）
    if (code.data !== lastDetected || now - lastDetectedTime > 2000) {
      lastDetected = code.data;
      lastDetectedTime = now;
      stopScan();
      qrContent.value = code.data;
      verify();
      return;
    }
  }
  rafId = requestAnimationFrame(tick);
};

const resetScan = () => {
  result.value = { ok: false, msg: '' };
  startScan();
};

// —— 核销动作（扫码/手动共用） ——
const verify = async () => {
  if (!qrContent.value.trim()) {
    ElMessage.warning('未识别到二维码内容');
    return;
  }
  checking.value = true;
  result.value = { ok: false, msg: '' };
  try {
    const res = await request.post('/checkin/verify', null, { params: { qrContent: qrContent.value.trim() } });
    result.value = { ok: true, msg: res.msg };
    qrContent.value = '';
    loadRecords();
  } catch (e) {
    result.value = { ok: false, msg: e.message || '核销失败' };
  } finally {
    checking.value = false;
  }
};

// —— 记录列表 ——
const loadRecords = async () => {
  loading.value = true;
  try {
    const res = await request.get('/checkin/records', {
      params: { activityId: activityId.value || undefined, pageNum: pageNum.value, pageSize: 10 }
    });
    records.value = res.data.records;
    total.value = res.data.total;
  } finally {
    loading.value = false;
  }
};

const loadActivities = async () => {
  const res = await request.get('/activity/list');
  activities.value = res.data;
};

onMounted(() => { loadRecords(); loadActivities(); });
onBeforeUnmount(() => stopScan());
</script>

<style scoped>
.page {
  padding: 16px;
  max-width: 560px;
  margin: 0 auto;
}
.mode-switch {
  margin-bottom: 16px;
  display: flex;
  width: 100%;
}
.mode-switch :deep(.el-radio-button) {
  flex: 1;
}
.mode-switch :deep(.el-radio-button__inner) {
  width: 100%;
  font-size: 15px;
}
h3 { margin: 0 0 8px; }
.tip { color: #909399; font-size: 13px; margin: 0 0 12px; }

/* 取景框 */
.scanner {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  background: #1f1f1f;
  border-radius: 8px;
  overflow: hidden;
}
.scanner video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.scan-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
  font-size: 16px;
}
.scan-frame {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 62%;
  height: 42%;
  border: 2px solid #67c23a;
  border-radius: 10px;
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.35);
  pointer-events: none;
}

/* 大按钮（手机友好） */
.big-btn {
  width: 100%;
  margin-top: 14px;
  height: 48px;
  font-size: 16px;
}
.result-bar {
  margin-top: 14px;
}

.checkin-card { max-width: 100%; }
.table-wrap { overflow-x: auto; }
.toolbar { margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
</style>

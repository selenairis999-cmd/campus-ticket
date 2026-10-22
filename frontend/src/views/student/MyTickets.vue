<template>
  <div class="page">
    <el-card>
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="未使用" name="unused" />
        <el-tab-pane label="已核销" name="checked" />
        <el-tab-pane label="已过期" name="expired" />
      </el-tabs>
      <el-table :data="paged" v-loading="loading">
        <el-table-column prop="ticketCode" label="票号" width="260" />
        <el-table-column prop="activityTitle" label="活动名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="活动开始" width="160">
          <template #default="{ row }">{{ formatTime(row.activityStartTime) }}</template>
        </el-table-column>
        <el-table-column prop="ticketName" label="票种" width="110" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="ticketState(row).type">
              {{ ticketState(row).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间">
          <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button type="primary" size="small" :disabled="ticketState(row).disabled" @click="showQr(row)">二维码</el-button>
            <el-button type="success" size="small" :disabled="row.status !== 1" @click="showCert(row)">证书</el-button>
            <el-button v-if="ticketState(row).expired" type="danger" size="small" @click="removeTicket(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="pageNum" :total="filtered.length" :page-size="pageSize"
                     layout="prev, pager, next, total"
                     style="margin-top: 15px; justify-content: center" />
    </el-card>

    <el-dialog v-model="qrDialog" title="入场二维码（每3秒自动刷新）" width="360px" @closed="stopRefresh">
      <div class="qr-box">
        <canvas ref="qrCanvas"></canvas>
        <p class="tip">二维码 3 秒内有效，截图转发后立即失效</p>
      </div>
    </el-dialog>

    <el-dialog v-model="certDialog" title="签到证书" width="440px">
      <el-descriptions :column="1" border v-if="cert">
        <el-descriptions-item label="证书编号">{{ cert.certificateNo }}</el-descriptions-item>
        <el-descriptions-item label="学生姓名">{{ cert.studentName }}</el-descriptions-item>
        <el-descriptions-item label="活动名称">{{ cert.activityTitle }}</el-descriptions-item>
        <el-descriptions-item label="活动地点">{{ cert.location }}</el-descriptions-item>
        <el-descriptions-item label="活动时间">{{ formatTime(cert.activityStartTime) }} ~ {{ formatTime(cert.activityEndTime) }}</el-descriptions-item>
        <el-descriptions-item label="签到时间">{{ formatTime(cert.checkinTime) }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import request from '@/utils/request';
import QRCode from 'qrcode';

const tickets = ref([]);
const activeTab = ref('unused');
const pageNum = ref(1);
const pageSize = ref(10);
const loading = ref(false);
const qrDialog = ref(false);
const qrCanvas = ref(null);
const currentTicketId = ref(null);
let timer = null;

const formatTime = t => (t ? t.replace('T', ' ').slice(0, 16) : '');

// 票状态：未使用 / 已过期（活动结束时间已过且未核销）/ 已核销 / 已作废
const ticketState = row => {
  if (row.status === 1) return { text: '已核销', type: 'info', disabled: true, expired: false };
  if (row.status === 2) return { text: '已作废', type: 'danger', disabled: true, expired: false };
  const end = row.activityEndTime ? new Date(row.activityEndTime.replace('T', ' ')).getTime() : 0;
  if (end && Date.now() > end) return { text: '已过期', type: 'warning', disabled: true, expired: true };
  return { text: '未使用', type: 'success', disabled: false, expired: false };
};

// 按当前标签页过滤：未使用 / 已核销 / 已过期（含已作废）
const filtered = computed(() => {
  const s = activeTab.value;
  return tickets.value.filter(t => {
    const st = ticketState(t);
    if (s === 'checked') return st.text === '已核销';
    if (s === 'expired') return st.text === '已过期' || st.text === '已作废';
    return st.text === '未使用';
  });
});
const paged = computed(() =>
  filtered.value.slice((pageNum.value - 1) * pageSize.value, pageNum.value * pageSize.value));
const onTabChange = () => { pageNum.value = 1; };

const load = async () => {
  loading.value = true;
  try {
    const res = await request.get('/ticket/myList', {
      params: { pageNum: 1, pageSize: 999 }
    });
    tickets.value = res.data.records;
  } finally {
    loading.value = false;
  }
};

// 删除过期票
const removeTicket = async row => {
  try {
    await ElMessageBox.confirm(
      `确认删除《${row.activityTitle}》的过期票（${row.ticketCode}）？删除后不可恢复！`, '提示',
      { type: 'warning' });
  } catch (e) { return; }
  const res = await request.post('/ticket/delete', null, { params: { ticketId: row.id } });
  ElMessage.success(res.msg);
  load();
};

// 打开弹窗并启动每 3 秒刷新（动态二维码核心）
const showQr = async row => {
  currentTicketId.value = row.id;
  qrDialog.value = true;
  await refreshQr();
  timer = setInterval(refreshQr, 3000);
};

const refreshQr = async () => {
  try {
    const res = await request.get('/ticket/qrcode', { params: { ticketId: currentTicketId.value } });
    if (qrCanvas.value) {
      QRCode.toCanvas(qrCanvas.value, res.data, { width: 280 });
    }
  } catch (e) { /* 错误已由拦截器提示 */ }
};

const certDialog = ref(false);
const cert = ref(null);

const showCert = async row => {
  certDialog.value = true;
  const res = await request.get('/stats/certificate', { params: { ticketId: row.id } });
  cert.value = res.data;
};

const stopRefresh = () => {
  if (timer) { clearInterval(timer); timer = null; }
};

onMounted(() => load());
onBeforeUnmount(stopRefresh);
</script>

<style scoped>
.page { padding: 20px; }
.qr-box { text-align: center; }
.tip { color: #909399; font-size: 13px; }
</style>

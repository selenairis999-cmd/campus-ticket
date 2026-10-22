<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索活动标题" clearable style="width: 260px"
                  @keyup.enter="load(1)" />
        <el-button type="primary" @click="load(1)">搜索</el-button>
        <el-button type="success" @click="openCreate">发布活动</el-button>
      </div>

      <el-table :data="records" v-loading="loading">
        <el-table-column prop="title" label="活动名称" min-width="150" />
        <el-table-column prop="location" label="地点" width="110" />
        <el-table-column label="抢票时间" width="270">
          <template #default="{ row }">{{ fmt(row.signStartTime) }} ~ {{ fmt(row.signEndTime) }}</template>
        </el-table-column>
        <el-table-column label="活动时间" width="270">
          <template #default="{ row }">{{ fmt(row.startTime) }} ~ {{ fmt(row.endTime) }}</template>
        </el-table-column>
        <el-table-column label="库存" width="90">
          <template #default="{ row }">{{ row.remainStock }}/{{ row.totalStock }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="['warning', 'success', 'info'][showStatus(row)]">
              {{ ['未开始', '进行中', '已结束'][showStatus(row)] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain :disabled="row.organizerId !== userId"
                       @click="openTickets(row)">票种</el-button>
            <el-button size="small" :disabled="row.organizerId !== userId" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="row.status === 0" size="small" type="warning"
                       :disabled="row.organizerId !== userId" @click="changeStatus(row, 1)">开始</el-button>
            <el-button v-else-if="row.status === 1" size="small" type="danger"
                       :disabled="row.organizerId !== userId" @click="changeStatus(row, 2)">结束</el-button>
            <el-button size="small" type="danger"
                       :disabled="row.organizerId !== userId" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination v-model:current-page="pageNum" :total="total" layout="prev, pager, next"
                     @current-change="load" style="margin-top: 15px" />
    </el-card>

    <!-- 发布 / 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑活动' : '发布活动'" width="600px" @closed="resetForm">
      <el-form :model="form" label-width="100px">
        <el-form-item label="活动名称" required>
          <el-input v-model="form.title" placeholder="请输入活动名称" />
        </el-form-item>
        <el-form-item label="活动地点" required>
          <el-input v-model="form.location" placeholder="如：大礼堂" />
        </el-form-item>
        <el-form-item label="活动描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
        <el-form-item label="抢票开始" required>
          <el-date-picker v-model="form.signStartTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss"
                          placeholder="选择日期时间" style="width: 100%" :disabled-date="disabledDate" />
        </el-form-item>
        <el-form-item label="抢票结束" required>
          <el-date-picker v-model="form.signEndTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss"
                          placeholder="选择日期时间" style="width: 100%" :disabled-date="disabledDate" />
        </el-form-item>
        <el-form-item label="活动开始" required>
          <el-date-picker v-model="form.startTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss"
                          placeholder="选择日期时间" style="width: 100%" :disabled-date="disabledDate" />
        </el-form-item>
        <el-form-item label="活动结束" required>
          <el-date-picker v-model="form.endTime" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss"
                          placeholder="选择日期时间" style="width: 100%" :disabled-date="disabledDate" />
        </el-form-item>
        <el-form-item label="总票数" required>
          <el-input-number v-model="form.totalStock" :min="1" :max="99999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 票种管理弹窗（功能12） -->
    <el-dialog v-model="ticketDialogVisible" :title="'票种管理 - ' + (currentActivity ? currentActivity.title : '')"
               width="700px" @open="loadTickets(currentActivity.id)">
      <div class="toolbar">
        <el-button type="success" size="small" @click="openTicketCreate">新增票种</el-button>
      </div>
      <el-table :data="tickets" v-loading="ticketLoading" size="small">
        <el-table-column prop="ticketName" label="票种名称" />
        <el-table-column label="库存（剩余/总）">
          <template #default="{ row }">{{ row.remainStock }}/{{ row.totalStock }}</template>
        </el-table-column>
        <el-table-column label="已售">
          <template #default="{ row }">{{ row.totalStock - row.remainStock }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="openTicketEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteTicket(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 新增/编辑票种（内层弹窗需 append-to-body） -->
      <el-dialog v-model="ticketFormVisible" :title="ticketForm.id ? '编辑票种' : '新增票种'"
                 width="400px" append-to-body>
        <el-form :model="ticketForm" label-width="80px">
          <el-form-item label="票种名称" required>
            <el-input v-model="ticketForm.ticketName" placeholder="如：普通票、前排票" />
          </el-form-item>
          <el-form-item label="总库存" required>
            <el-input-number v-model="ticketForm.totalStock" :min="1" :max="99999" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="ticketFormVisible = false">取消</el-button>
          <el-button type="primary" :loading="ticketSaving" @click="saveTicket">保存</el-button>
        </template>
      </el-dialog>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import request from '@/utils/request';

const records = ref([]);
const total = ref(0);
const pageNum = ref(1);
const keyword = ref('');
const loading = ref(false);

// 当前登录用户 id（用于判断"我的活动"，别人的活动按钮禁用，后端也有防越权）
let user = null;
try {
  const raw = localStorage.getItem('user');
  if (raw && raw !== 'undefined') user = JSON.parse(raw);
} catch (e) {}
const userId = user ? user.id : null;

const fmt = t => (t ? t.replace('T', ' ').slice(0, 16) : '');

// 状态显示：手动状态优先，但活动结束时间已过则一律显示"已结束"（与学生端口径一致）
const showStatus = row => {
  if (row.status === 2) return 2;
  const end = row.endTime ? new Date(row.endTime.replace('T', ' ')).getTime() : 0;
  if (end && Date.now() > end) return 2;
  return row.status;
};

const load = async () => {
  loading.value = true;
  try {
    const res = await request.get('/activity/page', {
      params: { pageNum: pageNum.value, pageSize: 10, keyword: keyword.value || undefined }
    });
    records.value = res.data.records;
    total.value = res.data.total;
  } finally {
    loading.value = false;
  }
};

// ---------- 发布 / 编辑 ----------
const dialogVisible = ref(false);
const saving = ref(false);
const emptyForm = () => ({
  id: null, title: '', location: '', description: '',
  signStartTime: '', signEndTime: '', startTime: '', endTime: '', totalStock: 100
});
const form = ref(emptyForm());

const openCreate = () => {
  form.value = emptyForm();
  dialogVisible.value = true;
};

const openEdit = row => {
  form.value = { ...row };  // 回填整行（含 id、各时间、库存），提交时走 update
  dialogVisible.value = true;
};

const resetForm = () => { form.value = emptyForm(); };
// 禁止选择昨天及以前（今天仍可选，支持"发布即开抢"）
const disabledDate = time => time.getTime() < Date.now() - 86400000;

const save = async () => {
  if (!form.value.title || !form.value.location || !form.value.totalStock) {
    ElMessage.warning('请填写活动名称、地点和总票数');
    return;
  }
  saving.value = true;
  try {
    const isEdit = !!form.value.id;
    const res = await request.post(isEdit ? '/activity/update' : '/activity/create', form.value);
    ElMessage.success(res.msg);
    dialogVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
};

// ---------- 状态变更（0未开始 → 1进行中 → 2已结束） ----------
const changeStatus = async (row, status) => {
  const text = status === 1 ? '开始' : '结束';
  let extra = '';
  if (status === 1) {
    const now = Date.now();
    const start = row.signStartTime ? new Date(row.signStartTime.replace('T', ' ')).getTime() : 0;
    const end = row.signEndTime ? new Date(row.signEndTime.replace('T', ' ')).getTime() : 0;
    if (start && now < start) {
      extra = `<br/>⚠️ 抢票窗口尚未开启（${fmt(row.signStartTime)}），学生在此之前无法抢票`;
    } else if (end && now > end) {
      extra = `<br/>⚠️ 抢票窗口已结束（${fmt(row.signEndTime)}），学生将无法抢票`;
    }
  }
  try {
    await ElMessageBox.confirm(`确认${text}活动《${row.title}》？${extra}`, '提示',
      { type: 'warning', dangerouslyUseHTMLString: true });
  } catch (e) { return; }
  const res = await request.post('/activity/changeStatus', null, { params: { activityId: row.id, status } });
  ElMessage.success(res.msg);
  load();
};

// ---------- 删除 ----------
const remove = async row => {
  try {
    await ElMessageBox.confirm(`确认删除活动《${row.title}》？删除后不可恢复！`, '警告', { type: 'error' });
  } catch (e) { return; }
  const res = await request.post('/activity/delete', null, { params: { activityId: row.id } });
  ElMessage.success(res.msg);
  load();
};

// ---------- 票种管理（功能12） ----------
const ticketDialogVisible = ref(false);
const ticketLoading = ref(false);
const currentActivity = ref(null);
const tickets = ref([]);
const ticketFormVisible = ref(false);
const ticketSaving = ref(false);
const ticketForm = ref({ id: null, ticketName: '', totalStock: 100 });

const openTickets = row => {
  currentActivity.value = row;
  ticketDialogVisible.value = true;
};

const loadTickets = async activityId => {
  ticketLoading.value = true;
  try {
    const res = await request.get('/activity/ticketTypes', { params: { activityId } });
    tickets.value = res.data;
  } finally {
    ticketLoading.value = false;
  }
};

const openTicketCreate = () => {
  ticketForm.value = { id: null, ticketName: '', totalStock: 100 };
  ticketFormVisible.value = true;
};

const openTicketEdit = row => {
  ticketForm.value = { id: row.id, ticketName: row.ticketName, totalStock: row.totalStock };
  ticketFormVisible.value = true;
};

const saveTicket = async () => {
  if (!ticketForm.value.ticketName) {
    ElMessage.warning('请填写票种名称');
    return;
  }
  ticketSaving.value = true;
  try {
    const isEdit = !!ticketForm.value.id;
    const res = await request.post(isEdit ? '/activity/ticketType/update' : '/activity/ticketType/create',
        null, { params: {
            ...(isEdit ? { ticketTypeId: ticketForm.value.id } : { activityId: currentActivity.value.id }),
            ticketName: ticketForm.value.ticketName,
            totalStock: ticketForm.value.totalStock
          }});
    ElMessage.success(res.msg);
    ticketFormVisible.value = false;
    loadTickets(currentActivity.value.id);
  } finally {
    ticketSaving.value = false;
  }
};

const deleteTicket = async row => {
  try {
    await ElMessageBox.confirm(`确认删除票种《${row.ticketName}》？`, '提示', { type: 'warning' });
  } catch (e) { return; }
  const res = await request.post('/activity/ticketType/delete', null, { params: { ticketTypeId: row.id } });
  ElMessage.success(res.msg);
  loadTickets(currentActivity.value.id);
};

onMounted(() => load());
</script>

<style scoped>
.page { padding: 20px; }
.toolbar { margin-bottom: 15px; display: flex; gap: 10px; }
</style>

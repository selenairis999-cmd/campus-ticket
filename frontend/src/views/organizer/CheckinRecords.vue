<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <span>核销记录</span>
        <el-select v-model="activityId" placeholder="全部活动（本组织）" clearable style="width: 220px"
                   @change="loadRecords">
          <el-option v-for="a in activities" :key="a.id" :label="a.title" :value="a.id" />
        </el-select>
      </div>
      <div class="table-wrap">
        <el-table :data="records" v-loading="loading" size="small">
          <el-table-column prop="ticketCode" label="票号" width="200" />
          <el-table-column prop="activityTitle" label="活动" min-width="120" show-overflow-tooltip />
          <el-table-column prop="ticketName" label="票种" width="90" />
          <el-table-column prop="userName" label="持票人" width="100" />
          <el-table-column prop="checkerName" label="核销员" width="100" />
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
import { ref, onMounted } from 'vue';
import request from '@/utils/request';

const records = ref([]);
const total = ref(0);
const pageNum = ref(1);
const activityId = ref(null);
const loading = ref(false);
const activities = ref([]);

const fmt = t => (t ? t.replace('T', ' ').slice(0, 16) : '');

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
</script>

<style scoped>
.page { padding: 16px; max-width: 900px; margin: 0 auto; }
.toolbar { margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.table-wrap { overflow-x: auto; }
</style>

<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Leaderboard</div>
    <q-select v-model="taskId" :options="taskOptions" label="Task" emit-value map-options class="q-mb-md" @update:model-value="load" />
    <div v-for="row in rows" :key="row.user_id">{{ row.user_id }} — {{ row.count }}</div>
  </q-page>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { apiService } from 'src/services/api';
const rows = ref<Array<{user_id:string;count:number}>>([]);
const taskOptions = ref<Array<{label:string; value:string}>>([]);
const taskId = ref<string>('');
const load = async () => { if(taskId.value) rows.value = await apiService.getLeaderboard(taskId.value); };
onMounted(async()=>{ const tasks = await apiService.getTasks(); taskOptions.value=tasks.map(t=>({label:t.name,value:t.id})); if(tasks[0]){taskId.value=tasks[0].id; await load();}});
</script>

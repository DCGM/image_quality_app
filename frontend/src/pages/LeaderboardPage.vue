<template>
  <q-page class="q-pa-md">

    <!-- My contributions -->
    <div class="text-h5 q-mb-sm">My contributions</div>
    <q-card class="q-mb-lg" bordered>
      <q-card-section>
        <div class="text-h6 q-mb-sm">Total: <strong>{{ myStats.total }}</strong> annotations</div>
        <q-table
          v-if="myPerTaskRows.length"
          :rows="myPerTaskRows"
          :columns="myStatsCols"
          flat
          dense
          hide-bottom
          :rows-per-page-options="[0]"
        />
        <div v-else class="text-caption text-grey-6">No annotations yet.</div>
      </q-card-section>
    </q-card>

    <!-- Overall top annotators -->
    <div class="text-h5 q-mb-sm">Top annotators</div>
    <q-tabs v-model="overallTab" align="left" class="q-mb-sm">
      <q-tab name="week" icon="date_range" label="This week" />
      <q-tab name="all" icon="all_inclusive" label="All time" />
    </q-tabs>
    <q-card class="q-mb-lg" bordered>
      <q-tab-panels v-model="overallTab" animated>
        <q-tab-panel name="week">
          <q-table :rows="weeklyLb" :columns="lbCols" flat dense hide-bottom :rows-per-page-options="[0]"
            :loading="loadingOverall" no-data-label="No data for this week" />
        </q-tab-panel>
        <q-tab-panel name="all">
          <q-table :rows="allTimeLb" :columns="lbCols" flat dense hide-bottom :rows-per-page-options="[0]"
            :loading="loadingOverall" no-data-label="No annotations yet" />
        </q-tab-panel>
      </q-tab-panels>
    </q-card>

    <!-- Global stats per task -->
    <div class="text-h5 q-mb-sm">Statistics per task</div>
    <q-card class="q-mb-lg" bordered>
      <q-card-section>
        <div class="text-caption text-grey-6 q-mb-sm">Total across all tasks: {{ globalStats.total_annotations }}</div>
        <q-table
          :rows="globalStats.per_task"
          :columns="taskStatsCols"
          flat dense hide-bottom :rows-per-page-options="[0]"
          :loading="loadingGlobal"
          no-data-label="No annotations yet"
        />
      </q-card-section>
    </q-card>

    <!-- Per-task leaderboards -->
    <div class="text-h5 q-mb-sm">Per-task leaderboards</div>
    <q-list bordered separator class="rounded-borders">
      <q-expansion-item
        v-for="task in tasks"
        :key="task.id"
        :label="task.name"
        icon="leaderboard"
        @before-show="loadTaskLeaderboard(task.id)"
      >
        <q-card flat>
          <q-card-section>
            <q-table
              :rows="taskLbs[task.id] || []"
              :columns="lbCols"
              flat dense hide-bottom :rows-per-page-options="[0]"
              :loading="loadingTask[task.id]"
              no-data-label="No annotations yet"
            />
          </q-card-section>
        </q-card>
      </q-expansion-item>
    </q-list>

  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { QTableColumn } from 'quasar';
import { apiService } from 'src/services/api';
import { GlobalStats, LeaderboardEntry, MyStats, TaskDefinition, TaskStats } from 'src/types/api';

const myStats = ref<MyStats>({ total: 0, per_task: {} });
const tasks = ref<TaskDefinition[]>([]);
const weeklyLb = ref<LeaderboardEntry[]>([]);
const allTimeLb = ref<LeaderboardEntry[]>([]);
const globalStats = ref<GlobalStats>({ total_annotations: 0, per_task: [] });
const taskLbs = ref<Record<string, LeaderboardEntry[]>>({});
const loadingOverall = ref(false);
const loadingGlobal = ref(false);
const loadingTask = ref<Record<string, boolean>>({});
const overallTab = ref('week');

const myPerTaskRows = ref<{ task_id: string; task_name: string; count: number }[]>([]);

const myStatsCols: QTableColumn[] = [
  { name: 'task_name', label: 'Task', field: 'task_name', align: 'left' },
  { name: 'count', label: 'Annotations', field: 'count', align: 'right' },
];
const lbCols: QTableColumn[] = [
  { name: 'rank', label: '#', field: (_, ri) => ri + 1, align: 'right', style: 'width:40px' },
  { name: 'display_name', label: 'Annotator', field: 'display_name', align: 'left' },
  { name: 'count', label: 'Annotations', field: 'count', align: 'right' },
];
const taskStatsCols: QTableColumn[] = [
  { name: 'task_name', label: 'Task', field: 'task_name', align: 'left' },
  { name: 'count', label: 'Total annotations', field: 'count', align: 'right' },
];

const loadTaskLeaderboard = async (taskId: string) => {
  if (taskLbs.value[taskId]) return;
  loadingTask.value[taskId] = true;
  taskLbs.value[taskId] = await apiService.getLeaderboard(taskId);
  loadingTask.value[taskId] = false;
};

onMounted(async () => {
  [tasks.value, myStats.value] = await Promise.all([
    apiService.getTasks(),
    apiService.getMyStats(),
  ]);

  // Build per-task rows for my stats, enriched with task names
  const taskNameMap: Record<string, string> = Object.fromEntries(tasks.value.map((t) => [t.id, t.name]));
  myPerTaskRows.value = Object.entries(myStats.value.per_task).map(([id, count]) => ({
    task_id: id, task_name: taskNameMap[id] || id, count,
  })).sort((a, b) => b.count - a.count);

  loadingOverall.value = true;
  loadingGlobal.value = true;
  [weeklyLb.value, allTimeLb.value, globalStats.value] = await Promise.all([
    apiService.getOverallLeaderboard(7),
    apiService.getOverallLeaderboard(),
    apiService.getGlobalStats(),
  ]);
  loadingOverall.value = false;
  loadingGlobal.value = false;
});
</script>

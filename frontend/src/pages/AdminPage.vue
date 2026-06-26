<template>
  <q-page class="q-pa-md">
    <div class="text-h4 q-mb-md">Admin Panel</div>

    <q-tabs v-model="tab" align="left" class="q-mb-md text-primary" indicator-color="primary">
      <q-tab name="tasks" icon="task" label="Tasks" />
      <q-tab name="images" icon="image" label="Images" />
      <q-tab name="rankings" icon="bar_chart" label="Rankings" />
      <q-tab name="data" icon="list_alt" label="Comparisons / Ratings" />
      <q-tab name="reliability" icon="verified_user" label="Reliability" />
    </q-tabs>

    <q-tab-panels v-model="tab" animated keep-alive>

      <!-- TASKS -->
      <q-tab-panel name="tasks">
        <div class="row items-center q-mb-md">
          <div class="text-h6">Tasks</div>
          <q-space />
          <q-btn color="primary" icon="add" label="New task" @click="openNewTask" />
        </div>
        <q-table :rows="adminTasks" :columns="taskCols" flat bordered :loading="tasksLoading"
          no-data-label="No tasks yet" row-key="id">
          <template #body-cell-enabled="props">
            <q-td :props="props">
              <q-badge :color="props.row.enabled ? 'positive' : 'grey'" :label="props.row.enabled ? 'Enabled' : 'Disabled'" />
            </q-td>
          </template>
          <template #body-cell-task_type="props">
            <q-td :props="props">
              <q-badge :color="props.row.task_type === 'two_forced_choice' ? 'deep-purple' : 'teal'"
                :label="props.row.task_type === 'two_forced_choice' ? '2-Choice' : 'Rating'" />
            </q-td>
          </template>
          <template #body-cell-actions="props">
            <q-td :props="props">
              <q-btn flat dense icon="edit" @click="editTask(props.row)" />
              <q-btn flat dense :icon="props.row.enabled ? 'visibility_off' : 'visibility'" @click="toggleTask(props.row)" />
              <q-btn flat dense icon="upload" color="primary" @click="openUploadImages(props.row.id)" />
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- IMAGES -->
      <q-tab-panel name="images">
        <div class="row items-center q-mb-md">
          <div class="text-h6">Image Browser</div>
          <q-space />
          <q-select v-model="imageTaskId" :options="taskOptions" label="Task" dense outlined class="q-mr-sm" style="min-width:180px" emit-value map-options />
          <q-btn color="primary" icon="search" @click="loadImages" dense />
        </div>
        <div class="row q-col-gutter-md q-mb-md">
          <div v-for="img in images" :key="img.id" class="col-6 col-sm-4 col-md-3 col-lg-2">
            <q-card bordered>
              <img :src="imageFullUrl(img.url)" class="thumb" :alt="img.filename" />
              <q-card-section class="q-pa-xs text-caption" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {{ img.filename }}
                <q-badge v-if="img.suspended" color="negative" label="Suspended" />
              </q-card-section>
              <q-card-actions class="q-pa-xs">
                <q-btn flat dense :icon="img.suspended ? 'visibility' : 'visibility_off'"
                  :color="img.suspended ? 'positive' : 'warning'" @click="toggleImage(img)" />
              </q-card-actions>
            </q-card>
          </div>
        </div>
        <q-pagination v-if="imagesTotalPages > 1" v-model="imagePage" :max="imagesTotalPages" @update:model-value="loadImages" />
      </q-tab-panel>

      <!-- RANKINGS -->
      <q-tab-panel name="rankings">
        <div class="row items-center q-mb-md">
          <div class="text-h6">Image Rankings</div>
          <q-space />
          <q-select v-model="rankingTaskId" :options="taskOptions" label="Task" dense outlined style="min-width:180px" emit-value map-options @update:model-value="loadRankings" />
        </div>
        <q-table :rows="rankings" :columns="rankingCols" flat bordered :loading="rankingsLoading"
          no-data-label="Select a task to see rankings" row-key="image_id">
          <template #body-cell-url="props">
            <q-td :props="props">
              <img :src="imageFullUrl(props.row.url)" style="height:48px;width:auto;object-fit:contain;" />
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- DATA -->
      <q-tab-panel name="data">
        <q-tabs v-model="dataTab" align="left" class="q-mb-md">
          <q-tab name="comparisons" label="Comparisons" />
          <q-tab name="ratings" label="Ratings" />
        </q-tabs>
        <div class="row items-center q-mb-md">
          <q-select v-model="dataTaskId" :options="[{label:'All tasks', value: ''}, ...taskOptions]" label="Filter by task"
            dense outlined style="min-width:180px" emit-value map-options @update:model-value="loadData" />
        </div>
        <q-tab-panels v-model="dataTab" animated>
          <q-tab-panel name="comparisons">
            <q-table :rows="comparisons.items" :columns="compCols" flat bordered :loading="dataLoading" no-data-label="No comparisons" row-key="id">
              <template #body-cell-is_reliability_check="props">
                <q-td :props="props"><q-badge v-if="props.row.is_reliability_check" color="amber" label="Reliability" /></q-td>
              </template>
            </q-table>
            <div class="row justify-end q-mt-sm">
              <q-pagination v-model="comparisonsPage" :max="Math.max(1, Math.ceil(comparisons.total/50))" @update:model-value="loadData" />
            </div>
          </q-tab-panel>
          <q-tab-panel name="ratings">
            <q-table :rows="ratings.items" :columns="ratingCols" flat bordered :loading="dataLoading" no-data-label="No ratings" row-key="id">
              <template #body-cell-is_reliability_check="props">
                <q-td :props="props"><q-badge v-if="props.row.is_reliability_check" color="amber" label="Reliability" /></q-td>
              </template>
            </q-table>
            <div class="row justify-end q-mt-sm">
              <q-pagination v-model="ratingsPage" :max="Math.max(1, Math.ceil(ratings.total/50))" @update:model-value="loadData" />
            </div>
          </q-tab-panel>
        </q-tab-panels>
      </q-tab-panel>

      <!-- RELIABILITY -->
      <q-tab-panel name="reliability">
        <div class="row items-center q-mb-md">
          <div class="text-h6">User Reliability</div>
          <q-space />
          <q-btn color="primary" icon="refresh" label="Recompute" :loading="recomputeLoading" @click="recompute" />
        </div>
        <q-table :rows="reliability" :columns="relCols" flat bordered no-data-label="No reliability data yet" row-key="user_id" />
      </q-tab-panel>
    </q-tab-panels>

    <!-- Task Dialog -->
    <q-dialog v-model="taskDialog" persistent>
      <q-card style="min-width: 500px; max-width: 700px; width: 90vw">
        <q-card-section><div class="text-h6">{{ editingTask?.id ? 'Edit Task' : 'New Task' }}</div></q-card-section>
        <q-card-section class="q-gutter-md" style="max-height: 70vh; overflow-y: auto">
          <q-input v-model="taskForm.id" label="Task ID (snake_case)" outlined dense :disable="!!editingTask?.id" />
          <q-input v-model="taskForm.name" label="Name" outlined dense />
          <q-input v-model="taskForm.description_md" label="Description (Markdown)" outlined dense type="textarea" autogrow />
          <q-input v-model="taskForm.instructions_md" label="Instructions (Markdown)" outlined dense type="textarea" autogrow />
          <q-select v-model="taskForm.task_type" :options="['two_forced_choice','single_rating']" label="Task type" outlined dense />
          <div v-if="taskForm.task_type === 'two_forced_choice'">
            <q-select v-model="taskForm.pair_algorithm"
              :options="[{label:'Least seen',value:'least_seen'},{label:'Swiss tournament',value:'swiss'},{label:'Bradley-Terry',value:'bradley_terry'}]"
              label="Pair selection algorithm" outlined dense emit-value map-options />
          </div>
          <div v-if="taskForm.task_type === 'single_rating'">
            <q-input v-model="ratingOptionsStr" label="Rating options (one per line)" outlined dense type="textarea" autogrow />
            <q-input v-model="ratingHotkeysStr" label="Hotkeys (one per line, optional)" outlined dense type="textarea" autogrow />
          </div>
          <q-input v-model.number="taskForm.bonus_multiplier" label="Bonus multiplier" outlined dense type="number" step="0.1" min="1" />
          <q-input v-model.number="taskForm.calib_ratio" label="Reliability re-check ratio (0-1)" outlined dense type="number" step="0.05" min="0" max="1" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" @click="taskDialog = false" />
          <q-btn color="primary" label="Save" :loading="taskSaving" @click="saveTask" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Upload Dialog -->
    <q-dialog v-model="uploadDialog">
      <q-card style="min-width: 400px">
        <q-card-section>
          <div class="text-h6">Upload Images — {{ uploadTaskId }}</div>
          <div class="text-body2 text-grey-7 q-mt-sm">Upload a ZIP. Images are grouped by filename prefix (e.g. groupA_01.jpg).</div>
        </q-card-section>
        <q-card-section>
          <q-file v-model="uploadFile" label="ZIP archive" accept=".zip" outlined dense />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" @click="uploadDialog = false" />
          <q-btn color="primary" label="Upload" :loading="uploadLoading" @click="doUpload" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import { apiService } from 'src/services/api';
import {
  ImageItemResponse, ImageRankingResponse, PaginatedComparisons, PaginatedRatings,
  TaskCreate, TaskRead, UserReliabilityResponse,
} from 'src/types/api';

const $q = useQuasar();
const tab = ref('tasks');
const dataTab = ref('comparisons');

const adminTasks = ref<TaskRead[]>([]);
const tasksLoading = ref(false);
const taskDialog = ref(false);
const taskSaving = ref(false);
const editingTask = ref<TaskRead | null>(null);
const taskForm = reactive<TaskCreate>({
  id: '', name: '', description_md: '', instructions_md: '',
  task_type: 'two_forced_choice', pair_algorithm: 'least_seen',
  rating_options: null, rating_hotkeys: null, bonus_multiplier: 1.0, calib_ratio: 0.15,
});
const ratingOptionsStr = ref('');
const ratingHotkeysStr = ref('');
const algorithmDescriptions = ref<Record<string, string>>({});

const imageTaskId = ref('');
const images = ref<ImageItemResponse[]>([]);
const imagePage = ref(1);
const imagePageSize = 48;
const imagesTotal = ref(0);
const imagesTotalPages = ref(1);

const rankingTaskId = ref('');
const rankings = ref<ImageRankingResponse[]>([]);
const rankingsLoading = ref(false);

const dataTaskId = ref('');
const comparisons = ref<PaginatedComparisons>({ total: 0, items: [] });
const ratings = ref<PaginatedRatings>({ total: 0, items: [] });
const comparisonsPage = ref(1);
const ratingsPage = ref(1);
const dataLoading = ref(false);

const reliability = ref<UserReliabilityResponse[]>([]);
const recomputeLoading = ref(false);

const uploadDialog = ref(false);
const uploadTaskId = ref('');
const uploadFile = ref<File | null>(null);
const uploadLoading = ref(false);

const taskOptions = ref<{ label: string; value: string }[]>([]);

const taskCols = [
  { name: 'id', label: 'ID', field: 'id', align: 'left' as const },
  { name: 'name', label: 'Name', field: 'name', align: 'left' as const },
  { name: 'task_type', label: 'Type', field: 'task_type', align: 'center' as const },
  { name: 'enabled', label: 'Status', field: 'enabled', align: 'center' as const },
  { name: 'bonus_multiplier', label: 'Bonus', field: 'bonus_multiplier', align: 'right' as const },
  { name: 'actions', label: 'Actions', field: 'id', align: 'center' as const },
];
const rankingCols = [
  { name: 'url', label: 'Preview', field: 'url', align: 'center' as const },
  { name: 'filename', label: 'Filename', field: 'filename', align: 'left' as const },
  { name: 'score', label: 'Score', field: 'score', sortable: true, align: 'right' as const, format: (v: number) => v.toFixed(1) },
  { name: 'comparisons', label: 'Comparisons', field: 'comparisons', sortable: true, align: 'right' as const },
  { name: 'wins', label: 'Wins', field: 'wins', sortable: true, align: 'right' as const },
];
const compCols = [
  { name: 'display_name', label: 'User', field: 'display_name', align: 'left' as const },
  { name: 'task_id', label: 'Task', field: 'task_id', align: 'left' as const },
  { name: 'group_id', label: 'Group', field: 'group_id', align: 'left' as const },
  { name: 'winner_id', label: 'Winner', field: 'winner_id', align: 'left' as const, format: (v: string) => v?.split('/').pop() ?? '' },
  { name: 'is_reliability_check', label: 'Type', field: 'is_reliability_check', align: 'center' as const },
  { name: 'points_earned', label: 'Points', field: 'points_earned', align: 'right' as const, format: (v: number | null) => v?.toFixed(2) ?? '-' },
  { name: 'created_at', label: 'Date', field: 'created_at', align: 'left' as const, format: (v: string) => new Date(v).toLocaleString() },
];
const ratingCols = [
  { name: 'display_name', label: 'User', field: 'display_name', align: 'left' as const },
  { name: 'task_id', label: 'Task', field: 'task_id', align: 'left' as const },
  { name: 'image_id', label: 'Image', field: 'image_id', align: 'left' as const, format: (v: string) => v?.split('/').pop() ?? '' },
  { name: 'selected_option', label: 'Option', field: 'selected_option', align: 'left' as const },
  { name: 'is_reliability_check', label: 'Type', field: 'is_reliability_check', align: 'center' as const },
  { name: 'points_earned', label: 'Points', field: 'points_earned', align: 'right' as const, format: (v: number | null) => v?.toFixed(2) ?? '-' },
  { name: 'created_at', label: 'Date', field: 'created_at', align: 'left' as const, format: (v: string) => new Date(v).toLocaleString() },
];
const relCols = [
  { name: 'display_name', label: 'User', field: 'display_name', align: 'left' as const },
  { name: 'task_id', label: 'Task', field: 'task_id', align: 'left' as const },
  { name: 'annotation_count', label: 'Count', field: 'annotation_count', align: 'right' as const },
  { name: 'consistency_score', label: 'Consistency', field: 'consistency_score', align: 'right' as const, format: (v: number | null) => v != null ? (v * 100).toFixed(0) + '%' : '-' },
  { name: 'inter_rater_agreement', label: 'Inter-rater', field: 'inter_rater_agreement', align: 'right' as const, format: (v: number | null) => v != null ? (v * 100).toFixed(0) + '%' : '-' },
  { name: 'computed_at', label: 'Computed', field: 'computed_at', align: 'left' as const, format: (v: string | null) => v ? new Date(v).toLocaleString() : '-' },
];

onMounted(async () => {
  await loadTasks();
  algorithmDescriptions.value = await apiService.getAlgorithmDescriptions().catch(() => ({}));
});

watch(tab, (val) => {
  if (val === 'data') void loadData();
  if (val === 'reliability') void loadReliability();
});

async function loadTasks() {
  tasksLoading.value = true;
  adminTasks.value = await apiService.getAdminTasks().catch(() => []);
  taskOptions.value = adminTasks.value.map((t) => ({ label: t.name, value: t.id }));
  tasksLoading.value = false;
}

function openNewTask() {
  editingTask.value = null;
  Object.assign(taskForm, { id: '', name: '', description_md: '', instructions_md: '', task_type: 'two_forced_choice', pair_algorithm: 'least_seen', rating_options: null, rating_hotkeys: null, bonus_multiplier: 1.0, calib_ratio: 0.15 });
  ratingOptionsStr.value = '';
  ratingHotkeysStr.value = '';
  taskDialog.value = true;
}

function editTask(task: TaskRead) {
  editingTask.value = task;
  Object.assign(taskForm, { ...task });
  ratingOptionsStr.value = (task.rating_options ?? []).join('\n');
  ratingHotkeysStr.value = (task.rating_hotkeys ?? []).join('\n');
  taskDialog.value = true;
}

async function saveTask() {
  taskSaving.value = true;
  try {
    const payload: TaskCreate = {
      ...taskForm,
      rating_options: taskForm.task_type === 'single_rating' ? ratingOptionsStr.value.split('\n').map((s) => s.trim()).filter(Boolean) : null,
      rating_hotkeys: taskForm.task_type === 'single_rating' && ratingHotkeysStr.value ? ratingHotkeysStr.value.split('\n').map((s) => s.trim()).filter(Boolean) : null,
    };
    if (editingTask.value?.id) await apiService.updateAdminTask(editingTask.value.id, payload);
    else await apiService.createAdminTask(payload);
    taskDialog.value = false;
    await loadTasks();
    $q.notify({ type: 'positive', message: 'Task saved' });
  } catch {
    $q.notify({ type: 'negative', message: 'Save failed' });
  } finally {
    taskSaving.value = false;
  }
}

async function toggleTask(task: TaskRead) {
  await apiService.patchAdminTask(task.id, { enabled: !task.enabled });
  await loadTasks();
}

function openUploadImages(taskId: string) {
  uploadTaskId.value = taskId;
  uploadFile.value = null;
  uploadDialog.value = true;
}

async function doUpload() {
  if (!uploadFile.value) return;
  uploadLoading.value = true;
  try {
    const result = await apiService.uploadImages(uploadTaskId.value, uploadFile.value);
    $q.notify({ type: 'positive', message: 'Imported ' + result.imported + ' images' });
    uploadDialog.value = false;
  } catch {
    $q.notify({ type: 'negative', message: 'Upload failed' });
  } finally {
    uploadLoading.value = false;
  }
}

async function loadImages() {
  if (!imageTaskId.value) return;
  const res = await apiService.getAdminImages(imageTaskId.value, imagePage.value, imagePageSize, undefined);
  images.value = res.items;
  imagesTotal.value = res.total;
  imagesTotalPages.value = Math.ceil(res.total / imagePageSize) || 1;
}

async function toggleImage(img: ImageItemResponse) {
  await apiService.patchAdminImage(img.id, !img.suspended);
  await loadImages();
}

async function loadRankings() {
  if (!rankingTaskId.value) return;
  rankingsLoading.value = true;
  rankings.value = await apiService.getAdminRankings(rankingTaskId.value).catch(() => []);
  rankingsLoading.value = false;
}

async function loadData() {
  dataLoading.value = true;
  const tid = dataTaskId.value || undefined;
  const [c, r] = await Promise.all([
    apiService.getAdminComparisons(tid, comparisonsPage.value),
    apiService.getAdminRatings(tid, ratingsPage.value),
  ]);
  comparisons.value = c;
  ratings.value = r;
  dataLoading.value = false;
}

async function loadReliability() {
  reliability.value = await apiService.getAdminReliability().catch(() => []);
}

async function recompute() {
  recomputeLoading.value = true;
  await apiService.recomputeReliability();
  await loadReliability();
  recomputeLoading.value = false;
  $q.notify({ type: 'positive', message: 'Reliability recomputed' });
}

function imageFullUrl(path: string): string {
  return apiService.imageUrl(path);
}
</script>

<style scoped>
.thumb { width: 100%; height: 100px; object-fit: cover; display: block; }
</style>

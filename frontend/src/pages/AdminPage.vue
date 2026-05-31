<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Admin</div>

    <q-tabs v-model="tab" align="left" class="q-mb-md" dense>
      <q-tab name="tasks" icon="assignment" label="Tasks" />
      <q-tab name="import" icon="upload_file" label="Import" />
      <q-tab name="texts" icon="article" label="Texts" />
      <q-tab name="reliability" icon="verified_user" label="Reliability" />
    </q-tabs>

    <!-- ===================== TASKS TAB ===================== -->
    <q-tab-panels v-model="tab" animated keep-alive>
      <q-tab-panel name="tasks" class="q-pa-none">
        <div class="row items-center q-mb-md">
          <div class="text-subtitle1">Task definitions</div>
          <q-space />
          <q-btn color="primary" icon="add" label="New task" @click="openNewTask" />
          <q-btn flat icon="refresh" class="q-ml-sm" @click="loadTasks" />
        </div>

        <q-table
          :rows="tasks"
          :columns="taskCols"
          flat
          bordered
          :rows-per-page-options="[0]"
          hide-bottom
          row-key="id"
        >
          <template #body-cell-enabled="props">
            <q-td :props="props">
              <q-badge :color="props.row.enabled ? 'positive' : 'grey-5'" :label="props.row.enabled ? 'enabled' : 'disabled'" />
            </q-td>
          </template>
          <template #body-cell-actions="props">
            <q-td :props="props" class="q-gutter-xs">
              <q-btn flat dense round icon="edit" size="sm" @click="openEditTask(props.row)" />
              <q-btn flat dense round :icon="props.row.enabled ? 'toggle_off' : 'toggle_on'"
                :color="props.row.enabled ? 'negative' : 'positive'" size="sm"
                @click="toggleEnabled(props.row)" />
              <q-btn flat dense round icon="delete" color="negative" size="sm" @click="confirmDelete(props.row)" />
            </q-td>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- ===================== IMPORT TAB ===================== -->
      <q-tab-panel name="import">
        <div class="text-subtitle1 q-mb-md">Import task definitions from prompts/*.md</div>
        <q-card flat bordered class="q-pa-md q-mb-lg">
          <div class="text-body2 text-grey-7 q-mb-md">
            Parses all Markdown files in the <code>prompts/</code> directory and upserts them as task definitions.
            Re-importing a prompt updates the existing task while preserving annotations.
          </div>
          <q-btn color="primary" icon="upload" label="Import prompts/*.md" :loading="importing" @click="importPrompts" />
          <div v-if="importMsg" class="q-mt-md text-positive">{{ importMsg }}</div>
        </q-card>

        <div class="text-subtitle1 q-mb-md">Upload ground-truth annotations (JSONL)</div>
        <q-card flat bordered class="q-pa-md q-mb-lg">
          <div class="text-body2 text-grey-7 q-mb-md">
            Each line: <code>{"text_id":"…","task_id":"…","selected_classes":["…"]}</code>.
            Existing GT for the same (text, task) will be overwritten.
          </div>
          <div class="row q-gutter-sm items-center">
            <q-file v-model="gtFile" label="GT JSONL file" accept=".jsonl,.txt,text/plain" dense outlined style="max-width:260px">
              <template #prepend><q-icon name="attach_file" /></template>
            </q-file>
            <q-btn color="primary" icon="upload" label="Upload GT" :disable="!gtFile" :loading="uploadingGt" @click="uploadGt" />
          </div>
          <div v-if="gtMsg" class="q-mt-sm" :class="gtError ? 'text-negative' : 'text-positive'">{{ gtMsg }}</div>
        </q-card>

        <div class="text-subtitle1 q-mb-md">Upload LLM annotations (JSONL)</div>
        <q-card flat bordered class="q-pa-md">
          <div class="text-body2 text-grey-7 q-mb-md">
            Same format as GT. Stored as <code>llm</code> type — used only for reliability computation, never shown to users.
          </div>
          <div class="row q-gutter-sm items-center">
            <q-file v-model="llmFile" label="LLM JSONL file" accept=".jsonl,.txt,text/plain" dense outlined style="max-width:260px">
              <template #prepend><q-icon name="attach_file" /></template>
            </q-file>
            <q-btn color="secondary" icon="upload" label="Upload LLM" :disable="!llmFile" :loading="uploadingLlm" @click="uploadLlm" />
          </div>
          <div v-if="llmMsg" class="q-mt-sm" :class="llmError ? 'text-negative' : 'text-positive'">{{ llmMsg }}</div>
        </q-card>
      </q-tab-panel>

      <!-- ===================== TEXTS TAB ===================== -->
      <q-tab-panel name="texts" class="q-pa-none">
        <div class="row items-center q-mb-md">
          <div class="text-subtitle1">Text records</div>
          <q-space />
          <q-file
            v-model="textFile"
            label="Upload JSONL file"
            accept=".jsonl,.txt,text/plain"
            dense outlined
            style="max-width:260px"
            class="q-mr-sm"
          >
            <template #prepend><q-icon name="attach_file" /></template>
          </q-file>
          <q-btn color="secondary" icon="upload" label="Upload" :disable="!textFile" :loading="uploading" @click="uploadTexts" />
        </div>

        <div v-if="uploadMsg" class="q-mb-md">
          <q-banner :class="uploadError ? 'bg-negative text-white' : 'bg-positive text-white'" dense rounded>{{ uploadMsg }}</q-banner>
        </div>

        <div class="row q-col-gutter-sm q-mb-md">
          <q-input v-model="textSearch" dense outlined placeholder="Search texts…" class="col-12 col-sm" debounce="400"
            @update:model-value="loadTexts(0)">
            <template #append><q-icon name="search" /></template>
          </q-input>
          <q-select
            v-model="textTaskFilter"
            :options="textTaskOptions"
            option-value="id"
            option-label="name"
            emit-value
            map-options
            clearable
            dense
            outlined
            label="Filter ann. count by task"
            class="col-12 col-sm-4"
            @update:model-value="loadTexts(0)"
          />
        </div>

        <q-table
          :rows="textRows"
          :columns="textCols"
          flat bordered
          :rows-per-page-options="[50]"
          :loading="loadingTexts"
          row-key="id"
        >
          <template #body-cell-suspended="props">
            <q-td :props="props">
              <q-badge :color="props.row.suspended ? 'negative' : 'positive'"
                :label="props.row.suspended ? 'suspended' : 'active'" />
            </q-td>
          </template>
          <template #body-cell-actions="props">
            <q-td :props="props" class="q-gutter-xs">
              <q-btn flat dense round icon="list_alt" color="primary" size="sm"
                @click="openTextAnnotations(props.row)">
                <q-tooltip>View annotations</q-tooltip>
              </q-btn>
              <q-btn flat dense round
                :icon="props.row.suspended ? 'play_circle' : 'pause_circle'"
                :color="props.row.suspended ? 'positive' : 'negative'"
                size="sm"
                @click="toggleSuspend(props.row)"
              >
                <q-tooltip>{{ props.row.suspended ? 'Unsuspend' : 'Suspend' }}</q-tooltip>
              </q-btn>
            </q-td>
          </template>
          <template #bottom>
            <q-pagination v-model="textPage" :max="textMaxPage" boundary-links @update:model-value="loadTexts($event - 1)" />
            <div class="q-ml-md text-caption text-grey-6">{{ textTotal }} total</div>
          </template>
        </q-table>
      </q-tab-panel>

      <!-- ===================== RELIABILITY TAB ===================== -->
      <q-tab-panel name="reliability" class="q-pa-none">
        <div class="row items-center q-mb-md">
          <div class="text-subtitle1">Inter-annotator reliability</div>
          <q-space />
          <q-btn flat icon="refresh" label="Recompute" :loading="recomputing" @click="recomputeIrr" />
        </div>
        <div v-if="irrData.length === 0 && !loadingIrr" class="text-caption text-grey-6 q-mb-md">
          No reliability data yet. Upload annotations and click Recompute.
        </div>
        <q-table
          :rows="irrData"
          :columns="irrCols"
          flat
          bordered
          :loading="loadingIrr"
          :rows-per-page-options="[0]"
          hide-bottom
          row-key="user_id+task_id"
        >
          <template #body-cell-pairwise_agreement="props">
            <q-td :props="props">{{ props.value != null ? `${(props.value * 100).toFixed(0)}%` : '—' }}</q-td>
          </template>
          <template #body-cell-cohens_kappa="props">
            <q-td :props="props">{{ props.value != null ? props.value.toFixed(3) : '—' }}</q-td>
          </template>
          <template #body-cell-krippendorffs_alpha="props">
            <q-td :props="props">{{ props.value != null ? props.value.toFixed(3) : '—' }}</q-td>
          </template>
          <template #body-cell-computed_at="props">
            <q-td :props="props">{{ props.value ? new Date(props.value).toLocaleString() : '—' }}</q-td>
          </template>
        </q-table>
      </q-tab-panel>
    </q-tab-panels>

    <!-- ===================== TEXT ANNOTATIONS DIALOG ===================== -->
    <q-dialog v-model="textAnnotationsDialog" maximized transition-show="slide-up" transition-hide="slide-down">
      <q-card class="column full-height">
        <q-card-section class="row items-center bg-primary text-white">
          <div class="text-h6">Annotations — {{ textAnnotationsTextId }}</div>
          <q-space />
          <q-btn flat round dense icon="close" @click="textAnnotationsDialog = false" />
        </q-card-section>
        <q-table
          class="col"
          :rows="textAnnotationRows"
          :columns="textAnnotationCols"
          flat
          :loading="loadingTextAnnotations"
          :rows-per-page-options="[0]"
          hide-bottom
          row-key="annotation_id"
        >
          <template #body-cell-annotation_type="props">
            <q-td :props="props">
              <q-badge :color="props.value === 'ground_truth' ? 'deep-orange' : props.value === 'llm' ? 'blue' : 'grey-7'"
                :label="props.value" />
            </q-td>
          </template>
          <template #body-cell-selected_classes="props">
            <q-td :props="props">{{ props.value.join(', ') }}</q-td>
          </template>
          <template #body-cell-points_earned="props">
            <q-td :props="props">{{ props.value != null ? props.value.toFixed(2) : '—' }}</q-td>
          </template>
          <template #body-cell-created_at="props">
            <q-td :props="props">{{ props.value ? new Date(props.value).toLocaleString() : '—' }}</q-td>
          </template>
        </q-table>
      </q-card>
    </q-dialog>

    <!-- ===================== TASK EDITOR DIALOG ===================== -->
    <q-dialog v-model="taskDialog" persistent maximized transition-show="slide-up" transition-hide="slide-down">
      <q-card class="column full-height" v-if="editingTask">
        <q-card-section class="row items-center bg-primary text-white">
          <div class="text-h6">{{ isNewTask ? 'New task' : `Edit: ${editingTask.id}` }}</div>
          <q-space />
          <q-btn flat round dense icon="close" @click="taskDialog = false" />
        </q-card-section>

        <q-scroll-area class="col">
          <div class="q-pa-md">
            <div class="row q-col-gutter-md q-mb-md">
              <div class="col-12 col-md-4">
                <q-input v-model="editingTask.id" label="Task ID" :readonly="!isNewTask" outlined dense />
              </div>
              <div class="col-12 col-md-4">
                <q-input v-model="editingTask.name" label="Task name" outlined dense />
              </div>
              <div class="col-12 col-md-2">
                <q-toggle v-model="editingTask.enabled" label="Enabled" />
              </div>
              <div class="col-12 col-md-2">
                <q-toggle v-model="editingTask.multi_choice" label="Multi-choice" @update:model-value="normalizeMaxChoices(editingTask)" />
              </div>
            </div>

            <div class="row q-col-gutter-md q-mb-md">
              <div class="col-12 col-md-3">
                <q-input v-model.number="editingTask.max_choices" type="number" label="Max choices"
                  :min="1" :max="editingTask.classes.length" :disable="!editingTask.multi_choice" outlined dense
                  @update:model-value="normalizeMaxChoices(editingTask)" />
              </div>
            </div>

            <q-input v-model="editingTask.description_md" type="textarea" label="Prompt markdown" autogrow outlined class="q-mb-md" />

            <div class="text-subtitle2 q-mb-sm q-mt-md">Sampling configuration</div>
            <div class="row q-col-gutter-md q-mb-md">
              <div class="col-12 col-sm-6 col-md-3">
                <q-input v-model.number="editingTask.calib_ratio_initial" type="number" label="Initial calib ratio (0–1)"
                  :min="0" :max="1" step="0.05" outlined dense />
              </div>
              <div class="col-12 col-sm-6 col-md-3">
                <q-input v-model.number="editingTask.calib_initial_count" type="number" label="Calib initial count"
                  :min="0" outlined dense />
              </div>
              <div class="col-12 col-sm-6 col-md-3">
                <q-input v-model.number="editingTask.calib_ratio_ongoing" type="number" label="Ongoing calib ratio (0–1)"
                  :min="0" :max="1" step="0.05" outlined dense />
              </div>
              <div class="col-12 col-sm-6 col-md-3">
                <q-input v-model.number="editingTask.repeat_probability" type="number" label="Repeat probability (0–1)"
                  :min="0" :max="1" step="0.05" outlined dense />
              </div>
              <div class="col-12 col-sm-6 col-md-3">
                <q-input v-model.number="editingTask.target_coverage" type="number" label="Target coverage (annotations/text)"
                  :min="1" outlined dense />
              </div>
            </div>

            <div class="text-subtitle2 q-mb-sm">Choices</div>
            <div v-for="(choice, index) in editingTask.classes" :key="`${editingTask.id}-${index}`"
              class="row q-col-gutter-sm q-mb-sm items-center">
              <div class="col-12 col-md-2">
                <q-input v-model="choice.id" label="Class ID" dense outlined />
              </div>
              <div class="col-12 col-md-2">
                <q-input v-model="choice.label_en" label="English label" dense outlined />
              </div>
              <div class="col-12 col-md-2">
                <q-input v-model="choice.label_cs" label="Czech label" dense outlined />
              </div>
              <div class="col-12 col-md-5">
                <q-input v-model="choice.description" label="Description (shown as tooltip)" dense outlined clearable />
              </div>
              <div class="col-12 col-md-1 flex items-center">
                <q-btn flat color="negative" icon="delete" dense :disable="editingTask.classes.length === 1" @click="removeChoice(editingTask, index)" />
              </div>
            </div>
            <q-btn flat color="primary" icon="add" label="Add choice" @click="addChoice(editingTask)" />

            <q-banner v-if="dialogError" class="bg-negative text-white q-mt-md" rounded>{{ dialogError }}</q-banner>
          </div>
        </q-scroll-area>

        <q-separator />
        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat label="Cancel" @click="taskDialog = false" />
          <q-btn color="primary" :label="isNewTask ? 'Create task' : 'Save changes'" :loading="savingTask" @click="saveTask" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Delete confirm dialog -->
    <q-dialog v-model="deleteDialog">
      <q-card>
        <q-card-section>
          <div class="text-h6">Delete task</div>
          <div class="q-mt-sm">Delete <strong>{{ deletingTask?.name }}</strong>? This cannot be undone.</div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" @click="deleteDialog = false" />
          <q-btn color="negative" label="Delete" @click="deleteTask" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { QTableColumn } from 'quasar';
import { TaskDefinition, TextAnnotationEntry, TextItemResponse, UserReliabilityResponse } from 'src/types/api';
import { apiService } from 'src/services/api';

// ---- Tabs ----
const tab = ref('tasks');

// ---- Tasks tab ----
const tasks = ref<TaskDefinition[]>([]);
const taskCols: QTableColumn[] = [
  { name: 'id', label: 'ID', field: 'id', align: 'left', style: 'width:160px' },
  { name: 'name', label: 'Name', field: 'name', align: 'left' },
  { name: 'enabled', label: 'Status', field: 'enabled', align: 'center', style: 'width:100px' },
  { name: 'actions', label: '', field: 'id', align: 'right', style: 'width:120px' },
];

const loadTasks = async () => {
  tasks.value = (await apiService.getAdminTasks()).map(cloneTask);
};

const cloneTask = (task: TaskDefinition): TaskDefinition => JSON.parse(JSON.stringify(task)) as TaskDefinition;

const toggleEnabled = async (task: TaskDefinition) => {
  await apiService.patchAdminTask(task.id, { enabled: !task.enabled });
  await loadTasks();
};

const deleteDialog = ref(false);
const deletingTask = ref<TaskDefinition | null>(null);
const confirmDelete = (task: TaskDefinition) => { deletingTask.value = task; deleteDialog.value = true; };
const deleteTask = async () => {
  if (!deletingTask.value) return;
  await apiService.patchAdminTask(deletingTask.value.id, { deleted: true });
  deleteDialog.value = false;
  await loadTasks();
};

// ---- Task editor dialog ----
const taskDialog = ref(false);
const isNewTask = ref(false);
const editingTask = ref<TaskDefinition | null>(null);
const savingTask = ref(false);
const dialogError = ref('');

const blankTask = (): TaskDefinition => ({
  id: '', name: '', description_md: '', multi_choice: false, max_choices: 1, enabled: true,
  classes: [{ id: 'class_1', label_en: 'Class 1', label_cs: 'Třída 1' }],
  calib_ratio_initial: 0.30, calib_initial_count: 20, calib_ratio_ongoing: 0.10,
  repeat_probability: 0.20, target_coverage: 3,
});

const openNewTask = () => {
  editingTask.value = blankTask();
  isNewTask.value = true;
  dialogError.value = '';
  taskDialog.value = true;
};

const openEditTask = (task: TaskDefinition) => {
  editingTask.value = cloneTask(task);
  isNewTask.value = false;
  dialogError.value = '';
  taskDialog.value = true;
};

const normalizeMaxChoices = (task: TaskDefinition) => {
  if (!task.multi_choice) { task.max_choices = 1; return; }
  const max = Math.max(task.classes.length, 1);
  task.max_choices = Math.min(Math.max(Number(task.max_choices) || 1, 1), max);
};

const addChoice = (task: TaskDefinition) => {
  task.classes.push({ id: `class_${task.classes.length + 1}`, label_en: 'New class', label_cs: 'nová třída', description: undefined });
  normalizeMaxChoices(task);
};

const removeChoice = (task: TaskDefinition, index: number) => {
  task.classes.splice(index, 1);
  normalizeMaxChoices(task);
};

const validateTask = (task: TaskDefinition): string | null => {
  if (!task.id.trim()) return 'Task ID is required.';
  if (!task.name.trim()) return 'Task name is required.';
  if (!task.description_md.trim()) return 'Prompt markdown is required.';
  if (task.classes.length === 0) return 'At least one choice is required.';
  const ids = task.classes.map((c) => c.id.trim());
  if (ids.some((id) => !id)) return 'Every choice must have a class ID.';
  if (new Set(ids).size !== ids.length) return 'Choice class IDs must be unique.';
  return null;
};

const saveTask = async () => {
  if (!editingTask.value) return;
  normalizeMaxChoices(editingTask.value);
  const err = validateTask(editingTask.value);
  if (err) { dialogError.value = err; return; }
  savingTask.value = true;
  try {
    if (isNewTask.value) {
      await apiService.createAdminTask(editingTask.value);
    } else {
      await apiService.saveAdminTask(editingTask.value);
    }
    taskDialog.value = false;
    await loadTasks();
  } finally {
    savingTask.value = false;
  }
};

// ---- Import tab ----
const importing = ref(false);
const importMsg = ref('');

const importPrompts = async () => {
  importing.value = true;
  importMsg.value = '';
  try {
    const result = await apiService.importPromptTasks();
    importMsg.value = `Imported ${result.imported} task(s) successfully.`;
    await loadTasks();
  } finally {
    importing.value = false;
  }
};

// ---- GT upload ----
const gtFile = ref<File | null>(null);
const uploadingGt = ref(false);
const gtMsg = ref('');
const gtError = ref(false);

const uploadGt = async () => {
  if (!gtFile.value) return;
  uploadingGt.value = true;
  gtMsg.value = '';
  gtError.value = false;
  try {
    const text = await gtFile.value.text();
    const result = await apiService.uploadGroundTruth(text);
    gtMsg.value = `Uploaded ${result.imported} GT annotation(s).`;
    gtFile.value = null;
  } catch (e: unknown) {
    gtError.value = true;
    const err = e as { response?: { data?: { detail?: string } } };
    gtMsg.value = err.response?.data?.detail || 'Upload failed.';
  } finally {
    uploadingGt.value = false;
  }
};

// ---- LLM upload ----
const llmFile = ref<File | null>(null);
const uploadingLlm = ref(false);
const llmMsg = ref('');
const llmError = ref(false);

const uploadLlm = async () => {
  if (!llmFile.value) return;
  uploadingLlm.value = true;
  llmMsg.value = '';
  llmError.value = false;
  try {
    const text = await llmFile.value.text();
    const result = await apiService.uploadLlmAnnotations(text);
    llmMsg.value = `Uploaded ${result.imported} LLM annotation(s).`;
    llmFile.value = null;
  } catch (e: unknown) {
    llmError.value = true;
    const err = e as { response?: { data?: { detail?: string } } };
    llmMsg.value = err.response?.data?.detail || 'Upload failed.';
  } finally {
    uploadingLlm.value = false;
  }
};

// ---- Texts tab ----
const textFile = ref<File | null>(null);
const textSearch = ref('');
const textTaskFilter = ref<string | null>(null);
const textTaskOptions = computed(() => tasks.value);
const textRows = ref<TextItemResponse[]>([]);
const textTotal = ref(0);
const textPage = ref(1);
const textPageSize = 50;
const loadingTexts = ref(false);
const uploading = ref(false);
const uploadMsg = ref('');
const uploadError = ref(false);

const textMaxPage = computed(() => Math.max(1, Math.ceil(textTotal.value / textPageSize)));

const textAnnotationCols: QTableColumn[] = [
  { name: 'display_name', label: 'Annotator', field: 'display_name', align: 'left', sortable: true },
  { name: 'task_id', label: 'Task', field: 'task_id', align: 'left', sortable: true },
  { name: 'annotation_type', label: 'Type', field: 'annotation_type', align: 'center', sortable: true },
  { name: 'selected_classes', label: 'Classes', field: 'selected_classes', align: 'left' },
  { name: 'points_earned', label: 'Points', field: 'points_earned', align: 'right', sortable: true },
  { name: 'created_at', label: 'Date', field: 'created_at', align: 'right', sortable: true },
];

const textAnnotationsDialog = ref(false);
const textAnnotationsTextId = ref('');
const textAnnotationRows = ref<TextAnnotationEntry[]>([]);
const loadingTextAnnotations = ref(false);

const openTextAnnotations = async (row: TextItemResponse) => {
  textAnnotationsTextId.value = row.id;
  textAnnotationsDialog.value = true;
  loadingTextAnnotations.value = true;
  try {
    textAnnotationRows.value = await apiService.getTextAnnotations(row.id, textTaskFilter.value ?? undefined);
  } finally {
    loadingTextAnnotations.value = false;
  }
};

const textCols: QTableColumn[] = [
  { name: 'id', label: 'ID', field: 'id', align: 'left', style: 'width:180px; font-size:11px' },
  { name: 'text_preview', label: 'Text', field: 'text_preview', align: 'left' },
  { name: 'language', label: 'Lang', field: 'language', align: 'center', style: 'width:60px' },
  { name: 'annotation_count', label: 'Annotations', field: 'annotation_count', align: 'right', style: 'width:110px' },
  { name: 'suspended', label: 'Status', field: 'suspended', align: 'center', style: 'width:100px' },
  { name: 'actions', label: '', field: 'id', align: 'right', style: 'width:100px' },
];

const loadTexts = async (page = 0) => {
  loadingTexts.value = true;
  try {
    const result = await apiService.getAdminTexts(page, textSearch.value, textPageSize, textTaskFilter.value ?? undefined);
    textRows.value = result.items;
    textTotal.value = result.total;
    textPage.value = page + 1;
  } finally {
    loadingTexts.value = false;
  }
};

const toggleSuspend = async (row: TextItemResponse) => {
  await apiService.patchAdminText(row.id, !row.suspended);
  row.suspended = !row.suspended;
};

const uploadTexts = async () => {
  if (!textFile.value) return;
  uploading.value = true;
  uploadMsg.value = '';
  uploadError.value = false;
  try {
    const text = await textFile.value.text();
    const result = await apiService.uploadTextsJsonl(text);
    uploadMsg.value = `Uploaded ${result.imported} text(s).`;
    textFile.value = null;
    await loadTexts(0);
  } catch (e: unknown) {
    uploadError.value = true;
    const err = e as { response?: { data?: { detail?: string } } };
    uploadMsg.value = err.response?.data?.detail || 'Upload failed.';
  } finally {
    uploading.value = false;
  }
};

// ---- Reliability tab ----
const irrData = ref<UserReliabilityResponse[]>([]);
const loadingIrr = ref(false);
const recomputing = ref(false);

const irrCols: QTableColumn[] = [
  { name: 'display_name', label: 'Annotator', field: 'display_name', align: 'left', sortable: true },
  { name: 'task_id', label: 'Task', field: 'task_id', align: 'left', sortable: true },
  { name: 'annotation_count', label: 'Annotations', field: 'annotation_count', align: 'right', sortable: true },
  { name: 'pairwise_agreement', label: 'Pairwise agr.', field: 'pairwise_agreement', align: 'right', sortable: true },
  { name: 'cohens_kappa', label: "Cohen's \u03ba", field: 'cohens_kappa', align: 'right', sortable: true },
  { name: 'krippendorffs_alpha', label: 'Kripp. \u03b1', field: 'krippendorffs_alpha', align: 'right', sortable: true },
  { name: 'computed_at', label: 'Last computed', field: 'computed_at', align: 'right', sortable: true },
];

const loadIrr = async () => {
  loadingIrr.value = true;
  try { irrData.value = await apiService.getAdminIrr(); }
  finally { loadingIrr.value = false; }
};

const recomputeIrr = async () => {
  recomputing.value = true;
  try { await apiService.recomputeIrr(); await loadIrr(); }
  finally { recomputing.value = false; }
};

onMounted(async () => {
  await loadTasks();
  await loadTexts(0);
  await loadIrr();
});</script>

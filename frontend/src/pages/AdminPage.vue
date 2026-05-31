<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Admin</div>

    <q-tabs v-model="tab" align="left" class="q-mb-md" dense>
      <q-tab name="tasks" icon="assignment" label="Tasks" />
      <q-tab name="import" icon="upload_file" label="Import" />
      <q-tab name="texts" icon="article" label="Texts" />
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
        <q-card flat bordered class="q-pa-md">
          <div class="text-body2 text-grey-7 q-mb-md">
            Parses all Markdown files in the <code>prompts/</code> directory and upserts them as task definitions.
            Re-importing a prompt updates the existing task while preserving annotations.
          </div>
          <q-btn color="primary" icon="upload" label="Import prompts/*.md" :loading="importing" @click="importPrompts" />
          <div v-if="importMsg" class="q-mt-md text-positive">{{ importMsg }}</div>
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

        <div class="row q-mb-md">
          <q-input v-model="textSearch" dense outlined placeholder="Search texts…" class="col" debounce="400"
            @update:model-value="loadTexts(0)">
            <template #append><q-icon name="search" /></template>
          </q-input>
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
            <q-td :props="props">
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
    </q-tab-panels>

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
import { TaskDefinition, TextItemResponse } from 'src/types/api';
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

// ---- Texts tab ----
const textFile = ref<File | null>(null);
const textSearch = ref('');
const textRows = ref<TextItemResponse[]>([]);
const textTotal = ref(0);
const textPage = ref(1);
const textPageSize = 50;
const loadingTexts = ref(false);
const uploading = ref(false);
const uploadMsg = ref('');
const uploadError = ref(false);

const textMaxPage = computed(() => Math.max(1, Math.ceil(textTotal.value / textPageSize)));

const textCols: QTableColumn[] = [
  { name: 'id', label: 'ID', field: 'id', align: 'left', style: 'width:180px; font-size:11px' },
  { name: 'text_preview', label: 'Text', field: 'text_preview', align: 'left' },
  { name: 'language', label: 'Lang', field: 'language', align: 'center', style: 'width:60px' },
  { name: 'suspended', label: 'Status', field: 'suspended', align: 'center', style: 'width:100px' },
  { name: 'actions', label: '', field: 'id', align: 'right', style: 'width:60px' },
];

const loadTexts = async (page = 0) => {
  loadingTexts.value = true;
  try {
    const result = await apiService.getAdminTexts(page, textSearch.value, textPageSize);
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

onMounted(async () => {
  await loadTasks();
  await loadTexts(0);
});
</script>

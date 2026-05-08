<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Classification</div>
    <div class="q-mb-md">My total annotations: {{ myTotal }}</div>
    <div v-if="!textItem">No more texts.</div>
    <div v-else>
      <q-card class="q-mb-md"><q-card-section>{{ textItem.text }}</q-card-section></q-card>
      <div v-for="task in tasks" :key="task.id" class="q-mb-md">
        <div class="text-subtitle1">{{ task.name }}</div>
        <q-option-group v-model="answers[task.id]" :type="task.multi_choice ? 'checkbox' : 'radio'" :options="task.classes.map(c=>({label:c.label_en,value:c.id}))" />
      </div>
      <q-btn color="primary" label="Submit" @click="submit" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { apiService } from 'src/services/api';
import { NextTextResponse, TaskDefinition } from 'src/types/api';

const tasks = ref<TaskDefinition[]>([]);
const textItem = ref<NextTextResponse | null>(null);
const answers = ref<Record<string, string[] | string>>({});
const myTotal = ref(0);

const load = async () => {
  const ids = JSON.parse(localStorage.getItem('selected_tasks') || '[]') as string[];
  const all = await apiService.getTasks();
  tasks.value = all.filter(t => ids.includes(t.id));
  textItem.value = await apiService.getNextText(ids);
  answers.value = {};
  const stats = await apiService.getMyStats();
  myTotal.value = stats.total;
};

onMounted(load);

const submit = async () => {
  if (!textItem.value) return;
  const now = new Date().toISOString();
  await apiService.submitAnnotations({
    text_id: textItem.value.id,
    annotations: tasks.value.map((t) => ({
      task_id: t.id,
      selected_classes: Array.isArray(answers.value[t.id]) ? answers.value[t.id] as string[] : [answers.value[t.id] as string],
      start_time: now,
      end_time: now,
    })),
  });
  await load();
};
</script>

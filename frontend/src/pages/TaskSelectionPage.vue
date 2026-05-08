<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Select up to 6 tasks</div>
    <q-option-group v-model="selected" type="checkbox" :options="options" />
    <q-btn class="q-mt-md" color="primary" label="Start classification" :disable="selected.length===0 || selected.length>6" @click="start" />
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { apiService } from 'src/services/api';

const router = useRouter();
const selected = ref<string[]>([]);
const options = ref<{label:string; value:string}[]>([]);

onMounted(async () => {
  const tasks = await apiService.getTasks();
  options.value = tasks.map((t) => ({ label: t.name, value: t.id }));
});

const start = async () => {
  localStorage.setItem('selected_tasks', JSON.stringify(selected.value));
  await router.push('/classify');
};
</script>

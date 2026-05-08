<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Admin</div>
    <q-btn color="primary" label="Import prompts/*.md as tasks" @click="importPrompts" class="q-mb-md"/>
    <q-input v-model="jsonl" type="textarea" label="Paste JSONL texts" autogrow class="q-mb-md"/>
    <q-btn color="secondary" label="Upload texts" @click="uploadTexts"/>
    <div class="q-mt-md">{{ msg }}</div>
  </q-page>
</template>
<script setup lang="ts">
import { ref } from 'vue';
import { api } from 'boot/axios';
const jsonl = ref(''); const msg = ref('');
const importPrompts = async()=>{ const r = await api.post('/api/admin/tasks/import-prompts'); msg.value=`Imported ${r.data.imported} tasks`; };
const uploadTexts = async()=>{ await api.post('/api/admin/texts', jsonl.value, {headers:{'Content-Type':'text/plain'}}); msg.value='Texts uploaded'; };
</script>

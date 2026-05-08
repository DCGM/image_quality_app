<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated>
      <q-toolbar>
        <q-toolbar-title>Text Classifier</q-toolbar-title>
        <q-btn flat to="/tasks" label="Tasks" />
        <q-btn flat to="/classify" label="Classify" />
        <q-btn flat to="/leaderboard" label="Leaderboard" />
        <q-btn v-if="authStore.user?.is_superuser" flat to="/admin" label="Admin" />
        <q-space />
        <div v-if="authStore.user" class="q-mr-md">{{ authStore.user.email }}</div>
        <q-btn v-if="authStore.isAuthenticated" flat label="Logout" icon="logout" @click="onLogout"/>
      </q-toolbar>
    </q-header>
    <q-page-container><router-view /></q-page-container>
  </q-layout>
</template>
<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useAuthStore } from 'src/stores/auth-store';
const router = useRouter();
const authStore = useAuthStore();
const onLogout = async () => { await authStore.logout(); await router.push('/login'); };
</script>

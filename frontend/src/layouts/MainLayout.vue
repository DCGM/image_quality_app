<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated class="bg-primary">
      <q-toolbar>
        <q-toolbar-title class="text-weight-bold">Image Rater</q-toolbar-title>
        <q-btn flat round dense icon="photo_library" to="/tasks" class="q-mr-xs">
          <q-tooltip>Tasks</q-tooltip>
        </q-btn>
        <q-btn flat round dense icon="leaderboard" to="/leaderboard" class="q-mr-xs">
          <q-tooltip>Leaderboard</q-tooltip>
        </q-btn>
        <q-btn v-if="authStore.user?.is_superuser" flat round dense icon="admin_panel_settings" to="/admin" class="q-mr-xs">
          <q-tooltip>Admin</q-tooltip>
        </q-btn>
        <q-separator dark vertical inset class="q-mx-sm" />
        <div v-if="authStore.user" class="text-caption q-mr-sm ellipsis" style="max-width:180px">
          {{ authStore.user.display_name || authStore.user.email }}
        </div>
        <q-btn v-if="authStore.isAuthenticated" flat round dense icon="logout" @click="onLogout">
          <q-tooltip>Logout</q-tooltip>
        </q-btn>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <div class="page-container">
        <router-view />
      </div>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useAuthStore } from 'src/stores/auth-store';
const router = useRouter();
const authStore = useAuthStore();
const onLogout = async () => { await authStore.logout(); await router.push('/login'); };
</script>

<style>
.page-container {
  max-width: 960px;
  margin: 0 auto;
  padding: 16px;
}
</style>

<template>
  <div class="login-container flex flex-center">
    <q-card class="login-card">
      <q-card-section>
        <div class="text-h4 text-center q-mb-md">Login</div>
      </q-card-section>

      <q-card-section>
        <q-form @submit="onSubmit" class="q-gutter-md">
          <q-input
            v-model="email"
            label="Email"
            type="email"
            outlined
            :rules="[(val) => !!val || 'Email is required']"
          />

          <q-input
            v-model="password"
            label="Password"
            type="password"
            outlined
            :rules="[(val) => !!val || 'Password is required']"
          />

          <q-btn
            type="submit"
            label="Login"
            color="primary"
            class="full-width"
            :loading="loading"
          />
        </q-form>
      </q-card-section>

      <q-card-section class="text-center">
        <q-btn
          flat
          dense
          label="Don't have an account? Register"
          color="primary"
          @click="showRegisterDialog = true"
        />
      </q-card-section>
    </q-card>

    <!-- Registration Dialog -->
    <q-dialog v-model="showRegisterDialog">
      <q-card style="min-width: 400px">
        <q-card-section>
          <div class="text-h6">Register New Account</div>
        </q-card-section>

        <q-card-section>
          <q-form @submit="onRegister" class="q-gutter-md">
            <q-input
              v-model="registerEmail"
              label="Email"
              type="email"
              outlined
              :rules="[(val) => !!val || 'Email is required']"
            />

            <q-input
              v-model="registerPassword"
              label="Password"
              type="password"
              outlined
              :rules="[
                (val) => !!val || 'Password is required',
                (val) => val.length >= 3 || 'Password must be at least 3 characters'
              ]"
            />

            <q-input
              v-model="registerPasswordConfirm"
              label="Confirm Password"
              type="password"
              outlined
              :rules="[
                (val) => !!val || 'Please confirm password',
                (val) => val === registerPassword || 'Passwords do not match'
              ]"
            />

            <q-input
              v-model="registerDisplayName"
              label="Display name (optional)"
              outlined
            />

            <div class="row q-gutter-sm">
              <q-btn
                type="submit"
                label="Register"
                color="primary"
                :loading="registerLoading"
              />
              <q-btn
                flat
                label="Cancel"
                color="primary"
                @click="showRegisterDialog = false"
              />
            </div>
          </q-form>
        </q-card-section>
      </q-card>
    </q-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from 'src/stores/auth-store';
import { useQuasar } from 'quasar';
import { apiService } from 'src/services/api';

const router = useRouter();
const authStore = useAuthStore();
const $q = useQuasar();

// Login form
const email = ref('');
const password = ref('');
const loading = ref(false);

// Registration dialog
const showRegisterDialog = ref(false);
const registerEmail = ref('');
const registerPassword = ref('');
const registerPasswordConfirm = ref('');
const registerDisplayName = ref('');
const registerLoading = ref(false);

const onSubmit = async () => {
  loading.value = true;
  try {
    await authStore.login({
      username: email.value,
      password: password.value,
    });

    $q.notify({
      type: 'positive',
      message: 'Login successful',
    });

    router.push('/classify');
  } catch (error) {
    const err = error as { response?: { data?: { detail?: string } } };
    $q.notify({
      type: 'negative',
      message: err.response?.data?.detail || 'Login failed',
    });
  } finally {
    loading.value = false;
  }
};

const onRegister = async () => {
  registerLoading.value = true;
  try {
    await apiService.register({
      email: registerEmail.value,
      password: registerPassword.value,
      display_name: registerDisplayName.value || undefined,
    });

    $q.notify({
      type: 'positive',
      message: 'Registration successful! You can now log in.',
    });

    // Close dialog and pre-fill login form
    showRegisterDialog.value = false;
    email.value = registerEmail.value;

    // Clear registration form
    registerEmail.value = '';
    registerPassword.value = '';
    registerPasswordConfirm.value = '';
    registerDisplayName.value = '';
  } catch (error) {
    const err = error as {
      response?: {
        data?: {
          detail?: string | { code?: string; reason?: string }
        }
      }
    };

    let errorMessage = 'Registration failed';

    if (err.response?.data?.detail) {
      const detail = err.response.data.detail;
      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (detail.reason) {
        errorMessage = detail.reason;
      }
    }

    $q.notify({
      type: 'negative',
      message: errorMessage,
    });
  } finally {
    registerLoading.value = false;
  }
};
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: 20px;
}
</style>

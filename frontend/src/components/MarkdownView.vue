<template>
  <!-- markdown content is admin-controlled, not user-supplied -->
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="markdown-body" v-html="rendered" />
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { marked } from 'marked';

const props = defineProps<{ content: string }>();

const rendered = computed(() => marked.parse(props.content) as string);
</script>

<style scoped>
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin-top: 0.6em;
  margin-bottom: 0.3em;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.4em;
}
.markdown-body :deep(p) {
  margin: 0.4em 0;
}
</style>

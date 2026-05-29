<template><svg class="svg-icon">
    <use :xlink:href="symbolId"></use>
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: String,
})

const symbolId = computed(() => `#icon-${props.name}`)
</script>

<style scoped>
.svg-icon {
  width: 1em;
  height: 1em;
  fill: currentColor;
  vertical-align: middle;
}
.svg-icon :deep(path),
.svg-icon :deep(circle),
.svg-icon :deep(rect),
.svg-icon :deep(ellipse),
.svg-icon :deep(line),
.svg-icon :deep(polyline),
.svg-icon :deep(polygon) {
  fill: inherit;
}
</style>

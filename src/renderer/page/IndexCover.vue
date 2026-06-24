<script setup lang="ts">
import { ElHeader, ElImage, ElRow } from 'element-plus';
import {ref} from 'vue';

</script>

<template>
    <div style="height: 40px;width:100%">
        header
    </div>
    <div style="height: calc(100% - 40px);width: 100%;background-color: var(--bg-page);display: flex;flex-direction: row;">
        <div style="width: 68%;height: 100%;display:flex;flex-direction: column;">
            <div style="height: 68%;" class="card"></div>
            <div style="height: 32%;" class="card"></div>
        </div>
        <div style="width: 32%;height: 100%;display:flex;flex-direction: column;">
            <div style="height: 68%;" class="card"></div>
            <div style="height: 32%;" class="card"></div>
        </div>
    </div>
</template>

<style scoped>
.card {
    box-sizing: border-box;
    margin: 10px;
    background-color: var(--bg-card);
    border-radius: 5px;
    padding: 20px;
}
</style>
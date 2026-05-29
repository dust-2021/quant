<script lang="ts" setup>
import { onBeforeMount, ref } from 'vue';

const props = defineProps({
    uuid: {
        type: String,
        required: true
    }
})

const finished = ref<boolean>(false);

async function checkFinished() {
    
}

onBeforeMount(() => {
    checkFinished();
})

</script>
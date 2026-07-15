<script lang="ts" setup>
import { ref, computed, onMounted } from 'vue';
import { Binance, wsResponse } from '../../exchanges/binance'

const data = ref({
    target: "BTC",
    interval: "1h",
    data: []
});
const binance = Binance.getInstance();

async function handle(data: wsResponse) {
    
}

binance.subscribe("", handle);

</script>
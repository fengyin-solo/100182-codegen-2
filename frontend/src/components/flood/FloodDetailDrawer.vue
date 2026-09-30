<template>
  <div v-if="open" class="drawer-mask" @click.self="$emit('close')">
    <aside class="drawer">
      <header class="drawer-head">
        <h3>汛情调度明细</h3>
        <button class="link" type="button" @click="$emit('close')">关闭</button>
      </header>

      <div v-if="detail" class="drawer-body">
        <section class="detail-section">
          <span class="status-tag" :class="statusClass(detail.status)">{{ detail.status }}<template v-if="detail.status === '应急响应'"> · {{ detail.current_level }}</template></span>
          <h4>{{ detail.汛情编号 }}</h4>
          <dl class="detail-grid">
            <div><dt>预警等级</dt><dd>{{ detail.预警等级 }}</dd></div>
            <div><dt>当前等级</dt><dd>{{ detail.current_level }}</dd></div>
            <div><dt>影响范围</dt><dd>{{ detail.影响范围 || '—' }}</dd></div>
            <div><dt>降雨情况</dt><dd>{{ detail.降雨情况 }}</dd></div>
            <div><dt>值班人员</dt><dd>{{ detail.登记人员 }}</dd></div>
            <div><dt>预警时间</dt><dd>{{ detail.预警时间 || '—' }}</dd></div>
            <div><dt>响应时间</dt><dd>{{ detail.响应时间 || '—' }}</dd></div>
            <div><dt>解除时间</dt><dd>{{ detail.解除时间 || '—' }}</dd></div>
          </dl>
          <p v-if="detail.解除说明" class="detail-note">解除说明：{{ detail.解除说明 }}</p>
        </section>

        <section class="detail-section">
          <h4>排涝泵车调度（{{ detail.trucks.length }} 台次）</h4>
          <table class="data-table">
            <thead>
              <tr><th>泵车编号</th><th>型号</th><th>排涝流量</th><th>调度时间</th><th>状态</th></tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in detail.trucks" :key="`${item.泵车id}-${index}`">
                <td>{{ item.泵车编号 }}</td>
                <td>{{ item.泵车型号 }}</td>
                <td>{{ item.排涝流量 }}</td>
                <td>{{ item.调度时间 }}</td>
                <td>{{ item.状态 }}</td>
              </tr>
              <tr v-if="!detail.trucks.length"><td colspan="5" class="empty-state">本场汛情未调度泵车</td></tr>
            </tbody>
          </table>
        </section>

        <section class="detail-section">
          <h4>应急物资调度（{{ detail.materials.length }} 批次）</h4>
          <table class="data-table">
            <thead>
              <tr><th>材料编号</th><th>材料名称</th><th>数量</th><th>调度时间</th><th>状态</th></tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in detail.materials" :key="`${item.物资id}-${index}`">
                <td>{{ item.材料编号 }}</td>
                <td>{{ item.材料名称 }}</td>
                <td>{{ item.数量 }} {{ item.计量单位 }}</td>
                <td>{{ item.调度时间 }}</td>
                <td>{{ item.状态 }}</td>
              </tr>
              <tr v-if="!detail.materials.length"><td colspan="5" class="empty-state">本场汛情未调度物资</td></tr>
            </tbody>
          </table>
        </section>

        <section class="detail-section">
          <h4>状态变更记录（{{ detail.change_logs.length }} 条）</h4>
          <ol class="timeline">
            <li v-for="(log, index) in [...detail.change_logs].reverse()" :key="index" class="timeline-item">
              <div class="timeline-dot" :class="log.变更后 === '已解除' ? 'dot-closed' : log.变更后 === '应急响应' ? 'dot-response' : 'dot-warning'"></div>
              <div class="timeline-content">
                <div class="timeline-head">
                  <strong>{{ log.变更前 }} → {{ log.变更后 }}</strong>
                  <span class="timeline-time">{{ log.时间 }} · {{ log.操作人 }}</span>
                </div>
                <p>{{ log.说明 }}</p>
              </div>
            </li>
          </ol>
        </section>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

import { useFloodStore, type FloodEntry, type FloodStatus } from '@/stores/flood'

const props = defineProps<{
  open: boolean
  entryId: number | null
}>()

defineEmits<{ (e: 'close'): void }>()

const store = useFloodStore()
const detail = ref<FloodEntry | null>(null)

watch(
  () => [props.open, props.entryId] as const,
  async ([open]) => {
    if (open && props.entryId !== null) {
      detail.value = await store.fetchDetail(props.entryId)
    } else if (!open) {
      detail.value = null
    }
  },
)

function statusClass(status: FloodStatus): string {
  if (status === '预警') return 'tag-warning'
  if (status === '应急响应') return 'tag-response'
  return 'tag-closed'
}
</script>

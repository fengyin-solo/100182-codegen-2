<template>
  <div class="modal-mask" @click.self="emit('close')">
    <div class="modal wide">
      <div class="modal-head">
        <h3>{{ event.汛情编号 }} · {{ event.汛情名称 }}</h3>
        <button class="modal-close" type="button" @click="emit('close')">×</button>
      </div>

      <table class="data-table">
        <tbody>
          <tr><th style="width: 110px;">当前状态</th><td><span :class="badgeClass">{{ event.status }}</span></td>
            <th style="width: 110px;">预警等级</th><td>{{ event.预警等级 }}</td></tr>
          <tr><th>响应等级</th><td>{{ event.响应等级 || '尚未启动响应' }}</td>
            <th>影响范围</th><td>{{ event.影响范围 }}</td></tr>
          <tr><th>发布时间</th><td>{{ event.发布时间 }}</td>
            <th>响应时间</th><td>{{ event.响应时间 || '—' }}</td></tr>
          <tr><th>最近调整</th><td>{{ event.调整时间 || '—' }}</td>
            <th>解除时间</th><td>{{ event.解除时间 || '—' }}</td></tr>
        </tbody>
      </table>

      <div class="section-title">调度排涝泵车（累计 {{ pumpQty }} 台）</div>
      <table class="data-table" v-if="event.泵车调度.length">
        <thead><tr><th>泵车编号</th><th>泵车名称</th><th>调度数量</th></tr></thead>
        <tbody>
          <tr v-for="item in event.泵车调度" :key="item.材料ID">
            <td>{{ item.泵车编号 }}</td><td>{{ item.泵车名称 }}</td><td>{{ item.数量 }} 台</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="alloc-summary">本汛情未调度排涝泵车</p>

      <div class="section-title">调拨应急物资（累计 {{ materialQty }} 件）</div>
      <table class="data-table" v-if="event.物资调度.length">
        <thead><tr><th>材料编号</th><th>材料名称</th><th>调拨数量</th></tr></thead>
        <tbody>
          <tr v-for="item in event.物资调度" :key="item.材料ID">
            <td>{{ item.材料编号 }}</td><td>{{ item.材料名称 }}</td><td>{{ item.数量 }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="alloc-summary">本汛情未调拨应急物资</p>

      <div class="section-title">状态变更记录（{{ event.变更记录.length }} 条）</div>
      <ul class="timeline">
        <li v-for="(record, index) in event.变更记录" :key="index">
          <div class="tl-time">{{ record.时间 }} · {{ record.值班人员 || '值班管理员' }}</div>
          <div>
            <strong>{{ record.动作 }}</strong>
            <span v-if="record.由状态">：{{ record.由状态 }} → {{ record.到状态 }}</span>
            <span class="badge" style="margin-left: 6px;">{{ record.响应等级 }}</span>
          </div>
          <div v-if="record.影响范围">影响范围：{{ record.影响范围 }}</div>
          <p v-if="record.说明" class="alloc-summary">{{ record.说明 }}</p>
          <p v-if="record.泵车调度?.length" class="alloc-summary">
            泵车：{{ formatAlloc(record.泵车调度, '泵车名称') }}
          </p>
          <p v-if="record.物资调度?.length" class="alloc-summary">
            物资：{{ formatAlloc(record.物资调度, '材料名称') }}
          </p>
        </li>
      </ul>

      <div class="modal-foot">
        <button class="btn primary" type="button" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { Allocation, ChangeRecord, FloodEvent } from '@/stores/flood'

const props = defineProps<{ event: FloodEvent }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const pumpQty = computed(() => sum(props.event.泵车调度))
const materialQty = computed(() => sum(props.event.物资调度))

const badgeClass = computed(() => {
  if (props.event.status === '预警中') return 'badge warning'
  if (props.event.status === '响应中') return 'badge responding'
  return 'badge lifted'
})

function sum(list: Allocation[]) {
  return list.reduce((total, item) => total + Number(item.数量 || 0), 0)
}

function formatAlloc(list: ChangeRecord['泵车调度'], nameKey: '泵车名称' | '材料名称') {
  return (list ?? [])
    .map((item) => `${String(item[nameKey] ?? '')} ${item.数量}${nameKey === '泵车名称' ? '台' : '件'}`)
    .join('，')
}
</script>

<template>
  <section class="page" data-module="flood-duty">
    <header class="page-head">
      <div>
        <h2>防汛值班台</h2>
        <p class="page-desc">值班入口只看未解除汛情：预警发布、响应启动、等级调整与解除都在这里处置，状态与调度台账实时一致。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="refreshPage">刷新状态</button>
        <button class="btn primary" type="button" @click="openDialog('warning')">发布汛情预警</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="card in store.cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>

    <div v-if="store.highestActiveLevel" class="alert-banner" :class="levelClass(store.highestActiveLevel.level)">
      <strong>当前最高响应：{{ store.highestActiveLevel.level }}应急响应</strong>
      <span>关联汛情 {{ store.highestActiveLevel.entry.汛情编号 }} · {{ store.highestActiveLevel.entry.影响范围 }}</span>
    </div>

    <h3 class="block-title">未解除汛情（值班关注）</h3>
    <table class="data-table">
      <thead>
        <tr>
          <th>汛情编号</th>
          <th>当前状态</th>
          <th>等级</th>
          <th>影响范围</th>
          <th>在调泵车</th>
          <th>占用物资</th>
          <th>预警/响应时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in store.active" :key="row.id">
          <td><button class="link" type="button" @click="openDetail(row.id)">{{ row.汛情编号 }}</button></td>
          <td><span class="status-tag" :class="statusClass(row.status)">{{ row.status }}</span></td>
          <td>{{ row.current_level }}</td>
          <td>{{ row.影响范围 || '—' }}</td>
          <td>{{ row.dispatched_truck_count }} 台</td>
          <td>{{ row.dispatched_material_count }} 件</td>
          <td>{{ row.响应时间 || row.预警时间 }}</td>
          <td class="row-actions">
            <button v-if="row.status === '预警'" class="link" type="button" @click="openDialog('start', row)">启动响应</button>
            <button v-if="row.status === '预警'" class="link" type="button" @click="openDialog('cancel-warning', row)">解除预警</button>
            <button v-if="row.status === '应急响应'" class="link" type="button" @click="openDialog('adjust', row)">调整等级</button>
            <button v-if="row.status === '应急响应'" class="link danger" type="button" @click="openDialog('terminate', row)">解除响应</button>
          </td>
        </tr>
        <tr v-if="!store.active.length">
          <td colspan="8" class="empty-state">当前没有未解除汛情，可发布新的汛情预警</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>数据与「防汛调度台账」同源，最后加载：{{ store.lastLoadedAt || '尚未加载' }}</span>
      <span v-if="store.errorMessage" class="error-text">{{ store.errorMessage }}</span>
    </footer>

    <ActionDialog :open="dialog.open" :mode="dialog.mode" :entry="dialog.entry" @close="dialog.open = false" @done="onDone" />
    <FloodDetailDrawer :open="drawerOpen" :entry-id="drawerId" @close="drawerOpen = false" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import ActionDialog, { type DialogMode } from '@/components/flood/ActionDialog.vue'
import FloodDetailDrawer from '@/components/flood/FloodDetailDrawer.vue'
import { useFloodStore, type FloodEntry, type FloodStatus, type ResponseLevel } from '@/stores/flood'

const store = useFloodStore()

const dialog = reactive<{ open: boolean; mode: DialogMode; entry: FloodEntry | null }>({
  open: false,
  mode: 'warning',
  entry: null,
})
const drawerOpen = ref(false)
const drawerId = ref<number | null>(null)

function openDialog(mode: DialogMode, entry: FloodEntry | null = null) {
  dialog.mode = mode
  dialog.entry = entry
  dialog.open = true
}

function openDetail(id: number) {
  drawerId.value = id
  drawerOpen.value = true
}

function onDone() {
  dialog.open = false
  // 写操作成功后 store.post 内部已统一 refresh，值班台与台账随之同步。
}

// 中途返回本页或刷新页面都重新拉取当前状态，保证看到的是最新状态。
onMounted(() => {
  void store.refresh()
})

function refreshPage() {
  void store.refresh()
}

function statusClass(status: FloodStatus): string {
  if (status === '预警') return 'tag-warning'
  if (status === '应急响应') return 'tag-response'
  return 'tag-closed'
}

function levelClass(level: ResponseLevel): string {
  return { Ⅳ级: 'banner-blue', Ⅲ级: 'banner-yellow', Ⅱ级: 'banner-orange', Ⅰ级: 'banner-red' }[level]
}
</script>

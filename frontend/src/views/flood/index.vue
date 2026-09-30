<template>
  <section class="page" data-module="flood-ledger">
    <header class="page-head">
      <div>
        <h2>防汛排涝应急调度台账</h2>
        <p class="page-desc">以汛情为主线串联预警、应急响应、等级调整与解除；每次调度登记泵车与物资，解除后物资可用数量回写物资台账。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="reload">刷新台账</button>
        <button class="btn primary" type="button" @click="openDialog('warning')">登记汛情预警</button>
      </div>
    </header>

    <!-- 汇总卡片与台账列表取自同一份数据：都来自 store.entries / store.cards。 -->
    <div class="stat-row">
      <article v-for="card in store.cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>汛情状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="status in statusFlow" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>响应等级</span>
        <select v-model="filters.level">
          <option value="">全部</option>
          <option v-for="level in levels" :key="level" :value="level">{{ level }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th>汛情编号</th>
          <th>当前状态</th>
          <th>等级</th>
          <th>影响范围</th>
          <th>调度泵车</th>
          <th>占用物资</th>
          <th>预警时间</th>
          <th>响应时间</th>
          <th>解除时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in filteredEntries" :key="row.id">
          <td><button class="link" type="button" @click="openDetail(row.id)">{{ row.汛情编号 }}</button></td>
          <td><span class="status-tag" :class="statusClass(row.status)">{{ row.status }}</span></td>
          <td>{{ row.current_level }}</td>
          <td>{{ row.影响范围 || '—' }}</td>
          <td>{{ activeTrucks(row) }} 台 <span v-if="row.trucks.length" class="muted-inline">/ 累计 {{ row.trucks.length }}</span></td>
          <td>{{ activeMaterials(row) }} 件</td>
          <td>{{ row.预警时间 || '—' }}</td>
          <td>{{ row.响应时间 || '—' }}</td>
          <td>{{ row.解除时间 || '—' }}</td>
          <td class="row-actions">
            <button v-if="row.status === '预警'" class="link" type="button" @click="openDialog('start', row)">启动响应</button>
            <button v-if="row.status === '预警'" class="link" type="button" @click="openDialog('cancel-warning', row)">解除预警</button>
            <button v-if="row.status === '应急响应'" class="link" type="button" @click="openDialog('adjust', row)">调整等级</button>
            <button v-if="row.status === '应急响应'" class="link danger" type="button" @click="openDialog('terminate', row)">解除响应</button>
            <button class="link" type="button" @click="openDetail(row.id)">变更记录</button>
          </td>
        </tr>
        <tr v-if="!filteredEntries.length">
          <td colspan="10" class="empty-state">没有符合条件的汛情记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ filteredEntries.length }} 条汛情记录，最后加载：{{ store.lastLoadedAt || '尚未加载' }}</span>
      <span v-if="store.errorMessage" class="error-text">{{ store.errorMessage }}</span>
    </footer>

    <ActionDialog :open="dialog.open" :mode="dialog.mode" :entry="dialog.entry" @close="dialog.open = false" @done="onDone" />
    <FloodDetailDrawer :open="drawerOpen" :entry-id="drawerId" @close="drawerOpen = false" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import ActionDialog, { type DialogMode } from '@/components/flood/ActionDialog.vue'
import FloodDetailDrawer from '@/components/flood/FloodDetailDrawer.vue'
import {
  RESPONSE_LEVELS,
  STATUS_FLOW,
  useFloodStore,
  type FloodEntry,
  type FloodStatus,
} from '@/stores/flood'

const store = useFloodStore()
const levels = RESPONSE_LEVELS
const statusFlow = STATUS_FLOW

const filters = reactive({ status: '', level: '' })

// 台账列表与卡片同源：store.entries 是 /api/flood 的全量数据，过滤只在前端派生。
const filteredEntries = computed(() =>
  store.entries.filter((row) => {
    if (filters.status && row.status !== filters.status) {
      return false
    }
    if (filters.level && row.current_level !== filters.level) {
      return false
    }
    return true
  }),
)

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
  // 写成功后 store.post 内部已统一 refresh，筛选视图与汇总卡片随之同步。
}

function resetFilters() {
  filters.status = ''
  filters.level = ''
}

// 刷新页面或从值班台切回本页都重新拉取，看到的一定是当前状态。
function reload() {
  void store.refresh()
}

onMounted(reload)

function statusClass(status: FloodStatus): string {
  if (status === '预警') return 'tag-warning'
  if (status === '应急响应') return 'tag-response'
  return 'tag-closed'
}

function activeTrucks(row: FloodEntry): number {
  return row.trucks.filter((item) => item.状态 !== '已解除回收').length
}

function activeMaterials(row: FloodEntry): number {
  return row.materials
    .filter((item) => item.状态 !== '已解除回收')
    .reduce((sum, item) => sum + item.数量, 0)
}
</script>

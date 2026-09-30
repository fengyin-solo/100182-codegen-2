<template>
  <section class="page" data-module="flood-ledger">
    <header class="page-head">
      <div>
        <h2>防汛排涝应急调度台账</h2>
        <p class="page-desc">一条汛情从预警、响应到解除的完整状态流转台账；汇总卡片与值班入口取同一份数据，解除后物资可用数量自动写回物资台账。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="reload">刷新</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in store.cards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>汛情编号/名称</span>
        <input v-model="keyword" placeholder="按编号或名称检索" />
      </label>
      <label class="filter-item">
        <span>状态</span>
        <select v-model="status">
          <option value="">全部</option>
          <option value="预警中">预警中</option>
          <option value="响应中">响应中</option>
          <option value="已解除">已解除</option>
        </select>
      </label>
      <label class="filter-item">
        <span>等级</span>
        <select v-model="level">
          <option value="">全部</option>
          <optgroup label="预警等级">
            <option v-for="item in store.warningLevels" :key="item" :value="item">{{ item }}</option>
          </optgroup>
          <optgroup label="响应等级">
            <option v-for="item in store.responseLevels" :key="item" :value="item">{{ item }}</option>
          </optgroup>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <p v-if="store.error" class="error-text">{{ store.error }}</p>

    <table class="data-table">
      <thead>
        <tr>
          <th>汛情编号</th><th>汛情名称</th><th>状态</th><th>预警等级</th><th>响应等级</th>
          <th>影响范围</th><th>排涝泵车</th><th>应急物资</th><th>发布/响应/解除</th><th>变更</th><th>台账</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.汛情编号 }}</td>
          <td>{{ row.汛情名称 }}</td>
          <td><span :class="badgeClass(row.status)">{{ row.status }}</span></td>
          <td>{{ row.预警等级 }}</td>
          <td>{{ row.响应等级 || '—' }}</td>
          <td>{{ row.影响范围 }}</td>
          <td>
            <span v-for="item in row.泵车调度" :key="item.材料ID" class="alloc-summary" style="display:block">
              {{ item.泵车名称 }} ×{{ item.数量 }}
            </span>
            <span v-if="!row.泵车调度.length">—</span>
          </td>
          <td>
            <span v-for="item in row.物资调度" :key="item.材料ID" class="alloc-summary" style="display:block">
              {{ item.材料名称 }} ×{{ item.数量 }}
            </span>
            <span v-if="!row.物资调度.length">—</span>
          </td>
          <td class="alloc-summary">
            发：{{ row.发布时间 }}<br />
            应：{{ row.响应时间 || '—' }}<br />
            解：{{ row.解除时间 || '—' }}
          </td>
          <td>{{ row.变更记录.length }} 条</td>
          <td><button class="link" type="button" @click="openDetail(row)">查看</button></td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="11" class="empty-state">没有符合条件的汛情台账</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ rows.length }} 条汛情记录（汇总卡片与本台账同源）</span>
      <span v-if="store.loading">正在同步最新状态…</span>
    </footer>

    <FloodTimeline v-if="current" :event="current" @close="current = null" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import FloodTimeline from '@/components/FloodTimeline.vue'
import { request } from '@/api/client'
import { useFloodStore, type FloodEvent } from '@/stores/flood'

const store = useFloodStore()

const keyword = ref('')
const status = ref('')
const level = ref('')
const rows = ref<FloodEvent[]>([])
const current = ref<FloodEvent | null>(null)

function badgeClass(value: string) {
  if (value === '预警中') return 'badge warning'
  if (value === '响应中') return 'badge responding'
  return 'badge lifted'
}

function resetFilters() {
  keyword.value = ''
  status.value = ''
  level.value = ''
  void reload()
}

async function reload() {
  // 先同步汇总卡片（与值班入口同源），再按筛选条件拉台账明细。
  await store.refresh()
  const params = new URLSearchParams()
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  if (status.value) params.set('status', status.value)
  if (level.value) params.set('level', level.value)
  try {
    const response = await request(`/api/flood?${params.toString()}`)
    const payload = (await response.json()) as { items: FloodEvent[] }
    rows.value = payload.items ?? []
  } catch {
    rows.value = []
  }
}

function openDetail(row: FloodEvent) {
  // 优先取 store 中最新版本，保证台账与值班入口状态一致。
  current.value = store.byId(row.id) ?? row
}

onMounted(reload)
</script>

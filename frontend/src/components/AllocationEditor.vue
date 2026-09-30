<template>
  <div class="alloc-block">
    <div v-for="(row, index) in rows" :key="index" class="alloc-row">
      <select v-model.number="row.id">
        <option :value="0" disabled>请选择{{ kindLabel }}</option>
        <option v-for="item in options" :key="item.id" :value="item.id">
          {{ nameOf(item) }}（可用 {{ item.可用数量 }} {{ unitOf(item) }}）
        </option>
      </select>
      <input v-model.number="row.qty" type="number" min="1" :placeholder="`${kindLabel}数量`" />
      <button class="btn ghost" type="button" @click="remove(index)">删</button>
    </div>
    <button class="btn" type="button" @click="add">添加{{ kindLabel }}</button>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'

import type { StockItem } from '@/stores/flood'

const props = defineProps<{
  kind: 'pump' | 'material'
  options: StockItem[]
  modelValue: { 材料ID: number; 数量: number }[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: { 材料ID: number; 数量: number }[]): void
}>()

const rows = reactive<{ id: number; qty: number | null }[]>([])

function syncFromModel() {
  rows.splice(0, rows.length)
  props.modelValue.forEach((item) => rows.push({ id: item.材料ID, qty: item.数量 }))
}

watch(() => props.modelValue, syncFromModel, { immediate: true, deep: false })

function emitValue() {
  emit(
    'update:modelValue',
    rows
      .filter((row) => row.id > 0 && Number(row.qty) > 0)
      .map((row) => ({ 材料ID: row.id, 数量: Number(row.qty) })),
  )
}

function add() {
  rows.push({ id: 0, qty: null })
}

function remove(index: number) {
  rows.splice(index, 1)
  emitValue()
}

watch(rows, emitValue, { deep: true })

const kindLabel = props.kind === 'pump' ? '排涝泵车' : '应急物资'

function nameOf(item: StockItem) {
  return props.kind === 'pump' ? `${item.泵车编号 ?? ''} ${item.泵车名称 ?? ''}` : `${item.材料编号 ?? ''} ${item.材料名称 ?? ''}`
}

function unitOf(item: StockItem) {
  return props.kind === 'pump' ? '台' : String(item.计量单位 ?? '')
}
</script>

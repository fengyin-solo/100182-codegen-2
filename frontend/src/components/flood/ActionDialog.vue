<template>
  <div v-if="open" class="modal-mask" @click.self="$emit('close')">
    <div class="modal">
      <header class="modal-head">
        <h3>{{ title }}</h3>
        <button class="link" type="button" @click="$emit('close')">关闭</button>
      </header>

      <div class="modal-body">
        <p v-if="entry" class="modal-sub">
          汛情 {{ entry.汛情编号 }} · 当前状态：
          <strong>{{ entry.status }}<template v-if="entry.status === '应急响应'">（{{ entry.current_level }}）</template></strong>
        </p>

        <!-- 预警登记 -->
        <template v-if="mode === 'warning'">
          <label class="form-item">
            <span>汛情编号 <i>*</i></span>
            <input v-model="form.汛情编号" placeholder="如 FLD-2026-003" />
          </label>
          <label class="form-item">
            <span>预警等级 <i>*</i></span>
            <select v-model="form.预警等级">
              <option v-for="level in levels" :key="level" :value="level">{{ level }}预警</option>
            </select>
          </label>
          <label class="form-item">
            <span>降雨情况 <i>*</i></span>
            <textarea v-model="form.降雨情况" rows="2" placeholder="累计雨量、水位、气象趋势等" />
          </label>
          <label class="form-item">
            <span>初始影响范围</span>
            <textarea v-model="form.影响范围" rows="2" placeholder="易涝点、道路、片区" />
          </label>
        </template>

        <!-- 启动响应 / 调整等级 -->
        <template v-else-if="mode === 'start' || mode === 'adjust'">
          <label class="form-item">
            <span>响应等级 <i>*</i></span>
            <select v-model="form.响应等级">
              <option v-for="level in availableLevels" :key="level" :value="level">{{ level }}应急响应</option>
            </select>
          </label>
          <label class="form-item">
            <span>影响范围 <i>*</i></span>
            <textarea v-model="form.影响范围" rows="2" placeholder="本次响应覆盖的片区、易涝点" />
          </label>

          <fieldset class="form-block">
            <legend>调度排涝泵车（{{ mode === 'start' ? '至少 1 台' : '不填则沿用原调度' }}）</legend>
            <div v-for="truck in availableTrucks" :key="truck.id" class="resource-row">
              <label class="check-line">
                <input v-model="selectedTrucks" type="checkbox" :value="truck.id" />
                <span>{{ truck.泵车编号 }} · {{ truck.泵车型号 }}（{{ truck.排涝流量 }}）</span>
              </label>
              <span class="resource-meta">{{ truck.停放场地 }} · {{ truck.状态 }}<template v-if="truck.占用汛情"> · {{ truck.占用汛情 }}</template></span>
            </div>
            <p v-if="!availableTrucks.length" class="form-hint">暂无可调度泵车，全部在外执行任务</p>
          </fieldset>

          <fieldset class="form-block">
            <legend>调度应急物资（不填则不追加物资）</legend>
            <div v-for="row in materialRows" :key="row.id" class="resource-row">
              <label class="check-line">
                <input v-model="row.checked" type="checkbox" />
                <span>{{ row.材料名称 }}（{{ row.材料编号 }}）</span>
              </label>
              <span class="resource-meta">可用 {{ row.可用数量 }} {{ row.计量单位 }}</span>
              <input
                v-model.number="row.quantity"
                class="qty-input"
                type="number"
                min="1"
                :max="row.可用数量"
                :disabled="!row.checked"
              />
            </div>
          </fieldset>
        </template>

        <!-- 解除预警 / 解除响应 -->
        <template v-else>
          <p class="form-tip">
            <template v-if="mode === 'terminate'">
              解除后将回收在调泵车（恢复待命）、把占用物资的可用数量写回物资台账，并登记一条状态变更记录。
            </template>
            <template v-else>预警解除后本场汛情归档，不再占用调度资源。</template>
          </p>
          <label class="form-item">
            <span>解除说明</span>
            <textarea v-model="form.解除说明" rows="3" placeholder="水位回落、积水排退、人员装备撤回情况" />
          </label>
        </template>

        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      </div>

      <footer class="modal-foot">
        <button class="btn" type="button" @click="$emit('close')">取消</button>
        <button class="btn primary" type="button" :disabled="submitting" @click="submit">
          {{ submitting ? '提交中…' : confirmLabel }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import { RESPONSE_LEVELS, useFloodStore, type FloodEntry, type ResponseLevel } from '@/stores/flood'

export type DialogMode = 'warning' | 'start' | 'adjust' | 'cancel-warning' | 'terminate'

const props = defineProps<{
  open: boolean
  mode: DialogMode
  entry?: FloodEntry | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'done', message: string): void
}>()

const store = useFloodStore()
const levels = RESPONSE_LEVELS

const form = reactive<Record<string, string>>({
  汛情编号: '',
  预警等级: 'Ⅳ级',
  响应等级: 'Ⅳ级',
  降雨情况: '',
  影响范围: '',
  解除说明: '',
})
const selectedTrucks = ref<number[]>([])
const materialRows = ref<{ id: number; 材料编号: string; 材料名称: string; 可用数量: number; 计量单位: string; checked: boolean; quantity: number | null }[]>([])
const submitting = ref(false)
const errorMessage = ref('')

const title = computed(() => {
  const titles: Record<DialogMode, string> = {
    warning: '发布汛情预警',
    start: '启动应急响应',
    adjust: '调整响应等级',
    'cancel-warning': '解除预警',
    terminate: '解除应急响应',
  }
  return titles[props.mode]
})

const confirmLabel = computed(() => {
  if (props.mode === 'warning') return '发布预警'
  if (props.mode === 'start') return '启动响应并调度'
  if (props.mode === 'adjust') return '确认调整'
  return '确认解除'
})

const availableLevels = computed<ResponseLevel[]>(
  () => RESPONSE_LEVELS.filter((level) => level !== props.entry?.current_level),
)

const availableTrucks = computed(() => store.truckResources.filter((truck) => truck.状态 === '待命'))

watch(
  () => props.open,
  async (open) => {
    if (!open) {
      return
    }
    errorMessage.value = ''
    selectedTrucks.value = []
    Object.assign(form, {
      汛情编号: `FLD-${new Date().getFullYear()}-${String(store.entries.length + 1).padStart(3, '0')}`,
      预警等级: props.entry?.预警等级 ?? 'Ⅳ级',
      响应等级: props.mode === 'adjust'
        ? RESPONSE_LEVELS.find((level) => level !== props.entry?.current_level) ?? 'Ⅳ级'
        : 'Ⅳ级',
      降雨情况: '',
      影响范围: props.entry?.影响范围 ?? '',
      解除说明: '',
    })
    if (props.mode === 'start' || props.mode === 'adjust') {
      await store.fetchResources()
      materialRows.value = store.materialResources
        // 已冻结/已耗尽的物资禁止调度占用。
        .filter((item) => item.可用数量 > 0 && !['已冻结', '已耗尽'].includes(item.状态))
        .map((item) => ({
          id: item.id,
          材料编号: item.材料编号,
          材料名称: item.材料名称,
          可用数量: item.可用数量,
          计量单位: item.计量单位,
          checked: false,
          quantity: null,
        }))
    }
  },
)

async function submit() {
  errorMessage.value = ''
  if (props.mode === 'warning') {
    if (!form.汛情编号.trim() || !form.降雨情况.trim()) {
      errorMessage.value = '请填写汛情编号与降雨情况'
      return
    }
    submitting.value = true
    const result = await store.createWarning({ ...form })
    submitting.value = false
    if (!result.ok) {
      errorMessage.value = result.message
      return
    }
    emit('done', result.message)
    return
  }

  if (props.mode === 'cancel-warning' || props.mode === 'terminate') {
    submitting.value = true
    const action = props.mode === 'terminate' ? '解除应急响应' : '解除预警'
    const result = await store.runAction(props.entry!.id, { action, 解除说明: form.解除说明 })
    submitting.value = false
    if (!result.ok) {
      errorMessage.value = result.message
      return
    }
    emit('done', result.message)
    return
  }

  // 启动 / 调整
  if (!form.影响范围.trim()) {
    errorMessage.value = '请填写本次响应的影响范围'
    return
  }
  if (props.mode === 'start' && !selectedTrucks.value.length) {
    errorMessage.value = '启动应急响应至少调度 1 台排涝泵车'
    return
  }
  const materials = materialRows.value
    .filter((row) => row.checked)
    .map((row) => {
      const quantity = Number(row.quantity)
      return { material_id: row.id, quantity }
    })
  const over = materials.find((row) => !row.quantity || row.quantity <= 0)
  if (over) {
    errorMessage.value = '请为勾选的物资填写正整数数量'
    return
  }
  const exceed = materials.find((row) => {
    const source = materialRows.value.find((item) => item.id === row.material_id)
    return source ? row.quantity > source.可用数量 : true
  })
  if (exceed) {
    errorMessage.value = `物资「${store.materialResources.find((item) => item.id === exceed.material_id)?.材料名称}」数量超过当前可用余量`
    return
  }

  submitting.value = true
  const action = props.mode === 'start' ? '启动应急响应' : '调整响应等级'
  const result = await store.runAction(props.entry!.id, {
    action,
    响应等级: form.响应等级,
    影响范围: form.影响范围,
    trucks: selectedTrucks.value,
    materials,
  })
  submitting.value = false
  if (!result.ok) {
    errorMessage.value = result.message
    return
  }
  emit('done', result.message)
}
</script>

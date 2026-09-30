<template>
  <section class="page" data-module="flood-duty">
    <header class="page-head">
      <div>
        <h2>防汛值班入口</h2>
        <p class="page-desc">值班岗一屏掌握在汛汛情：发布预警、启动响应、调整等级与解除都在此登记，状态与调度台账实时一致。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="reload">刷新当前状态</button>
        <button class="btn primary" type="button" @click="openIssue">发布汛情预警</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in store.cards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p v-if="store.error" class="error-text">{{ store.error }}</p>

    <h3 class="section-title">在汛汛情（{{ store.activeEvents.length }}）</h3>
    <table class="data-table">
      <thead>
        <tr>
          <th>汛情编号</th><th>汛情名称</th><th>当前状态</th><th>预警/响应等级</th>
          <th>影响范围</th><th>发布时间</th><th>泵车/物资</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in store.activeEvents" :key="row.id">
          <td>{{ row.汛情编号 }}</td>
          <td>{{ row.汛情名称 }}</td>
          <td><span :class="badgeClass(row.status)">{{ row.status }}</span></td>
          <td>{{ row.status === '预警中' ? row.预警等级 : row.响应等级 }}</td>
          <td>{{ row.影响范围 }}</td>
          <td>{{ row.发布时间 }}</td>
          <td>
            {{ sumQty(row.泵车调度) }} 台 / {{ sumQty(row.物资调度) }} 件
          </td>
          <td class="row-actions">
            <button v-if="row.status === '预警中'" class="link" type="button" @click="openResponse(row)">
              启动响应
            </button>
            <button v-if="row.status === '响应中'" class="link" type="button" @click="openAdjust(row)">
              等级调整
            </button>
            <button class="link" type="button" @click="openLift(row)">解除</button>
            <button class="link" type="button" @click="openDetail(row)">变更记录</button>
          </td>
        </tr>
        <tr v-if="!store.activeEvents.length">
          <td colspan="8" class="empty-state">当前没有在汛汛情，可发布一条新的汛情预警</td>
        </tr>
      </tbody>
    </table>

    <h3 class="section-title">已解除汛情（最近）</h3>
    <table class="data-table">
      <thead>
        <tr><th>汛情编号</th><th>汛情名称</th><th>最终等级</th><th>解除时间</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in liftedRows" :key="row.id">
          <td>{{ row.汛情编号 }}</td>
          <td>{{ row.汛情名称 }}</td>
          <td>{{ row.响应等级 || row.预警等级 }}</td>
          <td>{{ row.解除时间 }}</td>
          <td><button class="link" type="button" @click="openDetail(row)">查看台账</button></td>
        </tr>
        <tr v-if="!liftedRows.length">
          <td colspan="5" class="empty-state">暂无已解除汛情</td>
        </tr>
      </tbody>
    </table>

    <!-- 发布预警 -->
    <div v-if="dialog === 'issue'" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <div class="modal-head">
          <h3>发布汛情预警</h3>
          <button class="modal-close" type="button" @click="closeDialog">×</button>
        </div>
        <div class="form-grid">
          <div class="form-field full">
            <label>汛情名称 *</label>
            <input v-model="issueForm.汛情名称" placeholder="如：台风外围强降雨过程" />
          </div>
          <div class="form-field">
            <label>预警等级 *</label>
            <select v-model="issueForm.预警等级">
              <option v-for="level in store.warningLevels" :key="level" :value="level">{{ level }}</option>
            </select>
          </div>
          <div class="form-field">
            <label>影响范围 *</label>
            <input v-model="issueForm.影响范围" placeholder="如：老城片区、滨河下穿隧道" />
          </div>
          <div class="form-field full">
            <label>情况说明</label>
            <textarea v-model="issueForm.说明" placeholder="雨情、预报结论与布防要求" />
          </div>
        </div>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-foot">
          <button class="btn" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitIssue">发布预警</button>
        </div>
      </div>
    </div>

    <!-- 启动响应 -->
    <div v-if="dialog === 'response' && current" class="modal-mask" @click.self="closeDialog">
      <div class="modal wide">
        <div class="modal-head">
          <h3>启动应急响应 · {{ current.汛情编号 }}</h3>
          <button class="modal-close" type="button" @click="closeDialog">×</button>
        </div>
        <div class="form-grid">
          <div class="form-field">
            <label>响应等级 *</label>
            <select v-model="responseForm.响应等级">
              <option value="" disabled>请选择响应等级</option>
              <option v-for="level in store.responseLevels" :key="level" :value="level">{{ level }}</option>
            </select>
          </div>
          <div class="form-field">
            <label>影响范围 *</label>
            <input v-model="responseForm.影响范围" :placeholder="current.影响范围" />
          </div>
        </div>
        <div class="section-title">调度排涝泵车</div>
        <AllocationEditor kind="pump" :options="store.pumps" v-model="responseForm.泵车调度" />
        <div class="section-title">调拨应急物资</div>
        <AllocationEditor kind="material" :options="store.materials" v-model="responseForm.物资调度" />
        <div class="form-field full" style="margin-top: 10px;">
          <label>调度说明</label>
          <textarea v-model="responseForm.说明" placeholder="积水点、抢险力量部署等" />
        </div>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-foot">
          <button class="btn" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitResponse">登记并启动响应</button>
        </div>
      </div>
    </div>

    <!-- 等级调整 -->
    <div v-if="dialog === 'adjust' && current" class="modal-mask" @click.self="closeDialog">
      <div class="modal wide">
        <div class="modal-head">
          <h3>响应等级调整 · {{ current.汛情编号 }}（当前 {{ current.响应等级 }}）</h3>
          <button class="modal-close" type="button" @click="closeDialog">×</button>
        </div>
        <div class="form-grid">
          <div class="form-field">
            <label>调整后等级 *（同级不能覆盖）</label>
            <select v-model="adjustForm.响应等级">
              <option value="" disabled>请选择新的响应等级</option>
              <option v-for="level in store.responseLevels" :key="level" :value="level">{{ level }}</option>
            </select>
          </div>
          <div class="form-field">
            <label>影响范围（留空沿用原值）</label>
            <input v-model="adjustForm.影响范围" :placeholder="current.影响范围" />
          </div>
        </div>
        <div class="section-title">追加调度排涝泵车（可选）</div>
        <AllocationEditor kind="pump" :options="store.pumps" v-model="adjustForm.泵车调度" />
        <div class="section-title">追加调拨应急物资（可选）</div>
        <AllocationEditor kind="material" :options="store.materials" v-model="adjustForm.物资调度" />
        <div class="form-field full" style="margin-top: 10px;">
          <label>调整说明</label>
          <textarea v-model="adjustForm.说明" placeholder="提级/降级原因" />
        </div>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-foot">
          <button class="btn" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitAdjust">确认等级调整</button>
        </div>
      </div>
    </div>

    <!-- 解除 -->
    <div v-if="dialog === 'lift' && current" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <div class="modal-head">
          <h3>解除汛情 · {{ current.汛情编号 }}</h3>
          <button class="modal-close" type="button" @click="closeDialog">×</button>
        </div>
        <p class="page-desc">
          解除后本汛情调度的 {{ sumQty(current.泵车调度) }} 台排涝泵车归库、
          {{ sumQty(current.物资调度) }} 件应急物资恢复可用，可用数量将写回物资台账。
        </p>
        <div class="form-field">
          <label>解除说明</label>
          <textarea v-model="liftForm.说明" placeholder="积水退尽、现场恢复、力量撤收情况" />
        </div>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-foot">
          <button class="btn" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitLift">确认解除</button>
        </div>
      </div>
    </div>

    <!-- 变更记录 / 台账详情 -->
    <FloodTimeline v-if="dialog === 'detail' && current" :event="current" @close="closeDialog" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import AllocationEditor from '@/components/AllocationEditor.vue'
import FloodTimeline from '@/components/FloodTimeline.vue'
import { useFloodStore, type FloodEvent } from '@/stores/flood'

const store = useFloodStore()

const dialog = ref<'' | 'issue' | 'response' | 'adjust' | 'lift' | 'detail'>('')
const current = ref<FloodEvent | null>(null)
const submitting = ref(false)
const formError = ref('')

const issueForm = reactive({ 汛情名称: '', 预警等级: '蓝色预警', 影响范围: '', 说明: '' })
const responseForm = reactive({
  响应等级: '',
  影响范围: '',
  说明: '',
  泵车调度: [] as { 材料ID: number; 数量: number }[],
  物资调度: [] as { 材料ID: number; 数量: number }[],
})
const adjustForm = reactive({
  响应等级: '',
  影响范围: '',
  说明: '',
  泵车调度: [] as { 材料ID: number; 数量: number }[],
  物资调度: [] as { 材料ID: number; 数量: number }[],
})
const liftForm = reactive({ 说明: '' })

const liftedRows = computed(() =>
  [...store.events].filter((item) => item.status === '已解除').slice(0, 5),
)

function badgeClass(status: string) {
  if (status === '预警中') return 'badge warning'
  if (status === '响应中') return 'badge responding'
  return 'badge lifted'
}

function sumQty(list: { 数量: number }[]) {
  return list.reduce((total, item) => total + Number(item.数量 || 0), 0)
}

function reload() {
  void store.refresh()
}

function closeDialog() {
  dialog.value = ''
  current.value = null
  formError.value = ''
}

function resetAllocations(target: { 泵车调度: { 材料ID: number; 数量: number }[]; 物资调度: { 材料ID: number; 数量: number }[] }) {
  target.泵车调度.splice(0)
  target.物资调度.splice(0)
}

function openIssue() {
  Object.assign(issueForm, { 汛情名称: '', 预警等级: '蓝色预警', 影响范围: '', 说明: '' })
  formError.value = ''
  dialog.value = 'issue'
}

function openResponse(row: FloodEvent) {
  current.value = row
  Object.assign(responseForm, { 响应等级: '', 影响范围: row.影响范围, 说明: '' })
  resetAllocations(responseForm)
  formError.value = ''
  dialog.value = 'response'
}

function openAdjust(row: FloodEvent) {
  current.value = row
  Object.assign(adjustForm, { 响应等级: '', 影响范围: '', 说明: '' })
  resetAllocations(adjustForm)
  formError.value = ''
  dialog.value = 'adjust'
}

function openLift(row: FloodEvent) {
  current.value = row
  liftForm.说明 = ''
  formError.value = ''
  dialog.value = 'lift'
}

function openDetail(row: FloodEvent) {
  current.value = row
  dialog.value = 'detail'
}

async function submitIssue() {
  if (!issueForm.汛情名称.trim() || !issueForm.影响范围.trim()) {
    formError.value = '请填写汛情名称与影响范围'
    return
  }
  submitting.value = true
  formError.value = ''
  const result = await store.issueWarning({ ...issueForm })
  submitting.value = false
  if (!result.ok) {
    formError.value = result.message
    return
  }
  closeDialog()
}

async function submitResponse() {
  if (!current.value) return
  if (!responseForm.响应等级) {
    formError.value = '请选择响应等级'
    return
  }
  if (!responseForm.影响范围.trim()) {
    formError.value = '请填写影响范围'
    return
  }
  submitting.value = true
  formError.value = ''
  const result = await store.startResponse(current.value.id, { ...responseForm })
  submitting.value = false
  if (!result.ok) {
    formError.value = result.message
    return
  }
  closeDialog()
}

async function submitAdjust() {
  if (!current.value) return
  if (!adjustForm.响应等级) {
    formError.value = '请选择调整后的响应等级'
    return
  }
  submitting.value = true
  formError.value = ''
  const payload = {
    响应等级: adjustForm.响应等级,
    说明: adjustForm.说明,
    影响范围: adjustForm.影响范围 || undefined,
    泵车调度: adjustForm.泵车调度,
    物资调度: adjustForm.物资调度,
  }
  const result = await store.adjustLevel(current.value.id, payload)
  submitting.value = false
  if (!result.ok) {
    formError.value = result.message
    return
  }
  closeDialog()
}

async function submitLift() {
  if (!current.value) return
  submitting.value = true
  formError.value = ''
  const result = await store.lift(current.value.id, { 说明: liftForm.说明 })
  submitting.value = false
  if (!result.ok) {
    formError.value = result.message
    return
  }
  closeDialog()
}

onMounted(reload)
</script>

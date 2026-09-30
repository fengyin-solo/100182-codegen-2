import { defineStore } from 'pinia'

import { request } from '@/api/client'

/** 汛情状态：预警 -> 应急响应 -> 已解除。 */
export type FloodStatus = '预警' | '应急响应' | '已解除'
export type ResponseLevel = 'Ⅳ级' | 'Ⅲ级' | 'Ⅱ级' | 'Ⅰ级'
export const RESPONSE_LEVELS: ResponseLevel[] = ['Ⅳ级', 'Ⅲ级', 'Ⅱ级', 'Ⅰ级']
export const STATUS_FLOW: FloodStatus[] = ['预警', '应急响应', '已解除']

export interface TruckDispatch {
  泵车id: number
  泵车编号: string
  泵车型号: string
  排涝流量: string
  调度时间: string
  调度人: string
  状态: string
}

export interface MaterialDispatch {
  物资id: number
  材料编号: string
  材料名称: string
  数量: number
  计量单位: string
  调度时间: string
  调度人: string
  状态: string
}

export interface ChangeLog {
  时间: string
  操作人: string
  变更前: string
  变更后: string
  说明: string
}

export interface FloodEntry {
  id: number
  汛情编号: string
  预警等级: ResponseLevel
  current_level: ResponseLevel | '已解除'
  降雨情况: string
  影响范围: string
  登记人员: string
  status: FloodStatus
  pending: boolean
  abnormal: boolean
  预警时间: string | null
  响应时间: string | null
  解除时间: string | null
  解除说明?: string
  dispatched_truck_count: number
  dispatched_material_count: number
  trucks: TruckDispatch[]
  materials: MaterialDispatch[]
  change_logs: ChangeLog[]
}

export interface TruckResource {
  id: number
  泵车编号: string
  泵车型号: string
  排涝流量: string
  停放场地: string
  状态: string
  占用汛情: string | null
}

export interface MaterialResource {
  id: number
  材料编号: string
  材料名称: string
  规格型号: string
  结存数量: number
  可用数量: number
  计量单位: string
  存放场地: string
  状态: string
}

export interface SummaryCard {
  label: string
  value: number
}

interface ActionPayload {
  [key: string]: unknown
  action: string
  trucks?: (number | { truck_id: number })[]
  materials?: { material_id: number; quantity: number }[]
}

interface FloodState {
  entries: FloodEntry[]
  active: FloodEntry[]
  cards: SummaryCard[]
  levelDistribution: Record<string, number>
  truckResources: TruckResource[]
  materialResources: MaterialResource[]
  loading: boolean
  errorMessage: string
  lastLoadedAt: string
}

export const useFloodStore = defineStore('flood', {
  state: (): FloodState => ({
    entries: [],
    active: [],
    cards: [],
    levelDistribution: {},
    truckResources: [],
    materialResources: [],
    loading: false,
    errorMessage: '',
    lastLoadedAt: '',
  }),
  getters: {
    /** 台账与卡片都从 active/cards 取数；这个 getter 给值班台高亮当前最高等级响应。 */
    highestActiveLevel(state): { entry: FloodEntry; level: ResponseLevel } | null {
      const responding = state.active.filter((item) => item.status === '应急响应')
      if (!responding.length) {
        return null
      }
      const rank = (level: string) => RESPONSE_LEVELS.indexOf(level as ResponseLevel)
      const entry = [...responding].sort((a, b) => rank(b.current_level) - rank(a.current_level))[0]
      return { entry, level: entry.current_level as ResponseLevel }
    },
  },
  actions: {
    /** 一次拉齐台账列表、值班入口与汇总卡片：三者永远取自同一份后端数据。 */
    async refresh() {
      this.loading = true
      this.errorMessage = ''
      try {
        const [listRes, activeRes, summaryRes] = await Promise.all([
          request('/api/flood?size=200'),
          request('/api/flood/active'),
          request('/api/flood/summary'),
        ])
        if (!listRes.ok || !activeRes.ok || !summaryRes.ok) {
          throw new Error('防汛调度数据读取失败')
        }
        const listPayload = await listRes.json()
        const activePayload = await activeRes.json()
        const summaryPayload = await summaryRes.json()
        this.entries = listPayload.items ?? []
        this.active = activePayload.items ?? []
        this.cards = summaryPayload.cards ?? []
        this.levelDistribution = summaryPayload.level_distribution ?? {}
        this.lastLoadedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false })
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '防汛调度数据读取失败'
      } finally {
        this.loading = false
      }
    },
    async fetchDetail(id: number): Promise<FloodEntry | null> {
      try {
        const response = await request(`/api/flood/${id}`)
        if (!response.ok) {
          return null
        }
        return (await response.json()) as FloodEntry
      } catch {
        return null
      }
    },
    async fetchResources() {
      try {
        const response = await request('/api/flood/resources')
        if (!response.ok) {
          throw new Error('调度资源读取失败')
        }
        const payload = await response.json()
        this.truckResources = payload.trucks ?? []
        this.materialResources = payload.materials ?? []
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '调度资源读取失败'
      }
    },
    async createWarning(values: Record<string, unknown>): Promise<{ ok: boolean; message: string }> {
      return this.post('/api/flood/warnings', values)
    },
    async runAction(entryId: number, values: ActionPayload): Promise<{ ok: boolean; message: string }> {
      return this.post(`/api/flood/${entryId}/actions`, values as unknown as Record<string, unknown>)
    },
    async post(path: string, values: Record<string, unknown>): Promise<{ ok: boolean; message: string }> {
      this.errorMessage = ''
      try {
        const response = await request(path, {
          method: 'POST',
          body: JSON.stringify({ values }),
        })
        const payload = await response.json().catch(() => null)
        if (!response.ok || !payload) {
          return { ok: false, message: '操作未生效，请稍后重试' }
        }
        if (payload.ok) {
          // 任何写操作成功后立即重新拉取，值班台与台账随之保持一致。
          await this.refresh()
        }
        return { ok: Boolean(payload.ok), message: String(payload.message ?? '') }
      } catch (error) {
        return { ok: false, message: error instanceof Error ? error.message : '操作未送达' }
      }
    },
  },
})

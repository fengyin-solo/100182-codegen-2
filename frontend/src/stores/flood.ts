import { defineStore } from 'pinia'

import { request } from '@/api/client'

/** 防汛排涝调度：值班入口与台账页共用同一份后端数据。
 * 两个页面都在挂载时 refresh()，所以中途返回或刷新都能看到当前状态；
 * 任何动作成功后也会统一刷新，保证两处看到的响应状态一致。
 */

export type Allocation = {
  材料ID: number
  数量: number
  泵车编号?: string
  泵车名称?: string
  材料编号?: string
  材料名称?: string
}

export type ChangeRecord = {
  时间: string
  动作: string
  由状态: string
  到状态: string
  响应等级: string
  影响范围?: string
  值班人员?: string
  说明?: string
  泵车调度?: Allocation[]
  物资调度?: Allocation[]
}

export type FloodEvent = {
  id: number
  status: string
  汛情编号: string
  汛情名称: string
  预警等级: string
  响应等级: string
  影响范围: string
  值班人员: string
  发布时间: string
  响应时间: string
  调整时间: string
  解除时间: string
  泵车调度: Allocation[]
  物资调度: Allocation[]
  变更记录: ChangeRecord[]
}

export type StockItem = {
  id: number
  结存数量: number
  占用数量: number
  可用数量: number
  [key: string]: string | number
}

export type Card = { label: string; value: number }
export type ActionResponse = { ok: boolean; message: string; entry?: FloodEvent }

type State = {
  cards: Card[]
  events: FloodEvent[]
  pumps: StockItem[]
  materials: StockItem[]
  warningLevels: string[]
  responseLevels: string[]
  loading: boolean
  error: string
  loadedAt: number
}

async function postJson(path: string, body: unknown): Promise<ActionResponse> {
  const response = await request(path, { method: 'POST', body: JSON.stringify(body) })
  return (await response.json()) as ActionResponse
}

export const useFloodStore = defineStore('flood', {
  state: (): State => ({
    cards: [],
    events: [],
    pumps: [],
    materials: [],
    warningLevels: ['蓝色预警', '黄色预警', '橙色预警', '红色预警'],
    responseLevels: ['Ⅳ级响应', 'Ⅲ级响应', 'Ⅱ级响应', 'Ⅰ级响应'],
    loading: false,
    error: '',
    loadedAt: 0,
  }),
  getters: {
    activeEvents: (state) => state.events.filter((item) => item.status !== '已解除'),
    warningEvents: (state) => state.events.filter((item) => item.status === '预警中'),
    respondingEvents: (state) => state.events.filter((item) => item.status === '响应中'),
    byId: (state) => (id: number) => state.events.find((item) => item.id === id),
  },
  actions: {
    async refresh() {
      this.loading = true
      this.error = ''
      try {
        const [cardsRes, eventsRes, pumpsRes, materialsRes, optionsRes] = await Promise.all([
          request('/api/flood/summary'),
          request('/api/flood'),
          request('/api/flood/pumps'),
          request('/api/flood/materials?available_only=true'),
          request('/api/flood/meta/options'),
        ])
        const cards = (await cardsRes.json()) as { cards: Card[] }
        const events = (await eventsRes.json()) as { items: FloodEvent[] }
        const pumps = (await pumpsRes.json()) as { items: StockItem[] }
        const materials = (await materialsRes.json()) as { items: StockItem[] }
        const options = (await optionsRes.json()) as {
          warning_levels: string[]
          response_levels: string[]
        }
        this.cards = cards.cards
        this.events = events.items
        this.pumps = pumps.items
        this.materials = materials.items
        this.warningLevels = options.warning_levels
        this.responseLevels = options.response_levels
        this.loadedAt = Date.now()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '防汛调度数据读取失败'
      } finally {
        this.loading = false
      }
    },
    async issueWarning(body: {
      汛情名称: string
      预警等级: string
      影响范围: string
      说明?: string
    }): Promise<ActionResponse> {
      const result = await postJson('/api/flood/warning', body)
      if (result.ok) await this.refresh()
      return result
    },
    async startResponse(
      id: number,
      body: {
        响应等级: string
        影响范围: string
        说明?: string
        泵车调度: { 材料ID: number; 数量: number }[]
        物资调度: { 材料ID: number; 数量: number }[]
      },
    ): Promise<ActionResponse> {
      const result = await postJson(`/api/flood/${id}/response`, body)
      if (result.ok) await this.refresh()
      return result
    },
    async adjustLevel(
      id: number,
      body: {
        响应等级: string
        说明?: string
        泵车调度: { 材料ID: number; 数量: number }[]
        物资调度: { 材料ID: number; 数量: number }[]
      },
    ): Promise<ActionResponse> {
      const result = await postJson(`/api/flood/${id}/adjust`, body)
      if (result.ok) await this.refresh()
      return result
    },
    async lift(id: number, body: { 说明?: string }): Promise<ActionResponse> {
      const result = await postJson(`/api/flood/${id}/lift`, body)
      if (result.ok) await this.refresh()
      return result
    },
  },
})

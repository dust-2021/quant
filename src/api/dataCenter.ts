import { fetch } from './base'
import { setSetting } from './setting'
import { ElMessage } from 'element-plus'

export interface ExchangeItem {
  id: number
  name: string
}

export interface ScriptItem {
  id: number
  name: string
  content: string
}

export async function getExchanges(): Promise<ExchangeItem[]> {
  const resp = await fetch<ExchangeItem[]>('/api/data_center/exchanges', 'GET')
  if (resp === null || resp.code !== 0) {
    return []
  }
  return resp.data || []
}

export async function getScripts(): Promise<ScriptItem[]> {
  const resp = await fetch<ScriptItem[]>('/api/data_center/scripts', 'GET')
  if (resp === null || resp.code !== 0) {
    return []
  }
  return resp.data || []
}

export async function setExchangeConfig(exchange: string): Promise<boolean> {
  return await setSetting('Exchange', exchange)
}

export async function saveScript(name: string, content: string): Promise<boolean> {
  const resp = await fetch('/api/data_center/script', 'POST', { name, content })
  if (resp === null || resp.code !== 0) {
    ElMessage.error(resp?.msg || '保存脚本失败')
    return false
  }
  ElMessage.success(resp.msg || '脚本已保存')
  return true
}

export async function deleteScript(name: string): Promise<boolean> {
  const resp = await fetch('/api/data_center/script/delete', 'POST', { name })
  if (resp === null || resp.code !== 0) {
    ElMessage.error(resp?.msg || '删除脚本失败')
    return false
  }
  ElMessage.success(resp.msg || '脚本已删除')
  return true
}

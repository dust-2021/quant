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

export async function createExchange(name: string): Promise<boolean> {
  const resp = await fetch('/api/data_center/exchange', 'POST', { name })
  if (resp === null || resp.code !== 0) {
    ElMessage.error(resp?.msg || '创建交易所失败')
    return false
  }
  ElMessage.success(resp.msg || '交易所已创建')
  return true
}

export async function deleteExchange(name: string): Promise<boolean> {
  const resp = await fetch('/api/data_center/exchange/delete', 'POST', { name })
  if (resp === null || resp.code !== 0) {
    ElMessage.error(resp?.msg || '删除交易所失败')
    return false
  }
  ElMessage.success(resp.msg || '交易所已删除')
  return true
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

export async function executeScript(name: string, params?: Record<string, any>): Promise<{ data: any; error: string | null }> {
  const resp = await fetch('/api/data_center/script/execute', 'POST', { name, params })
  if (resp === null || resp.code !== 0) {
    return { data: null, error: resp?.msg || '执行脚本失败' }
  }
  return { data: resp.data, error: null }
}

export async function getTargets(exchange: string, keyword: string = ''): Promise<string[]> {
  const resp = await fetch<string[]>(
    `/api/data_center/targets?exchange=${encodeURIComponent(exchange)}&keyword=${encodeURIComponent(keyword)}`, 'GET')
  if (resp === null || resp.code !== 0) return []
  return resp.data || []
}

export async function checkDataTable(exchange: string, code: string, period: number): Promise<{ table: string; exists: boolean } | null> {
  const resp = await fetch<{ table: string; exists: boolean }>(
    `/api/data_center/check_table?exchange=${encodeURIComponent(exchange)}&code=${encodeURIComponent(code)}&period=${period}`, 'GET');
  if (resp === null || resp.code !== 0) return null
  return resp.data || null
}

export interface DataIntegrityGroup {
  data_type: number
  count: number
  expected: number
  complete: boolean
  min_time: number | null
  max_time: number | null
}

export interface DataIntegrityResult {
  table: string
  query_start: number
  query_end: number
  expected: number
  all_complete: boolean
  groups: DataIntegrityGroup[]
}

export async function checkDataIntegrity(
  exchange: string, code: string, period: number, start: number, end: number
): Promise<DataIntegrityResult | string> {
  const resp = await fetch<DataIntegrityResult>(
    `/api/data_center/check_data?exchange=${encodeURIComponent(exchange)}&code=${encodeURIComponent(code)}&period=${period}&start=${start}&end=${end}`, 'GET')
  if (resp === null || resp.code !== 0) {
      console.log(resp.msg);
      return resp.msg ?? '未知错误'; 
  }
  return resp.data ?? '';
}

import { fetch } from './base'
import { ElMessage } from 'element-plus'

export interface CalculatorItem {
  id: number
  name: string
  description: string
  content: string
  create_time: number
  update_time: number
}

export async function getCalculatorList(): Promise<CalculatorItem[]> {
  const resp = await fetch<CalculatorItem[]>('/api/calculator/list', 'GET')
  if (resp === null || resp.code !== 0) {
    return []
  }
  return resp.data || []
}

export async function saveCalculator(name: string, content: string, description: string = ''): Promise<boolean> {
  const resp = await fetch('/api/calculator/save', 'POST', { name, content, description })
  if (resp === null || resp.code !== 0) {
    ElMessage.error(resp?.msg || '保存算子失败')
    return false
  }
  ElMessage.success(resp.msg || '算子已保存')
  return true
}

export async function deleteCalculator(name: string): Promise<boolean> {
  const resp = await fetch('/api/calculator/delete', 'POST', { name })
  if (resp === null || resp.code !== 0) {
    ElMessage.error(resp?.msg || '删除算子失败')
    return false
  }
  ElMessage.success(resp.msg || '算子已删除')
  return true
}

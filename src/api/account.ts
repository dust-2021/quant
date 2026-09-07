import { fetch } from './base'
import { ElMessage } from 'element-plus'

export interface AccountItem {
  id: number
  name: string
  exchange: string
  api_key: string
  api_secret: string
  api_passphrase: string | null
  encrypt_type: string
  strategy_uuid: string | null
  status: number
  trader_id: number | null
  period: number
  target: string
}

export async function getAccounts(): Promise<AccountItem[]> {
  const resp = await fetch<AccountItem[]>('/api/account/list', 'GET')
  if (resp === null || resp.code !== 0) {
    return []
  }
  return resp.data || []
}

export async function createAccount(data: Record<string, any>): Promise<boolean> {
  const resp = await fetch('/api/account/create', 'POST', data)
  if (resp === null || resp.code !== 0) {
    ElMessage.error(resp?.msg || '创建账号失败')
    return false
  }
  ElMessage.success('账号已创建')
  return true
}

export async function updateAccount(data: Record<string, any>): Promise<boolean> {
  const resp = await fetch('/api/account/update', 'POST', data)
  if (resp === null || resp.code !== 0) {
    ElMessage.error(resp?.msg || '更新账号失败')
    return false
  }
  ElMessage.success('账号已更新')
  return true
}

export async function deleteAccount(id: number): Promise<boolean> {
  const resp = await fetch('/api/account/delete', 'POST', { id })
  if (resp === null || resp.code !== 0) {
    ElMessage.error(resp?.msg || '删除账号失败')
    return false
  }
  ElMessage.success('账号已删除')
  return true
}

export async function setAccountStatus(id: number, status: number): Promise<boolean> {
  const resp = await fetch('/api/account/status', 'POST', { id, status })
  if (resp === null || resp.code !== 0) {
    ElMessage.error(resp?.msg || '修改状态失败')
    return false
  }
  ElMessage.success('状态已更新')
  return true
}

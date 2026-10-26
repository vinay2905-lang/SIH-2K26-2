import { useQuery } from '@tanstack/react-query'
import type { AppConfig, Programme, RuleInfo } from '@/types/api'
import { api } from './api'

export function useAppConfig() {
  return useQuery({
    queryKey: ['meta-config'],
    queryFn: () => api.get<AppConfig>('/meta/config'),
    staleTime: 5 * 60_000,
  })
}

export function useRules() {
  return useQuery({
    queryKey: ['rules'],
    queryFn: () => api.get<RuleInfo[]>('/rules'),
    staleTime: 5 * 60_000,
  })
}

export function useProgrammes(institutionId?: string) {
  return useQuery({
    queryKey: ['programmes', institutionId ?? 'scope'],
    queryFn: () =>
      api.get<Programme[]>('/programmes', institutionId ? { institution_id: institutionId } : undefined),
  })
}

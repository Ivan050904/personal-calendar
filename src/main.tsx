import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { LocalDayCalendarService } from './application/day-calendar'
import { LocalPlansService } from './application/plans'
import { LocalTasksService } from './application/tasks'
import { LocalListsService } from './application/lists'
import { LocalCategoriesService } from './application/categories'
import { LocalRemindersService, type ReminderRepository } from './application/reminders'
import { ensureLocalCalendar } from './application/seed-local-calendar'
import {
  createIndexedDbRepositories,
  openCalendarDatabase,
  IndexedDbEntityRepository,
} from './infrastructure/indexed-db-repositories'
import { createApiRepositories, shouldUseApiRepository } from './infrastructure/api-repositories'
import { fetchAuthMe, logout } from './infrastructure/auth'
import { ApiDayCalendarService, ApiTasksService, ApiPlansService } from './infrastructure/api-calendar-services'
import { App, type AppServices } from './presentation/App'
import { LoginPage } from './presentation/LoginPage'
import type { Reminder } from './domain/models'
import type { Repositories } from './application/repositories'
import './presentation/day-calendar.css'
import './presentation/app-shell.css'

const root = createRoot(document.getElementById('root')!)

class IndexedDbReminderRepository extends IndexedDbEntityRepository<Reminder> implements ReminderRepository {
  async delete(id: string): Promise<void> {
    const transaction = this.database.transaction(this.storeName, 'readwrite')
    await new Promise<void>((resolve, reject) => {
      const request = transaction.objectStore(this.storeName).delete(id)
      request.onsuccess = () => resolve()
      request.onerror = () => reject(request.error ?? new Error('IndexedDB delete failed'))
    })
  }
}

async function loadRepositories(): Promise<{ repositories: Repositories; reminderRepo: ReminderRepository }> {
  if (shouldUseApiRepository()) {
    const repositories = createApiRepositories('/api')
    return {
      repositories,
      reminderRepo: {
        get: (id) => repositories.reminders.get(id),
        list: () => repositories.reminders.list(),
        put: (entity) => repositories.reminders.put(entity),
        delete: async (id) => {
          const row = await repositories.reminders.get(id)
          const response = await fetch(`/api/entities/reminders/${id}`, { method: 'DELETE', credentials: 'include', headers: { 'If-Match': String(row?.revision ?? '') } })
          if (!response.ok) throw new Error('Не удалось удалить напоминание')
        },
      },
    }
  }

  const database = await openCalendarDatabase()
  const repositories = createIndexedDbRepositories(database)
  return {
    repositories,
    reminderRepo: new IndexedDbReminderRepository(database, 'reminders'),
  }
}

function AppBoot({ onLogout }: { onLogout?: () => void }) {
  const [ready, setReady] = useState<{ services: AppServices } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const { repositories, reminderRepo } = await loadRepositories()
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
        const calendar = await ensureLocalCalendar(
          repositories.calendars,
          timezone,
          () => new Date().toISOString(),
          repositories.events,
        )
        const reminders = new LocalRemindersService(reminderRepo)
        if (cancelled) return
        setReady({
          services: {
            calendar: shouldUseApiRepository() ? new ApiDayCalendarService(calendar) : new LocalDayCalendarService(
              calendar,
              repositories.events,
              repositories.recurrenceRules,
              repositories.eventExceptions,
            ),
            plans: shouldUseApiRepository() ? new ApiPlansService(calendar, repositories.plans, repositories.planTasks) : new LocalPlansService(calendar, repositories.plans, repositories.planTasks),
            tasks: shouldUseApiRepository() ? new ApiTasksService(calendar, repositories.tasks, repositories.recurrenceRules) : new LocalTasksService(calendar, repositories.tasks, repositories.recurrenceRules),
            lists: new LocalListsService(calendar, repositories.lists, repositories.listItems),
            categories: new LocalCategoriesService(calendar, repositories.categories),
            reminders,
            repositories,
          },
        })
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Не удалось загрузить приложение')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return (
      <div className="login-shell">
        <div className="login-card">
          <h1>Ошибка</h1>
          <p className="login-error" role="alert">
            {error}
          </p>
        </div>
      </div>
    )
  }

  if (!ready) {
    return (
      <div className="login-shell">
        <p className="login-hint">Загрузка…</p>
      </div>
    )
  }

  return <App services={ready.services} onLogout={onLogout} />
}

function Root() {
  const useApi = shouldUseApiRepository()
  const [gate, setGate] = useState<'loading' | 'login' | 'app'>(useApi ? 'loading' : 'app')
  const [identity, setIdentity] = useState<string | null>(null)

  useEffect(() => {
    if (!useApi) return
    let cancelled = false
    const refreshIdentity = () => { void fetchAuthMe().then((me) => {
      if (cancelled) return
      setIdentity(me.principal_id)
      setGate(me.authenticated ? 'app' : 'login')
    }) }
    refreshIdentity()
    window.addEventListener('focus', refreshIdentity)
    window.addEventListener('pageshow', refreshIdentity)
    const onVisibility = () => { if (document.visibilityState === 'visible') refreshIdentity() }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      cancelled = true
      window.removeEventListener('focus', refreshIdentity)
      window.removeEventListener('pageshow', refreshIdentity)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [useApi])

  if (gate === 'loading') {
    return (
      <div className="login-shell">
        <p className="login-hint">Проверка сессии…</p>
      </div>
    )
  }

  if (gate === 'login') {
    return <LoginPage onSuccess={() => { void fetchAuthMe().then(me => { setIdentity(me.principal_id); setGate(me.authenticated ? 'app' : 'login') }) }} />
  }

  return (
    <AppBoot
      key={identity ?? 'standalone'}
      onLogout={
        useApi
          ? () => {
              void logout().finally(() => setGate('login'))
            }
          : undefined
      }
    />
  )
}

root.render(
  <StrictMode>
    <Root />
  </StrictMode>,
)

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js').catch(() => undefined)
  })
}

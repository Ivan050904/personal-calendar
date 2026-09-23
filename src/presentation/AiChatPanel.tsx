import { useEffect, useRef, useState } from 'react'
import { isoToZonedInput, zonedInputToIso } from '../application/day-calendar'

export interface AiDraftCard {
  draftId: string
  operation: string
  entityType?: string | null
  payload: Record<string, unknown>
  status: string
  clarification?: string | null
  missingFields?: string[]
  message?: string | null
  recurrenceScope?: string | null
  result?: {
    executed?: boolean
    idempotent?: boolean
    entityType?: string
    entity?: { title?: string }
  } | null
}

interface ChatResponse {
  provider: string
  action: {
    intent: string
    message?: string | null
    clarification?: string | null
    missingFields?: string[]
  }
  draft: AiDraftCard | null
}

type ChatRole = 'user' | 'assistant' | 'system'
type Phase = 'idle' | 'recording' | 'transcribing' | 'sending' | 'confirming'
type EntityType = 'event' | 'plan' | 'task' | 'list'

interface ChatMessage {
  id: string
  role: ChatRole
  text: string
  draft?: AiDraftCard | null
  editing?: boolean
  kind?: 'error' | 'status' | 'normal'
  pending?: boolean
}

type RecurrenceFrequency = 'never' | 'daily' | 'weekly' | 'weekdays' | 'monthly'

interface DraftFormState {
  entityType: EntityType
  title: string
  description: string
  start: string
  end: string
  dueDate: string
  recurrenceScope: string
  recurrenceFrequency: RecurrenceFrequency
  recurrenceWeekdays: number[]
}

const WEEKDAY_OPTS: { value: number; label: string }[] = [
  { value: 1, label: 'пн' },
  { value: 2, label: 'вт' },
  { value: 3, label: 'ср' },
  { value: 4, label: 'чт' },
  { value: 5, label: 'пт' },
  { value: 6, label: 'сб' },
  { value: 7, label: 'вс' },
]

const FREQ_LABELS: Record<Exclude<RecurrenceFrequency, 'never'>, string> = {
  daily: 'каждый день',
  weekly: 'каждую неделю',
  weekdays: 'по выбранным дням',
  monthly: 'каждый месяц',
}

const SUCCESS_LABELS: Record<string, string> = {
  event: 'Событие создано',
  plan: 'План создан',
  task: 'Задача создана',
  list: 'Список создан',
}

const DRAFT_STATUS_LABELS: Record<string, string> = {
  ready: 'Готово',
  collecting: 'Нужны данные',
  confirmed: 'Подтверждено',
  cancelled: 'Отменено',
  expired: 'Истекло',
}

const OPERATION_LABELS: Record<string, string> = {
  CREATE: 'Создать',
  UPDATE: 'Изменить',
  DELETE: 'Удалить',
}

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function deviceTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
}

function toLocalInput(value: unknown, timezone = deviceTimezone()): string {
  if (typeof value !== 'string' || !value) return ''
  // Naive wall-clock from AI — keep as datetime-local digits.
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value) && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(value.slice(0, 25))) {
    return value.slice(0, 16)
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 16)
  return isoToZonedInput(value, timezone)
}

function localInputToIso(value: string, timezone = deviceTimezone()): string | undefined {
  if (!value) return undefined
  const normalized = value.length >= 16 ? value.slice(0, 16) : value
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(normalized)) return value
  return zonedInputToIso(normalized, timezone)
}

function readRecurrence(payload: Record<string, unknown>): {
  frequency: RecurrenceFrequency
  weekdays: number[]
} {
  const raw = payload.recurrence
  if (!raw || typeof raw !== 'object') return { frequency: 'never', weekdays: [] }
  const rec = raw as { frequency?: string; weekdays?: unknown }
  const frequency = (['daily', 'weekly', 'weekdays', 'monthly'].includes(String(rec.frequency))
    ? rec.frequency
    : 'never') as RecurrenceFrequency
  const weekdays = Array.isArray(rec.weekdays)
    ? rec.weekdays.map(Number).filter((n) => n >= 1 && n <= 7)
    : []
  return { frequency, weekdays }
}

function draftToForm(draft: AiDraftCard): DraftFormState {
  const payload = draft.payload ?? {}
  const recurrence = readRecurrence(payload)
  return {
    entityType: (draft.entityType as EntityType) || 'task',
    title: String(payload.title ?? ''),
    description: String(payload.description ?? payload.notes ?? ''),
    start: toLocalInput(payload.start ?? payload.startAt),
    end: toLocalInput(payload.end ?? payload.endAt),
    dueDate: String(payload.dueDate ?? '').slice(0, 10),
    recurrenceScope: draft.recurrenceScope ?? '',
    recurrenceFrequency: recurrence.frequency,
    recurrenceWeekdays: recurrence.weekdays,
  }
}

function formToPayload(form: DraftFormState): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    title: form.title.trim(),
    description: form.description.trim() || undefined,
  }
  if (form.entityType === 'event' || form.entityType === 'plan') {
    payload.start = localInputToIso(form.start)
    payload.startAt = payload.start
    payload.end = localInputToIso(form.end)
    payload.endAt = payload.end
    payload.timezone = deviceTimezone()
  }
  if (form.entityType === 'task') {
    payload.dueDate = form.dueDate || undefined
  }
  if (form.entityType === 'event') {
    if (form.recurrenceFrequency === 'never') {
      payload.recurrence = null
    } else {
      payload.recurrence = {
        frequency: form.recurrenceFrequency,
        interval: 1,
        weekdays:
          form.recurrenceFrequency === 'weekly' || form.recurrenceFrequency === 'weekdays'
            ? form.recurrenceWeekdays
            : [],
      }
    }
  }
  return payload
}

function formatWhen(payload: Record<string, unknown>): string | null {
  const start = toLocalInput(payload.start ?? payload.startAt)
  const end = toLocalInput(payload.end ?? payload.endAt)
  if (!start) return null
  const fmt = (value: string) => {
    const [date, time] = value.split('T')
    if (!date) return value
    const [y, m, d] = date.split('-')
    return `${d}.${m}.${y}${time ? ` ${time}` : ''}`
  }
  return end ? `${fmt(start)} – ${fmt(end)}` : fmt(start)
}

function formatRecurrence(payload: Record<string, unknown>): string {
  const { frequency, weekdays } = readRecurrence(payload)
  if (frequency === 'never') return 'Без повтора'
  const days =
    weekdays.length > 0
      ? weekdays
          .map((n) => WEEKDAY_OPTS.find((d) => d.value === n)?.label ?? String(n))
          .join(', ')
      : null
  const base = FREQ_LABELS[frequency]
  return days ? `Повтор: ${base} · ${days}` : `Повтор: ${base}`
}

function draftSummary(draft: AiDraftCard): string {
  const title = String(draft.payload.title ?? 'Без названия')
  const op = OPERATION_LABELS[draft.operation] ?? draft.operation
  const type = draft.entityType ?? 'объект'
  if (draft.clarification) return draft.clarification
  if (draft.missingFields?.length) {
    return `Нужно уточнить поля. Можно поправить форму ниже или ответить в чате.`
  }
  return `Проверьте черновик: ${op.toLowerCase()} ${type} «${title}».`
}

function DraftEditor({
  draft,
  busy,
  onSave,
  onCancelEdit,
}: {
  draft: AiDraftCard
  busy: boolean
  onSave: (form: DraftFormState) => void
  onCancelEdit: () => void
}) {
  const [form, setForm] = useState<DraftFormState>(() => draftToForm(draft))

  const set = <K extends keyof DraftFormState>(key: K, value: DraftFormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <form
      className="chat-draft-form"
      onSubmit={(event) => {
        event.preventDefault()
        onSave(form)
      }}
    >
      <label>
        Тип
        <select
          value={form.entityType}
          disabled={busy || draft.operation === 'DELETE'}
          onChange={(event) => set('entityType', event.target.value as EntityType)}
        >
          <option value="task">Задача</option>
          <option value="event">Событие</option>
          <option value="plan">План</option>
          <option value="list">Список</option>
        </select>
      </label>
      <label>
        Название
        <input
          value={form.title}
          disabled={busy}
          onChange={(event) => set('title', event.target.value)}
          required
        />
      </label>
      {(form.entityType === 'event' || form.entityType === 'plan') && (
        <>
          <label>
            Начало
            <input
              type="datetime-local"
              value={form.start}
              disabled={busy}
              onChange={(event) => set('start', event.target.value)}
            />
          </label>
          <label>
            Конец
            <input
              type="datetime-local"
              value={form.end}
              disabled={busy}
              onChange={(event) => set('end', event.target.value)}
            />
          </label>
        </>
      )}
      {form.entityType === 'event' && draft.operation !== 'DELETE' && (
        <>
          <label>
            Повтор
            <select
              value={form.recurrenceFrequency}
              disabled={busy}
              onChange={(event) => {
                const next = event.target.value as RecurrenceFrequency
                setForm((prev) => ({
                  ...prev,
                  recurrenceFrequency: next,
                  recurrenceWeekdays:
                    next === 'weekly' || next === 'weekdays'
                      ? prev.recurrenceWeekdays.length
                        ? prev.recurrenceWeekdays
                        : [2]
                      : [],
                }))
              }}
            >
              <option value="never">Без повтора</option>
              <option value="daily">Каждый день</option>
              <option value="weekly">Каждую неделю</option>
              <option value="weekdays">По дням недели</option>
              <option value="monthly">Каждый месяц</option>
            </select>
          </label>
          {(form.recurrenceFrequency === 'weekly' || form.recurrenceFrequency === 'weekdays') && (
            <fieldset className="chat-draft-weekdays" disabled={busy}>
              <legend>Дни недели</legend>
              {WEEKDAY_OPTS.map((day) => (
                <label key={day.value} className="chat-draft-weekday">
                  <input
                    type="checkbox"
                    checked={form.recurrenceWeekdays.includes(day.value)}
                    onChange={() => {
                      setForm((prev) => {
                        const has = prev.recurrenceWeekdays.includes(day.value)
                        const next = has
                          ? prev.recurrenceWeekdays.filter((n) => n !== day.value)
                          : [...prev.recurrenceWeekdays, day.value].sort((a, b) => a - b)
                        return { ...prev, recurrenceWeekdays: next }
                      })
                    }}
                  />
                  {day.label}
                </label>
              ))}
            </fieldset>
          )}
        </>
      )}
      {form.entityType === 'task' && (
        <label>
          Срок (дата)
          <input
            type="date"
            value={form.dueDate}
            disabled={busy}
            onChange={(event) => set('dueDate', event.target.value)}
          />
        </label>
      )}
      <label>
        Описание
        <textarea
          rows={2}
          value={form.description}
          disabled={busy}
          onChange={(event) => set('description', event.target.value)}
        />
      </label>
      {draft.operation !== 'CREATE' && draft.entityType === 'event' && (
        <label>
          Область повторения
          <select
            value={form.recurrenceScope}
            disabled={busy}
            onChange={(event) => set('recurrenceScope', event.target.value)}
          >
            <option value="">Не нужно / не повторяется</option>
            <option value="occurrence">Только это вхождение</option>
            <option value="this_and_following">Это и следующие</option>
            <option value="entire_series">Вся серия</option>
          </select>
        </label>
      )}
      <div className="chat-draft-actions">
        <button type="submit" className="btn btn-primary" disabled={busy || form.title.trim().length === 0}>
          Сохранить в черновик
        </button>
        <button type="button" className="btn btn-ghost" disabled={busy} onClick={onCancelEdit}>
          Закрыть форму
        </button>
      </div>
    </form>
  )
}

const CHAT_STORAGE_KEY = 'personal-calendar-ai-chat-v1'

const WELCOME: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  text: 'Я помогаю только с календарём: события, планы, задачи и списки. Напишите или надиктуйте команду. Если что-то неясно — спрошу, либо откройте «Изменить форму» и поправьте поля (в том числе повтор).',
  kind: 'normal',
}

function loadChatState(): { messages: ChatMessage[]; activeDraft: AiDraftCard | null } {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY)
    if (!raw) return { messages: [WELCOME], activeDraft: null }
    const parsed = JSON.parse(raw) as { messages?: ChatMessage[]; activeDraft?: AiDraftCard | null }
    if (!Array.isArray(parsed.messages) || parsed.messages.length === 0) {
      return { messages: [WELCOME], activeDraft: null }
    }
    return { messages: parsed.messages, activeDraft: parsed.activeDraft ?? null }
  } catch {
    return { messages: [WELCOME], activeDraft: null }
  }
}

export function AiChatPanel({
  apiBase = '/api',
  onApplied,
  onClose,
}: {
  apiBase?: string
  onApplied?: () => void | Promise<void>
  onClose?: () => void
}) {
  const initial = loadChatState()
  const [input, setInput] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [activeDraft, setActiveDraft] = useState<AiDraftCard | null>(initial.activeDraft)
  const [messages, setMessages] = useState<ChatMessage[]>(initial.messages)
  const [recordSeconds, setRecordSeconds] = useState(0)

  const mediaRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const recordTimerRef = useRef<number | undefined>(undefined)
  const stopTimeoutRef = useRef<number | undefined>(undefined)
  const listRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const draftRef = useRef<AiDraftCard | null>(null)

  const busy = phase !== 'idle' && phase !== 'recording'

  useEffect(() => {
    draftRef.current = activeDraft
  }, [activeDraft])

  useEffect(() => {
    try {
      localStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify({ messages, activeDraft }),
      )
    } catch {
      /* ignore quota */
    }
  }, [messages, activeDraft])

  useEffect(() => {
    const el = listRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [messages, phase])

  useEffect(() => {
    return () => {
      mediaRef.current?.stop()
      if (recordTimerRef.current) window.clearInterval(recordTimerRef.current)
      if (stopTimeoutRef.current) window.clearTimeout(stopTimeoutRef.current)
    }
  }, [])

  const pushMessage = (message: Omit<ChatMessage, 'id'> & { id?: string }) => {
    const next = { ...message, id: message.id ?? uid() }
    setMessages((prev) => [...prev, next])
    return next.id
  }

  const updateMessage = (id: string, patch: Partial<ChatMessage>) => {
    setMessages((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)))
  }

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || busy || phase === 'recording') return

    pushMessage({ role: 'user', text: trimmed })
    setInput('')
    setPhase('sending')
    const pendingId = pushMessage({
      role: 'assistant',
      text: 'Думаю…',
      pending: true,
      kind: 'status',
    })

    try {
      const response = await fetch(`${apiBase}/ai/chat`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: trimmed,
          draft_id: draftRef.current?.status === 'collecting' ? draftRef.current.draftId : undefined,
        }),
      })
      const body = (await response.json()) as ChatResponse & { error?: { message?: string } }
      if (!response.ok) {
        throw new Error(body.error?.message ?? `Ошибка ${response.status}`)
      }

      if (body.action.intent === 'OFF_TOPIC') {
        setActiveDraft(null)
        updateMessage(pendingId, {
          pending: false,
          kind: 'normal',
          text: body.action.message ?? 'Я могу помогать только с календарём, планами, задачами и списками.',
          draft: null,
          editing: false,
        })
        return
      }

      const draft = body.draft
      setActiveDraft(draft)
      const needsEdit = Boolean(draft && (draft.status === 'collecting' || draft.missingFields?.length))
      updateMessage(pendingId, {
        pending: false,
        kind: 'normal',
        text: draft
          ? draftSummary(draft)
          : (body.action.clarification ?? body.action.message ?? 'Готово.'),
        draft,
        editing: needsEdit,
      })
    } catch (err) {
      updateMessage(pendingId, {
        pending: false,
        kind: 'error',
        text: err instanceof Error ? err.message : 'Не удалось отправить сообщение',
        draft: null,
        editing: false,
      })
    } finally {
      setPhase('idle')
      inputRef.current?.focus()
    }
  }

  const saveDraftEdits = async (draft: AiDraftCard, messageId: string, form: DraftFormState) => {
    if (busy) return
    setPhase('confirming')
    try {
      const response = await fetch(`${apiBase}/ai/drafts/${draft.draftId}`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entityType: form.entityType,
          payload: formToPayload(form),
          recurrenceScope: form.recurrenceScope || null,
        }),
      })
      const body = await response.json()
      if (!response.ok) {
        throw new Error(body.error?.message ?? 'Не удалось сохранить черновик')
      }
      const updated = body as AiDraftCard
      setActiveDraft(updated)
      updateMessage(messageId, {
        draft: updated,
        editing: updated.status !== 'ready',
        text: updated.status === 'ready'
          ? draftSummary(updated)
          : `Ещё не хватает: ${(updated.missingFields ?? []).join(', ') || 'поля'}. Дополните форму.`,
      })
    } catch (err) {
      pushMessage({
        role: 'system',
        kind: 'error',
        text: err instanceof Error ? err.message : 'Ошибка сохранения формы',
      })
    } finally {
      setPhase('idle')
    }
  }

  const confirm = async (draft: AiDraftCard, messageId: string) => {
    if (busy) return
    setPhase('confirming')
    try {
      const response = await fetch(`${apiBase}/ai/drafts/${draft.draftId}/confirm`, {
        method: 'POST',
        credentials: 'include',
      })
      const body = await response.json()
      if (!response.ok) {
        const details = body.error?.details as { candidates?: Array<{ title?: string }> } | undefined
        if (body.error?.code === 'ambiguous_target' && details?.candidates?.length) {
          const titles = details.candidates.map((c) => c.title ?? 'без названия').join(', ')
          throw new Error(`Несколько совпадений: ${titles}. Уточните название.`)
        }
        throw new Error(body.error?.message ?? 'Не удалось подтвердить')
      }

      // MySQL is the source of truth — refresh the board from API.
      await onApplied?.()

      const entityType = body.result?.entityType ?? draft.entityType ?? ''
      const label = SUCCESS_LABELS[entityType] ?? 'Готово'
      const title = body.result?.entity?.title
        ? ` «${body.result.entity.title}»`
        : draft.payload.title
          ? ` «${String(draft.payload.title)}»`
          : ''
      setActiveDraft(null)
      updateMessage(messageId, {
        draft: null,
        editing: false,
        text: `${label}${title}.`,
      })
      pushMessage({
        role: 'assistant',
        text: 'Можете дать следующую команду.',
      })
    } catch (err) {
      pushMessage({
        role: 'system',
        kind: 'error',
        text: err instanceof Error ? err.message : 'Ошибка подтверждения',
      })
    } finally {
      setPhase('idle')
    }
  }

  const cancel = async (draft: AiDraftCard, messageId: string) => {
    if (busy) return
    setPhase('confirming')
    try {
      await fetch(`${apiBase}/ai/drafts/${draft.draftId}/cancel`, {
        method: 'POST',
        credentials: 'include',
      })
      setActiveDraft(null)
      updateMessage(messageId, {
        draft: null,
        editing: false,
        text: 'Отменено. Объект не изменён.',
      })
    } catch (err) {
      pushMessage({
        role: 'system',
        kind: 'error',
        text: err instanceof Error ? err.message : 'Не удалось отменить',
      })
    } finally {
      setPhase('idle')
    }
  }

  const stopRecording = () => {
    if (recordTimerRef.current) {
      window.clearInterval(recordTimerRef.current)
      recordTimerRef.current = undefined
    }
    if (stopTimeoutRef.current) {
      window.clearTimeout(stopTimeoutRef.current)
      stopTimeoutRef.current = undefined
    }
    if (mediaRef.current && mediaRef.current.state === 'recording') {
      mediaRef.current.stop()
    }
  }

  const toggleVoice = async () => {
    if (phase === 'recording') {
      stopRecording()
      return
    }
    if (busy) return

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        void uploadAudio(blob)
      }
      mediaRef.current = recorder
      recorder.start()
      setPhase('recording')
      setRecordSeconds(0)
      pushMessage({
        role: 'system',
        kind: 'status',
        text: 'Запись… нажмите микрофон ещё раз, чтобы отправить (макс. 20 с).',
      })
      recordTimerRef.current = window.setInterval(() => {
        setRecordSeconds((value) => value + 1)
      }, 1000)
      stopTimeoutRef.current = window.setTimeout(() => {
        stopRecording()
      }, 20_000)
    } catch {
      pushMessage({
        role: 'system',
        kind: 'error',
        text: 'Нет доступа к микрофону. Разрешите доступ в браузере и попробуйте снова.',
      })
      setPhase('idle')
    }
  }

  const uploadAudio = async (blob: Blob) => {
    if (blob.size === 0) {
      setPhase('idle')
      pushMessage({
        role: 'system',
        kind: 'error',
        text: 'Пустая запись. Попробуйте ещё раз.',
      })
      return
    }

    setPhase('transcribing')
    const pendingId = pushMessage({
      role: 'assistant',
      text: 'Распознаю голос…',
      pending: true,
      kind: 'status',
    })

    try {
      const form = new FormData()
      form.append('audio', blob, 'voice.webm')
      const response = await fetch(`${apiBase}/ai/transcribe`, {
        method: 'POST',
        credentials: 'include',
        body: form,
      })
      const body = await response.json()
      if (!response.ok) {
        throw new Error(body.error?.message ?? 'Распознавание недоступно')
      }
      const text = typeof body.text === 'string' ? body.text.trim() : ''
      if (!text) {
        throw new Error('Не удалось распознать речь')
      }
      updateMessage(pendingId, {
        pending: false,
        kind: 'status',
        text: `Распознано: «${text}»`,
      })
      setPhase('idle')
      await send(text)
    } catch (err) {
      updateMessage(pendingId, {
        pending: false,
        kind: 'error',
        text: err instanceof Error ? err.message : 'Ошибка голоса',
      })
      setPhase('idle')
    }
  }

  const phaseLabel =
    phase === 'recording'
      ? `Запись ${recordSeconds}с / 20с`
      : phase === 'transcribing'
        ? 'Распознавание…'
        : phase === 'sending'
          ? 'Отправка…'
          : phase === 'confirming'
            ? 'Сохранение…'
            : null

  return (
    <section className="chat-shell" aria-label="Ассистент">
      <header className="chat-topbar">
        <div>
          <h1>Ассистент</h1>
          <p>Календарь · задачи · планы · списки</p>
        </div>
        <div className="chat-topbar-actions">
          {phaseLabel && (
            <div className={`chat-phase${phase === 'recording' ? ' is-recording' : ''}`} role="status" aria-live="polite">
              <span className="chat-phase-dot" aria-hidden="true" />
              {phaseLabel}
            </div>
          )}
          {onClose && (
            <button type="button" className="btn btn-ghost chat-close" onClick={onClose} aria-label="Закрыть ассистента">
              Закрыть
            </button>
          )}
        </div>
      </header>

      <div className="chat-thread" ref={listRef} role="log" aria-live="polite">
        {messages.map((message) => (
          <div
            key={message.id}
            className={[
              'chat-row',
              `chat-row-${message.role}`,
              message.kind === 'error' ? 'is-error' : '',
              message.pending ? 'is-pending' : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            {message.role !== 'user' && (
              <div className="chat-avatar" aria-hidden="true">
                {message.kind === 'error' ? '!' : 'A'}
              </div>
            )}
            <div className="chat-bubble">
              <p>{message.text}</p>
              {message.draft && (
                <div className="chat-draft">
                  <div className="chat-draft-meta">
                    <span>{OPERATION_LABELS[message.draft.operation] ?? message.draft.operation}</span>
                    <span>{message.draft.entityType ?? '—'}</span>
                    <span>{DRAFT_STATUS_LABELS[message.draft.status] ?? message.draft.status}</span>
                  </div>
                  {!message.editing && (
                    <>
                      <strong>{String(message.draft.payload.title ?? 'Без названия')}</strong>
                      {formatWhen(message.draft.payload) && (
                        <p className="chat-draft-hint">{formatWhen(message.draft.payload)}</p>
                      )}
                      {message.draft.entityType === 'event' && (
                        <p className="chat-draft-hint chat-draft-recurrence">
                          {formatRecurrence(message.draft.payload)}
                        </p>
                      )}
                    </>
                  )}
                  {!!message.draft.missingFields?.length && !message.editing && (
                    <p className="chat-draft-hint">Не хватает: {message.draft.missingFields.join(', ')}</p>
                  )}

                  {message.editing ? (
                    <DraftEditor
                      key={`${message.draft.draftId}-${message.draft.status}-${String(message.draft.payload.title ?? '')}-${JSON.stringify(message.draft.payload.recurrence ?? null)}`}
                      draft={message.draft}
                      busy={busy}
                      onSave={(form) => void saveDraftEdits(message.draft!, message.id, form)}
                      onCancelEdit={() => updateMessage(message.id, { editing: false })}
                    />
                  ) : (
                    <div className="chat-draft-actions">
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={busy || message.draft.status !== 'ready'}
                        onClick={() => void confirm(message.draft!, message.id)}
                      >
                        {message.draft.operation === 'DELETE'
                          ? 'Удалить'
                          : message.draft.operation === 'UPDATE'
                            ? 'Подтвердить'
                            : 'Создать'}
                      </button>
                      <button
                        type="button"
                        className="btn"
                        disabled={busy}
                        onClick={() => updateMessage(message.id, { editing: true })}
                      >
                        Изменить форму
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        disabled={busy}
                        onClick={() => void cancel(message.draft!, message.id)}
                      >
                        Отмена
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <form
        className="chat-composer"
        onSubmit={(event) => {
          event.preventDefault()
          void send(input)
        }}
      >
        <textarea
          ref={inputRef}
          value={input}
          rows={1}
          placeholder="Уточните текстом или голосом — либо «Изменить форму»"
          disabled={busy || phase === 'recording'}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              void send(input)
            }
          }}
        />
        <div className="chat-composer-bar">
          <button
            type="button"
            className={`chat-mic${phase === 'recording' ? ' is-on' : ''}`}
            onClick={() => void toggleVoice()}
            disabled={phase === 'transcribing' || phase === 'sending' || phase === 'confirming'}
            aria-pressed={phase === 'recording'}
            aria-label={phase === 'recording' ? 'Остановить запись' : 'Записать голос'}
            title={phase === 'recording' ? 'Стоп' : 'Голос до 20 секунд'}
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <rect x="9" y="3" width="6" height="11" rx="3" />
              <path d="M5 11a7 7 0 0 0 14 0" />
              <path d="M12 18v3" />
            </svg>
          </button>
          <button
            type="submit"
            className="btn btn-primary chat-send"
            disabled={busy || phase === 'recording' || input.trim().length === 0}
          >
            {phase === 'sending' ? 'Отправка…' : 'Отправить'}
          </button>
        </div>
      </form>
    </section>
  )
}

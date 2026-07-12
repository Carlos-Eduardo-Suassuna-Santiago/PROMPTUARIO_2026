import { test, expect, type APIRequestContext } from '@playwright/test'

type ClinicalContext = {
  patientId: string
  recordId?: string
}

async function fetchSeededClinicalContext(request: APIRequestContext, apiBaseUrl: string): Promise<ClinicalContext> {
  const loginResp = await request.post(`${apiBaseUrl}/auth/login`, {
    data: { email: 'admin@promptuario.health', password: 'Admin@12345' },
  })
  expect(loginResp.ok()).toBeTruthy()

  const loginData = await loginResp.json()
  const token = loginData.access_token as string
  expect(token).toBeTruthy()

  const authHeaders = {
    Authorization: `Bearer ${token}`,
  }

  const apptResp = await request.get(`${apiBaseUrl}/appointments?page=1&size=25`, {
    headers: authHeaders,
  })
  expect(apptResp.ok()).toBeTruthy()

  const apptData = await apptResp.json()
  const appointments = (apptData.items ?? []) as Array<{ patient_id: string }>
  expect(appointments.length).toBeGreaterThan(0)

  const fallbackPatientId = appointments[0].patient_id
  for (const appt of appointments) {
    const recordsResp = await request.get(`${apiBaseUrl}/records/patient/${appt.patient_id}?page=1&size=10`, {
      headers: authHeaders,
    })

    if (!recordsResp.ok()) continue

    const recordsData = await recordsResp.json()
    const records = (recordsData.items ?? []) as Array<{ id: string }>
    if (records.length > 0) {
      return { patientId: appt.patient_id, recordId: records[0].id }
    }
  }

  return { patientId: fallbackPatientId }
}

test('deve solicitar análise de IA na tela /ai usando dados existentes', async ({ page, request, baseURL }) => {
  const apiBaseUrl = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000/api/v1'
  const context = await fetchSeededClinicalContext(request, apiBaseUrl)

  await page.goto('/login')

  await page.getByLabel('Email').fill('admin@promptuario.health')
  await page.getByLabel('Senha').fill('Admin@12345')
  await page.getByRole('button', { name: 'Entrar' }).click()

  await page.waitForURL('**/dashboard')

  await page.goto('/ai')
  await expect(page.getByRole('heading', { name: 'Análise de IA' })).toBeVisible()

  await page.getByLabel('ID do paciente *').fill(context.patientId)

  if (context.recordId) {
    await page.getByLabel('ID do prontuário (opcional)').fill(context.recordId)
  }

  await page
    .getByLabel('Contexto adicional (JSON opcional)')
    .fill('{"symptoms":["cefaleia","náusea"],"duration_days":2}')

  await page.getByRole('button', { name: 'Solicitar análise' }).click()

  await expect(page.getByRole('heading', { name: 'Job ativo' })).toBeVisible()
  await expect(
    page.getByText(/PENDING|RUNNING|COMPLETED|FAILED/, { exact: false }).first()
  ).toBeVisible()

  if (context.recordId) {
    await page.getByLabel('ID do prontuário').fill(context.recordId)
    await page.getByRole('button', { name: 'Carregar análises' }).click()
    await expect(page.getByRole('heading', { name: 'Histórico de análises do prontuário' })).toBeVisible()
  }
})

import { expect, test, type Page } from '@playwright/test'

const PASSWORD = 'Demo@12345'

async function signIn(page: Page, email: string) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL((url) => !url.pathname.startsWith('/login'))
}

async function signOut(page: Page) {
  await page.getByRole('button', { name: 'Sign out' }).click()
  await page.waitForURL('**/login')
}

test('happy path: upload, explainable findings, review, dashboard update', async ({ page }) => {
  await signIn(page, 'aranya.operator@demo.example')
  await page.goto('/uploads')

  const sample = await page.request.get('/api/v1/demo/sample-upload.csv')
  expect(sample.ok()).toBeTruthy()
  await page.locator('input[type=file]').setInputFiles({
    name: 'aranya-admissions.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(await sample.body()),
  })
  await page.getByRole('button', { name: 'Upload and validate' }).click()

  await expect(page.getByText('Partially accepted').first()).toBeVisible()
  await expect(page.getByText('Findings raised by this upload')).toBeVisible()
  await page.getByRole('tab', { name: /Rejected/ }).click()
  await expect(page.getByText('IDENTIFIER_MISSING')).toBeVisible()
  await expect(page.getByText('IDENTIFIER_FORMAT_INVALID')).toBeVisible()

  await page.goto('/dashboard')
  await expect(page.getByText('Over intake', { exact: true })).toBeVisible()
  await signOut(page)

  await signIn(page, 'aranya.admin@demo.example')
  await page.goto('/exceptions?rule_code=CATEGORY_CONFLICT')
  await page.getByRole('link', { name: 'Conflicting NRI / OCI / FN / nationality fields' }).click()
  await expect(page.getByText('Marked as both NRI and Foreign National').first()).toBeVisible()
  await expect(page.getByText('Policy assumption (configurable)')).toBeVisible()

  const resolve = page.getByRole('button', { name: 'Resolve' })
  await expect(resolve).toBeDisabled()
  await page.getByLabel('Reviewer comment').fill('Checked documents: FN flag entered by mistake.')
  await resolve.click()
  await expect(page.getByText('Resolved').first()).toBeVisible()

  await page.goto('/audit')
  await expect(page.getByText('finding.resolve')).toBeVisible()
  await signOut(page)

  await signIn(page, 'verifier@demo.example')
  await expect(page).toHaveURL(/\/verification/)
  await page.getByLabel('APAAR ID').fill('DEMO-APAAR-210001')
  await page.getByLabel('Purpose of verification').fill('Pre-employment background check')
  await page.getByRole('button', { name: 'Verify' }).click()
  await expect(page.getByText('Records found · consent on record')).toBeVisible()
  await expect(page.getByText('SIMULATED — NOT OFFICIAL APAAR VERIFICATION').first()).toBeVisible()
})

test('failure path: malformed file and cross-institution access are refused safely', async ({ page }) => {
  await signIn(page, 'aranya.operator@demo.example')
  await page.goto('/uploads')
  await page.locator('input[type=file]').setInputFiles({
    name: 'wrong.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('name,age\nA,1\n'),
  })
  await page.getByRole('button', { name: 'Upload and validate' }).click()
  await expect(page.getByText('The file was rejected')).toBeVisible()
  await expect(page.getByText('Missing required columns')).toBeVisible()

  // A Kaveri student is invisible to an Aranya user, even by direct API request.
  const kaveri = await page.request.post('/api/v1/students/lookup', {
    data: { apaar_id: 'DEMO-APAAR-210001' },
    headers: { 'X-CSRF-Token': await csrf(page) },
  })
  expect(await kaveri.json()).toEqual([])
  const central = await page.request.get('/api/v1/dashboard/central')
  expect(central.status()).toBe(403)
})

async function csrf(page: Page): Promise<string> {
  const me = await page.request.get('/api/v1/auth/me')
  return (await me.json()).csrf_token
}

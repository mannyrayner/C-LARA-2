// Run only through browser_rehearsal.py's disposable local database.
const { chromium, devices } = require(process.env.COMMUNITY_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.COMMUNITY_CHROMIUM_PATH || undefined,
    args: ['--no-sandbox'],
  });
  try {
    const context = await browser.newContext({ ...devices['Pixel 7'] });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    const base = 'http://127.0.0.1:8765';
    const resetPassword = 'Orchard-and-river-37!';
    const ownPassword = 'Lantern-at-harbour-68!';
    const clickAndWait = async (locator, url) => {
      await Promise.all([page.waitForURL(url), locator.click()]);
    };
    const login = async (username, password) => {
      await page.goto(base + '/accounts/login/');
      await page.locator('#id_username').fill(username);
      await page.locator('#id_password').fill(password);
      await clickAndWait(page.getByRole('button', { name: 'Login', exact: true }), base + '/');
    };

    // Registration follows the application's existing bootstrap-admin rule.
    await page.goto(base + '/accounts/register/');
    await page.locator('#id_username').fill('admin');
    await page.locator('#id_email').fill('browser-admin@example.invalid');
    await page.locator('#id_password1').fill('Local-admin-testing-91!');
    await page.locator('#id_password2').fill('Local-admin-testing-91!');
    await clickAndWait(page.getByRole('button', { name: 'Register', exact: true }), base + '/accounts/login/');
    await login('admin', 'Local-admin-testing-91!');
    await page.getByRole('link', { name: 'Admin', exact: true }).click();
    await page.getByRole('link', { name: "Reset a user's password", exact: true }).click();
    await page.locator('#id_user').selectOption({ label: 'browser_owner' });
    await page.getByRole('button', { name: 'Continue', exact: true }).click();
    await page.getByRole('heading', { name: 'Reset password for browser_owner' }).waitFor();
    await page.screenshot({ path: path.join(process.env.COMMUNITY_BROWSER_OUTPUT, 'password-admin-mobile.png'), fullPage: true });
    await page.locator('#id_new_password1').fill(resetPassword);
    await page.locator('#id_new_password2').fill(resetPassword);
    await clickAndWait(page.getByRole('button', { name: 'Reset password', exact: true }), base + '/admin-tools/passwords/');
    assert.match(await page.locator('.messages').innerText(), /Password reset for browser_owner/);
    await page.getByRole('button', { name: 'Logout', exact: true }).click();
    await login('browser_owner', resetPassword);
    await page.goto(base + '/community-dictionaries/');
    await page.getByRole('link', { name: 'browser_owner', exact: true }).click();
    await page.getByRole('link', { name: 'Change my password', exact: true }).click();
    await page.getByRole('heading', { name: 'Change my password' }).waitFor();
    await page.screenshot({ path: path.join(process.env.COMMUNITY_BROWSER_OUTPUT, 'password-change-mobile.png'), fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    await page.locator('#id_old_password').fill(resetPassword);
    await page.locator('#id_new_password1').fill(ownPassword);
    await page.locator('#id_new_password2').fill(ownPassword);
    await clickAndWait(page.getByRole('button', { name: 'Change password', exact: true }), base + '/accounts/profile/');
    assert.match(await page.locator('.messages').innerText(), /Your password has been changed/);
    await page.getByRole('button', { name: 'Logout', exact: true }).click();
    await login('browser_owner', ownPassword);
    console.log('PASS: admin recovery, new-password login, dictionary → Profile → own password change, subsequent login; Chromium Pixel 7 viewport.');
    await context.close();
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

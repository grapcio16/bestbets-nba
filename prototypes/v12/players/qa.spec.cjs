// Run from this directory: npx playwright test qa.spec.cjs
// Requires @playwright/test and Chromium installed in the local QA environment.
// Isolated static prototype; no production network or account access.
const {test,expect}=require('@playwright/test');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
for(const [width,height] of [[1231,691],[1672,941],[390,844],[430,932]]){
 test('Players prototype '+width+'x'+height,async({page})=>{
  await page.setViewportSize({width,height});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(__dirname,'index.html')).href);
  await expect(page.locator('#profile h2')).toHaveText('Demo A');
  await expect(page.locator('.metric strong').first()).toHaveText('25.0');
  await expect(page.locator('.player')).toHaveCount(3);
  await page.screenshot({path:test.info().outputPath('initial.png'),fullPage:true});
  const search=page.locator('#search');
  await search.fill(' BET ');
  await expect(page.locator('.player')).toHaveCount(1);
  await search.press('Tab');
  await expect(page.locator('.player')).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#profile h2')).toHaveText('Demo B');
  await expect(page.locator('.metric strong').first()).toHaveText('20.0');
  await expect(page.locator('.player')).toHaveAttribute('aria-pressed','true');
  await search.fill('no-match');
  await expect(page.locator('#list')).toHaveText('Brak wyników wyszukiwania.');
  await search.fill('');
  await expect(page.locator('.player')).toHaveCount(3);
  await expect(page.locator('.player[aria-pressed=true]')).toContainText('Demo B');
  await page.locator('.footer').scrollIntoViewIfNeeded();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await expect(page.locator('.footer')).toBeInViewport();
  expect(errors).toEqual([]);
  await page.screenshot({path:test.info().outputPath('selected.png'),fullPage:true});
 });
}

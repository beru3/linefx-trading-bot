import asyncio
import csv
import os
from playwright.async_api import async_playwright

class TestBot:
    def __init__(self):
        self.page = None
        self.browser = None

    async def setup_browser(self):
        p = await async_playwright().start()
        self.browser = await p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
        context = await self.browser.new_context()
        self.page = await context.new_page()
        await self.page.set_viewport_size({'width': 1920, 'height': 1080})
        await self.page.goto('https://trade.line-sec.co.jp/')
        print('[INFO] ブラウザ起動完了')

    async def select_currency_pair(self, currency_pair):
        print(f'[INFO] 通貨ペア選択開始: {currency_pair}')
        
        dropdown_selectors = [
            'button.button-dropdown-frame.button-dropdown-frame2',
            'button[class*="dropdown"]',
            '.dropdown-button',
        ]
        
        selected_selector = None
        for selector in dropdown_selectors:
            try:
                dropdown = self.page.locator(selector)
                if await dropdown.count() > 0:
                    print(f'[INFO] ドロップダウンボタン見つかりました: {selector}')
                    await dropdown.click()
                    selected_selector = selector
                    await asyncio.sleep(1)
                    break
            except Exception as e:
                print(f'[DEBUG] セレクタ {selector} 失敗: {e}')
                continue
                
        if not selected_selector:
            print('[ERROR] ドロップダウンボタンが見つかりません')
            return False
            
        currency_selectors = [
            f'td.table-cell-left.text-jp >> text="{currency_pair}"',
            f'td.table-cell-left.text-jp:has-text(" {currency_pair} ")',
            f'td.table-cell-left.text-jp:has-text("{currency_pair}")',
            f'tbody td.table-cell-left.text-jp:has-text("{currency_pair}")',
            f'tr td:has-text("{currency_pair}")',
        ]
        
        await asyncio.sleep(1)
        try:
            available_pairs = await self.page.locator('td.table-cell-left.text-jp').all_text_contents()
            print(f'[INFO] 利用可能な通貨ペア: {available_pairs}')
        except Exception as e:
            print(f'[DEBUG] 通貨ペア取得エラー: {e}')
        
        for selector in currency_selectors:
            try:
                pair_element = self.page.locator(selector)
                if await pair_element.count() > 0:
                    print(f'[INFO] 通貨ペア選択: {selector}')
                    await pair_element.click()
                    await asyncio.sleep(1)
                    print(f'[INFO] 通貨ペア {currency_pair} 選択完了')
                    return True
            except Exception as e:
                print(f'[DEBUG] 通貨ペアセレクタ {selector} 失敗: {e}')
                continue
        
        print(f'[ERROR] 通貨ペア {currency_pair} が見つかりません')
        return False

    async def close_browser(self):
        if self.browser:
            await self.browser.close()

async def test_currency_selection():
    bot = TestBot()
    try:
        await bot.setup_browser()
        await asyncio.sleep(3)  # 3秒待機
        result = await bot.select_currency_pair('EUR/JPY')
        print(f'[RESULT] EUR/JPY選択結果: {result}')
    except Exception as e:
        print(f'[ERROR] テスト実行中エラー: {e}')
    finally:
        await bot.close_browser()

if __name__ == '__main__':
    asyncio.run(test_currency_selection())
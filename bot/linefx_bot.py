import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict

from playwright.async_api import async_playwright, Browser, Page
from data_reader import DataReaderFactory, TradeScheduleManager


class LineFXBot:
    """LINE FX自動取引ボット - Python版"""
    
    def __init__(self, config_path: str = None):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.settings = None
        self.base_path = Path(__file__).parent.parent
        self.config_path = config_path or self.base_path / "config" / "settings.json"
        
        # データリーダー関連
        self.data_reader = None
        self.schedule_manager = None
        self.running = False
        
        # 実行状況管理（メモリ内）
        self.executed_trades = set()  # 実行済みトレードID
        self.closed_trades = set()    # 決済済みトレードID
        self.prepared_trades = {}     # 事前準備済みトレード
        self.prepared_closings = {}   # 決済事前準備済みトレード
        
        self.setup_logging()
        
    def setup_logging(self):
        """ログ設定を初期化"""
        log_dir = self.base_path / "logs"
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"bot_{datetime.now().strftime('%Y-%m-%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    async def load_settings(self):
        """設定ファイルを読み込み"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
            self.logger.info("設定ファイルを正常に読み込みました")
            
            # trading_settings.jsonも読み込み
            from data_reader import load_trading_settings
            config_dir = os.path.dirname(self.config_path)
            self.trading_config = load_trading_settings(config_dir)
            
            # データリーダーを初期化
            self.data_reader = DataReaderFactory.create_reader(self.settings, self.trading_config)
            self.schedule_manager = TradeScheduleManager(self.data_reader)
            
        except Exception as e:
            self.logger.error(f"設定ファイルの読み込みに失敗: {e}")
            raise
            
    async def take_screenshot(self, name: str):
        """スクリーンショットを撮影"""
        if not self.settings["bot_settings"]["screenshot_enabled"] or not self.page:
            return
            
        try:
            screenshot_dir = self.base_path / self.settings["paths"]["screenshots"]
            screenshot_dir.mkdir(exist_ok=True)
            
            timestamp = int(time.time() * 1000)
            screenshot_path = screenshot_dir / f"{name}_{timestamp}.png"
            
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            self.logger.info(f"スクリーンショット保存: {screenshot_path}")
        except Exception as e:
            self.logger.error(f"スクリーンショット撮影失敗: {e}")
            
    async def random_wait(self, base_time: int = None):
        """ランダム待機時間"""
        wait_settings = self.settings["bot_settings"]["wait_time"]
        
        if base_time is None:
            base = random.randint(wait_settings["min"], wait_settings["max"])
        else:
            base = base_time
            
        variance = base * wait_settings["random_variance"]
        final_wait = base + random.uniform(-variance, variance)
        final_wait = max(100, final_wait) / 1000  # ミリ秒を秒に変換
        
        self.logger.debug(f"待機時間: {final_wait:.2f}秒")
        await asyncio.sleep(final_wait)
        
    async def type_with_delay(self, element, text: str):
        """遅延付きタイピング"""
        typing_settings = self.settings["bot_settings"]["typing_delay"]
        
        for char in text:
            await element.type(char)
            delay = random.randint(typing_settings["min"], typing_settings["max"]) / 1000
            await asyncio.sleep(delay)
            
    async def find_element(self, selectors: List[str], timeout: int = 5000):
        """複数セレクターでの要素検索"""
        for selector in selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=timeout)
                if element:
                    self.logger.debug(f"要素発見 - セレクター: {selector}")
                    return element
            except Exception:
                self.logger.debug(f"セレクター失敗: {selector}")
                continue
                
        raise Exception(f"要素が見つかりません - セレクター: {selectors}")
        
    async def init_browser(self):
        """ブラウザを初期化"""
        try:
            self.logger.info("ブラウザを初期化中...")
            
            playwright = await async_playwright().start()
            
            self.browser = await playwright.chromium.launch(
                headless=self.settings["bot_settings"]["headless"],
                args=self.settings["browser_settings"]["extra_args"]
            )
            
            # ブラウザコンテキスト作成
            context = await self.browser.new_context(
                viewport=self.settings["browser_settings"]["viewport"],
                user_agent=self.settings["browser_settings"]["user_agent"]
            )
            
            # 自動化検出を回避するJavaScriptを実行
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                window.chrome = {
                    runtime: {},
                };
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ja-JP', 'ja'],
                });
            """)
            
            self.page = await context.new_page()
            self.page.set_default_timeout(self.settings["bot_settings"]["timeout"])
            
            self.logger.info("ブラウザ初期化完了")
            
        except Exception as e:
            self.logger.error(f"ブラウザ初期化失敗: {e}")
            raise
            
    async def login(self):
        """ログイン処理"""
        try:
            self.logger.info("ログイン処理開始...")
            
            # ログインページにアクセス
            await self.page.goto(self.settings["login"]["url"])
            await self.random_wait(2000)
            await self.take_screenshot("01_login_page")
            
            # ユーザーID入力
            self.logger.info("ユーザーID入力中...")
            user_id_element = await self.find_element(self.settings["selectors"]["userId"])
            await user_id_element.focus()
            await self.random_wait(500)
            
            # 既存のテキストを選択して削除
            await self.page.keyboard.press("Control+a")
            await self.random_wait(300)
            await self.type_with_delay(user_id_element, self.settings["login"]["userId"])
            
            await self.random_wait(1000)
            await self.take_screenshot("02_userid_filled")
            
            # パスワード入力
            self.logger.info("パスワード入力中...")
            password_element = await self.find_element(self.settings["selectors"]["password"])
            await password_element.focus()
            await self.random_wait(500)
            
            await self.page.keyboard.press("Control+a")
            await self.random_wait(300)
            await self.type_with_delay(password_element, self.settings["login"]["password"])
            
            await self.random_wait(1000)
            await self.take_screenshot("03_password_filled")
            
            # ユーザーID保存チェックボックス処理
            if not self.settings["login"]["saveUserId"]:
                try:
                    self.logger.info("ユーザーID保存チェックボックスの処理中...")
                    checkbox_element = await self.find_element(
                        self.settings["selectors"]["saveUserIdCheckbox"], 2000
                    )
                    is_checked = await checkbox_element.is_checked()
                    if is_checked:
                        await checkbox_element.uncheck()
                        await self.random_wait(500)
                except Exception as e:
                    self.logger.warning(f"チェックボックス処理失敗: {e}")
                    
            # ログインボタンクリック
            self.logger.info("ログインボタンをクリック中...")
            login_button = await self.find_element(self.settings["selectors"]["loginButton"])
            await self.random_wait(1000)
            await login_button.click()
            
            await self.random_wait(3000)
            await self.take_screenshot("04_after_login_click")
            
            # ナビゲーション待機
            self.logger.info("ページ遷移を待機中...")
            await self.page.wait_for_load_state("networkidle", timeout=30000)
            await self.random_wait(2000)
            await self.take_screenshot("05_post_login")
            
            # ログイン成功確認
            current_url = self.page.url
            self.logger.info(f"ログイン後URL: {current_url}")
            
            if "signin" in current_url:
                await self.take_screenshot("06_login_failed")
                raise Exception("ログイン失敗 - サインインページに留まっています")
                
            self.logger.info("ログイン完了!")
            return True
            
        except Exception as e:
            self.logger.error(f"ログイン失敗: {e}")
            await self.take_screenshot("error_login_failed")
            raise
            
    async def analyze_trading_page(self):
        """取引ページの構造を解析"""
        try:
            self.logger.info("取引ページ構造を解析中...")
            
            # ページが完全に読み込まれるまで待機
            await self.random_wait(3000)
            await self.take_screenshot("06_trading_page_analysis")
            
            # HTML構造を保存
            if self.trading_config.get("save_html_structure", False):
                html_content = await self.page.content()
                html_dir = self.base_path / "debug"
                html_file = html_dir / f"trading_page_{int(time.time())}.html"
                
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                self.logger.info(f"HTML構造保存: {html_file}")
            
            # 取引要素の存在確認
            trading_elements = {}
            for element_name, selectors in self.settings["selectors"]["trading"].items():
                try:
                    element = await self.find_element(selectors, timeout=2000)
                    if element:
                        trading_elements[element_name] = True
                        self.logger.info(f"取引要素発見: {element_name}")
                except:
                    trading_elements[element_name] = False
                    self.logger.warning(f"取引要素未発見: {element_name}")
            
            # ページ情報をログ出力
            current_url = self.page.url
            page_title = await self.page.title()
            self.logger.info(f"取引ページURL: {current_url}")
            self.logger.info(f"ページタイトル: {page_title}")
            self.logger.info(f"発見された取引要素: {trading_elements}")
            
            return trading_elements
            
        except Exception as e:
            self.logger.error(f"取引ページ解析失敗: {e}")
            await self.take_screenshot("error_trading_analysis")
            raise
            
    async def navigate_to_new_order(self):
        """新規注文画面に移動"""
        try:
            self.logger.info("新規注文画面に移動中...")
            
            # テキスト内容で新規注文メニューを検索
            menu_links = await self.page.query_selector_all("a")
            new_order_link = None
            
            for link in menu_links:
                try:
                    text = await link.inner_text()
                    if "新規注文" in text:
                        new_order_link = link
                        break
                except:
                    continue
                    
            if not new_order_link:
                raise Exception("新規注文メニューが見つかりません")
                
            await self.random_wait(1000)
            await new_order_link.click()
            await self.take_screenshot("07_new_order_menu_clicked")
            
            # ページが読み込まれるまで待機
            await self.random_wait(3000)
            await self.take_screenshot("08_new_order_page")
            
            return True
            
        except Exception as e:
            self.logger.error(f"新規注文画面への移動失敗: {e}")
            await self.take_screenshot("error_new_order_navigation")
            raise
            
    async def select_currency_pair(self, currency_pair: str):
        """新規注文パネルで通貨ペアを選択（改良版）"""
        try:
            self.logger.info(f"通貨ペア選択: {currency_pair}")
            
            # 正しい注文パネルの通貨プルダウンを開く
            dropdown_selectors = [
                'button.button-dropdown-frame.button-dropdown-frame2',  # 正しい注文パネル用セレクター
                'button[title*="USD/JPY"] i.svg-icons.icon-dropdown',   # タイトル属性付きボタン内のアイコン
                'symbol-selector button i.svg-icons.icon-dropdown',     # symbol-selector内のアイコン
                'i.svg-icons.icon-dropdown',                            # 汎用（フォールバック）
            ]
            
            dropdown_icon = None
            for selector in dropdown_selectors:
                try:
                    dropdown_icon = await self.page.wait_for_selector(selector, timeout=2000)
                    if dropdown_icon:
                        self.logger.info(f"プルダウンアイコン発見: {selector}")
                        break
                except:
                    continue
                    
            if not dropdown_icon:
                # デバッグ用：現在のページ状態をスクリーンショット
                await self.take_screenshot("dropdown_search_failed")
                raise Exception("正しい通貨プルダウンアイコンが見つかりません")
            
            # どのドロップダウンを開く前かを記録
            await self.take_screenshot("before_dropdown_click")
            await dropdown_icon.click()
            await self.random_wait(1500)  # 待機時間を延長
            await self.take_screenshot("currency_dropdown_opened")
            
            # 正しいプルダウンリストから通貨ペア選択
            currency_selectors = [
                f'td.table-cell-left.text-jp >> text="{currency_pair}"',          # Playwrightの正確なテキストマッチ
                f'td.table-cell-left.text-jp:has-text(" {currency_pair} ")',      # 空白を含む選択
                f'td.table-cell-left.text-jp:has-text("{currency_pair}")',        # 標準選択
                f'tbody td.table-cell-left.text-jp:has-text("{currency_pair}")',  # tbody内のセル
                f'tr td:has-text("{currency_pair}")',                             # tr内の汎用セル
            ]
            
            currency_option = None
            for selector in currency_selectors:
                try:
                    currency_option = await self.page.wait_for_selector(selector, timeout=2000)
                    if currency_option:
                        self.logger.info(f"通貨ペアオプション発見: {selector}")
                        break
                except:
                    continue
                    
            if not currency_option:
                # デバッグ: 利用可能な通貨ペアをすべて表示
                self.logger.info("利用可能な通貨ペアを検索中...")
                all_currency_cells = await self.page.query_selector_all('td.table-cell-left.text-jp')
                available_pairs = []
                for cell in all_currency_cells:
                    try:
                        text = await cell.inner_text()
                        clean_text = text.strip()
                        available_pairs.append(clean_text)
                        if currency_pair in clean_text or clean_text == currency_pair:
                            currency_option = cell
                            self.logger.info(f"通貨ペア発見: '{clean_text}' (検索対象: '{currency_pair}')")
                            break
                    except:
                        continue
                
                if available_pairs:
                    self.logger.info(f"利用可能な通貨ペア: {available_pairs[:10]}...")  # 最初の10個を表示
                
                if not currency_option:
                    # 完全一致での再検索
                    self.logger.info(f"完全一致で再検索: '{currency_pair}'")
                    for cell in all_currency_cells:
                        try:
                            text = await cell.inner_text()
                            if text.strip() == currency_pair:
                                currency_option = cell
                                self.logger.info(f"完全一致で発見: '{text.strip()}'")
                                break
                        except:
                            continue
                        
            if not currency_option:
                raise Exception(f"通貨ペア {currency_pair} のオプションが見つかりません")
                
            await currency_option.click()
            await self.random_wait(1000)
            await self.take_screenshot("currency_selected")
            
            self.logger.info(f"通貨ペア {currency_pair} を選択しました")
            return True
            
        except Exception as e:
            self.logger.error(f"通貨ペア選択失敗: {e}")
            await self.take_screenshot("error_currency_selection")
            raise
            
    async def set_order_quantity(self, quantity: float):
        """注文数量を設定"""
        try:
            self.logger.info(f"数量設定: {quantity}")
            
            # 数量の種類を判定
            if quantity >= 10000:
                # x 10,000 を選択
                quantity_button = await self.page.wait_for_selector(
                    'li[btnradio="10"].label', timeout=5000
                )
                await quantity_button.click()
                target_quantity = quantity // 10000
            else:
                # x 1,000 を選択  
                quantity_button = await self.page.wait_for_selector(
                    'li[btnradio="1"].label', timeout=5000
                )
                await quantity_button.click()
                target_quantity = quantity // 1000
                
            await self.random_wait(500)
            
            # 数量調整（プラスボタンをクリック）
            plus_button = await self.page.wait_for_selector(
                'i.svg-icons.icon-qty-add', timeout=5000
            )
            
            # 現在値を1として、target_quantityまでプラスボタンをクリック
            for _ in range(int(target_quantity) - 1):
                await plus_button.click()
                await self.random_wait(200)
                
            self.logger.info(f"数量を {quantity} に設定しました")
            return True
            
        except Exception as e:
            self.logger.error(f"数量設定失敗: {e}")
            await self.take_screenshot("error_quantity_setting")
            raise
            
    async def execute_order(self, order_type: str):
        """注文を実行（Bid/Ask ボタンをクリック）"""
        try:
            self.logger.info(f"注文実行: {order_type}")
            
            if order_type.lower() in ['sell', 'short', '売り']:
                # Bid（売り）ボタンをクリック
                bid_button = await self.page.wait_for_selector(
                    'button.button-order-bid', timeout=5000
                )
                await bid_button.click()
                await self.take_screenshot("bid_order_executed")
                self.logger.info("Bid（売り）注文を実行しました")
                
            elif order_type.lower() in ['buy', 'long', '買い']:
                # Ask（買い）ボタンをクリック
                ask_button = await self.page.wait_for_selector(
                    'button.button-order-ask', timeout=5000
                )
                await ask_button.click()
                await self.take_screenshot("ask_order_executed")
                self.logger.info("Ask（買い）注文を実行しました")
                
            else:
                raise ValueError(f"無効な注文タイプ: {order_type}")
                
            await self.random_wait(2000)
            return True
            
        except Exception as e:
            self.logger.error(f"注文実行失敗: {e}")
            await self.take_screenshot("error_order_execution")
            raise
            
    async def handle_market_order_agreement(self):
        """成り行き注文の同意ボタンを処理（例外処理付き）"""
        try:
            self.logger.info("成り行き注文同意ボタンを検索中...")
            
            # 同意ボタンのセレクターリスト
            agreement_selectors = [
                'button.button-large.button-confirm:has-text("同意する")',
                'button[class*="button-confirm"]:has-text("同意する")',
                'button:has-text("同意する")',
                '.button-confirm',
                '[class*="confirm"]'
            ]
            
            agreement_button = None
            for selector in agreement_selectors:
                try:
                    agreement_button = await self.page.wait_for_selector(selector, timeout=2000)
                    if agreement_button:
                        # ボタンが表示されているかチェック
                        is_visible = await agreement_button.is_visible()
                        if is_visible:
                            self.logger.info(f"同意ボタン発見: {selector}")
                            break
                        else:
                            agreement_button = None
                except:
                    continue
                    
            if agreement_button:
                await agreement_button.click()
                await self.random_wait(1000)
                await self.take_screenshot("market_order_agreement_clicked")
                self.logger.info("成り行き注文に同意しました")
                return True
            else:
                self.logger.info("成り行き注文同意ボタンが見つかりません（既に同意済みまたは不要）")
                return True
                
        except Exception as e:
            # 例外が発生しても継続する
            self.logger.warning(f"成り行き注文同意処理で例外発生（継続します）: {e}")
            await self.take_screenshot("market_order_agreement_error")
            return True
            
    async def prepare_order(self, currency_pair: str, amount: float):
        """注文の事前準備（通貨ペア選択、数量設定）"""
        try:
            self.logger.info(f"注文事前準備 - 通貨ペア: {currency_pair}, 数量: {amount}")
            
            # 成り行き注文同意処理
            await self.handle_market_order_agreement()
            
            # 通貨ペア選択
            await self.select_currency_pair(currency_pair)
            
            # 数量設定
            await self.set_order_quantity(amount)
            
            self.logger.info(f"注文事前準備完了 - {currency_pair} {amount}")
            return True
            
        except Exception as e:
            self.logger.error(f"注文事前準備失敗: {e}")
            await self.take_screenshot("error_order_preparation")
            raise
    
    async def execute_prepared_order(self, order_type: str):
        """事前準備済みの注文を実行"""
        try:
            self.logger.info(f"準備済み注文実行: {order_type}")
            
            # 注文実行
            await self.execute_order(order_type)
            
            # 最終同意処理
            await self.handle_market_order_agreement()
            
            self.logger.info(f"準備済み注文実行完了: {order_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"準備済み注文実行失敗: {e}")
            await self.take_screenshot("error_prepared_order_execution")
            raise
    
    async def place_order(self, order_type: str, amount: float = None, currency_pair: str = None):
        """注文を出す（完全自動化版）"""
        try:
            if not currency_pair:
                raise ValueError("通貨ペアが指定されていません。安全のため処理を停止します。")
                
            if not amount:
                amount = self.trading_config.get('default_lot_size', 1000)
                
            self.logger.info(f"注文開始 - 通貨ペア: {currency_pair}, タイプ: {order_type}, 数量: {amount}")
            
            # 事前準備と実行を一括で行う（従来の動作）
            await self.prepare_order(currency_pair, amount)
            await self.execute_prepared_order(order_type)
            
            self.logger.info(f"注文完了 - {currency_pair} {order_type} {amount}")
            return True
            
        except Exception as e:
            self.logger.error(f"注文実行失敗: {e}")
            await self.take_screenshot(f"error_{order_type}_order_failed")
            raise
            
    async def close_position_by_currency(self, currency_pair: str):
        """指定通貨ペアのポジションを一括決済"""
        try:
            self.logger.info(f"一括決済実行 - 通貨ペア: {currency_pair}")
            
            # 建玉決済ボタンを検索
            settle_button_selector = f'button.button-order-settle:has-text("{currency_pair}")'
            
            try:
                settle_button = await self.page.wait_for_selector(
                    settle_button_selector, timeout=5000
                )
                
                if settle_button:
                    await settle_button.click()
                    await self.take_screenshot(f"close_position_{currency_pair.replace('/', '_')}")
                    
                    # 決済確認ダイアログが出た場合の処理
                    await self.random_wait(1000)
                    
                    # 確認ボタンを探してクリック
                    confirm_selectors = [
                        'button:has-text("確認")',
                        'button:has-text("実行")',
                        'button:has-text("OK")',
                        '.modal button[type="submit"]',
                        '.dialog button.confirm'
                    ]
                    
                    for selector in confirm_selectors:
                        try:
                            confirm_button = await self.page.wait_for_selector(
                                selector, timeout=2000
                            )
                            if confirm_button:
                                await confirm_button.click()
                                await self.take_screenshot("position_close_confirmed")
                                break
                        except:
                            continue
                    
                    await self.random_wait(2000)
                    self.logger.info(f"{currency_pair} の一括決済を実行しました")
                    return True
                    
                else:
                    self.logger.warning(f"{currency_pair} の決済ボタンが見つかりません。ポジションがない可能性があります。")
                    return False
                    
            except Exception as e:
                self.logger.warning(f"{currency_pair} の決済ボタンが見つかりません: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"一括決済失敗: {e}")
            await self.take_screenshot("error_close_position")
            raise
            
    async def close_all_positions(self):
        """全てのポジションを一括決済"""
        try:
            self.logger.info("全ポジションの一括決済を開始")
            
            # 新しい一括決済ボタンを探す
            bulk_settle_selectors = [
                'button.button-position-collective-settlement.settle-all.only-position',
                'button:has-text("全決済")',
                'button[class*="collective-settlement"]',
                'button[class*="settle-all"]'
            ]
            
            bulk_settle_button = None
            for selector in bulk_settle_selectors:
                try:
                    bulk_settle_button = await self.page.wait_for_selector(selector, timeout=3000)
                    if bulk_settle_button:
                        break
                except:
                    continue
            
            if not bulk_settle_button:
                self.logger.info("一括決済ボタンが見つかりません。ポジションがない可能性があります。")
                return True
                
            # 一括決済ボタンをクリック
            await bulk_settle_button.click()
            await self.random_wait(1000)
            await self.take_screenshot("bulk_settle_clicked")
            
            # 新しい確認ボタンを待つ
            confirm_selectors = [
                'button[class*="button-large button-confirm"]',
                'button:has-text("確定")',
                'button.button-large.button-confirm'
            ]
            
            confirm_button = None
            for selector in confirm_selectors:
                try:
                    confirm_button = await self.page.wait_for_selector(selector, timeout=5000)
                    if confirm_button:
                        break
                except:
                    continue
                    
            if confirm_button:
                await confirm_button.click()
                await self.random_wait(2000)
                await self.take_screenshot("settlement_confirmed")
                self.logger.info("一括決済を実行しました")
                return True
            else:
                self.logger.warning("確定ボタンが見つかりません")
                return False
            
        except Exception as e:
            self.logger.error(f"全ポジション決済失敗: {e}")
            await self.take_screenshot("error_close_all_positions")
            raise
            
    async def close_position(self, currency_pair: str = None):
        """ポジションを決済（完全自動化版）"""
        try:
            if currency_pair:
                # 特定通貨ペアの決済
                self.logger.info(f"指定ポジション決済開始: {currency_pair}")
                result = await self.close_position_by_currency(currency_pair)
            else:
                # 全ポジションの決済
                self.logger.info("全ポジション決済開始")
                result = await self.close_all_positions()
                
            if result:
                self.logger.info("ポジション決済完了")
            else:
                self.logger.warning("決済対象のポジションがありませんでした")
                
            return result
            
        except Exception as e:
            self.logger.error(f"ポジション決済失敗: {e}")
            await self.take_screenshot("error_close_position_failed")
            raise
            
    async def navigate_to_position_summary(self):
        """建玉サマリ画面に移動"""
        try:
            self.logger.info("建玉サマリ画面に移動中...")
            
            # テキスト内容で建玉サマリメニューを検索
            menu_links = await self.page.query_selector_all("a")
            position_link = None
            
            for link in menu_links:
                try:
                    text = await link.inner_text()
                    if "建玉サマリ" in text:
                        position_link = link
                        break
                except:
                    continue
                    
            if not position_link:
                raise Exception("建玉サマリメニューが見つかりません")
                
            await self.random_wait(1000)
            await position_link.click()
            await self.take_screenshot("13_position_summary_clicked")
            
            # ページが読み込まれるまで待機
            await self.random_wait(3000)
            await self.take_screenshot("14_position_summary_page")
            
            return True
            
        except Exception as e:
            self.logger.error(f"建玉サマリ画面への移動失敗: {e}")
            await self.take_screenshot("error_position_summary_navigation")
            raise
            
    async def get_positions(self):
        """現在のポジション情報を取得"""
        try:
            self.logger.info("ポジション情報を取得中...")
            
            # 建玉サマリ画面に移動
            await self.navigate_to_position_summary()
            
            # 証拠金状況から評価損益を取得
            try:
                account_info_elements = await self.page.query_selector_all(".account-info li")
                positions_info = {}
                
                for element in account_info_elements:
                    try:
                        text = await element.inner_text()
                        if "証拠金維持率" in text:
                            positions_info["margin_ratio"] = text
                        elif "資産合計" in text:
                            positions_info["total_assets"] = text
                        elif "評価損益" in text:
                            positions_info["unrealized_pnl"] = text
                    except:
                        continue
                        
                self.logger.info(f"ポジション情報: {positions_info}")
                return positions_info
                
            except Exception as e:
                self.logger.warning(f"詳細ポジション情報取得失敗: {e}")
                return {}
            
        except Exception as e:
            self.logger.error(f"ポジション情報取得失敗: {e}")
            return {}
            
    async def run(self, mode: str = "analysis"):
        """メイン実行"""
        try:
            await self.load_settings()
            await self.init_browser()
            await self.login()
            
            # 取引ページ解析を実行
            trading_elements = await self.analyze_trading_page()
            
            if mode == "analysis":
                self.logger.info("解析モード完了 - 取引ページの構造を解析しました")
            elif mode == "trading":
                self.logger.info("取引モード - 実際の取引機能を利用可能")
                # ここで実際の取引ロジックを実装可能
                
            self.logger.info("BOT実行完了")
            
        except Exception as e:
            self.logger.error(f"BOT実行失敗: {e}")
            raise
        finally:
            if self.browser:
                await self.browser.close()
                self.logger.info("ブラウザを終了しました")
                
    def load_trade_data(self):
        """トレードデータを読み込み"""
        try:
            data_source_type = self.settings.get('data_source', {}).get('type', 'excel')
            self.logger.info(f"トレードデータを読み込み中 (ソース: {data_source_type})")
            
            success = self.schedule_manager.load_data()
            if success:
                summary = self.schedule_manager.get_trade_summary()
                self.logger.info(
                    f"トレードデータ読み込み完了: {summary['total']}件 "
                    f"(実行済み: {summary['executed']}, 決済済み: {summary['closed']}, 待機中: {summary['pending']})"
                )
                
                # 最初の5件を表示
                trades = self.schedule_manager.trades_data[:5]
                for trade in trades:
                    self.logger.info(
                        f"  - {trade['currency_pair']} {trade['side']} {trade['quantity']} "
                        f"エントリー: {trade['entry_time']} 決済: {trade['exit_time']}"
                    )
                if len(self.schedule_manager.trades_data) > 5:
                    self.logger.info(f"  ... 他{len(self.schedule_manager.trades_data) - 5}件")
            else:
                self.logger.warning("トレードデータが見つかりませんでした")
                
        except Exception as e:
            self.logger.error(f"トレードデータ読み込みエラー: {e}")

    async def execute_scheduled_trade(self, trade: Dict) -> bool:
        """スケジュールされたトレードを実行"""
        try:
            self.logger.info(f"スケジュールトレード実行: {trade['id']} - {trade['currency_pair']} {trade['side']} {trade['quantity']}")
            
            # LINE FXの形式に変換
            order_type = trade['side']  # buy/sell
            currency_pair = trade['currency_pair']  # そのまま使用（USD/JPYなど）
            amount = trade['quantity']
            
            await self.place_order(order_type, amount, currency_pair)
            
            # 実行完了をマーク（メモリ管理のため、ここではCSV更新エラーを無視）
            try:
                self.schedule_manager.mark_trade_executed(trade['id'])
            except Exception as e:
                self.logger.warning(f"CSV更新エラー（メモリ管理で代替済み）: {e}")
            
            self.logger.info(f"スケジュールトレード実行完了: {trade['id']}")
            return True
            
        except Exception as e:
            self.logger.error(f"スケジュールトレード実行エラー {trade['id']}: {e}")
            return False

    async def prepare_scheduled_trade(self, trade: Dict) -> bool:
        """スケジュールトレードの事前準備"""
        try:
            trade_id = trade['id']
            self.logger.info(f"スケジュールトレード事前準備: {trade_id} - {trade['currency_pair']} {trade['side']} {trade['quantity']}")
            
            currency_pair = trade['currency_pair']
            amount = trade['quantity']
            
            # 事前準備実行
            await self.prepare_order(currency_pair, amount)
            
            # 準備済みとしてマーク
            self.prepared_trades[trade_id] = {
                'trade': trade,
                'prepared_at': datetime.now()
            }
            
            self.logger.info(f"スケジュールトレード事前準備完了: {trade_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"スケジュールトレード事前準備エラー {trade['id']}: {e}")
            return False

    async def execute_prepared_trade(self, trade: Dict) -> bool:
        """事前準備済みトレードの高速実行"""
        try:
            trade_id = trade['id']
            self.logger.info(f"事前準備済みトレード高速実行: {trade_id}")
            
            if trade_id not in self.prepared_trades:
                self.logger.error(f"トレードが事前準備されていません: {trade_id}")
                return False
            
            # 事前準備済みなので、Bid/Askボタンを直接クリック
            order_type = trade['side'].lower()
            if order_type in ['buy', 'long']:
                button_selector = 'button.button-order-ask'  # 買い注文はAskボタン
                button_name = "Ask(買い)"
            else:
                button_selector = 'button.button-order-bid'  # 売り注文はBidボタン
                button_name = "Bid(売り)"
            
            self.logger.info(f"高速注文実行: {button_name}ボタンをクリック")
            order_button = await self.page.query_selector(button_selector)
            if order_button:
                await order_button.click()
                await self.page.wait_for_timeout(1000)
                
                # 注文確認ダイアログがある場合は確定ボタンをクリック
                confirm_button = await self.page.query_selector('button.button-large.button-confirm')
                if confirm_button:
                    await confirm_button.click()
                    await self.page.wait_for_timeout(500)
                    self.logger.info(f"注文確定完了: {trade_id}")
                
                # 事前準備データをクリア
                if trade_id in self.prepared_trades:
                    del self.prepared_trades[trade_id]
                
                self.logger.info(f"事前準備済みトレード高速実行完了: {trade_id}")
                return True
            else:
                self.logger.error(f"注文ボタンが見つかりません: {button_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"事前準備済みトレード実行エラー {trade['id']}: {e}")
            return False

    async def prepare_closing(self, trade: Dict) -> bool:
        """決済の事前準備"""
        try:
            trade_id = trade['id']
            self.logger.info(f"決済事前準備開始: {trade_id} - {trade['currency_pair']}")
            
            # 決済事前準備として全決済ボタンの存在確認
            bulk_settle_selectors = [
                'button.button-position-collective-settlement.settle-all.only-position',
                'button:has-text("全決済")',
                'button[class*="collective-settlement"]',
                'button[class*="settle-all"]'
            ]
            
            bulk_settle_button = None
            for selector in bulk_settle_selectors:
                try:
                    bulk_settle_button = await self.page.wait_for_selector(selector, timeout=2000)
                    if bulk_settle_button and await bulk_settle_button.is_visible():
                        break
                    else:
                        bulk_settle_button = None
                except:
                    continue
            
            if bulk_settle_button:
                # 決済準備済みとしてマーク
                self.prepared_closings[trade_id] = {
                    'trade': trade,
                    'prepared_at': datetime.now()
                }
                self.logger.info(f"決済事前準備完了: {trade_id}")
                return True
            else:
                self.logger.warning(f"決済ボタンが見つかりません: {trade_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"決済事前準備エラー {trade['id']}: {e}")
            return False
    
    async def execute_prepared_closing(self, trade: Dict) -> bool:
        """事前準備済み決済を実行"""
        try:
            trade_id = trade['id']
            self.logger.info(f"事前準備済み決済実行: {trade_id} - {trade['currency_pair']}")
            
            if trade_id not in self.prepared_closings:
                self.logger.error(f"決済が事前準備されていません: {trade_id}")
                return False
            
            # 事前準備済みの決済を実行
            await self.close_all_positions()
            
            # 準備済みリストから削除
            del self.prepared_closings[trade_id]
            
            self.logger.info(f"事前準備済み決済実行完了: {trade_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"事前準備済み決済実行エラー {trade['id']}: {e}")
            return False

    async def close_scheduled_trade(self, trade: Dict) -> bool:
        """スケジュールされたトレードを決済"""
        try:
            self.logger.info(f"スケジュール決済実行: {trade['id']} - {trade['currency_pair']}")
            
            # 決済処理（新しい一括決済機能を利用）
            currency_pair = trade['currency_pair']
            result = await self.close_position(currency_pair)
            
            if result:
                # 決済完了をマーク（メモリ管理のため、ここではCSV更新エラーを無視）
                try:
                    self.schedule_manager.mark_trade_closed(trade['id'])
                except Exception as e:
                    self.logger.warning(f"CSV更新エラー（メモリ管理で代替済み）: {e}")
                self.logger.info(f"スケジュール決済完了: {trade['id']}")
                return True
            else:
                self.logger.warning(f"決済対象ポジションが見つかりません: {trade['id']}")
                return False
            
        except Exception as e:
            self.logger.error(f"スケジュール決済エラー {trade['id']}: {e}")
            return False

    async def main_trading_loop(self):
        """メイン取引ループ（スケジュールベース）"""
        check_interval = self.trading_config.get('check_interval', 30)
        
        while self.running:
            try:
                current_time = datetime.now()
                self.logger.info(f"--- スケジュールチェック開始: {current_time.strftime('%Y-%m-%d %H:%M:%S')} ---")
                
                if not self.schedule_manager.trades_data:
                    self.logger.info("トレードデータがありません")
                    await asyncio.sleep(check_interval)
                    continue
                
                # エントリー対象のトレードをチェック
                tolerance_seconds = self.trading_config.get('time_tolerance_seconds', 15)
                
                # エントリー事前準備（30秒前から準備開始）
                prep_trades = self.schedule_manager.get_trades_for_time(current_time + timedelta(seconds=30), tolerance_seconds)
                for trade in prep_trades:
                    trade_id = trade['id']
                    if trade_id not in self.prepared_trades and trade_id not in self.executed_trades:
                        self.logger.info(f"エントリー事前準備開始: {trade_id}")
                        success = await self.prepare_scheduled_trade(trade)
                        if success:
                            self.logger.info(f"エントリー事前準備完了: {trade_id}")
                        else:
                            self.logger.error(f"エントリー事前準備失敗: {trade_id}")
                
                # エントリー実行（時刻指定）
                entry_trades = self.schedule_manager.get_trades_for_time(current_time, tolerance_seconds)
                for trade in entry_trades:
                    trade_id = trade['id']
                    
                    # メモリ内で重複チェック
                    if trade_id in self.executed_trades:
                        self.logger.info(f"既に実行済みをスキップ: {trade_id}")
                        continue
                    
                    # 事前準備済みなら高速実行、未準備なら従来方式
                    if trade_id in self.prepared_trades:
                        success = await self.execute_prepared_trade(trade)
                    else:
                        success = await self.execute_scheduled_trade(trade)
                        
                    if success:
                        self.executed_trades.add(trade_id)  # メモリに記録
                        self.logger.info(f"エントリー成功: {trade_id}")
                    else:
                        self.logger.error(f"エントリー失敗: {trade_id}")
                    
                    await self.random_wait(1000)  # 連続実行の間隔
                
                # 決済事前準備（30秒前から準備開始）
                prep_closings = self.schedule_manager.get_trades_to_close(current_time + timedelta(seconds=30), tolerance_seconds)
                for trade in prep_closings:
                    trade_id = trade['id']
                    # 実行済みかつ未決済かつ未準備の場合のみ準備
                    if (trade_id in self.executed_trades and 
                        trade_id not in self.closed_trades and 
                        trade_id not in self.prepared_closings):
                        self.logger.info(f"決済事前準備開始: {trade_id}")
                        success = await self.prepare_closing(trade)
                        if success:
                            self.logger.info(f"決済事前準備完了: {trade_id}")
                        else:
                            self.logger.error(f"決済事前準備失敗: {trade_id}")
                
                # 決済実行（時刻指定）
                close_trades = self.schedule_manager.get_trades_to_close(current_time, tolerance_seconds)
                self.logger.info(f"決済対象チェック: {len(close_trades)}件 (現在時刻: {current_time.strftime('%H:%M:%S')})")
                if len(close_trades) > 0:
                    for t in close_trades:
                        self.logger.info(f"決済候補: {t['id']} - {t['currency_pair']} 決済時刻: {t.get('exit_time', 'なし')}")
                for trade in close_trades:
                    trade_id = trade['id']
                    
                    # メモリ内で重複チェック（実行済みかつ未決済のもの）
                    executed = trade_id in self.executed_trades
                    closed = trade_id in self.closed_trades
                    self.logger.info(f"決済チェック {trade_id}: executed={executed}, closed={closed}")
                    
                    if not executed or closed:
                        self.logger.info(f"決済対象外をスキップ: {trade_id} (executed={executed}, closed={closed})")
                        continue
                    
                    # 事前準備済みなら高速実行、未準備なら従来方式
                    if trade_id in self.prepared_closings:
                        success = await self.execute_prepared_closing(trade)
                    else:
                        success = await self.close_scheduled_trade(trade)
                    if success:
                        self.closed_trades.add(trade_id)  # メモリに記録
                        self.logger.info(f"決済成功: {trade_id}")
                    else:
                        self.logger.error(f"決済失敗: {trade_id}")
                    
                    await self.random_wait(2000)
                
                self.logger.info("--- スケジュールチェック完了 ---")
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                self.logger.error(f"メインループエラー: {e}")
                await asyncio.sleep(60)  # エラー時は1分待機

    async def start_scheduled_trading(self):
        """スケジュールベースの自動取引を開始"""
        try:
            self.logger.info("スケジュールベース取引開始")
            
            # 設定とデータを読み込み
            await self.load_settings()
            self.load_trade_data()
            
            if not self.schedule_manager.trades_data:
                self.logger.error("実行可能なトレードデータがありません")
                return False
            
            # ブラウザ初期化とログイン
            await self.init_browser()
            await self.login()
            
            self.running = True
            
            # メイン取引ループを実行
            await self.main_trading_loop()
            
            return True
            
        except Exception as e:
            self.logger.error(f"スケジュール取引開始エラー: {e}")
            return False

    async def stop_scheduled_trading(self):
        """スケジュールベースの自動取引を停止"""
        self.running = False
        self.logger.info("スケジュールベース取引停止")

    async def run_trading_session(self, orders: list = None):
        """取引セッションを実行（手動またはスケジュール）"""
        try:
            if orders:
                # 手動モード：従来の処理
                self.logger.info("手動取引セッション開始")
                await self.load_settings()
                await self.init_browser()
                await self.login()
                await self.analyze_trading_page()
                
                for order in orders:
                    order_type = order.get("type", "buy")
                    amount = order.get("amount")
                    currency_pair = order.get("currency_pair")
                    
                    await self.place_order(order_type, amount, currency_pair)
                    await self.random_wait(2000)  # 注文間の待機時間
                    
                self.logger.info("手動取引セッション完了")
            else:
                # スケジュールモード：新機能
                await self.start_scheduled_trading()
                
        except Exception as e:
            self.logger.error(f"取引セッション失敗: {e}")
            raise
        finally:
            if self.browser:
                await self.browser.close()
                self.logger.info("ブラウザを終了しました")
                
    async def test_element_detection(self):
        """要素検出テスト（環境調査用）"""
        try:
            self.logger.info("=== 要素検出テスト開始 ===")
            
            # 通貨プルダウンアイコン
            try:
                dropdown = await self.page.query_selector('i.svg-icons.icon-dropdown')
                self.logger.info(f"✓ 通貨プルダウンアイコン: {'Found' if dropdown else 'Not Found'}")
            except Exception as e:
                self.logger.warning(f"✗ 通貨プルダウンアイコン: {e}")
                
            # 数量ボタン
            try:
                qty_buttons = await self.page.query_selector_all('li[btnradio].label')
                self.logger.info(f"✓ 数量ボタン: {len(qty_buttons)}個検出")
            except Exception as e:
                self.logger.warning(f"✗ 数量ボタン: {e}")
                
            # 数量プラスボタン
            try:
                plus_btn = await self.page.query_selector('i.svg-icons.icon-qty-add')
                self.logger.info(f"✓ 数量プラスボタン: {'Found' if plus_btn else 'Not Found'}")
            except Exception as e:
                self.logger.warning(f"✗ 数量プラスボタン: {e}")
                
            # Bid/Askボタン
            try:
                bid_btn = await self.page.query_selector('button.button-order-bid')
                ask_btn = await self.page.query_selector('button.button-order-ask')
                self.logger.info(f"✓ Bidボタン: {'Found' if bid_btn else 'Not Found'}")
                self.logger.info(f"✓ Askボタン: {'Found' if ask_btn else 'Not Found'}")
            except Exception as e:
                self.logger.warning(f"✗ Bid/Askボタン: {e}")
                
            # 決済ボタン
            try:
                settle_buttons = await self.page.query_selector_all('button.button-order-settle')
                self.logger.info(f"✓ 決済ボタン: {len(settle_buttons)}個検出")
                for i, btn in enumerate(settle_buttons[:3]):  # 最初の3個だけ表示
                    try:
                        text = await btn.inner_text()
                        self.logger.info(f"  - 決済ボタン{i+1}: {text.strip()}")
                    except:
                        pass
            except Exception as e:
                self.logger.warning(f"✗ 決済ボタン: {e}")
                
            await self.take_screenshot("element_detection_test")
            self.logger.info("=== 要素検出テスト完了 ===")
            
        except Exception as e:
            self.logger.error(f"要素検出テストエラー: {e}")
            
    async def test_order_flow(self, currency_pair: str = "USD/JPY", order_type: str = "buy", amount: float = 1000):
        """注文フローテスト（実際には注文しない）"""
        try:
            self.logger.info(f"=== 注文フローテスト開始: {currency_pair} {order_type} {amount} ===")
            
            # 1. 要素検出テスト
            await self.test_element_detection()
            
            # 2. 通貨ペア選択テスト（クリックはしない）
            try:
                dropdown = await self.page.query_selector('i.svg-icons.icon-dropdown')
                if dropdown:
                    self.logger.info("✓ 通貨プルダウンアイコンが操作可能")
                else:
                    self.logger.warning("✗ 通貨プルダウンアイコンが見つかりません")
            except Exception as e:
                self.logger.warning(f"通貨ペア選択テストエラー: {e}")
                
            # 3. 数量設定テスト（クリックはしない）
            try:
                plus_btn = await self.page.query_selector('i.svg-icons.icon-qty-add')
                if plus_btn:
                    self.logger.info("✓ 数量プラスボタンが操作可能")
                else:
                    self.logger.warning("✗ 数量プラスボタンが見つかりません")
            except Exception as e:
                self.logger.warning(f"数量設定テストエラー: {e}")
                
            # 4. 決済ボタンテスト（クリックはしない）
            try:
                settle_buttons = await self.page.query_selector_all('button.button-order-settle')
                self.logger.info(f"✓ {len(settle_buttons)}個の決済ボタンが操作可能")
            except Exception as e:
                self.logger.warning(f"決済ボタンテストエラー: {e}")
                
            self.logger.info("=== 注文フローテスト完了 ===")
            
        except Exception as e:
            self.logger.error(f"注文フローテストエラー: {e}")
            
    async def environment_check(self):
        """環境調査とテスト実行"""
        try:
            await self.load_settings()
            await self.init_browser()
            await self.login()
            
            # 取引ページの構造を解析
            await self.analyze_trading_page()
            
            # 要素検出テスト
            await self.test_element_detection()
            
            # 成り行き注文同意ボタンテスト
            await self.handle_market_order_agreement()
            
            # 注文フローテスト（実際には注文しない）
            await self.test_order_flow()
            
            self.logger.info("環境調査完了 - 全ての機能がテストされました")
            
        except Exception as e:
            self.logger.error(f"環境調査エラー: {e}")
            raise
        finally:
            if self.browser:
                await self.browser.close()
                self.logger.info("ブラウザを終了しました")
                
    async def cleanup(self):
        """クリーンアップ処理"""
        if hasattr(self, 'running'):
            await self.stop_scheduled_trading()


async def main():
    """メイン関数"""
    import sys
    
    bot = LineFXBot()
    
    try:
        print("=== LINE FX Trading Bot ===")
        print("データソース対応版（Excel/CSV/Google Sheets）")
        print("モード選択:")
        print("1. 環境調査モード (test)")
        print("2. スケジュール取引モード (trading)")
        print("3. 手動テストモード (manual)")
        print("停止するには Ctrl+C を押してください")
        print("=" * 40)
        
        # コマンドライン引数でモードを決定
        mode = "trading"  # デフォルト
        if len(sys.argv) > 1:
            mode = sys.argv[1].lower()
            
        if mode == "test":
            print("🔍 環境調査モードで実行中...")
            await bot.environment_check()
        elif mode == "manual":
            print("📝 手動テストモードで実行中...")
            # 手動テスト用のサンプル注文
            test_orders = [
                {"type": "buy", "amount": 1000, "currency_pair": "USD/JPY"}
            ]
            await bot.run_trading_session(test_orders)
        else:
            print("🚀 スケジュール取引モードで実行中...")
            # スケジュールモードで実行（ordersを渡さない）
            await bot.run_trading_session()
        
    except KeyboardInterrupt:
        print("\n停止要求を受信しました")
        await bot.stop_scheduled_trading()
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    finally:
        await bot.cleanup()
        print("Bot停止完了")


if __name__ == "__main__":
    import sys
    asyncio.run(main())
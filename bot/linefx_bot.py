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
            
    async def place_order_from_rate_table(self, currency_pair: str, order_type: str):
        """レート表から直接注文を出す"""
        try:
            self.logger.info(f"レート表から注文実行 - 通貨ペア: {currency_pair}, タイプ: {order_type}")
            
            # 通貨ペアを含む行を探す
            currency_rows = await self.page.query_selector_all(".pq-grid-row")
            target_row = None
            
            for row in currency_rows:
                try:
                    row_text = await row.inner_text()
                    if currency_pair in row_text:
                        target_row = row
                        break
                except:
                    continue
                    
            if not target_row:
                raise Exception(f"通貨ペア {currency_pair} が見つかりません")
                
            # BidまたはAskボタンをクリック
            if order_type.lower() in ['sell', 'short', '売り']:
                # Bidボタンをクリック（売り注文）
                bid_button = await target_row.query_selector("td[pq-col-indx='2'] .button")
                if bid_button:
                    await bid_button.click()
                    await self.take_screenshot(f"09_{order_type}_bid_clicked")
                    order_name = "売り注文（Bid）"
                else:
                    raise Exception("Bidボタンが見つかりません")
                    
            elif order_type.lower() in ['buy', 'long', '買い']:
                # Askボタンをクリック（買い注文）
                ask_button = await target_row.query_selector("td[pq-col-indx='4'] .button")
                if ask_button:
                    await ask_button.click()
                    await self.take_screenshot(f"09_{order_type}_ask_clicked")
                    order_name = "買い注文（Ask）"
                else:
                    raise Exception("Askボタンが見つかりません")
            else:
                raise ValueError(f"無効な注文タイプ: {order_type}")
                
            await self.random_wait(2000)
            await self.take_screenshot(f"10_{order_type}_order_dialog")
            
            self.logger.info(f"{order_name}をクリックしました - 注文ダイアログを確認してください")
            return True
            
        except Exception as e:
            self.logger.error(f"レート表からの注文失敗: {e}")
            await self.take_screenshot(f"error_rate_table_order")
            raise
            
    async def place_order(self, order_type: str, amount: float = None, currency_pair: str = None):
        """注文を出す（改良版）"""
        try:
            if not currency_pair:
                raise ValueError("通貨ペアが指定されていません。安全のため処理を停止します。")
            
            # レート表から直接注文
            await self.place_order_from_rate_table(currency_pair, order_type)
            
            # 注文ダイアログでの操作は手動確認が必要
            self.logger.info("注文ダイアログが表示されました。手動で確認・実行してください。")
            
            return True
            
        except Exception as e:
            self.logger.error(f"注文実行失敗: {e}")
            await self.take_screenshot(f"error_{order_type}_order_failed")
            raise
            
    async def navigate_to_close_order(self):
        """決済注文画面に移動"""
        try:
            self.logger.info("決済注文画面に移動中...")
            
            # テキスト内容で決済注文メニューを検索
            menu_links = await self.page.query_selector_all("a")
            close_order_link = None
            
            for link in menu_links:
                try:
                    text = await link.inner_text()
                    if "決済注文" in text:
                        close_order_link = link
                        break
                except:
                    continue
                    
            if not close_order_link:
                raise Exception("決済注文メニューが見つかりません")
                
            await self.random_wait(1000)
            await close_order_link.click()
            await self.take_screenshot("11_close_order_menu_clicked")
            
            # ページが読み込まれるまで待機
            await self.random_wait(3000)
            await self.take_screenshot("12_close_order_page")
            
            return True
            
        except Exception as e:
            self.logger.error(f"決済注文画面への移動失敗: {e}")
            await self.take_screenshot("error_close_order_navigation")
            raise
            
    async def close_position(self, position_id: str = None):
        """ポジションを決済"""
        try:
            self.logger.info("ポジション決済開始...")
            
            # 決済注文画面に移動
            await self.navigate_to_close_order()
            
            self.logger.info("決済注文画面が表示されました。手動で決済を実行してください。")
            
            return True
            
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
            currency_pair = trade['currency_pair'].replace('JPY', '/JPY') if 'JPY' in trade['currency_pair'] else trade['currency_pair']
            amount = trade['quantity']
            
            await self.place_order(order_type, amount, currency_pair)
            
            # 実行完了をマーク
            self.schedule_manager.mark_trade_executed(trade['id'])
            
            self.logger.info(f"スケジュールトレード実行完了: {trade['id']}")
            return True
            
        except Exception as e:
            self.logger.error(f"スケジュールトレード実行エラー {trade['id']}: {e}")
            return False

    async def close_scheduled_trade(self, trade: Dict) -> bool:
        """スケジュールされたトレードを決済"""
        try:
            self.logger.info(f"スケジュール決済実行: {trade['id']}")
            
            # 決済処理（LINE FXの決済機能を利用）
            await self.navigate_to_close_order()
            
            # 決済完了をマーク
            self.schedule_manager.mark_trade_closed(trade['id'])
            
            self.logger.info(f"スケジュール決済完了: {trade['id']}")
            return True
            
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
                tolerance_minutes = self.trading_config.get('time_tolerance_minutes', 1)
                
                # エントリー対象
                entry_trades = self.schedule_manager.get_trades_for_time(current_time, tolerance_minutes)
                for trade in entry_trades:
                    success = await self.execute_scheduled_trade(trade)
                    if success:
                        self.logger.info(f"エントリー成功: {trade['id']}")
                    else:
                        self.logger.error(f"エントリー失敗: {trade['id']}")
                    
                    await self.random_wait(2000)  # 連続実行の間隔
                
                # 決済対象
                close_trades = self.schedule_manager.get_trades_to_close(current_time, tolerance_minutes)
                for trade in close_trades:
                    success = await self.close_scheduled_trade(trade)
                    if success:
                        self.logger.info(f"決済成功: {trade['id']}")
                    else:
                        self.logger.error(f"決済失敗: {trade['id']}")
                    
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


async def main():
    """メイン関数"""
    import sys
    
    bot = LineFXBot()
    
    try:
        print("=== LINE FX Trading Bot ===")
        print("データソース対応版（Excel/CSV/Google Sheets）")
        print("停止するには Ctrl+C を押してください")
        print("=" * 40)
        
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
import pandas as pd
import csv
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
import os
from abc import ABC, abstractmethod

def load_trading_settings(config_dir: str = 'config') -> Dict:
    """trading_settings.jsonを読み込む"""
    trading_settings_path = os.path.join(config_dir, 'trading_settings.json')
    try:
        with open(trading_settings_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning(f"trading_settings.json not found at {trading_settings_path}")
        return {}
    except Exception as e:
        logging.error(f"Failed to load trading_settings.json: {e}")
        return {}

class DataReader(ABC):
    """データ読み込みの抽象基底クラス"""
    
    @abstractmethod
    def read_data(self) -> List[Dict]:
        """データを読み込んで統一形式で返す"""
        pass
    
    @abstractmethod
    def mark_trade_executed(self, trade_id: str) -> bool:
        """トレード実行済みマークを付ける"""
        pass
    
    @abstractmethod
    def mark_trade_closed(self, trade_id: str) -> bool:
        """トレード決済済みマークを付ける"""
        pass
    
    def _validate_currency_pair(self, currency_pair) -> str:
        """通貨ペアのバリデーション（必須チェック）"""
        if not currency_pair or str(currency_pair).strip() == '' or str(currency_pair).strip().lower() == 'nan':
            raise ValueError("通貨ペアが設定されていません。安全のため処理を停止します。")
        return str(currency_pair).strip()
    
    def _validate_quantity(self, quantity) -> float:
        """数量のバリデーション（必須チェック）"""
        if not quantity or str(quantity).strip() == '' or str(quantity).strip().lower() == 'nan':
            raise ValueError("数量が設定されていません。安全のため処理を停止します。")
        try:
            qty = float(quantity)
            if qty <= 0:
                raise ValueError(f"数量は正の値である必要があります: {qty}")
            return qty
        except (ValueError, TypeError) as e:
            raise ValueError(f"無効な数量形式: {quantity} - {e}")

class ExcelDataReader(DataReader):
    """Excel形式のトレードデータリーダー"""
    
    def __init__(self, file_path: str, config: Dict = None):
        self.file_path = file_path
        self.config = config or {}
        self.data = []
        self.df = None
        self.logger = logging.getLogger(__name__)
    
    def read_data(self) -> List[Dict]:
        """Excelファイルからトレードデータを読み込み"""
        try:
            if not os.path.exists(self.file_path):
                self.logger.error(f"Excelファイルが見つかりません: {self.file_path}")
                return []
            
            self.df = pd.read_excel(self.file_path)
            self.logger.info(f"Excel読み込み完了: {len(self.df)}件")
            
            trades = []
            for index, row in self.df.iterrows():
                trade = self._convert_row_to_trade(row, index)
                if trade:
                    trades.append(trade)
            
            self.data = trades
            return trades
            
        except Exception as e:
            self.logger.error(f"Excel読み込みエラー: {e}")
            return []
    
    def _convert_row_to_trade(self, row: pd.Series, index: int) -> Optional[Dict]:
        """行データをトレード形式に変換"""
        try:
            # 数量処理：CSVに値があればそれを使用、空ならdefault_amountを使用
            quantity_value = row.get('数量', row.get('quantity'))
            if pd.isna(quantity_value) or str(quantity_value).strip() == '' or str(quantity_value).strip().lower() == 'nan':
                # 設定からdefault_amountを取得（LINEFXではdefault_lot_sizeを使用）
                default_amount = self.config.get('trading_settings', {}).get('default_lot_size')
                if default_amount:
                    quantity = float(default_amount)
                    self.logger.info(f"行{index}: 数量が空のためdefault_lot_size({default_amount})を使用")
                else:
                    raise ValueError(f"行{index}: 数量が設定されておらず、default_lot_sizeも設定されていません")
            else:
                quantity = self._validate_quantity(quantity_value)
                self.logger.info(f"行{index}: Excel指定の数量({quantity})を使用")
            
            return {
                'id': f"excel_{index}",
                'currency_pair': self._validate_currency_pair(row.get('通貨ペア', row.get('currency_pair'))),
                'side': self._normalize_side(str(row.get('方向', row.get('direction', row.get('売買', row.get('side', 'Long')))))),
                'quantity': quantity,
                'entry_time': self._parse_time_only(row.get('エントリー時刻', row.get('entry_time', row.get('エントリー時間')))),
                'exit_time': self._parse_time_only(row.get('クローズ時刻', row.get('exit_time', row.get('決済時間')))),
                'price': row.get('価格', row.get('price')),
                'status': str(row.get('ステータス', row.get('status', 'pending'))).lower(),
                'executed': str(row.get('実行済み', row.get('executed', 'no'))).lower() == 'yes',
                'closed': str(row.get('決済済み', row.get('closed', 'no'))).lower() == 'yes'
            }
        except Exception as e:
            self.logger.warning(f"行{index}の変換に失敗: {e}")
            return None
    
    def _normalize_side(self, side: str) -> str:
        """売買方向を正規化"""
        side = side.lower().strip()
        if side in ['買い', 'buy', 'long', 'l', 'ロング']:
            return 'buy'
        elif side in ['売り', 'sell', 'short', 's', 'ショート']:
            return 'sell'
        return 'buy'
    
    def _parse_datetime(self, dt) -> Optional[datetime]:
        """日時文字列をdatetimeオブジェクトに変換"""
        if pd.isna(dt):
            return None
        
        if isinstance(dt, datetime):
            return dt
        
        if isinstance(dt, str):
            try:
                return datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
            except:
                try:
                    return datetime.strptime(dt, '%Y/%m/%d %H:%M')
                except:
                    self.logger.warning(f"日時形式の解析に失敗: {dt}")
                    return None
        
        return None
    
    def _parse_time_only(self, time_str) -> Optional[datetime]:
        """時間のみ（H:MM:SS）をdatetimeオブジェクトに変換（今日の日付で）"""
        if pd.isna(time_str) or not time_str:
            return None
        
        if isinstance(time_str, datetime):
            return time_str
        
        if isinstance(time_str, str):
            try:
                # H:MM:SS または HH:MM:SS フォーマット
                time_str = str(time_str).strip()
                
                # 今日の日付を取得
                today = datetime.now().date()
                
                # 時間文字列をパース
                if ':' in time_str:
                    time_parts = time_str.split(':')
                    if len(time_parts) >= 2:
                        hour = int(time_parts[0])
                        minute = int(time_parts[1])
                        second = int(time_parts[2]) if len(time_parts) > 2 else 0
                        
                        # 今日の日付 + 指定時間でdatetimeを作成
                        return datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute, second=second))
                
                self.logger.warning(f"時間形式の解析に失敗: {time_str}")
                return None
                
            except Exception as e:
                self.logger.warning(f"時間解析エラー: {time_str} - {e}")
                return None
        
        return None
    
    def mark_trade_executed(self, trade_id: str) -> bool:
        """トレード実行済みマークを付ける"""
        try:
            if self.df is None:
                return False
            
            index = int(trade_id.replace('excel_', ''))
            if index < len(self.df):
                self.df.at[index, '実行済み'] = 'yes'
                self.df.to_excel(self.file_path.replace('.xlsx', '_updated.xlsx'), index=False)
                return True
        except Exception as e:
            self.logger.error(f"実行マーク失敗: {e}")
        
        return False
    
    def mark_trade_closed(self, trade_id: str) -> bool:
        """トレード決済済みマークを付ける"""
        try:
            if self.df is None:
                return False
            
            index = int(trade_id.replace('excel_', ''))
            if index < len(self.df):
                self.df.at[index, '決済済み'] = 'yes'
                self.df.to_excel(self.file_path.replace('.xlsx', '_updated.xlsx'), index=False)
                return True
        except Exception as e:
            self.logger.error(f"決済マーク失敗: {e}")
        
        return False

class CSVDataReader(DataReader):
    """CSV形式のトレードデータリーダー"""
    
    def __init__(self, file_path: str, encoding: str = 'utf-8', config: Dict = None):
        self.file_path = file_path
        self.encoding = encoding
        self.config = config or {}
        self.data = []
        self.logger = logging.getLogger(__name__)
    
    def read_data(self) -> List[Dict]:
        """CSVファイルからトレードデータを読み込み"""
        try:
            if not os.path.exists(self.file_path):
                self.logger.error(f"CSVファイルが見つかりません: {self.file_path}")
                return []
            
            trades = []
            
            # エンコーディングを自動判定して読み込み
            encodings_to_try = [self.encoding, 'utf-8-sig', 'cp932', 'shift_jis', 'utf-8']
            
            for encoding in encodings_to_try:
                try:
                    with open(self.file_path, 'r', encoding=encoding) as csvfile:
                        # ファイルの最初の数行をチェック
                        content = csvfile.read()
                        csvfile.seek(0)
                        
                        # BOM付きUTF-8かチェック
                        if content.startswith('\ufeff'):
                            content = content[1:]  # BOMを除去
                            # 一時的にBOMなしでファイルを読み込み
                            import io
                            csvfile = io.StringIO(content)
                        
                        reader = csv.DictReader(csvfile)
                        
                        # 最初の行をテスト読み込み
                        first_row = next(reader, None)
                        if first_row and '通貨ペア' in str(first_row.keys()):
                            # 正常に読み込めた場合
                            csvfile.seek(0)
                            if content.startswith('\ufeff'):
                                csvfile = io.StringIO(content)
                            reader = csv.DictReader(csvfile)
                            
                            for index, row in enumerate(reader):
                                trade = self._convert_row_to_trade(row, index)
                                if trade:
                                    trades.append(trade)
                            
                            self.logger.info(f"CSV読み込み成功 (エンコーディング: {encoding})")
                            break
                            
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception as e:
                    self.logger.warning(f"エンコーディング {encoding} での読み込み失敗: {e}")
                    continue
            
            if not trades:
                self.logger.error("全てのエンコーディングでCSV読み込みに失敗しました")
            
            self.data = trades
            self.logger.info(f"CSV読み込み完了: {len(trades)}件")
            return trades
            
        except Exception as e:
            self.logger.error(f"CSV読み込みエラー: {e}")
            return []
    
    def _convert_row_to_trade(self, row: Dict, index: int) -> Optional[Dict]:
        """行データをトレード形式に変換"""
        try:
            # 数量処理：CSVに値があればそれを使用、空ならdefault_lot_sizeを使用
            quantity_value = row.get('数量', row.get('quantity'))
            if quantity_value is None or str(quantity_value).strip() == '' or str(quantity_value).strip().lower() == 'nan':
                # 設定からdefault_lot_sizeを取得
                default_amount = self.config.get('trading_settings', {}).get('default_lot_size')
                if default_amount:
                    quantity = float(default_amount)
                    self.logger.info(f"行{index}: 数量が空のためdefault_lot_size({default_amount})を使用")
                else:
                    raise ValueError(f"行{index}: 数量が設定されておらず、default_lot_sizeも設定されていません")
            else:
                quantity = self._validate_quantity(quantity_value)
                self.logger.info(f"行{index}: CSV指定の数量({quantity})を使用")
            
            return {
                'id': f"csv_{index}",
                'currency_pair': self._validate_currency_pair(row.get('通貨ペア', row.get('currency_pair'))),
                'side': self._normalize_side(str(row.get('方向', row.get('direction', row.get('売買', row.get('side', 'Long')))))),
                'quantity': quantity,
                'entry_time': self._parse_time_only(row.get('エントリー時刻', row.get('entry_time', row.get('エントリー時間')))),
                'exit_time': self._parse_time_only(row.get('クローズ時刻', row.get('exit_time', row.get('決済時間')))),
                'price': row.get('価格', row.get('price')),
                'status': str(row.get('ステータス', row.get('status', 'pending'))).lower(),
                'executed': str(row.get('実行済み', row.get('executed', 'no'))).lower() == 'yes',
                'closed': str(row.get('決済済み', row.get('closed', 'no'))).lower() == 'yes'
            }
        except Exception as e:
            self.logger.warning(f"行{index}の変換に失敗: {e}")
            return None
    
    def _normalize_side(self, side: str) -> str:
        """売買方向を正規化"""
        side = side.lower().strip()
        if side in ['買い', 'buy', 'long', 'l', 'ロング']:
            return 'buy'
        elif side in ['売り', 'sell', 'short', 's', 'ショート']:
            return 'sell'
        return 'buy'
    
    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """日時文字列をdatetimeオブジェクトに変換"""
        if not dt_str or dt_str.strip() == '':
            return None
        
        try:
            return datetime.strptime(dt_str.strip(), '%Y-%m-%d %H:%M:%S')
        except:
            try:
                return datetime.strptime(dt_str.strip(), '%Y/%m/%d %H:%M')
            except:
                self.logger.warning(f"日時形式の解析に失敗: {dt_str}")
                return None
    
    def _parse_time_only(self, time_str) -> Optional[datetime]:
        """時間のみ（H:MM:SS）をdatetimeオブジェクトに変換（今日の日付で）"""
        if not time_str or str(time_str).strip() == '':
            return None
        
        if isinstance(time_str, datetime):
            return time_str
        
        try:
            # H:MM:SS または HH:MM:SS フォーマット
            time_str = str(time_str).strip()
            
            # 今日の日付を取得
            today = datetime.now().date()
            
            # 時間文字列をパース
            if ':' in time_str:
                time_parts = time_str.split(':')
                if len(time_parts) >= 2:
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    second = int(time_parts[2]) if len(time_parts) > 2 else 0
                    
                    # 今日の日付 + 指定時間でdatetimeを作成
                    return datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute, second=second))
            
            self.logger.warning(f"時間形式の解析に失敗: {time_str}")
            return None
            
        except Exception as e:
            self.logger.warning(f"時間解析エラー: {time_str} - {e}")
            return None
    
    def mark_trade_executed(self, trade_id: str) -> bool:
        """トレード実行済みマークを付ける"""
        return self._update_csv_status(trade_id, '実行済み', 'yes')
    
    def mark_trade_closed(self, trade_id: str) -> bool:
        """トレード決済済みマークを付ける"""
        return self._update_csv_status(trade_id, '決済済み', 'yes')
    
    def _update_csv_status(self, trade_id: str, column: str, value: str) -> bool:
        """CSVファイルのステータスを更新"""
        try:
            index = int(trade_id.replace('csv_', ''))
            
            # CSVを読み込み
            rows = []
            with open(self.file_path, 'r', encoding=self.encoding) as csvfile:
                reader = csv.DictReader(csvfile)
                fieldnames = reader.fieldnames
                
                for i, row in enumerate(reader):
                    if i == index:
                        row[column] = value
                    rows.append(row)
            
            # CSVに書き戻し
            backup_file = self.file_path.replace('.csv', '_backup.csv')
            os.rename(self.file_path, backup_file)
            
            # エンコーディングを決定（BOM付きの場合は維持）
            write_encoding = 'utf-8-sig' if self.encoding == 'utf-8-sig' else self.encoding
            
            with open(self.file_path, 'w', newline='', encoding=write_encoding) as csvfile:
                if fieldnames:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
            
            return True
            
        except Exception as e:
            self.logger.error(f"CSV更新エラー: {e}")
            return False

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False

class GoogleSheetsDataReader(DataReader):
    """Googleスプレッドシート形式のトレードデータリーダー"""
    
    def __init__(self, spreadsheet_id: str, sheet_name: str, credentials_file: str, config: Dict = None):
        if not GOOGLE_SHEETS_AVAILABLE:
            raise ImportError("Google Sheets連携には gspread と google-auth が必要です: pip install gspread google-auth")
        
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.credentials_file = credentials_file
        self.config = config or {}
        self.data = []
        self.worksheet = None
        self.logger = logging.getLogger(__name__)
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Google Sheets APIクライアントを初期化"""
        try:
            if not os.path.exists(self.credentials_file):
                self.logger.error(f"認証ファイルが見つかりません: {self.credentials_file}")
                return
            
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(
                self.credentials_file, scopes=scope
            )
            
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self.worksheet = self.spreadsheet.worksheet(self.sheet_name)
            
            self.logger.info("Google Sheets接続完了")
            
        except Exception as e:
            self.logger.error(f"Google Sheets初期化エラー: {e}")
    
    def read_data(self) -> List[Dict]:
        """Googleスプレッドシートからトレードデータを読み込み"""
        try:
            if not self.worksheet:
                self.logger.error("Google Sheetsワークシートが初期化されていません")
                return []
            
            records = self.worksheet.get_all_records()
            trades = []
            
            for index, row in enumerate(records):
                trade = self._convert_row_to_trade(row, index)
                if trade:
                    trades.append(trade)
            
            self.data = trades
            self.logger.info(f"Google Sheets読み込み完了: {len(trades)}件")
            return trades
            
        except Exception as e:
            self.logger.error(f"Google Sheets読み込みエラー: {e}")
            return []
    
    def _convert_row_to_trade(self, row: Dict, index: int) -> Optional[Dict]:
        """行データをトレード形式に変換"""
        try:
            # 数量処理：スプレッドシートに値があればそれを使用、空ならdefault_lot_sizeを使用
            quantity_value = row.get('数量', row.get('quantity'))
            if quantity_value is None or str(quantity_value).strip() == '' or str(quantity_value).strip().lower() == 'nan':
                # 設定からdefault_lot_sizeを取得
                default_amount = self.config.get('trading_settings', {}).get('default_lot_size')
                if default_amount:
                    quantity = float(default_amount)
                    self.logger.info(f"行{index}: 数量が空のためdefault_lot_size({default_amount})を使用")
                else:
                    raise ValueError(f"行{index}: 数量が設定されておらず、default_lot_sizeも設定されていません")
            else:
                quantity = self._validate_quantity(quantity_value)
                self.logger.info(f"行{index}: Google Sheets指定の数量({quantity})を使用")
            
            return {
                'id': f"gsheets_{index}",
                'currency_pair': self._validate_currency_pair(row.get('通貨ペア', row.get('currency_pair'))),
                'side': self._normalize_side(str(row.get('方向', row.get('direction', row.get('売買', row.get('side', 'Long')))))),
                'quantity': quantity,
                'entry_time': self._parse_time_only(row.get('エントリー時刻', row.get('entry_time', row.get('エントリー時間')))),
                'exit_time': self._parse_time_only(row.get('クローズ時刻', row.get('exit_time', row.get('決済時間')))),
                'price': row.get('価格', row.get('price')),
                'status': str(row.get('ステータス', row.get('status', 'pending'))).lower(),
                'executed': str(row.get('実行済み', row.get('executed', 'no'))).lower() == 'yes',
                'closed': str(row.get('決済済み', row.get('closed', 'no'))).lower() == 'yes'
            }
        except Exception as e:
            self.logger.warning(f"行{index}の変換に失敗: {e}")
            return None
    
    def _normalize_side(self, side: str) -> str:
        """売買方向を正規化"""
        side = side.lower().strip()
        if side in ['買い', 'buy', 'long', 'l', 'ロング']:
            return 'buy'
        elif side in ['売り', 'sell', 'short', 's', 'ショート']:
            return 'sell'
        return 'buy'
    
    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """日時文字列をdatetimeオブジェクトに変換"""
        if not dt_str or str(dt_str).strip() == '':
            return None
        
        try:
            return datetime.strptime(str(dt_str).strip(), '%Y-%m-%d %H:%M:%S')
        except:
            try:
                return datetime.strptime(str(dt_str).strip(), '%Y/%m/%d %H:%M')
            except:
                self.logger.warning(f"日時形式の解析に失敗: {dt_str}")
                return None
    
    def _parse_time_only(self, time_str) -> Optional[datetime]:
        """時間のみ（H:MM:SS）をdatetimeオブジェクトに変換（今日の日付で）"""
        if not time_str or str(time_str).strip() == '':
            return None
        
        if isinstance(time_str, datetime):
            return time_str
        
        try:
            # H:MM:SS または HH:MM:SS フォーマット
            time_str = str(time_str).strip()
            
            # 今日の日付を取得
            today = datetime.now().date()
            
            # 時間文字列をパース
            if ':' in time_str:
                time_parts = time_str.split(':')
                if len(time_parts) >= 2:
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    second = int(time_parts[2]) if len(time_parts) > 2 else 0
                    
                    # 今日の日付 + 指定時間でdatetimeを作成
                    return datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute, second=second))
            
            self.logger.warning(f"時間形式の解析に失敗: {time_str}")
            return None
            
        except Exception as e:
            self.logger.warning(f"時間解析エラー: {time_str} - {e}")
            return None
    
    def mark_trade_executed(self, trade_id: str) -> bool:
        """トレード実行済みマークを付ける"""
        return self._update_cell_value(trade_id, '実行済み', 'yes')
    
    def mark_trade_closed(self, trade_id: str) -> bool:
        """トレード決済済みマークを付ける"""
        return self._update_cell_value(trade_id, '決済済み', 'yes')
    
    def _update_cell_value(self, trade_id: str, column: str, value: str) -> bool:
        """スプレッドシートのセル値を更新"""
        try:
            if not self.worksheet:
                return False
            
            index = int(trade_id.replace('gsheets_', ''))
            row_number = index + 2  # ヘッダー行を考慮
            
            # 列名から列番号を取得
            headers = self.worksheet.row_values(1)
            try:
                col_number = headers.index(column) + 1
            except ValueError:
                try:
                    # 英語列名も試す
                    english_columns = {'実行済み': 'executed', '決済済み': 'closed'}
                    english_column = english_columns.get(column, column)
                    col_number = headers.index(english_column) + 1
                except ValueError:
                    self.logger.warning(f"列が見つかりません: {column}")
                    return False
            
            # セルを更新
            self.worksheet.update_cell(row_number, col_number, value)
            self.logger.info(f"Google Sheets更新完了: {trade_id} {column}={value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Google Sheets更新エラー: {e}")
            return False

class DataReaderFactory:
    """データリーダーのファクトリークラス"""
    
    @staticmethod
    def create_reader(config: Dict, trading_config: Dict = None) -> DataReader:
        """設定に基づいてデータリーダーを作成"""
        # trading_configが渡されていない場合は、configから読み込み（後方互換性）
        if trading_config is None:
            trading_config = config.get('trading_settings', {})
        
        # configにtrading_settingsを追加（既存のコードとの互換性のため）
        merged_config = config.copy()
        merged_config['trading_settings'] = trading_config
        
        data_source_config = config.get('data_source', {})
        source_type = data_source_config.get('type', 'excel').lower()
        
        if source_type == 'excel':
            excel_config = data_source_config.get('excel', {})
            file_path = excel_config.get('file_path', 'data/trade_schedule.xlsx')
            return ExcelDataReader(file_path, merged_config)
        
        elif source_type == 'csv':
            csv_config = data_source_config.get('csv', {})
            file_path = csv_config.get('file_path', 'data/trade_schedule.csv')
            encoding = csv_config.get('encoding', 'utf-8')
            return CSVDataReader(file_path, encoding, merged_config)
        
        elif source_type == 'google_sheets':
            if not GOOGLE_SHEETS_AVAILABLE:
                raise ImportError("Google Sheets連携には追加パッケージが必要です: pip install gspread google-auth")
            
            gsheets_config = data_source_config.get('google_sheets', {})
            spreadsheet_id = gsheets_config.get('spreadsheet_id', '')
            sheet_name = gsheets_config.get('sheet_name', 'Trade Schedule')
            credentials_file = gsheets_config.get('credentials_file', 'config/google_credentials.json')
            
            if not spreadsheet_id:
                raise ValueError("Google SheetsのスプレッドシートIDが設定されていません")
            
            return GoogleSheetsDataReader(spreadsheet_id, sheet_name, credentials_file, merged_config)
        
        else:
            raise ValueError(f"サポートされていないデータソース: {source_type}")

class TradeScheduleManager:
    """トレードスケジュール管理クラス"""
    
    def __init__(self, data_reader: DataReader):
        self.data_reader = data_reader
        self.trades_data = []
        self.logger = logging.getLogger(__name__)
    
    def load_data(self) -> bool:
        """データを読み込み"""
        try:
            self.trades_data = self.data_reader.read_data()
            return len(self.trades_data) > 0
        except Exception as e:
            self.logger.error(f"データ読み込みエラー: {e}")
            return False
    
    def get_trades_for_time(self, current_time: datetime, tolerance_minutes: int = 1) -> List[Dict]:
        """指定時間のエントリー対象トレードを取得"""
        target_trades = []
        
        for trade in self.trades_data:
            if trade.get('executed', False):
                continue
            
            entry_time = trade.get('entry_time')
            if not entry_time:
                continue
            
            time_diff = abs((current_time - entry_time).total_seconds() / 60)
            if time_diff <= tolerance_minutes:
                target_trades.append(trade)
        
        return target_trades
    
    def get_trades_to_close(self, current_time: datetime, tolerance_minutes: int = 1) -> List[Dict]:
        """指定時間の決済対象トレードを取得"""
        target_trades = []
        
        for trade in self.trades_data:
            if not trade.get('executed', False) or trade.get('closed', False):
                continue
            
            exit_time = trade.get('exit_time')
            if not exit_time:
                continue
            
            time_diff = abs((current_time - exit_time).total_seconds() / 60)
            if time_diff <= tolerance_minutes:
                target_trades.append(trade)
        
        return target_trades
    
    def mark_trade_executed(self, trade_id: str) -> bool:
        """トレード実行済みマーク"""
        return self.data_reader.mark_trade_executed(trade_id)
    
    def mark_trade_closed(self, trade_id: str) -> bool:
        """トレード決済済みマーク"""
        return self.data_reader.mark_trade_closed(trade_id)
    
    def get_trade_summary(self) -> Dict:
        """トレードデータの概要を取得"""
        total = len(self.trades_data)
        executed = sum(1 for trade in self.trades_data if trade.get('executed', False))
        closed = sum(1 for trade in self.trades_data if trade.get('closed', False))
        
        return {
            'total': total,
            'executed': executed,
            'closed': closed,
            'pending': total - executed
        }
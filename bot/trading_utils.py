"""
LINE FX取引ユーティリティ
取引に関する便利な関数を提供
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class TradingAnalyzer:
    """取引データ分析クラス"""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.data_dir = base_path / "data"
        self.data_dir.mkdir(exist_ok=True)
        
    def save_trading_session(self, session_data: Dict):
        """取引セッションデータを保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trading_session_{timestamp}.json"
        filepath = self.data_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
            
        return filepath
        
    def load_trading_history(self) -> List[Dict]:
        """取引履歴を読み込み"""
        history = []
        for json_file in self.data_dir.glob("trading_session_*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    history.append(data)
            except Exception:
                continue
                
        return sorted(history, key=lambda x: x.get('timestamp', ''))
        
    def analyze_html_structure(self, html_file: Path) -> Dict:
        """HTML構造を解析"""
        if not html_file.exists():
            return {}
            
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
                
            analysis = {
                'file_size': len(html_content),
                'element_counts': {},
                'potential_selectors': [],
                'forms': [],
                'buttons': []
            }
            
            # 簡単な要素カウント
            for tag in ['button', 'input', 'form', 'div', 'span', 'a']:
                count = html_content.lower().count(f'<{tag}')
                analysis['element_counts'][tag] = count
                
            # 潜在的な取引要素を検索
            trading_keywords = [
                'buy', 'sell', 'trade', 'order', 'position',
                '買い', '売り', '注文', '取引', 'ポジション',
                'amount', 'price', 'lot', '金額', '価格', '数量'
            ]
            
            for keyword in trading_keywords:
                if keyword.lower() in html_content.lower():
                    analysis['potential_selectors'].append(keyword)
                    
            return analysis
            
        except Exception as e:
            return {'error': str(e)}


class OrderManager:
    """注文管理クラス"""
    
    def __init__(self):
        self.orders = []
        self.executed_orders = []
        
    def add_order(self, order_type: str, amount: float, currency_pair: str = "USD/JPY", 
                  stop_loss: float = None, take_profit: float = None) -> Dict:
        """注文を追加"""
        order = {
            'id': f"order_{int(time.time())}_{len(self.orders)}",
            'type': order_type.lower(),
            'amount': amount,
            'currency_pair': currency_pair,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'created_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        self.orders.append(order)
        return order
        
    def get_pending_orders(self) -> List[Dict]:
        """未実行の注文を取得"""
        return [order for order in self.orders if order['status'] == 'pending']
        
    def mark_order_executed(self, order_id: str, execution_data: Dict):
        """注文を実行済みにマーク"""
        for order in self.orders:
            if order['id'] == order_id:
                order['status'] = 'executed'
                order['executed_at'] = datetime.now().isoformat()
                order['execution_data'] = execution_data
                self.executed_orders.append(order)
                break
                
    def get_order_summary(self) -> Dict:
        """注文サマリーを取得"""
        return {
            'total_orders': len(self.orders),
            'pending_orders': len(self.get_pending_orders()),
            'executed_orders': len(self.executed_orders),
            'buy_orders': len([o for o in self.orders if o['type'] == 'buy']),
            'sell_orders': len([o for o in self.orders if o['type'] == 'sell'])
        }


class RiskManager:
    """リスク管理クラス"""
    
    def __init__(self, max_positions: int = 5, max_loss_per_trade: float = 1000):
        self.max_positions = max_positions
        self.max_loss_per_trade = max_loss_per_trade
        self.current_positions = 0
        self.total_loss = 0.0
        
    def can_place_order(self, amount: float) -> tuple[bool, str]:
        """注文が可能かチェック"""
        if self.current_positions >= self.max_positions:
            return False, f"最大ポジション数({self.max_positions})に達しています"
            
        if amount > self.max_loss_per_trade:
            return False, f"注文金額が最大損失額({self.max_loss_per_trade})を超えています"
            
        return True, "OK"
        
    def update_positions(self, position_count: int):
        """ポジション数を更新"""
        self.current_positions = position_count
        
    def add_loss(self, loss_amount: float):
        """損失を追加"""
        self.total_loss += loss_amount
        
    def get_risk_status(self) -> Dict:
        """リスク状況を取得"""
        return {
            'current_positions': self.current_positions,
            'max_positions': self.max_positions,
            'total_loss': self.total_loss,
            'max_loss_per_trade': self.max_loss_per_trade,
            'risk_level': 'HIGH' if self.current_positions >= self.max_positions * 0.8 else 'NORMAL'
        }


def create_sample_orders() -> List[Dict]:
    """サンプル注文を作成"""
    return [
        {
            "type": "buy",
            "amount": 1000,
            "currency_pair": "USD/JPY",
            "description": "テスト買い注文"
        },
        {
            "type": "sell", 
            "amount": 1000,
            "currency_pair": "EUR/JPY",
            "description": "テスト売り注文"
        }
    ]


def validate_order(order: Dict) -> tuple[bool, str]:
    """注文データを検証"""
    required_fields = ['type', 'amount']
    
    for field in required_fields:
        if field not in order:
            return False, f"必須フィールド '{field}' が不足しています"
            
    if order['type'].lower() not in ['buy', 'sell', 'long', 'short', '買い', '売り']:
        return False, f"無効な注文タイプ: {order['type']}"
        
    if not isinstance(order['amount'], (int, float)) or order['amount'] <= 0:
        return False, "金額は正の数値である必要があります"
        
    return True, "OK"
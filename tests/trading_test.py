import asyncio
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bot.linefx_bot import LineFXBot


async def test_trading_analysis():
    """取引ページ解析テスト"""
    print("=== LINE FX 取引ページ解析テスト ===")
    print("取引ページの構造解析を開始します...")
    print()
    
    bot = LineFXBot()
    
    try:
        # 解析モードで実行
        await bot.run(mode="analysis")
        print()
        print("✅ 取引ページ解析テスト成功!")
        print("debugフォルダで以下を確認してください:")
        print("- 取引ページのスクリーンショット")
        print("- HTML構造ファイル")
        print("- ログファイルで取引要素の発見状況")
        return 0
        
    except Exception as e:
        print()
        print("❌ 取引ページ解析テスト失敗:")
        print(f"エラー: {e}")
        return 1


async def test_mock_trading():
    """模擬取引テスト（実際の注文は行わない）"""
    print("=== LINE FX 模擬取引テスト ===")
    print("模擬取引を実行します（実際の注文は行いません）...")
    print()
    
    bot = LineFXBot()
    
    try:
        await bot.load_settings()
        await bot.init_browser()
        await bot.login()
        
        # 取引ページ解析
        trading_elements = await bot.analyze_trading_page()
        
        # ポジション情報取得テスト
        positions = await bot.get_positions()
        print(f"現在のポジション数: {len(positions)}")
        
        print()
        print("✅ 模擬取引テスト成功!")
        print("実際の取引機能が利用可能な状態です。")
        
        # ブラウザを手動で閉じるまで待機（取引画面確認用）
        print()
        print("🔍 取引画面を確認してください。")
        print("ブラウザを手動で閉じるか、Ctrl+C で終了してください。")
        
        try:
            while True:
                await asyncio.sleep(5)
                # 定期的にポジション確認
                current_positions = await bot.get_positions()
                if len(current_positions) != len(positions):
                    print(f"ポジション変化検出: {len(current_positions)}件")
                    positions = current_positions
        except KeyboardInterrupt:
            print("\n⏹️ テスト終了")
            
        return 0
        
    except Exception as e:
        print()
        print("❌ 模擬取引テスト失敗:")
        print(f"エラー: {e}")
        return 1
    finally:
        if bot.browser:
            await bot.browser.close()


async def test_sample_orders():
    """サンプル注文テスト"""
    print("=== LINE FX サンプル注文テスト ===")
    print("⚠️  この機能は実際の注文を行います！")
    print("テスト環境でのみ実行してください。")
    print()
    
    response = input("実際に注文を実行しますか？ (yes/no): ")
    if response.lower() != 'yes':
        print("テストをキャンセルしました。")
        return 0
    
    # サンプル注文
    sample_orders = [
        {
            "type": "buy",
            "amount": 1000,
            "currency_pair": "USD/JPY"
        }
    ]
    
    bot = LineFXBot()
    
    try:
        await bot.run_trading_session(sample_orders)
        print()
        print("✅ サンプル注文テスト完了!")
        return 0
        
    except Exception as e:
        print()
        print("❌ サンプル注文テスト失敗:")
        print(f"エラー: {e}")
        return 1


async def main():
    """メイン関数"""
    print("LINE FX 取引機能テストメニュー")
    print("=" * 40)
    print("1. 取引ページ解析テスト（安全）")
    print("2. 模擬取引テスト（安全・手動確認）")
    print("3. サンプル注文テスト（⚠️実際の注文⚠️）")
    print("4. 終了")
    print()
    
    choice = input("選択してください (1-4): ")
    
    if choice == "1":
        return await test_trading_analysis()
    elif choice == "2":
        return await test_mock_trading()
    elif choice == "3":
        return await test_sample_orders()
    elif choice == "4":
        print("終了します。")
        return 0
    else:
        print("無効な選択です。")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
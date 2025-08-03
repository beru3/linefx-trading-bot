import asyncio
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bot.linefx_bot import LineFXBot


async def test_login():
    """ログインテスト"""
    print("=== LINE FX ログインテスト（Python版） ===")
    print("ログインテストを開始します...")
    print()
    
    bot = LineFXBot()
    
    try:
        await bot.run()
        print()
        print("✅ ログインテスト成功!")
        print("debugフォルダでスクリーンショットを確認してください。")
        print("logsフォルダで詳細ログを確認してください。")
        return 0
        
    except Exception as e:
        print()
        print("❌ ログインテスト失敗:")
        print(f"エラー: {e}")
        print()
        print("debugフォルダでエラースクリーンショットを確認してください。")
        print("logsフォルダで詳細ログを確認してください。")
        return 1


def main():
    """メイン関数"""
    return asyncio.run(test_login())


if __name__ == "__main__":
    sys.exit(main())
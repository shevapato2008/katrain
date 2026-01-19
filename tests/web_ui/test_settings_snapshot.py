import time
import pytest
from katrain.web.interface import WebKaTrain, NullEngine
from katrain.core.constants import MODE_PLAY

class MockEngine(NullEngine):
    def request_analysis(self, *args, **kwargs):
        pass

def test_timer_snapshot_immutability():
    """验证对局中途修改设置不会影响当前快照"""
    katrain = WebKaTrain(force_package_config=True, enable_engine=False)
    katrain.engine = MockEngine()
    
    # 1. 初始设置：10分钟
    katrain._config["timer"] = {
        "main_time": 10,
        "byo_length": 30,
        "byo_periods": 5,
        "minimal_use": 0
    }
    
    # 2. 开始新游戏（触发快照）
    katrain._do_new_game(size=19)
    assert katrain.active_game_timer["main_time"] == 10
    
    # 3. 在游戏中途修改配置
    katrain.update_config("timer/main_time", 20)
    
    # 验证：配置已变，但快照未变
    assert katrain._config["timer"]["main_time"] == 20
    assert katrain.active_game_timer["main_time"] == 10
    
    # 4. 再次开始新游戏
    katrain._do_new_game(size=19)
    
    # 验证：新游戏使用了新配置
    assert katrain.active_game_timer["main_time"] == 20

def test_persistence_call():
    """验证 update_config 是否会触发 save_config (对齐 Kivy)"""
    katrain = WebKaTrain(force_package_config=True, enable_engine=False)
    katrain.engine = MockEngine()
    
    saved_domain = None
    def mock_save(domain=None):
        nonlocal saved_domain
        saved_domain = domain
        
    katrain.save_config = mock_save
    
    # 修改计时器设置
    katrain.update_config("timer/main_time", 15)
    assert saved_domain == "timer"
    assert katrain._config["timer"]["main_time"] == 15

def test_teaching_settings_parity():
    """验证教学设置的批量更新逻辑"""
    katrain = WebKaTrain(force_package_config=True, enable_engine=False)
    
    new_settings = {
        "eval_thresholds": [0.5, 1.0, 2.0, 4.0, 8.0, 16.0],
        "lock_ai": True,
        "eval_show_ai": False
    }
    
    # 模拟前端 updateConfigBulk
    for key, value in new_settings.items():
        katrain.update_config(f"trainer/{key}", value)
        
    assert katrain.config("trainer/eval_thresholds") == [0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
    assert katrain.config("trainer/lock_ai") is True
    assert katrain.config("trainer/eval_show_ai") is False

if __name__ == "__main__":
    test_timer_snapshot_immutability()
    test_persistence_call()
    test_teaching_settings_parity()
    print("Settings snapshot tests passed!")

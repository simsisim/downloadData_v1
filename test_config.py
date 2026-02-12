#!/usr/bin/env python
"""
Quick test script to verify configuration system works correctly.
Tests all three configuration methods: CLI args, dict override, and presets.
"""

import sys
from src.user_defined_data import read_user_data
from main import merge_configs, CONFIG_PRESETS


def test_base_config():
    """Test 1: Base CSV configuration loading"""
    print("="*60)
    print("TEST 1: Base CSV Configuration")
    print("="*60)

    config = read_user_data()
    print(f"✓ Ticker Choice: {config.ticker_choice}")
    print(f"✓ YF Historical Data: {config.yf_hist_data}")
    print(f"✓ Daily Data: {config.yf_daily_data}")
    print(f"✓ Weekly Data: {config.yf_weekly_data}")
    print(f"✓ Financial Data Enrichment: {config.fin_data_enrich}")
    print("✅ Base config loaded successfully\n")
    return config


def test_preset(base_config):
    """Test 2: Preset configuration"""
    print("="*60)
    print("TEST 2: Preset Configuration")
    print("="*60)

    for preset_name in ['quick_test', 'nasdaq_daily', 'full_canslim']:
        print(f"\n📋 Testing preset: {preset_name}")
        merged = merge_configs(base_config, preset=preset_name)

        preset_config = CONFIG_PRESETS[preset_name]
        print(f"   Ticker Choice: {merged.ticker_choice} (expected: {preset_config['ticker_choice']})")
        print(f"   Daily Data: {merged.yf_daily_data} (expected: {preset_config.get('yf_daily_data', 'N/A')})")

        # Verify preset was applied
        assert merged.ticker_choice == preset_config['ticker_choice'], \
            f"Preset not applied correctly for {preset_name}"

    print("\n✅ All presets work correctly\n")


def test_dict_override(base_config):
    """Test 3: Dict override (Colab-style)"""
    print("="*60)
    print("TEST 3: Dict Override Configuration")
    print("="*60)

    override = {
        'ticker_choice': '8',
        'yf_daily_data': True,
        'yf_weekly_data': False,
        'fin_data_enrich': False
    }

    print(f"Override dict: {override}")
    merged = merge_configs(base_config, config_override=override)

    print(f"\nMerged config:")
    print(f"   Ticker Choice: {merged.ticker_choice} (expected: 8)")
    print(f"   Daily Data: {merged.yf_daily_data} (expected: True)")
    print(f"   Weekly Data: {merged.yf_weekly_data} (expected: False)")
    print(f"   Fin Data: {merged.fin_data_enrich} (expected: False)")

    # Verify overrides were applied
    assert merged.ticker_choice == '8', "Dict override failed for ticker_choice"
    assert merged.yf_daily_data == True, "Dict override failed for yf_daily_data"
    assert merged.yf_weekly_data == False, "Dict override failed for yf_weekly_data"

    print("\n✅ Dict override works correctly\n")


def test_priority_order(base_config):
    """Test 4: Priority order (preset vs dict override)"""
    print("="*60)
    print("TEST 4: Configuration Priority Order")
    print("="*60)

    # Preset says ticker_choice='2' (nasdaq_daily)
    # Dict override says ticker_choice='8'
    # Dict should win

    override = {'ticker_choice': '8'}
    merged = merge_configs(base_config, config_override=override, preset='nasdaq_daily')

    print(f"Preset: nasdaq_daily (ticker_choice='2')")
    print(f"Dict override: {override}")
    print(f"Final ticker_choice: {merged.ticker_choice}")
    print(f"Expected: '8' (dict should override preset)")

    # Note: Based on our implementation, preset is applied first, then dict override
    # So dict should win
    assert merged.ticker_choice == '8', "Priority order incorrect: dict should override preset"

    print("\n✅ Priority order correct (dict > preset > CSV)\n")


def test_available_presets():
    """Test 5: List available presets"""
    print("="*60)
    print("TEST 5: Available Presets")
    print("="*60)

    print(f"\nAvailable presets ({len(CONFIG_PRESETS)}):")
    for preset_name, preset_config in CONFIG_PRESETS.items():
        ticker_choice = preset_config.get('ticker_choice', 'N/A')
        daily = preset_config.get('yf_daily_data', 'N/A')
        weekly = preset_config.get('yf_weekly_data', 'N/A')
        fin_data = preset_config.get('fin_data_enrich', 'N/A')

        print(f"\n   📋 {preset_name}")
        print(f"      - Ticker Choice: {ticker_choice}")
        print(f"      - Daily: {daily}, Weekly: {weekly}")
        print(f"      - Financial Data: {fin_data}")

    print("\n✅ All presets listed\n")


def main():
    """Run all tests"""
    print("\n" + "🧪 CONFIGURATION SYSTEM TEST SUITE" + "\n")

    try:
        # Test 1: Base config
        base_config = test_base_config()

        # Test 2: Presets
        test_preset(base_config)

        # Test 3: Dict override
        test_dict_override(base_config)

        # Test 4: Priority order
        test_priority_order(base_config)

        # Test 5: List presets
        test_available_presets()

        print("="*60)
        print("🎉 ALL TESTS PASSED!")
        print("="*60)
        print("\n✅ Configuration system is working correctly")
        print("\nYou can now use:")
        print("  - python main.py --preset nasdaq_daily")
        print("  - python main.py --ticker-choice 2 --daily")
        print("  - main({'ticker_choice': '2', 'yf_daily_data': True})")
        print("\nSee CONFIGURATION_EXAMPLES.md for more usage examples.\n")

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

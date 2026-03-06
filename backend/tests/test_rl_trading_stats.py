"""
Test Suite for RL Trading Stats API Endpoint
GET /api/rl/trading-stats?hours={1,6,24}

Tests the following:
- Response structure validation for all periods (1h, 6h, 24h)
- No-data case returns warning status with 'no_data' reason
- Hold stats, Net PnL stats, Fee stats, Sell sources, Trade counts
- Core performance metrics and RL-specific metrics
- Health status logic (healthy/warning/critical with reasons)
- Fee ratio calculation documented in code
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if BASE_URL:
    BASE_URL = BASE_URL.rstrip('/')


class TestRLTradingStatsAuth:
    """Authentication tests for RL Trading Stats endpoint"""
    
    def test_endpoint_requires_auth(self):
        """Verify endpoint returns 401 without authentication"""
        response = requests.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        assert response.status_code == 401, f"Expected 401 but got {response.status_code}"
        print("✓ Endpoint correctly requires authentication")


class TestRLTradingStatsStructure:
    """Tests for response structure validation"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for tests"""
        # Create/login test user
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": "rlstats_test@example.com", "password": "TestPass123!"}
        )
        if response.status_code == 200:
            return response.json()['token']
        
        # If registration fails, try login
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "rlstats_test@example.com", "password": "TestPass123!"}
        )
        if response.status_code == 200:
            return response.json()['token']
        
        pytest.skip("Could not authenticate for tests")
    
    @pytest.fixture(scope="class")
    def api_client(self, auth_token):
        """Create an authenticated session"""
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        })
        return session
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ENDPOINT TESTS FOR hours=1
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_trading_stats_hours_1_status_code(self, api_client):
        """GET /api/rl/trading-stats?hours=1 returns 200"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=1")
        assert response.status_code == 200, f"Expected 200 but got {response.status_code}"
        print("✓ GET /api/rl/trading-stats?hours=1 returns 200")
    
    def test_trading_stats_hours_1_period(self, api_client):
        """Verify period_hours is 1"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=1")
        data = response.json()
        assert data.get('period_hours') == 1, f"Expected period_hours=1 but got {data.get('period_hours')}"
        print("✓ period_hours correctly set to 1")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ENDPOINT TESTS FOR hours=6
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_trading_stats_hours_6_status_code(self, api_client):
        """GET /api/rl/trading-stats?hours=6 returns 200"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=6")
        assert response.status_code == 200, f"Expected 200 but got {response.status_code}"
        print("✓ GET /api/rl/trading-stats?hours=6 returns 200")
    
    def test_trading_stats_hours_6_period(self, api_client):
        """Verify period_hours is 6"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=6")
        data = response.json()
        assert data.get('period_hours') == 6, f"Expected period_hours=6 but got {data.get('period_hours')}"
        print("✓ period_hours correctly set to 6")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ENDPOINT TESTS FOR hours=24
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_trading_stats_hours_24_status_code(self, api_client):
        """GET /api/rl/trading-stats?hours=24 returns 200"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        assert response.status_code == 200, f"Expected 200 but got {response.status_code}"
        print("✓ GET /api/rl/trading-stats?hours=24 returns 200")
    
    def test_trading_stats_hours_24_period(self, api_client):
        """Verify period_hours is 24"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        assert data.get('period_hours') == 24, f"Expected period_hours=24 but got {data.get('period_hours')}"
        print("✓ period_hours correctly set to 24")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RESPONSE STRUCTURE - HOLD STATS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_response_contains_hold_stats(self, api_client):
        """Verify response includes hold_stats object"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        assert 'hold_stats' in data, "Response missing 'hold_stats'"
        
        hold_stats = data['hold_stats']
        expected_fields = [
            'avg_hold_seconds', 'min_hold_seconds', 'max_hold_seconds',
            'avg_hold_formatted', 'min_hold_formatted', 'max_hold_formatted'
        ]
        for field in expected_fields:
            assert field in hold_stats, f"hold_stats missing '{field}'"
        
        print(f"✓ hold_stats structure valid with all {len(expected_fields)} fields")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RESPONSE STRUCTURE - PNL STATS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_response_contains_pnl_stats(self, api_client):
        """Verify response includes pnl_stats object"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        assert 'pnl_stats' in data, "Response missing 'pnl_stats'"
        
        pnl_stats = data['pnl_stats']
        expected_fields = [
            'avg_net_pnl_usdt', 'avg_net_pnl_pct', 'avg_theoretical_pnl_pct',
            'total_net_pnl_usdt', 'total_net_pnl_pct', 'total_theoretical_pnl_pct',
            'pnl_gap_pct'
        ]
        for field in expected_fields:
            assert field in pnl_stats, f"pnl_stats missing '{field}'"
        
        print(f"✓ pnl_stats structure valid with all {len(expected_fields)} fields")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RESPONSE STRUCTURE - FEE STATS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_response_contains_fee_stats(self, api_client):
        """Verify response includes fee_stats object"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        assert 'fee_stats' in data, "Response missing 'fee_stats'"
        
        fee_stats = data['fee_stats']
        expected_fields = [
            'total_fees_paid', 'total_slippage', 'total_costs', 'fee_ratio_pct'
        ]
        for field in expected_fields:
            assert field in fee_stats, f"fee_stats missing '{field}'"
        
        print(f"✓ fee_stats structure valid with all {len(expected_fields)} fields")
    
    def test_fee_ratio_calculation_documented(self, api_client):
        """
        Verify fee_ratio_pct field exists and is documented in code
        
        Fee ratio formula: (total_fees / total_notional) * 100
        This measures what percentage of traded volume went to fees
        """
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        
        # Verify field exists
        assert 'fee_stats' in data, "Response missing 'fee_stats'"
        assert 'fee_ratio_pct' in data['fee_stats'], "fee_stats missing 'fee_ratio_pct'"
        
        # For no-data case, fee_ratio should be 0
        fee_ratio = data['fee_stats']['fee_ratio_pct']
        assert isinstance(fee_ratio, (int, float)), f"fee_ratio_pct should be numeric, got {type(fee_ratio)}"
        assert fee_ratio >= 0, f"fee_ratio_pct should be non-negative, got {fee_ratio}"
        
        print(f"✓ fee_ratio_pct exists and is valid: {fee_ratio}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RESPONSE STRUCTURE - SELL SOURCES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_response_contains_sell_sources(self, api_client):
        """Verify response includes sell_sources breakdown"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        assert 'sell_sources' in data, "Response missing 'sell_sources'"
        
        sell_sources = data['sell_sources']
        assert 'counts' in sell_sources, "sell_sources missing 'counts'"
        assert 'percentages' in sell_sources, "sell_sources missing 'percentages'"
        
        expected_keys = ['exploitation', 'random_exploration', 'emergency', 'time_limit', 'unknown']
        for key in expected_keys:
            assert key in sell_sources['counts'], f"sell_sources.counts missing '{key}'"
            assert key in sell_sources['percentages'], f"sell_sources.percentages missing '{key}'"
        
        print(f"✓ sell_sources structure valid with counts and percentages for all {len(expected_keys)} sources")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RESPONSE STRUCTURE - TRADE COUNTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_response_contains_trade_counts(self, api_client):
        """Verify response includes trade_counts object"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        assert 'trade_counts' in data, "Response missing 'trade_counts'"
        
        trade_counts = data['trade_counts']
        expected_fields = ['total', 'winning', 'losing']
        for field in expected_fields:
            assert field in trade_counts, f"trade_counts missing '{field}'"
        
        # Verify logical consistency: total = winning + losing (or total = 0)
        total = trade_counts['total']
        winning = trade_counts['winning']
        losing = trade_counts['losing']
        assert total >= winning + losing, f"trade_counts logic error: total={total} but winning={winning}, losing={losing}"
        
        print(f"✓ trade_counts structure valid: total={total}, winning={winning}, losing={losing}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RESPONSE STRUCTURE - PERFORMANCE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_response_contains_performance(self, api_client):
        """Verify response includes performance object with core metrics"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        assert 'performance' in data, "Response missing 'performance'"
        
        performance = data['performance']
        expected_fields = [
            'win_rate_pct', 'avg_win_usdt', 'avg_loss_usdt',
            'avg_win_pct', 'avg_loss_pct', 'profit_factor',
            'gross_profit', 'gross_loss'
        ]
        for field in expected_fields:
            assert field in performance, f"performance missing '{field}'"
        
        print(f"✓ performance structure valid with all {len(expected_fields)} metrics")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RESPONSE STRUCTURE - RL METRICS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_response_contains_rl_metrics(self, api_client):
        """Verify response includes rl_metrics object"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        assert 'rl_metrics' in data, "Response missing 'rl_metrics'"
        
        rl_metrics = data['rl_metrics']
        expected_fields = [
            'exploration_sell_ratio_pct', 'exploitation_sell_ratio_pct',
            'avg_duration_winning', 'avg_duration_losing',
            'avg_duration_winning_formatted', 'avg_duration_losing_formatted'
        ]
        for field in expected_fields:
            assert field in rl_metrics, f"rl_metrics missing '{field}'"
        
        print(f"✓ rl_metrics structure valid with all {len(expected_fields)} fields")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # RESPONSE STRUCTURE - HEALTH STATUS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_response_contains_health(self, api_client):
        """Verify response includes health status object"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        assert 'health' in data, "Response missing 'health'"
        
        health = data['health']
        expected_fields = ['status', 'status_color', 'reasons']
        for field in expected_fields:
            assert field in health, f"health missing '{field}'"
        
        print(f"✓ health structure valid with status, status_color, and reasons")
    
    def test_health_status_valid_values(self, api_client):
        """Verify health status has valid values (healthy/warning/critical)"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        
        health = data['health']
        valid_statuses = ['healthy', 'warning', 'critical']
        valid_colors = ['green', 'yellow', 'red', 'gray']
        
        assert health['status'] in valid_statuses, f"Invalid status: {health['status']}"
        assert health['status_color'] in valid_colors, f"Invalid status_color: {health['status_color']}"
        assert isinstance(health['reasons'], list), f"reasons should be a list, got {type(health['reasons'])}"
        
        print(f"✓ health status valid: {health['status']} ({health['status_color']})")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # NO-DATA CASE TESTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_no_data_returns_warning_status(self, api_client):
        """Verify no-data case returns warning status with 'no_data' reason"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        
        # For a new user with no trades, expect warning status
        if data['total_closed_trades'] == 0:
            health = data['health']
            assert health['status'] == 'warning', f"No-data case should have warning status, got {health['status']}"
            assert 'no_data' in health['reasons'], f"No-data case should have 'no_data' in reasons: {health['reasons']}"
            print("✓ No-data case correctly returns warning status with 'no_data' reason")
        else:
            print(f"✓ User has {data['total_closed_trades']} trades, skipping no-data test")
    
    def test_no_data_returns_zero_values(self, api_client):
        """Verify no-data case returns zeroed values for all metrics"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        
        if data['total_closed_trades'] == 0:
            # Verify all numeric values are 0
            assert data['hold_stats']['avg_hold_seconds'] == 0
            assert data['pnl_stats']['avg_net_pnl_usdt'] == 0
            assert data['fee_stats']['total_fees_paid'] == 0
            assert data['trade_counts']['total'] == 0
            assert data['performance']['win_rate_pct'] == 0
            
            print("✓ No-data case correctly returns zeroed values")
        else:
            print(f"✓ User has {data['total_closed_trades']} trades, skipping zero values test")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DEFAULT PARAMETER TEST
    # ═══════════════════════════════════════════════════════════════════════════
    
    def test_default_hours_parameter(self, api_client):
        """Verify default hours parameter is 24"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats")
        data = response.json()
        assert data.get('period_hours') == 24, f"Default period should be 24 hours, got {data.get('period_hours')}"
        print("✓ Default hours parameter is 24")


class TestRLTradingStatsDataTypes:
    """Tests for data type validation"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "rlstats_test@example.com", "password": "TestPass123!"}
        )
        if response.status_code == 200:
            return response.json()['token']
        pytest.skip("Could not authenticate")
    
    @pytest.fixture(scope="class")
    def api_client(self, auth_token):
        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {auth_token}"})
        return session
    
    def test_numeric_fields_are_numbers(self, api_client):
        """Verify all numeric fields return proper numeric types"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        
        # Check hold_stats numeric fields
        assert isinstance(data['hold_stats']['avg_hold_seconds'], (int, float))
        
        # Check pnl_stats numeric fields
        assert isinstance(data['pnl_stats']['avg_net_pnl_usdt'], (int, float))
        assert isinstance(data['pnl_stats']['avg_net_pnl_pct'], (int, float))
        
        # Check fee_stats numeric fields
        assert isinstance(data['fee_stats']['total_fees_paid'], (int, float))
        assert isinstance(data['fee_stats']['fee_ratio_pct'], (int, float))
        
        # Check performance numeric fields
        assert isinstance(data['performance']['win_rate_pct'], (int, float))
        assert isinstance(data['performance']['profit_factor'], (int, float))
        
        print("✓ All numeric fields return proper numeric types")
    
    def test_formatted_fields_are_strings(self, api_client):
        """Verify formatted fields return proper string types"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        
        # Check hold_stats formatted fields
        assert isinstance(data['hold_stats']['avg_hold_formatted'], str)
        assert isinstance(data['hold_stats']['min_hold_formatted'], str)
        assert isinstance(data['hold_stats']['max_hold_formatted'], str)
        
        # Check rl_metrics formatted fields
        assert isinstance(data['rl_metrics']['avg_duration_winning_formatted'], str)
        assert isinstance(data['rl_metrics']['avg_duration_losing_formatted'], str)
        
        print("✓ All formatted fields return proper string types")
    
    def test_health_reasons_is_list_of_strings(self, api_client):
        """Verify health.reasons is a list of strings"""
        response = api_client.get(f"{BASE_URL}/api/rl/trading-stats?hours=24")
        data = response.json()
        
        reasons = data['health']['reasons']
        assert isinstance(reasons, list), f"reasons should be list, got {type(reasons)}"
        for reason in reasons:
            assert isinstance(reason, str), f"Each reason should be string, got {type(reason)}"
        
        print("✓ health.reasons is a valid list of strings")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

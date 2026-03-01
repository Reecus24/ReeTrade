"""
ReeTrade Terminal - AI V2 Profile Backend Tests
Testing new position sizing: % of available USDT instead of budget-based min/max

Tests:
- GET /api/ai/profiles - must return position_pct_range, position_usd_min, position_usd_max based on usdt_free
- GET /api/ai/preview/{mode} - must return correct Position % ranges and calculated USD values
- Profile validation: Aggressive (15-35%), Moderate (8-18%), Conservative (3-8%)
"""
import pytest
import requests
import os

# Get base URL from frontend env
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env', 'r') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break

# Test credentials
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpass123"

# Global token cache
_cached_token = None


def get_auth_token():
    """Get authentication token with caching"""
    global _cached_token
    if _cached_token:
        return _cached_token
    
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        _cached_token = response.json()["token"]
        return _cached_token
    raise Exception(f"Login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="session")
def auth_token():
    return get_auth_token()


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestAIProfilesV2:
    """AI Profiles V2 endpoint tests - position sizing based on available USDT"""
    
    def test_profiles_returns_new_v2_fields(self, auth_headers):
        """
        Test GET /api/ai/profiles returns new V2 fields:
        - position_pct_range (e.g., "15%-35%")
        - position_usd_min (calculated from usdt_free)
        - position_usd_max (calculated from usdt_free)
        - usdt_free (available USDT balance)
        """
        response = requests.get(f"{BASE_URL}/api/ai/profiles", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Check root level fields
        assert "usdt_free" in data, "Response must include usdt_free"
        assert "trading_budget" in data, "Response must include trading_budget"
        assert "trading_budget_remaining" in data, "Response must include trading_budget_remaining"
        
        # Check profiles
        assert "profiles" in data
        profiles = data["profiles"]
        assert len(profiles) == 4, f"Expected 4 profiles, got {len(profiles)}"
        
        for profile in profiles:
            mode = profile["mode"]
            
            # All profiles must have these V2 fields
            assert "position_pct_range" in profile, f"Profile {mode} missing position_pct_range"
            assert "position_usd_min" in profile, f"Profile {mode} missing position_usd_min"
            assert "position_usd_max" in profile, f"Profile {mode} missing position_usd_max"
            assert "usdt_free" in profile, f"Profile {mode} missing usdt_free"
            assert "trading_budget_remaining" in profile, f"Profile {mode} missing trading_budget_remaining"
            
            # position_usd_min should be <= position_usd_max
            assert profile["position_usd_min"] <= profile["position_usd_max"], \
                f"Profile {mode}: position_usd_min ({profile['position_usd_min']}) > position_usd_max ({profile['position_usd_max']})"
            
            print(f"✅ Profile {mode}: {profile['position_pct_range']} = ${profile['position_usd_min']:.2f} - ${profile['position_usd_max']:.2f}")
        
        print(f"✅ All profiles returned V2 fields correctly")
    
    def test_aggressive_profile_position_range(self, auth_headers):
        """
        Test Aggressive profile has correct position range: 15%-35%
        """
        response = requests.get(f"{BASE_URL}/api/ai/profiles", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        aggressive = next((p for p in data["profiles"] if p["mode"] == "ai_aggressive"), None)
        
        assert aggressive is not None, "Aggressive profile not found"
        assert aggressive["position_pct_range"] == "15%-35%", \
            f"Aggressive position_pct_range should be '15%-35%', got '{aggressive['position_pct_range']}'"
        
        # Verify calculation: 15% of 500 = 75, 35% of 500 = 175
        usdt_free = aggressive["usdt_free"]
        expected_min = usdt_free * 0.15
        expected_max = usdt_free * 0.35
        
        # Allow small tolerance for capping
        assert abs(aggressive["position_usd_min"] - expected_min) < 1 or aggressive["position_usd_min"] <= aggressive["trading_budget_remaining"], \
            f"Aggressive position_usd_min calculation incorrect"
        
        print(f"✅ Aggressive profile: {aggressive['position_pct_range']} = ${aggressive['position_usd_min']:.2f} - ${aggressive['position_usd_max']:.2f}")
    
    def test_moderate_profile_position_range(self, auth_headers):
        """
        Test Moderate profile has correct position range: 8%-18%
        """
        response = requests.get(f"{BASE_URL}/api/ai/profiles", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        moderate = next((p for p in data["profiles"] if p["mode"] == "ai_moderate"), None)
        
        assert moderate is not None, "Moderate profile not found"
        assert moderate["position_pct_range"] == "8%-18%", \
            f"Moderate position_pct_range should be '8%-18%', got '{moderate['position_pct_range']}'"
        
        print(f"✅ Moderate profile: {moderate['position_pct_range']} = ${moderate['position_usd_min']:.2f} - ${moderate['position_usd_max']:.2f}")
    
    def test_conservative_profile_position_range(self, auth_headers):
        """
        Test Conservative profile has correct position range: 3%-8%
        """
        response = requests.get(f"{BASE_URL}/api/ai/profiles", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        conservative = next((p for p in data["profiles"] if p["mode"] == "ai_conservative"), None)
        
        assert conservative is not None, "Conservative profile not found"
        assert conservative["position_pct_range"] == "3%-8%", \
            f"Conservative position_pct_range should be '3%-8%', got '{conservative['position_pct_range']}'"
        
        print(f"✅ Conservative profile: {conservative['position_pct_range']} = ${conservative['position_usd_min']:.2f} - ${conservative['position_usd_max']:.2f}")
    
    def test_profiles_have_atr_stop_loss(self, auth_headers):
        """
        Test AI profiles include ATR-based stop loss info
        """
        response = requests.get(f"{BASE_URL}/api/ai/profiles", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Only AI profiles (not manual) should have ATR stop loss
        ai_profiles = [p for p in data["profiles"] if p["mode"] != "manual"]
        
        for profile in ai_profiles:
            assert "sl_atr_multiplier" in profile, f"Profile {profile['mode']} missing sl_atr_multiplier"
            assert "ATR" in profile["sl_atr_multiplier"], f"Profile {profile['mode']} sl_atr_multiplier should contain 'ATR'"
            print(f"✅ Profile {profile['mode']}: SL = {profile['sl_atr_multiplier']}")


class TestAIPreviewV2:
    """AI Preview endpoint tests - verifies position sizing display"""
    
    def test_preview_aggressive_position_format(self, auth_headers):
        """
        Test GET /api/ai/preview/ai_aggressive returns:
        - position_pct_range: "15%-35%"
        - position_usd_min and position_usd_max calculated from usdt_free
        - reasoning with new format
        """
        response = requests.get(f"{BASE_URL}/api/ai/preview/ai_aggressive", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        assert data["mode"] == "ai_aggressive"
        assert data["position_pct_range"] == "15%-35%", f"Expected '15%-35%', got '{data['position_pct_range']}'"
        assert "position_usd_min" in data
        assert "position_usd_max" in data
        assert "usdt_free" in data
        assert "trading_budget_remaining" in data
        
        # Check reasoning includes new format
        reasoning = data.get("reasoning", [])
        assert len(reasoning) > 0, "Reasoning should not be empty"
        
        # Check for position size text in reasoning
        position_reason = [r for r in reasoning if "Position Size:" in r]
        assert len(position_reason) > 0, "Reasoning should include 'Position Size' entry"
        
        # Check for calculated order text in reasoning
        order_reason = [r for r in reasoning if "Berechnete Order:" in r]
        assert len(order_reason) > 0, "Reasoning should include 'Berechnete Order' entry"
        
        print(f"✅ Preview aggressive: {data['position_pct_range']} = ${data['position_usd_min']:.2f} - ${data['position_usd_max']:.2f}")
        print(f"   Reasoning: {reasoning[0:3]}")
    
    def test_preview_moderate_position_format(self, auth_headers):
        """
        Test GET /api/ai/preview/ai_moderate returns correct position range: 8%-18%
        """
        response = requests.get(f"{BASE_URL}/api/ai/preview/ai_moderate", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        assert data["mode"] == "ai_moderate"
        assert data["position_pct_range"] == "8%-18%", f"Expected '8%-18%', got '{data['position_pct_range']}'"
        
        print(f"✅ Preview moderate: {data['position_pct_range']} = ${data['position_usd_min']:.2f} - ${data['position_usd_max']:.2f}")
    
    def test_preview_conservative_position_format(self, auth_headers):
        """
        Test GET /api/ai/preview/ai_conservative returns correct position range: 3%-8%
        """
        response = requests.get(f"{BASE_URL}/api/ai/preview/ai_conservative", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        assert data["mode"] == "ai_conservative"
        assert data["position_pct_range"] == "3%-8%", f"Expected '3%-8%', got '{data['position_pct_range']}'"
        
        print(f"✅ Preview conservative: {data['position_pct_range']} = ${data['position_usd_min']:.2f} - ${data['position_usd_max']:.2f}")
    
    def test_preview_includes_atr_stop_loss(self, auth_headers):
        """
        Test preview endpoints include ATR-based stop loss
        """
        for mode in ["ai_aggressive", "ai_moderate", "ai_conservative"]:
            response = requests.get(f"{BASE_URL}/api/ai/preview/{mode}", headers=auth_headers)
            assert response.status_code == 200
            
            data = response.json()
            
            assert "sl_atr_multiplier" in data, f"Preview {mode} missing sl_atr_multiplier"
            assert "ATR" in data["sl_atr_multiplier"], f"Preview {mode} sl_atr_multiplier should contain 'ATR'"
            
            print(f"✅ Preview {mode}: SL = {data['sl_atr_multiplier']}")
    
    def test_preview_includes_trading_budget(self, auth_headers):
        """
        Test preview endpoints include trading_budget as cap info
        """
        response = requests.get(f"{BASE_URL}/api/ai/preview/ai_aggressive", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        assert "trading_budget" in data, "Preview should include trading_budget"
        assert "trading_budget_remaining" in data, "Preview should include trading_budget_remaining"
        
        print(f"✅ Preview includes budget cap: ${data['trading_budget']} (remaining: ${data['trading_budget_remaining']})")
    
    def test_preview_invalid_mode_returns_400(self, auth_headers):
        """Test GET /api/ai/preview with invalid mode returns 400"""
        response = requests.get(f"{BASE_URL}/api/ai/preview/invalid_mode", headers=auth_headers)
        assert response.status_code == 400
        print("✅ Invalid AI mode correctly rejected with 400")


class TestRiskProfilesV2Config:
    """Test RISK_PROFILES_V2 configuration values in API response"""
    
    def test_aggressive_risk_config(self, auth_headers):
        """Test Aggressive profile risk configuration"""
        response = requests.get(f"{BASE_URL}/api/ai/preview/ai_aggressive", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Check ATR multiplier range 2.0-2.5x
        assert "2.0x" in data["sl_atr_multiplier"] and "2.5x" in data["sl_atr_multiplier"], \
            f"Aggressive SL should be 2.0x-2.5x ATR, got {data['sl_atr_multiplier']}"
        
        # Check TP R:R range 2.5:1 - 3.5:1
        assert "2.5" in data["tp_rr_range"] and "3.5" in data["tp_rr_range"], \
            f"Aggressive TP should include 2.5:1 - 3.5:1, got {data['tp_rr_range']}"
        
        # Max positions should be 3
        assert data["max_positions"] == 3, f"Aggressive max_positions should be 3, got {data['max_positions']}"
        
        print(f"✅ Aggressive risk config verified: SL={data['sl_atr_multiplier']}, TP={data['tp_rr_range']}, Max={data['max_positions']}")
    
    def test_conservative_risk_config(self, auth_headers):
        """Test Conservative profile risk configuration"""
        response = requests.get(f"{BASE_URL}/api/ai/preview/ai_conservative", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Check ATR multiplier range 1.2-1.8x (tighter)
        assert "1.2x" in data["sl_atr_multiplier"] and "1.8x" in data["sl_atr_multiplier"], \
            f"Conservative SL should be 1.2x-1.8x ATR, got {data['sl_atr_multiplier']}"
        
        # Max positions should be 2 (more conservative)
        assert data["max_positions"] == 2, f"Conservative max_positions should be 2, got {data['max_positions']}"
        
        print(f"✅ Conservative risk config verified: SL={data['sl_atr_multiplier']}, Max={data['max_positions']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

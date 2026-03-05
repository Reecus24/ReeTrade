#!/usr/bin/env python3
import requests
import sys
import time
from datetime import datetime
from typing import Dict, Optional

class TradingBotAPITester:
    def __init__(self, base_url="https://rl-mexc-bot.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_password = "Rainer_70!PK"

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None) -> tuple:
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        request_headers = {'Content-Type': 'application/json'}
        
        if headers:
            request_headers.update(headers)
        
        if self.token and 'Authorization' not in request_headers:
            request_headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   {method} {endpoint}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=request_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=request_headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                    return False, error_data
                except:
                    print(f"   Error text: {response.text}")
                    return False, {'error': response.text}

        except requests.exceptions.Timeout:
            print(f"❌ FAILED - Timeout after 30 seconds")
            return False, {'error': 'timeout'}
        except Exception as e:
            print(f"❌ FAILED - Exception: {str(e)}")
            return False, {'error': str(e)}

    def test_health_check(self):
        """Test API health check"""
        return self.run_test("Health Check", "GET", "api", 200)

    def test_login(self):
        """Test login with admin password"""
        success, response = self.run_test(
            "Login",
            "POST",
            "api/auth/login",
            200,
            data={"password": self.admin_password}
        )
        if success and 'token' in response:
            self.token = response['token']
            print(f"   🔑 Token received: {self.token[:20]}...")
            return True
        return False

    def test_login_invalid(self):
        """Test login with invalid password"""
        success, _ = self.run_test(
            "Login Invalid Password",
            "POST",
            "api/auth/login",
            401,
            data={"password": "wrong_password"}
        )
        return success

    def test_status(self):
        """Test status endpoint"""
        return self.run_test("Get Status", "GET", "api/status", 200)

    def test_bot_start(self):
        """Test bot start"""
        success, response = self.run_test("Start Bot", "POST", "api/bot/start", 200)
        if success:
            print(f"   📊 Response: {response}")
        return success

    def test_bot_stop(self):
        """Test bot stop"""
        success, response = self.run_test("Stop Bot", "POST", "api/bot/stop", 200)
        if success:
            print(f"   📊 Response: {response}")
        return success

    def test_logs(self):
        """Test logs endpoint"""
        success, response = self.run_test("Get Logs", "GET", "api/logs?limit=10", 200)
        if success and 'logs' in response:
            print(f"   📋 Retrieved {len(response['logs'])} log entries")
        return success

    def test_top_pairs(self):
        """Test top pairs endpoint"""
        success, response = self.run_test("Get Top Pairs", "GET", "api/market/top_pairs", 200)
        if success:
            print(f"   📈 Top pairs: {response}")
        return success

    def test_candles(self):
        """Test candles endpoint"""
        return self.run_test(
            "Get Candles",
            "GET",
            "api/market/candles?symbol=BTCUSDT&interval=15m&limit=10",
            200
        )

    def test_live_mode_request(self):
        """Test live mode request"""
        success, response = self.run_test("Request Live Mode", "POST", "api/bot/live/request", 200)
        if success:
            print(f"   ⚠️  Live mode requested: {response}")
        return success

    def test_live_mode_confirm_invalid(self):
        """Test live mode confirm with invalid password"""
        return self.run_test(
            "Confirm Live Mode (Invalid)",
            "POST",
            "api/bot/live/confirm",
            401,
            data={"password": "wrong_password"}
        )

    def test_live_mode_confirm_no_keys(self):
        """Test live mode confirm without API keys"""
        success, response = self.run_test(
            "Confirm Live Mode (No API Keys)",
            "POST",
            "api/bot/live/confirm",
            400,
            data={"password": self.admin_password}
        )
        if success:
            print(f"   🔑 Expected error for missing API keys: {response}")
        return success

    def test_backtest(self):
        """Test backtest endpoint"""
        print(f"   ⏱️  Running backtest (may take 15-30 seconds)...")
        success, response = self.run_test(
            "Run Backtest",
            "POST",
            "api/backtest/run",
            200,
            data={}
        )
        if success:
            print(f"   📊 Backtest completed:")
            print(f"      Total trades: {response.get('total_trades', 0)}")
            print(f"      Win rate: {response.get('win_rate', 0):.1f}%")
            print(f"      Total PnL: {response.get('total_pnl', 0):.2f}%")
        return success

    def test_live_mode_disable(self):
        """Test live mode disable"""
        success, response = self.run_test("Disable Live Mode", "POST", "api/bot/live/disable", 200)
        if success:
            print(f"   📊 Response: {response}")
        return success

    def test_unauthorized_access(self):
        """Test unauthorized access without token"""
        old_token = self.token
        self.token = None
        success, _ = self.run_test("Unauthorized Access", "GET", "api/status", 401)
        self.token = old_token
        return success

def main():
    print("🚀 Starting MEXC Trading Bot API Tests")
    print("="*60)
    
    tester = TradingBotAPITester()
    
    # Core functionality tests
    test_results = []
    
    print("\n📋 BASIC CONNECTIVITY TESTS")
    print("-" * 40)
    test_results.append(("Health Check", tester.test_health_check()))
    
    print("\n🔐 AUTHENTICATION TESTS")
    print("-" * 40)
    test_results.append(("Login Valid", tester.test_login()))
    test_results.append(("Login Invalid", tester.test_login_invalid()))
    test_results.append(("Unauthorized Access", tester.test_unauthorized_access()))
    
    if not tester.token:
        print("❌ Cannot continue without valid token")
        return 1
    
    print("\n📊 STATUS & MONITORING TESTS")
    print("-" * 40)
    test_results.append(("Get Status", tester.test_status()))
    test_results.append(("Get Logs", tester.test_logs()))
    
    print("\n🤖 BOT CONTROL TESTS")
    print("-" * 40)
    test_results.append(("Start Bot", tester.test_bot_start()))
    time.sleep(2)  # Let bot start
    test_results.append(("Stop Bot", tester.test_bot_stop()))
    
    print("\n📈 MARKET DATA TESTS")
    print("-" * 40)
    test_results.append(("Top Pairs", tester.test_top_pairs()))
    test_results.append(("Get Candles", tester.test_candles()))
    
    print("\n⚠️  LIVE MODE TESTS")
    print("-" * 40)
    test_results.append(("Request Live Mode", tester.test_live_mode_request()))
    test_results.append(("Confirm Live Invalid", tester.test_live_mode_confirm_invalid()))
    test_results.append(("Confirm Live No Keys", tester.test_live_mode_confirm_no_keys()))
    test_results.append(("Disable Live Mode", tester.test_live_mode_disable()))
    
    print("\n🔙 BACKTEST TESTS")
    print("-" * 40)
    test_results.append(("Run Backtest", tester.test_backtest()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed_tests = []
    failed_tests = []
    
    for test_name, result in test_results:
        if result:
            passed_tests.append(test_name)
            print(f"✅ {test_name}")
        else:
            failed_tests.append(test_name)
            print(f"❌ {test_name}")
    
    print(f"\nTotal: {len(test_results)} tests")
    print(f"Passed: {len(passed_tests)} tests")
    print(f"Failed: {len(failed_tests)} tests")
    print(f"Success Rate: {len(passed_tests)/len(test_results)*100:.1f}%")
    
    if failed_tests:
        print(f"\n❌ FAILED TESTS:")
        for test in failed_tests:
            print(f"   - {test}")
    
    return 0 if len(failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
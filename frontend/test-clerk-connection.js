/**
 * Test script to diagnose Clerk connection issues
 * Run with: node test-clerk-connection.js
 */

const https = require('https');
const http = require('http');

// Disable SSL verification for testing (matches .env.local setting)
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

console.log('Testing Clerk connectivity...\n');

// Test 1: Check if we can reach Clerk's API
console.log('Test 1: Checking Clerk API endpoint...');
const clerkDomain = 'wise-coral-92.clerk.accounts.dev';

https.get(`https://${clerkDomain}/.well-known/openid-configuration`, (res) => {
  console.log(`✓ Connected to Clerk (Status: ${res.statusCode})`);

  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    try {
      const config = JSON.parse(data);
      console.log(`✓ Issuer: ${config.issuer}`);
      console.log(`✓ JWKS URI: ${config.jwks_uri}`);
    } catch (e) {
      console.log('Response:', data.substring(0, 200));
    }
  });
}).on('error', (err) => {
  console.error('✗ Failed to connect to Clerk:', err.message);
  console.error('\nPossible issues:');
  console.error('1. Corporate firewall blocking Clerk API');
  console.error('2. Proxy configuration needed');
  console.error('3. Internet connection issue');
});

// Test 2: Verify publishable key format
console.log('\nTest 2: Checking publishable key format...');
const pubKey = 'pk_test_d2lzZS1jb3JhbC05Mi5jbGVyay5hY2NvdW50cy5kZXYk';
if (pubKey.startsWith('pk_test_')) {
  console.log('✓ Key format looks correct (pk_test_...)');
  try {
    const decoded = Buffer.from(pubKey.replace('pk_test_', ''), 'base64').toString();
    console.log(`✓ Decoded domain: ${decoded}`);
  } catch (e) {
    console.log('✗ Could not decode key:', e.message);
  }
} else {
  console.log('✗ Invalid key format');
}

// Test 3: Check local backend
console.log('\nTest 3: Checking local backend...');
http.get('http://localhost:8000/docs', (res) => {
  console.log(`✓ Backend is running (Status: ${res.statusCode})`);
}).on('error', (err) => {
  console.log('✗ Backend not running:', err.message);
  console.log('  Start with: cd backend && uvicorn app.main:app --reload');
});

setTimeout(() => {
  console.log('\n--- Test Complete ---');
}, 2000);

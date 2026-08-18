/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * Appwrite Database Setup Script (EXAMPLE)
 *
 * This script creates the CPET database and patients collection in Appwrite.
 * Before running, set the environment variables or replace the placeholder values below.
 *
 * Usage:
 *   1. Copy this file to setup-appwrite.js
 *   2. Fill in your Appwrite credentials
 *   3. Run: node setup-appwrite.js
 */
const https = require('https');

// ── Replace these with your Appwrite project credentials ──────────────────────
const PROJECT_ID = process.env.APPWRITE_PROJECT_ID || 'YOUR_PROJECT_ID';
const API_KEY    = process.env.APPWRITE_API_KEY    || 'YOUR_API_KEY';
const HOST       = process.env.APPWRITE_HOST       || 'cloud.appwrite.io';
// ──────────────────────────────────────────────────────────────────────────────

function callApi(method, path, payload) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(payload || {});
    const req = https.request({
      hostname: HOST,
      path: '/v1' + path,
      method: method,
      headers: {
        'Content-Type': 'application/json',
        'X-Appwrite-Project': PROJECT_ID,
        'X-Appwrite-Key': API_KEY,
        'Content-Length': Buffer.byteLength(data)
      }
    }, (res) => {
      let responseBody = '';
      res.on('data', chunk => responseBody += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(responseBody);
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(parsed);
          } else {
            console.error(`[Error on ${path}]`, parsed);
            resolve(parsed);
          }
        } catch {
          resolve(responseBody);
        }
      });
    });

    req.on('error', reject);
    if (payload) req.write(data);
    req.end();
  });
}

async function run() {
  console.log('1. Creating Database (cpet_db)...');
  await callApi('POST', '/databases', { databaseId: 'cpet_db', name: 'CPET Database' });

  console.log('2. Creating Collection (patients)...');
  await callApi('POST', '/databases/cpet_db/collections', {
    collectionId: 'patients',
    name: 'Patients',
    documentSecurity: false,
    permissions: [
      'read("any")',
      'create("any")',
      'update("any")',
      'delete("any")'
    ]
  });

  console.log('3. Creating Attributes...');
  await callApi('POST', '/databases/cpet_db/collections/patients/attributes/string', { key: 'name', size: 255, required: true });
  await callApi('POST', '/databases/cpet_db/collections/patients/attributes/integer', { key: 'age', required: true });
  await callApi('POST', '/databases/cpet_db/collections/patients/attributes/string', { key: 'position', size: 50, required: false });
  await callApi('POST', '/databases/cpet_db/collections/patients/attributes/datetime', { key: 'last_test_date', required: false });
  await callApi('POST', '/databases/cpet_db/collections/patients/attributes/string', { key: 'fitness_status', size: 50, required: false });

  console.log('\nDone! You can verify in your Appwrite Dashboard.');
}

run();

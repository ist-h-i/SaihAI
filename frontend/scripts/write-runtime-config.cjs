const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_API_BASE_URL = 'http://localhost:8000/api/v1';

const apiBaseUrl = (process.env.SAIHAI_API_BASE_URL || '').trim() || DEFAULT_API_BASE_URL;
const authToken = (process.env.SAIHAI_AUTH_TOKEN || '').trim();

const config = {
  apiBaseUrl,
  authToken,
};

const outputPath = path.join(process.cwd(), 'src', 'assets', 'runtime-config.json');
fs.writeFileSync(outputPath, `${JSON.stringify(config, null, 2)}\n`);

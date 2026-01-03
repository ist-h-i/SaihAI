const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_API_BASE_URL = 'http://localhost:8000/api/v1';

const apiBaseUrl = (process.env.SAIHAI_API_BASE_URL || '').trim() || DEFAULT_API_BASE_URL;
const authToken = (process.env.SAIHAI_AUTH_TOKEN || '').trim();
const logLevel = (process.env.SAIHAI_LOG_LEVEL || '').trim().toLowerCase();
const logToServer = (process.env.SAIHAI_LOG_TO_SERVER || '').trim().toLowerCase();
const serverLogLevel = (process.env.SAIHAI_SERVER_LOG_LEVEL || '').trim().toLowerCase();

const config = {
  apiBaseUrl,
  authToken,
  logLevel: logLevel || undefined,
  logToServer: logToServer || undefined,
  serverLogLevel: serverLogLevel || undefined,
};

const outputPath = path.join(process.cwd(), 'src', 'assets', 'runtime-config.json');
fs.writeFileSync(outputPath, `${JSON.stringify(config, null, 2)}\n`);

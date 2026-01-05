const fs = require('node:fs');
const path = require('node:path');

const ENV_PATHS = [
  path.join(process.cwd(), '.env'),
  path.resolve(__dirname, '..', '..', '.env')
];

const loadEnv = () => {
  for (const envPath of ENV_PATHS) {
    if (!fs.existsSync(envPath)) continue;
    const contents = fs.readFileSync(envPath, 'utf8');
    for (const rawLine of contents.split(/\r?\n/)) {
      let line = rawLine.trim();
      if (!line || line.startsWith('#')) continue;
      if (line.startsWith('export ')) line = line.slice(7).trim();
      const idx = line.indexOf('=');
      if (idx === -1) continue;
      const key = line.slice(0, idx).trim();
      let value = line.slice(idx + 1).trim();
      if (!key) continue;
      if (
        value.length >= 2 &&
        ((value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'")))
      ) {
        value = value.slice(1, -1);
      }
      if (process.env[key] === undefined) {
        process.env[key] = value;
      }
    }
    break;
  }
};

loadEnv();

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

// 9Router Proxy Preload Script
// Forces all outgoing fetch() calls in 9Router to route through local Privoxy HTTP proxy (127.0.0.1:40001 -> Cloudflare WARP)
let undici;
try {
  undici = require('/usr/lib/node_modules/undici');
} catch (e) {
  try {
    undici = require('/usr/local/lib/node_modules/undici');
  } catch (e2) {
    undici = require('undici');
  }
}
const { setGlobalDispatcher, ProxyAgent } = undici;

const proxyUrl = process.env.HTTP_PROXY || 'http://127.0.0.1:40001';
try {
  const dispatcher = new ProxyAgent(proxyUrl);
  setGlobalDispatcher(dispatcher);
  console.log('[9Router-Proxy] Global ProxyAgent (HTTP) registered successfully to', proxyUrl);
} catch (err) {
  console.error('[9Router-Proxy] Failed to register ProxyAgent:', err);
}

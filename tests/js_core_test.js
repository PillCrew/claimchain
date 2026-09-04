// Temporary harness: extracts the pure engine <script> from docs/index.html
// and asserts the JS port matches the Python extraction engine on key cases.
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'docs', 'index.html'), 'utf8');
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (blocks.length < 1) { console.error('no inline script found'); process.exit(1); }

// First <script> is the pure engine; it has no DOM references.
const src = blocks[0];
if (/document|getElementById|addEventListener/.test(src)) {
  console.error('first script block unexpectedly references DOM');
  process.exit(1);
}

// Evaluate in a fake global context so `globalThis` is available.
const sandbox = { console, fetch, Date, Math, parseFloat, isNaN, encodeURIComponent };
sandbox.globalThis = sandbox;
const fn = new Function('globalThis', src + '\nreturn globalThis.claimchain;');
const cc = fn(sandbox);

let failures = 0;
function check(name, cond, detail) {
  if (cond) { console.log('  ok  ' + name); }
  else { failures++; console.log('FAIL  ' + name + (detail ? '  -> ' + detail : '')); }
}

// 1. direction word flips sign
let claims = cc.extractClaims('down 12.4% in 24h', 'BONK');
check('direction sign', claims.length === 1 && claims[0].metric === 'change_24h' && claims[0].value === -12.4,
  JSON.stringify(claims));

// 2. noun BEFORE figure money
claims = cc.extractClaims('mcap $608.6K · volume $269.3K', 'BONK');
check('noun-before money count', claims.length === 2, JSON.stringify(claims));
const mcap = claims.find(c => c.metric === 'market_cap');
const vol = claims.find(c => c.metric === 'volume');
check('noun-before market_cap', mcap && mcap.value === 608600, JSON.stringify(mcap));
check('noun-before volume', vol && vol.value === 269300, JSON.stringify(vol));

// 3. comma thousands
claims = cc.extractClaims('mcap $1,234,567', 'BONK');
check('comma thousands', claims.length === 1 && claims[0].value === 1234567, JSON.stringify(claims));

// 3b. comma thousands BEFORE "market cap" (m must not be eaten as M magnitude)
claims = cc.extractClaims('a $5,000,000 market cap', 'BONK');
const mcapAfter = claims.find(c => c.metric === 'market_cap');
check('comma thousands before market cap', claims.length === 1 && mcapAfter && mcapAfter.value === 5000000, JSON.stringify(claims));

// 4. "in the last 24h" window
claims = cc.extractClaims('up 3.1% in the last 24h', 'BONK');
check('in-the-last window', claims.length === 1 && claims[0].metric === 'change_24h' && claims[0].value === 3.1, JSON.stringify(claims));

// 5. "1d" is not age (mirrors Python test_change_1d_is_not_age)
claims = cc.extractClaims('+5.2% 1d', 'BONK');
check('1d is change, not age', claims.some(c => c.metric === 'change_24h' && c.value === 5.2) && !claims.some(c => c.metric === 'age_days'), JSON.stringify(claims));

// 6. age extraction still works
claims = cc.extractClaims('1347d old', 'BONK');
check('age days', claims.some(c => c.metric === 'age_days' && c.value === 1347), JSON.stringify(claims));

// 7. vol/liq ratio
claims = cc.extractClaims('141x vol/liq', 'BONK');
check('vol/liq ratio', claims.some(c => c.metric === 'volume_liquidity_ratio' && c.value === 141), JSON.stringify(claims));

// 8. verifyClaims on fake truth
const truth = { priceUsd: 0.00005, marketCap: 1.5e9, volumeUsd: 1.7e8, liquidityUsd: 1.2e6, ageSeconds: 1347 * 86400, change24h: 3.1 };
claims = cc.extractClaims('$1.50B mcap · $170M volume · $1.2M liquidity · price $0.00005 · 1347d old · 141x vol/liq · +3.1% 24h', 'BONK');
const report = cc.verifyClaims(claims, truth);
check('verify verdicts count', report.verdicts.length >= 7, report.verdicts.length);
const bad = report.verdicts.filter(v => v.verdict !== 'VERIFIED');
check('all verified vs exact truth', bad.length === 0, JSON.stringify(bad));

// 9. contradicted detection
const lie = cc.extractClaims('$9.9B mcap', 'BONK');
const r2 = cc.verifyClaims(lie, truth);
check('contradiction detected', r2.verdicts[0].verdict === 'CONTRADICTED', JSON.stringify(r2.verdicts));

if (failures) { console.log('\n' + failures + ' failure(s)'); process.exit(1); }
console.log('\nall js-core checks passed');

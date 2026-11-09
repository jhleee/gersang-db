// Gersang DB & Market Viewer Application
let monstersData = [];
let dropsIndexData = {};
let dungeonsData = [];
let marketData = { items: [], servers: [] };

let currentServerId = 10; // Default: 비호
let currentServerName = '비호';
let currentTab = 'items';
let currentItemFilter = 'all';
let currentMonsterElemFilter = 'all';

// Init
document.addEventListener('DOMContentLoaded', async () => {
  initServerSelector();
  initTabs();
  initCalculators();
  await loadData();
});

// Server Mapping & Selector
const SERVERS = [
  { id: 1, name: '백호', type: '3대도시' },
  { id: 2, name: '주작', type: '3대도시' },
  { id: 3, name: '현무', type: '3대도시' },
  { id: 4, name: '청룡', type: '일반' },
  { id: 5, name: '봉황', type: '일반' },
  { id: 6, name: '해태', type: '일반' },
  { id: 7, name: '세종', type: '일반' },
  { id: 8, name: '신구', type: '일반' },
  { id: 9, name: '단군', type: '일반' },
  { id: 10, name: '비호', type: '일반 (현재 선택)' },
  { id: 11, name: '태극', type: '일반' },
  { id: 12, name: '화랑', type: '일반' },
  { id: 13, name: '태왕', type: '일반' }
];

function initServerSelector() {
  const select = document.getElementById('globalServerSelect');
  if (!select) return;

  const saved = localStorage.getItem('gersang_server_id');
  if (saved) {
    currentServerId = parseInt(saved, 10);
    const found = SERVERS.find(s => s.id === currentServerId);
    if (found) currentServerName = found.name;
  }

  select.innerHTML = SERVERS.map(s => 
    `<option value="${s.id}" ${s.id === currentServerId ? 'selected' : ''}>${s.name} (${s.type})</option>`
  ).join('');

  select.addEventListener('change', (e) => {
    currentServerId = parseInt(e.target.value, 10);
    const found = SERVERS.find(s => s.id === currentServerId);
    currentServerName = found ? found.name : '비호';
    localStorage.setItem('gersang_server_id', currentServerId);
    
    // Update badge in banner
    const badge = document.getElementById('selectedServerBadge');
    if (badge) badge.textContent = `${currentServerName} 서버`;

    // Re-render current view with updated server links
    if (currentTab === 'items') renderItems();
    if (currentTab === 'guide') renderNewbieGuide();
  });

  const badge = document.getElementById('selectedServerBadge');
  if (badge) badge.textContent = `${currentServerName} 서버`;
}

// Tabs
function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const tabId = btn.getAttribute('data-tab');
      currentTab = tabId;
      const targetPane = document.getElementById(`tab-${tabId}`);
      if (targetPane) targetPane.classList.add('active');

      if (tabId === 'items') renderItems();
      if (tabId === 'monsters') renderMonsters();
      if (tabId === 'dungeons') renderDungeons();
      if (tabId === 'guide') renderNewbieGuide();
    });
  });
}

// Load Data Files
async function loadData() {
  try {
    const [monstersRes, dropsRes, dungeonsRes, marketRes] = await Promise.all([
      fetch('data/monsters.json').then(r => r.json()),
      fetch('data/drops_index.json').then(r => r.json()),
      fetch('data/dungeons.json').then(r => r.json()),
      fetch('data/market_snapshot.json').then(r => r.json())
    ]);

    monstersData = monstersRes || [];
    dropsIndexData = dropsRes || {};
    dungeonsData = dungeonsRes || [];
    marketData = marketRes || { items: [] };

    document.getElementById('statMonstersCount').textContent = `${monstersData.length.toLocaleString()}종`;
    document.getElementById('statItemsCount').textContent = `${Object.keys(dropsIndexData).length.toLocaleString()}종`;
    document.getElementById('statDungeonsCount').textContent = `${dungeonsData.length.toLocaleString()}곳`;

    // Initial Render
    renderItems();
    initItemSearch();
    initMonsterSearch();
  } catch (err) {
    console.error('Data load error:', err);
    document.getElementById('itemsContainer').innerHTML = `
      <div style="padding: 2rem; text-align: center; color: #ef4444;">
        ⚠️ 데이터를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 새로고침 해주세요.<br>
        <small style="color: #64748b;">${err.message}</small>
      </div>
    `;
  }
}

// 1. Items Section
function initItemSearch() {
  const input = document.getElementById('itemSearchInput');
  if (input) {
    input.addEventListener('input', (e) => {
      renderItems(e.target.value.trim());
    });
  }

  const filterBtns = document.querySelectorAll('.item-filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentItemFilter = btn.getAttribute('data-category');
      renderItems(input ? input.value.trim() : '');
    });
  });
}

function renderItems(query = '') {
  const container = document.getElementById('itemsContainer');
  if (!container) return;

  const marketMap = {};
  marketData.items.forEach(it => { marketMap[it.name] = it; });

  // Get list of all unique item names
  let itemNames = Object.keys(dropsIndexData);

  // If search query is empty and category is not all, prioritize market snapshot items
  if (!query && currentItemFilter === 'all') {
    // Show market items first, then others
    const marketNames = marketData.items.map(i => i.name);
    const restNames = itemNames.filter(n => !marketMap[n]);
    itemNames = [...marketNames, ...restNames];
  } else if (!query && currentItemFilter !== 'all') {
    itemNames = marketData.items.filter(i => i.category === currentItemFilter).map(i => i.name);
  }

  // Search filter
  if (query) {
    const q = query.toLowerCase();
    itemNames = itemNames.filter(name => {
      if (name.toLowerCase().includes(q)) return true;
      // Also search if monsters drop it
      const monsters = dropsIndexData[name] || [];
      return monsters.some(m => m.name.toLowerCase().includes(q) || (m.dungeon && m.dungeon.toLowerCase().includes(q)));
    });
  }

  if (itemNames.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; padding: 3rem; text-align: center; color: var(--text-muted);">
        🔍 검색 결과가 없습니다. 다른 검색어를 입력해 보세요.
      </div>
    `;
    return;
  }

  // Render top 48 items
  const renderList = itemNames.slice(0, 48);
  container.innerHTML = renderList.map(name => {
    const mInfo = marketMap[name];
    const dropMonsters = dropsIndexData[name] || [];

    const gerineeLink = `https://gerinee.com/trade?server=${currentServerId}&item=${encodeURIComponent(name)}`;
    const geotaLink = `https://geota.co.kr`;

    return `
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <span>📦</span>
            <span>${name}</span>
          </div>
          ${mInfo ? `<span class="badge badge-gold">${mInfo.category}</span>` : `<span class="badge badge-blue">드랍 ${dropMonsters.length}종</span>`}
        </div>

        ${mInfo ? `
          <div class="price-box">
            <div class="price-item highlight">
              <label>최저가</label>
              <strong>${formatMoney(mInfo.min_price)}</strong>
            </div>
            <div class="price-item">
              <label>평균가</label>
              <strong>${formatMoney(mInfo.avg_price)}</strong>
            </div>
            <div class="price-item">
              <label>매물</label>
              <strong>${mInfo.stock.toLocaleString()}개</strong>
            </div>
          </div>
          <div style="font-size: 0.75rem; color: var(--accent-cyan); margin-bottom: 0.5rem;">
            💡 ${mInfo.tip || mInfo.desc}
          </div>
        ` : `
          <div style="font-size: 0.8rem; color: var(--text-muted); margin: 0.5rem 0;">
            실시간 육의전 조회 버튼을 눌러 ${currentServerName} 서버 매물을 바로 확인하세요.
          </div>
        `}

        <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.5rem;">
          <strong>출현 몬스터 (${dropMonsters.length}곳):</strong>
        </div>
        <div class="drop-tag-list">
          ${dropMonsters.slice(0, 5).map(m => `
            <span class="drop-tag" onclick="switchMonsterSearch('${escapeQuotes(m.name)}')">
              ${m.name} <small style="color:var(--text-muted)">(${m.dungeon || '필드'})</small>
            </span>
          `).join('')}
          ${dropMonsters.length > 5 ? `<span class="drop-tag" style="color:var(--accent-gold);">+${dropMonsters.length - 5}곳 더보기</span>` : ''}
        </div>

        <div class="card-actions">
          <a href="${gerineeLink}" target="_blank" rel="noopener" class="btn btn-primary btn-full">
            <span>🏛️ 육의전 조회 (${currentServerName})</span>
            <span>↗</span>
          </a>
        </div>
      </div>
    `;
  }).join('');
}

// 2. Monsters Section
function initMonsterSearch() {
  const input = document.getElementById('monsterSearchInput');
  if (input) {
    input.addEventListener('input', () => renderMonsters());
  }

  const elemBtns = document.querySelectorAll('.elem-filter-btn');
  elemBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      elemBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentMonsterElemFilter = btn.getAttribute('data-elem');
      renderMonsters();
    });
  });
}

function renderMonsters() {
  const container = document.getElementById('monstersContainer');
  if (!container) return;

  const query = (document.getElementById('monsterSearchInput')?.value || '').trim().toLowerCase();
  
  let list = monstersData;

  // Element filter
  if (currentMonsterElemFilter !== 'all') {
    list = list.filter(m => (m.element || '무') === currentMonsterElemFilter);
  }

  // Text search
  if (query) {
    list = list.filter(m => 
      m.name.toLowerCase().includes(query) ||
      (m.dungeon && m.dungeon.toLowerCase().includes(query)) ||
      (m.drops && m.drops.some(d => d.toLowerCase().includes(query)))
    );
  }

  if (list.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; padding: 3rem; text-align: center; color: var(--text-muted);">
        🔍 일치하는 몬스터가 없습니다.
      </div>
    `;
    return;
  }

  const renderList = list.slice(0, 40);
  container.innerHTML = renderList.map(m => {
    const elemColor = getElemColor(m.element);
    const elemName = m.element ? `${m.element}(${m.element_raw || ''})` : '무속성';
    const hitRes = m.hit_res !== null ? `${m.hit_res}%` : '—';
    const magRes = m.mag_res !== null ? `${m.mag_res}%` : '—';
    const hpStr = m.hp ? m.hp.toLocaleString() : '—';
    const expStr = m.exp ? m.exp.toLocaleString() : '—';

    // Resist reduction calculation: 0.16 * res + 57%
    let dmgReduction = null;
    if (m.mag_res !== null) {
      dmgReduction = Math.min(98.6, (0.16 * m.mag_res + 57)).toFixed(1);
    }

    return `
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <span style="color: ${elemColor}; font-weight: 800;">[${elemName}]</span>
            <span>${m.name}</span>
          </div>
          <span class="badge" style="background: ${elemColor}22; color: ${elemColor}; border: 1px solid ${elemColor}44;">
            ${m.grade ? m.grade + '등급' : '일반'}
          </span>
        </div>

        <div class="monster-meta">
          <div>📍 <strong>위치:</strong> ${m.dungeon || m.area || '전체 필드'}</div>
          <div>❤️ <strong>체력(HP):</strong> ${hpStr} | 🌟 <strong>경험치:</strong> ${expStr}</div>
          <div>🛡️ <strong>타격저항:</strong> ${hitRes} | 🔮 <strong>마법저항:</strong> ${magRes}</div>
          ${dmgReduction ? `<div style="color: var(--accent-gold); font-size: 0.75rem;">💥 기본 데미지 감소율: <strong>${dmgReduction}%</strong> (주박/허영 필수)</div>` : ''}
        </div>

        <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.5rem;">
          <strong>드랍 아이템 (${(m.drops || []).length}개):</strong>
        </div>
        <div class="drop-tag-list">
          ${(m.drops || []).map(drop => `
            <span class="drop-tag" onclick="switchItemSearch('${escapeQuotes(drop)}')">
              ${drop}
            </span>
          `).join('')}
        </div>

        <div class="card-actions">
          <button class="btn btn-outline btn-full" onclick="openCombatModal('${escapeQuotes(m.name)}', ${m.mag_res || 0}, ${m.hp || 0})">
            ⚔️ 데미지/저깍 시뮬레이션
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// 3. Newbie 190 Ho-sun Guide Section
function renderNewbieGuide() {
  const container = document.getElementById('newbieGuideContainer');
  if (!container) return;

  const spots = [
    {
      name: '유명계 3층 — 이무기 & 염라대왕',
      rank: '1순위 돈벌이 / 안전성 S',
      rankBadge: 'badge-gold',
      target: '이무기(HP 6,000) · 염라대왕(HP 14,000)',
      ttk: '폭뢰격 2방 컷 (100% 스턴, 사망 위험 0%)',
      income: '시간당 2,500만 ~ 3,500만 냥',
      exp: '마리당 4,100 ~ 8,000',
      keyDrops: ['유명계석 (128~131만)', '상급정수 (245~316만)', '이무기의비늘 (59~90만)'],
      pros: '뇌 빼고 유튜브 보면서 안전하게 자본금 축적. 비호 서버 유석 회전율 매우 빠름.',
      tip: '짭호선 끝나기 전 본호선 증서나 신수 근원 맞출 때 가장 안정적인 국민 코스.'
    },
    {
      name: '대둔산 1층 — 어린도철',
      rank: '레벨업 + 지전 밸런스 A+',
      rankBadge: 'badge-blue',
      target: '어린도철 (HP 60,000 / 마저 235%)',
      ttk: '폭뢰격 3~4방 컷',
      income: '시간당 3,000만 ~ 4,500만 냥 (흉혼 대박 시 급상승)',
      exp: '마리당 22,000 (누에의 6배)',
      keyDrops: ['흉수의혼 (228~252만)', '상급정수 (245~316만)', '도철의어깨뿔 (상재)'],
      pros: '환수(누에)보다 경험치가 압도적으로 높아 200~210렙까지 고속 육성 가능.',
      tip: '흉수의혼이 비호 서버에서 230~250만 냥대에 꾸준히 매입되므로 뉴비 졸업 사냥터로 최적.'
    },
    {
      name: '귀곡성 3층 / 대둔산 2층 — 누에 & 기',
      rank: '단가 극대화 / 1초 컷 A',
      rankBadge: 'badge-purple',
      target: '누에 · 기 (HP 6,000 / 마저 190%)',
      ttk: '폭뢰격 1~2방 컷',
      income: '시간당 2,500만 ~ 3,500만 냥',
      exp: '마리당 3,400 (매우 낮음)',
      keyDrops: ['환수의혼 (245~271만)', '상급정수 (245~316만)', '낡은일타홍경대'],
      pros: '환혼 단가가 250만 냥대로 흉혼보다 약간 높음. 피통이 6천이라 누르면 사망.',
      tip: '경험치가 너무 낮아 레벨업은 안 되니, 오직 환수의혼 캐서 지전만 모으고 싶을 때 추천.'
    },
    {
      name: '검은상단 주둔지 — 중독된삼문',
      rank: '순수 상재 + 경험치 A',
      rankBadge: 'badge-green',
      target: '중독된삼문 (HP 70,000 / 마저 230%)',
      ttk: '폭뢰격 3~4방 컷',
      income: '시간당 2,500만 ~ 3,000만 냥 (즉시 환금 상재 중심)',
      exp: '마리당 20,000',
      keyDrops: ['낡은귀면도 (상재)', '생명의정수 (120~133만)', '영혼석(喜)'],
      pros: '육의전에 매물 올려두고 팔리길 기다릴 필요 없이 상재로 지전이 바로바로 꽂힘.',
      tip: '각뇌공 뇌전벽으로 본캐 쪽 통로 막고 폭뢰격 치면 노피격 사냥 가능.'
    },
    {
      name: '얼음성 1층 — 얼음게 & 거대얼음나무',
      rank: '210렙 초고속 달성 S',
      rankBadge: 'badge-gold',
      target: '얼음게(HP 14만/마저 245%) · 거대얼음나무(HP 20만/마저 260%)',
      ttk: '폭뢰격 5~7방 컷 (주박 200렙+ 필수)',
      income: '시간당 2,000만 ~ 2,800만 냥',
      exp: '마리당 36,000 ~ 48,000 (최고 수준)',
      keyDrops: ['생명의정수 (120~133만)', '혈응조도 (고액 상재)', '차가운 영혼석'],
      pros: '210렙(태황 세트/본호선 착용 레벨)을 최단기로 뚫을 수 있는 경험치 명당.',
      tip: '190렙 짭호선은 몬스터에게 닿으면 즉사하므로 도술사 마나 관리와 각뇌공 뇌전벽 필수!'
    }
  ];

  container.innerHTML = `
    <div class="guide-banner">
      <h2>⚡ 190렙 짭호선(폭뢰격) 뉴비 맞춤 파밍 가이드 (${currentServerName} 서버 기준)</h2>
      <p>
        짭호선(기간제)은 시간이 돈입니다! <strong>"기간 내에 본호선/신수 자본금을 모을 것인가"</strong>, 
        <strong>"태황 세트 착용선인 210렙을 먼저 뚫을 것인가"</strong>에 맞춰 사냥터를 선택하세요.
      </p>
    </div>

    ${spots.map((s, idx) => `
      <div class="spot-card">
        <div class="spot-header">
          <div>
            <span style="font-size: 1.1rem; font-weight: 800;">${idx + 1}. ${s.name}</span>
          </div>
          <span class="badge ${s.rankBadge}">${s.rank}</span>
        </div>
        <div class="spot-body">
          <div>
            <ul class="spot-spec-list">
              <li><span class="label">🎯 목표 몬스터</span><span class="value">${s.target}</span></li>
              <li><span class="label">⚡ 사냥 난이도 (TTK)</span><span class="value">${s.ttk}</span></li>
              <li><span class="label">💰 시간당 예상 수익</span><span class="value" style="color:var(--accent-gold);">${s.income}</span></li>
              <li><span class="label">📈 경험치 획득량</span><span class="value">${s.exp}</span></li>
            </ul>
          </div>
          <div>
            <div style="font-size: 0.8rem; font-weight: 700; color: var(--accent-cyan); margin-bottom: 0.4rem;">
              💎 핵심 드랍템:
            </div>
            <div class="drop-tag-list" style="margin-bottom: 0.75rem;">
              ${s.keyDrops.map(d => `<span class="drop-tag" style="background:#1e293b; color:#fbbf24;">${d}</span>`).join('')}
            </div>
            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.4rem;">
              ✨ <strong>장점:</strong> ${s.pros}
            </p>
            <p style="font-size: 0.8rem; color: var(--accent-gold);">
              💡 <strong>팁:</strong> ${s.tip}
            </p>
          </div>
        </div>
      </div>
    `).join('')}

    <div class="calc-card" style="margin-top: 1.5rem;">
      <h3 style="margin-bottom: 0.5rem; color: #60a5fa;">💡 190렙 짭호선 3대 생존 & 딜 세팅 법칙</h3>
      <ol style="padding-left: 1.25rem; font-size: 0.85rem; color: var(--text-secondary); line-height: 1.8;">
        <li><strong>주박청음(음양사):</strong> 짭호선 폭뢰격은 마법 데미지입니다. 음양사의 주박청음 레벨(최소 200렙 권장)이 데미지의 70% 이상을 좌우합니다.</li>
        <li><strong>각뇌공 뇌전벽:</strong> 190렙 본캐는 몬스터 평타 한 대에 터집니다. 각뇌공의 뇌전벽(길막)으로 몬스터 접근을 원천 차단하고 원거리에서 폭뢰격을 난사하세요.</li>
        <li><strong>추천 테크트리:</strong> [유명계 이무기]로 안전하게 3~5억 냥 종잣돈 마련 ➔ [대둔산 어린도철]로 200렙 달성 ➔ [얼음성]에서 210렙 완성!</li>
      </ol>
    </div>
  `;
}

// 4. Dungeons Section
function renderDungeons() {
  const container = document.getElementById('dungeonsContainer');
  if (!container) return;

  container.innerHTML = dungeonsData.slice(0, 50).map(d => {
    return `
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <span>🗺️</span>
            <span>${d.name}</span>
          </div>
          <span class="badge badge-blue">${d.area || '던전'}</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.75rem;">
          <div>🏢 <strong>층수:</strong> ${d.floors || '단일'}</div>
          <div>🚪 <strong>입장 조건:</strong> ${d.entry_condition || '제한 없음'}</div>
          <div style="margin-top: 0.35rem; color: var(--text-muted); font-size: 0.75rem;">${d.official_desc || ''}</div>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-secondary);">
          <strong>서식 몬스터 (${(d.monsters || []).length}종):</strong>
        </div>
        <div class="drop-tag-list">
          ${(d.monsters || []).slice(0, 6).map(mName => `
            <span class="drop-tag" onclick="switchMonsterSearch('${escapeQuotes(mName)}')">${mName}</span>
          `).join('')}
          ${(d.monsters || []).length > 6 ? `<span class="drop-tag" style="color:var(--accent-gold);">+${(d.monsters || []).length - 6}종</span>` : ''}
        </div>
      </div>
    `;
  }).join('');
}

// 5. Combat / Debuff Calculator
function initCalculators() {
  const resInput = document.getElementById('calcTargetRes');
  const debuffInput = document.getElementById('calcDebuffPercent');

  const updateCalc = () => {
    const res = parseFloat(resInput?.value || 0);
    const debuff = parseFloat(debuffInput?.value || 0);

    const effectiveRes = Math.max(0, res - debuff);
    
    // Formula: 0.16 * res + 57 (capped at 98.6%)
    const rawRed = Math.min(98.6, 0.16 * res + 57);
    const debuffedRed = Math.min(98.6, 0.16 * effectiveRes + 57);

    const dmgMultiplier = ((100 - debuffedRed) / (100 - rawRed)).toFixed(2);

    const resResult = document.getElementById('calcResultBox');
    if (resResult) {
      resResult.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; text-align: center;">
          <div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">적용 전 피해 감소율</div>
            <strong style="font-size: 1.1rem; color: #ef4444;">${rawRed.toFixed(1)}%</strong>
          </div>
          <div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">저항 깎기 적용 후</div>
            <strong style="font-size: 1.1rem; color: #10b981;">${debuffedRed.toFixed(1)}%</strong>
          </div>
          <div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">실제 데미지 증가율</div>
            <strong style="font-size: 1.25rem; color: var(--accent-gold);">x ${dmgMultiplier}배</strong>
          </div>
        </div>
      `;
    }
  };

  if (resInput) resInput.addEventListener('input', updateCalc);
  if (debuffInput) debuffInput.addEventListener('input', updateCalc);
  updateCalc();
}

// Helper: Switch to items search
window.switchItemSearch = function(itemName) {
  const itemTabBtn = document.querySelector('.tab-btn[data-tab="items"]');
  if (itemTabBtn) itemTabBtn.click();

  const searchInput = document.getElementById('itemSearchInput');
  if (searchInput) {
    searchInput.value = itemName;
    renderItems(itemName);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
};

// Helper: Switch to monsters search
window.switchMonsterSearch = function(monsterName) {
  const monTabBtn = document.querySelector('.tab-btn[data-tab="monsters"]');
  if (monTabBtn) monTabBtn.click();

  const searchInput = document.getElementById('monsterSearchInput');
  if (searchInput) {
    searchInput.value = monsterName;
    renderMonsters();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
};

window.openCombatModal = function(name, res, hp) {
  const calcTabBtn = document.querySelector('.tab-btn[data-tab="calculator"]');
  if (calcTabBtn) calcTabBtn.click();

  const resInput = document.getElementById('calcTargetRes');
  if (resInput) {
    resInput.value = res;
    resInput.dispatchEvent(new Event('input'));
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

// Helpers
function formatMoney(amount) {
  if (!amount) return '—';
  if (amount >= 100000000) {
    const eok = (amount / 100000000).toFixed(1);
    return `${eok}억 냥`;
  }
  if (amount >= 10000) {
    const man = Math.round(amount / 10000);
    return `${man.toLocaleString()}만 냥`;
  }
  return `${amount.toLocaleString()}냥`;
}

function getElemColor(elem) {
  switch(elem) {
    case '불': return 'var(--elem-fire)';
    case '물': return 'var(--elem-water)';
    case '바람': return 'var(--elem-wind)';
    case '뇌전': return 'var(--elem-thunder)';
    case '땅': return 'var(--elem-earth)';
    default: return 'var(--elem-none)';
  }
}

function escapeQuotes(str) {
  return (str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

/* desktop/plugin.js — Hermes Desktop plugin (Electron) для HermesDashboard.
   Регистрирует вкладку /hermes-dashboard с iframe, указывающим на standalone backend.
*/
import { registerMany, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk';
import { h } from 'react';

const BACKEND_URL = 'http://127.0.0.1:5557';
const STANDALONE_URL = 'http://127.0.0.1:5557/';  // root — мы не отдаём HTML; см. notice

function Page() {
  // Простая заглушка: backend не отдаёт HTML, поэтому iframe будет пустой.
  // Пользователю рекомендуется открывать дашборд через start.bat в браузере.
  // (Standalone UI = dist/index.html — см. README)
  return h('div', {
    style: {
      padding: 20, fontFamily: 'Manrope, sans-serif',
      color: '#E8E2D0', background: '#0B0810',
      height: '100%', overflowY: 'auto',
    },
  },
    h('h2', { style: { color: '#C9A24A', fontFamily: 'Cinzel, serif' } },
      'Hermes Dashboard'),
    h('p', null,
      'Backend стартован на ', h('code', { style: { color: '#2DE2FF' } }, BACKEND_URL),
      '. Откройте в браузере: ', h('a', { href: 'http://127.0.0.1:5557', target: '_blank', style: { color: '#2DE2FF' } }, 'http://127.0.0.1:5557')),
    h('p', { style: { color: '#9A8FB0', fontSize: 12 } },
      'API эндпоинты: /snapshot, /runs, /logs, /connections, /budget, /ws'),
    h('hr', { style: { border: 'none', borderTop: '1px solid #8C6B2A' } }),
    h('p', { style: { color: '#9A8FB0', fontSize: 11 } },
      'Для standalone UI запустите start.bat, затем откройте http://127.0.0.1:5557 в браузере.'),
  );
}

export default {
  id: 'hermes-dashboard',
  defaultEnabled: true,
  register(ctx) {
    ctx.registerMany([
      {
        id: 'hermes-dashboard-page',
        area: ROUTES_AREA,
        data: { path: '/hermes-dashboard', label: 'Hermes Dashboard' },
        render: () => h('div', { className: 'hermes-dashboard-frame' }, h(Page)),
      },
      {
        id: 'hermes-dashboard-nav',
        area: SIDEBAR_NAV_AREA,
        order: 50,
        data: {
          codicon: 'dashboard',
          label: 'Dashboard',
          path: '/hermes-dashboard',
        },
      },
    ]);
  },
};
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { authRedirect, loginUrl, safeNextPath } from './auth-rules.ts';

const on = { enabled: true };

describe('authRedirect', () => {
  it('does nothing while auth_cookie_enforce is off', () => {
    assert.equal(authRedirect('/dashboard', false), null);
    assert.equal(authRedirect('/login', true, { enabled: false }), null);
  });

  it('sends signed-out visitors of app pages to sign in, keeping path and query', () => {
    assert.equal(authRedirect('/dashboard', false, on), '/login?next=%2Fdashboard');
    assert.equal(
      authRedirect('/dashboard/projects/42', false, { ...on, search: '?tab=clips' }),
      '/login?next=%2Fdashboard%2Fprojects%2F42%3Ftab%3Dclips',
    );
    assert.equal(authRedirect('/admin/users', false, { ...on, search: 'q=a' }), '/login?next=%2Fadmin%2Fusers%3Fq%3Da');
  });

  it('lets OAuth returns, email links and public pages through', () => {
    for (const path of ['/login/google', '/dashboard/connect/youtube', '/unsubscribe', '/data-deletion', '/', '/terms', '/login', '/dashboardx']) {
      assert.equal(authRedirect(path, false, on), null, path);
    }
  });

  it('sends signed-in visitors of the sign-in pages onwards', () => {
    assert.equal(authRedirect('/login', true, on), '/dashboard');
    assert.equal(authRedirect('/signup/', true, on), '/dashboard');
    assert.equal(authRedirect('/login', true, { ...on, search: '?next=%2Fdashboard%2Freels' }), '/dashboard/reels');
    assert.equal(authRedirect('/login', true, { ...on, search: '?next=https://evil.example' }), '/dashboard');
  });

  it('leaves signed-in visitors alone everywhere else', () => {
    assert.equal(authRedirect('/dashboard', true, on), null);
    assert.equal(authRedirect('/', true, on), null);
  });
});

describe('safeNextPath', () => {
  it('keeps same-origin paths with query and hash', () => {
    assert.equal(safeNextPath('/dashboard/projects?sort=new#top'), '/dashboard/projects?sort=new#top');
  });

  it('refuses anything that could leave the site or loop', () => {
    for (const raw of [null, '', 'dashboard', 'https://evil.example', '//evil.example', '/\\evil.example', '/%0d/x\n', '/login', '/signup?next=/x', '/login/google', '/v2/dashboard']) {
      assert.equal(safeNextPath(raw), null, String(raw));
    }
  });
});

describe('loginUrl', () => {
  it('adds next and reason only when present and safe', () => {
    assert.equal(loginUrl(null), '/login');
    assert.equal(loginUrl('//evil.example'), '/login');
    assert.equal(loginUrl('/dashboard', 'expired'), '/login?next=%2Fdashboard&reason=expired');
  });
});

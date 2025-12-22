const GITHUB_OWNER = 'StepanPotiienko';
const GITHUB_REPO = 'google-contacts-notion-integration';
const WORKFLOW_FILE = 'run-sync.yml';
const GITHUB_API = 'https://api.github.com';

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization"
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    console.log(`[${request.method}] ${url.pathname}`);
    console.log(`Token present: ${!!env.GITHUB_TOKEN}`);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // Handle API route explicitly to avoid assets catching POST on '/'
    if (url.pathname === "/trigger" && request.method === "POST") {
      try {
        const defaultBranch = env.DEFAULT_BRANCH || 'main';
        const endpoint = `${GITHUB_API}/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`;

        console.log(`Triggering workflow at: ${endpoint}`);
        console.log(`Branch: ${defaultBranch}`);

        const res = await fetch(endpoint, {
          method: 'POST',
          headers: {
            // GitHub REST API headers
            'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'agropride-worker/1.0',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ ref: defaultBranch })
        }
        );

        if (!res.ok) {
          const contentType = res.headers.get('content-type') || '';
          const body = contentType.includes('application/json') ? JSON.stringify(await res.json()) : (await res.text());
          console.log(`GitHub API error ${res.status} ${res.statusText}: ${body}`);

          // Helpful hints based on common statuses
          let hint = '';
          if (res.status === 404) {
            hint = 'Check workflow file name, repo access, and token repo scope.';
          } else if (res.status === 422) {
            hint = 'Ensure the workflow has `on: workflow_dispatch` and the ref branch exists.';
          } else if (res.status === 401) {
            hint = 'Token invalid/expired or missing required permissions.';
          } else if (res.status === 405) {
            hint = 'Method not allowed: verify endpoint and Accept headers.';
          }

          const message = `GitHub API Error ${res.status} ${res.statusText}. ${hint}\n${body}`.trim();
          return new Response(message, { status: res.status, headers: corsHeaders });
        }

        return new Response(JSON.stringify({ success: true }), { headers: corsHeaders });
      } catch (err) {
        return new Response(`Error: ${err}`, { status: 500, headers: corsHeaders });
      }
    }

    // Simple diagnostics: verify the token can reach GitHub without exposing secrets
    if (url.pathname === "/diag" && request.method === "GET") {
      try {
        const res = await fetch(`${GITHUB_API}/rate_limit`, {
          headers: {
            'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'agropride-worker/1.0',
            'X-GitHub-Api-Version': '2022-11-28'
          }
        });
        const body = await res.text();
        const ok = res.ok;
        const status = res.status;
        const statusText = res.statusText;
        const tokenPresent = !!env.GITHUB_TOKEN;
        return new Response(JSON.stringify({ ok, status, statusText, tokenPresent }), { headers: { ...corsHeaders, 'Content-Type': 'application/json' } });
      } catch (err) {
        return new Response(JSON.stringify({ ok: false, error: String(err) }), { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } });
      }
    }

    if (url.pathname === "/diag-hash" && request.method === "GET") {
      try {
        const token = env.GITHUB_TOKEN || '';
        const enc = new TextEncoder().encode(token);
        const digest = await crypto.subtle.digest('SHA-256', enc);
        const bytes = new Uint8Array(digest);
        const hex = [...bytes].map(b => b.toString(16).padStart(2, '0')).join('');
        // Return only a short prefix to avoid leaking too much info
        return new Response(JSON.stringify({ tokenHashPrefix: hex.slice(0, 16), tokenPresent: !!token }), { headers: { ...corsHeaders, 'Content-Type': 'application/json' } });
      } catch (err) {
        return new Response(JSON.stringify({ ok: false, error: String(err) }), { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } });
      }
    }

    // For everything else, let static assets serve if configured; otherwise 405
    if (env.ASSETS) {
      return env.ASSETS.fetch(request);
    }
    return new Response("Method Not Allowed", { status: 405, headers: corsHeaders });
  }
};

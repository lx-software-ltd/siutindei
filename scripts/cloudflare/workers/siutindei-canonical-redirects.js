/**
 * 301 www.siutindei.com to the apex, keeping the path and query.
 *
 * The legacy siutindei-www.lx-software.com host was removed from DNS, so it
 * is not a redirect target.
 */

const CANONICAL_ORIGIN = "https://siutindei.com";
const REDIRECT_HOSTS = new Set(["www.siutindei.com"]);

export function handleRequest(request) {
  const incomingUrl = new URL(request.url);
  if (!REDIRECT_HOSTS.has(incomingUrl.hostname)) {
    return fetch(request);
  }
  const redirectUrl = new URL(
    incomingUrl.pathname + incomingUrl.search,
    CANONICAL_ORIGIN,
  );
  return Response.redirect(redirectUrl.toString(), 301);
}

export default {
  async fetch(request) {
    return handleRequest(request);
  },
};

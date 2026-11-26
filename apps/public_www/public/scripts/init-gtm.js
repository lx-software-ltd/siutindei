(function initGtm() {
  function parseAllowedHosts(rawValue) {
    if (typeof rawValue !== 'string') {
      return [];
    }

    var seen = {};
    return rawValue
      .split(',')
      .map(function normalizeHost(hostValue) {
        return hostValue.trim().toLowerCase();
      })
      .filter(function isUniqueHost(hostValue) {
        if (hostValue === '' || seen[hostValue]) {
          return false;
        }
        seen[hostValue] = true;
        return true;
      });
  }

  function readAnalyticsConsent() {
    try {
      return window.localStorage.getItem('siutindei-analytics-consent');
    } catch (storageError) {
      return null;
    }
  }

  function loadGtm() {
    var allowedHosts = parseAllowedHosts(
      document.documentElement.getAttribute('data-gtm-allowed-hosts'),
    );
    var currentHost = window.location.hostname.toLowerCase();
    if (allowedHosts.length === 0 || allowedHosts.indexOf(currentHost) === -1) {
      return;
    }

    var gtmId = document.documentElement.getAttribute('data-gtm-id');
    var matched = /^GTM-[A-Z0-9]+$/.exec(gtmId || '');
    if (!matched) {
      return;
    }

    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      'gtm.start': new Date().getTime(),
      event: 'gtm.js',
    });

    var script = document.createElement('script');
    script.async = true;
    script.src =
      'https://www.googletagmanager.com/gtm.js?id=' +
      encodeURIComponent(matched[0]);
    document.head.appendChild(script);
  }

  if (readAnalyticsConsent() === 'granted') {
    loadGtm();
    return;
  }

  window.addEventListener('siutindei-analytics-consent-granted', loadGtm, {
    once: true,
  });
})();

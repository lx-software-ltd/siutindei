var UNPREFIXED = {
  '/': true,
  '/search': true,
  '/about': true,
  '/privacy': true,
  '/terms': true,
  '/activity': true,
};

function barePath(uri) {
  if (uri.length > 1 && uri.charAt(uri.length - 1) === '/') {
    return uri.slice(0, -1);
  }
  return uri;
}

function preferredLocale(request) {
  var header = request.headers && request.headers['accept-language'];
  var value = header && header.value ? String(header.value) : '';
  var bestTag = '';
  var bestQ = -1;
  var parts = value.split(',');
  var index;
  for (index = 0; index < parts.length; index += 1) {
    var piece = parts[index].replace(/^\s+|\s+$/g, '');
    if (!piece) {
      continue;
    }
    var bits = piece.split(';');
    var tag = bits[0].replace(/^\s+|\s+$/g, '').toLowerCase();
    var quality = 1;
    var paramIndex;
    for (paramIndex = 1; paramIndex < bits.length; paramIndex += 1) {
      var param = bits[paramIndex].replace(/^\s+|\s+$/g, '');
      if (param.indexOf('q=') === 0) {
        var parsed = parseFloat(param.substring(2));
        if (!isNaN(parsed)) {
          quality = parsed;
        }
      }
    }
    if (tag && quality > bestQ) {
      bestQ = quality;
      bestTag = tag;
    }
  }
  if (bestTag.indexOf('zh') === 0) {
    return 'zh-HK';
  }
  return 'en';
}

function querySuffix(request) {
  if (typeof request.rawQueryString !== 'function') {
    return '';
  }
  var raw = request.rawQueryString();
  if (!raw) {
    return '';
  }
  return '?' + raw;
}

function redirectResponse(location) {
  return {
    statusCode: 302,
    statusDescription: 'Found',
    headers: {
      location: { value: location },
    },
  };
}

// edgeVerifyRejection comes from public-www-edge-verify.js, which the stack
// prepends to this file.
function handler(event) {
  var request = event.request;
  var rejection = edgeVerifyRejection(request);
  if (rejection) {
    return rejection;
  }
  var uri = request.uri;

  if (uri.indexOf('/_next/') === 0) {
    return request;
  }

  var bare = barePath(uri);
  if (UNPREFIXED[bare]) {
    var locale = preferredLocale(request);
    var target = bare === '/' ? '/' + locale + '/' : '/' + locale + bare + '/';
    return redirectResponse(target + querySuffix(request));
  }

  if (uri.charAt(uri.length - 1) === '/') {
    request.uri = uri + 'index.html';
    return request;
  }

  if (uri.indexOf('.') === -1) {
    request.uri = uri + '/index.html';
  }

  return request;
}

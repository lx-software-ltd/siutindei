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
  var value = header && header.value ? String(header.value).toLowerCase() : '';
  if (value.indexOf('zh') !== -1) {
    return 'zh-HK';
  }
  return 'en';
}

function querySuffix(request) {
  var querystring = request.querystring || {};
  var parts = [];
  for (var key in querystring) {
    if (!Object.prototype.hasOwnProperty.call(querystring, key)) {
      continue;
    }
    var entry = querystring[key];
    if (entry && entry.multiValue) {
      for (var index = 0; index < entry.multiValue.length; index += 1) {
        parts.push(
          encodeURIComponent(key) +
            '=' +
            encodeURIComponent(entry.multiValue[index].value),
        );
      }
    } else if (entry && entry.value !== undefined) {
      parts.push(
        encodeURIComponent(key) + '=' + encodeURIComponent(entry.value),
      );
    }
  }
  return parts.length ? '?' + parts.join('&') : '';
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

function handler(event) {
  var request = event.request;
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

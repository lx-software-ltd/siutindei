/// Custom exception types for the application.
///
/// Following Flutter architecture recommendations for explicit error types
/// that can be handled differently by the UI layer.
///
/// See: https://docs.flutter.dev/app-architecture/recommendations
library;

/// Base class for all application exceptions.
///
/// Provides a common interface for error handling across layers.
sealed class AppException implements Exception {
  const AppException(this.message, [this.originalError]);

  /// Human-readable error message.
  final String message;

  /// The original error that caused this exception, if any.
  final Object? originalError;

  @override
  String toString() => '$runtimeType: $message';
}

/// Exception for network-related errors.
///
/// Thrown when network requests fail due to connectivity issues,
/// timeouts, or server errors.
final class NetworkException extends AppException {
  const NetworkException(super.message, [super.originalError]);

  /// Creates from a generic error.
  factory NetworkException.fromError(Object error) {
    return NetworkException('Network error: ${error.toString()}', error);
  }

  /// No internet connection.
  factory NetworkException.noConnection() {
    return const NetworkException('No internet connection');
  }

  /// Request timeout.
  factory NetworkException.timeout() {
    return const NetworkException('Request timed out');
  }

  /// Server error.
  factory NetworkException.serverError([int? statusCode]) {
    final msg = statusCode != null
        ? 'Server error (status $statusCode)'
        : 'Server error';
    return NetworkException(msg);
  }
}

/// Exception for data parsing/validation errors.
///
/// Thrown when data cannot be parsed or doesn't match expected format.
final class DataException extends AppException {
  const DataException(super.message, [super.originalError]);

  /// Invalid data format.
  factory DataException.invalidFormat(String details) {
    return DataException('Invalid data format: $details');
  }

  /// Missing required field.
  factory DataException.missingField(String fieldName) {
    return DataException('Missing required field: $fieldName');
  }

  /// Data validation failed.
  factory DataException.validationFailed(String details) {
    return DataException('Validation failed: $details');
  }
}

/// Exception for authentication errors.
///
/// Thrown when authentication fails or session expires.
final class AuthException extends AppException {
  const AuthException(super.message, [super.originalError]);

  /// User not authenticated.
  factory AuthException.notAuthenticated() {
    return const AuthException('User not authenticated');
  }

  /// Session expired.
  factory AuthException.sessionExpired() {
    return const AuthException('Session expired. Please sign in again.');
  }

  /// Invalid credentials.
  factory AuthException.invalidCredentials() {
    return const AuthException('Invalid credentials');
  }

  /// Account not found.
  factory AuthException.accountNotFound() {
    return const AuthException('Account not found');
  }
}

/// Exception for cache-related errors.
///
/// Thrown when cache operations fail.
final class CacheException extends AppException {
  const CacheException(super.message, [super.originalError]);

  /// Cache miss - data not found.
  factory CacheException.notFound(String key) {
    return CacheException('Cache miss for key: $key');
  }

  /// Cache expired.
  factory CacheException.expired(String key) {
    return CacheException('Cache expired for key: $key');
  }

  /// Cache write failed.
  factory CacheException.writeFailed(String key) {
    return CacheException('Failed to write cache for key: $key');
  }
}

/// Exception for business logic errors.
///
/// Thrown when business rules are violated.
final class BusinessException extends AppException {
  const BusinessException(super.message, [super.originalError]);

  /// Invalid input.
  factory BusinessException.invalidInput(String details) {
    return BusinessException('Invalid input: $details');
  }

  /// Operation not allowed.
  factory BusinessException.notAllowed(String operation) {
    return BusinessException('Operation not allowed: $operation');
  }

  /// Resource not found.
  factory BusinessException.notFound(String resource) {
    return BusinessException('$resource not found');
  }
}

/// Exception for validation errors.
///
/// Thrown when input validation fails.
final class ValidationException extends AppException {
  const ValidationException(super.message, [super.originalError]);

  /// Field validation failed.
  factory ValidationException.field(String fieldName, String reason) {
    return ValidationException('$fieldName: $reason');
  }

  /// Range validation failed.
  factory ValidationException.outOfRange(
    String fieldName, {
    num? min,
    num? max,
  }) {
    if (min != null && max != null) {
      return ValidationException('$fieldName must be between $min and $max');
    } else if (min != null) {
      return ValidationException('$fieldName must be at least $min');
    } else if (max != null) {
      return ValidationException('$fieldName must be at most $max');
    }
    return ValidationException('$fieldName is out of valid range');
  }
}

/// Exception for invalid state errors.
///
/// Thrown when an operation is attempted in an invalid state.
final class InvalidStateException extends AppException {
  const InvalidStateException(super.message, [super.originalError]);

  /// No more items available.
  factory InvalidStateException.noMoreItems() {
    return const InvalidStateException('No more items to load');
  }

  /// Operation not ready.
  factory InvalidStateException.notReady(String operation) {
    return InvalidStateException('Cannot $operation: not ready');
  }
}

/// Extension for formatting exceptions for UI display.
extension AppExceptionDisplay on AppException {
  /// Returns a user-friendly message for display.
  String get displayMessage {
    return switch (this) {
      NetworkException(:final message) => _networkMessage(message),
      AuthException() => message,
      DataException() => 'Something went wrong. Please try again.',
      CacheException() => 'Unable to load cached data.',
      BusinessException() => message,
      ValidationException() => message,
      InvalidStateException() => message,
    };
  }

  String _networkMessage(String message) {
    if (message.contains('No internet')) {
      return 'No internet connection. Please check your network.';
    }
    if (message.contains('timeout')) {
      return 'Request timed out. Please try again.';
    }
    return 'Network error. Please try again later.';
  }

  /// Returns true if this error might be resolved by retrying.
  bool get isRetryable {
    return switch (this) {
      NetworkException() => true,
      AuthException() => false,
      DataException() => false,
      CacheException() => true,
      BusinessException() => false,
      ValidationException() => false,
      InvalidStateException() => false,
    };
  }
}

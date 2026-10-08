/// Result type for representing success or failure.
///
/// Based on Flutter architecture guide's recommendation for error handling.
/// Provides a type-safe way to handle operations that can fail.
///
/// ## Usage
///
/// ```dart
/// // Creating results
/// final success = Result.ok(data);
/// final failure = Result.error(Exception('Failed'));
///
/// // Pattern matching (Dart 3)
/// switch (result) {
///   case Ok(value: final data):
///     print('Success: $data');
///   case Error(error: final e):
///     print('Error: $e');
/// }
///
/// // Convenience methods
/// final data = result.valueOrNull;
/// final error = result.errorOrNull;
/// ```
sealed class Result<T> {
  const Result();

  /// Creates a successful result.
  const factory Result.ok(T value) = Ok<T>;

  /// Creates a failed result.
  const factory Result.error(Exception error) = Error<T>;

  /// Returns true if this is a successful result.
  bool get isOk => this is Ok<T>;

  /// Returns true if this is a failed result.
  bool get isError => this is Error<T>;

  /// Returns the value if successful, null otherwise.
  T? get valueOrNull => switch (this) {
    Ok(value: final v) => v,
    Error() => null,
  };

  /// Returns the error if failed, null otherwise.
  Exception? get errorOrNull => switch (this) {
    Ok() => null,
    Error(error: final e) => e,
  };

  /// Returns the value if successful, throws the error otherwise.
  T get valueOrThrow => switch (this) {
    Ok(value: final v) => v,
    Error(error: final e) => throw e,
  };

  /// Maps the value if successful.
  Result<U> map<U>(U Function(T value) transform) => switch (this) {
    Ok(value: final v) => Result.ok(transform(v)),
    Error(error: final e) => Result.error(e),
  };

  /// Maps the value if successful, with a function that returns a Result.
  Result<U> flatMap<U>(Result<U> Function(T value) transform) => switch (this) {
    Ok(value: final v) => transform(v),
    Error(error: final e) => Result.error(e),
  };

  /// Executes callback if successful.
  Result<T> onOk(void Function(T value) callback) {
    if (this case Ok(value: final v)) {
      callback(v);
    }
    return this;
  }

  /// Executes callback if failed.
  Result<T> onError(void Function(Exception error) callback) {
    if (this case Error(error: final e)) {
      callback(e);
    }
    return this;
  }
}

/// Successful result containing a value.
final class Ok<T> extends Result<T> {
  const Ok(this.value);

  final T value;

  @override
  bool operator ==(Object other) =>
      identical(this, other) || (other is Ok<T> && other.value == value);

  @override
  int get hashCode => value.hashCode;

  @override
  String toString() => 'Ok($value)';
}

/// Failed result containing an error.
final class Error<T> extends Result<T> {
  const Error(this.error);

  final Exception error;

  @override
  bool operator ==(Object other) =>
      identical(this, other) || (other is Error<T> && other.error == error);

  @override
  int get hashCode => error.hashCode;

  @override
  String toString() => 'Error($error)';
}

/// Extension for converting nullable values to Result.
extension ResultNullableExtension<T> on T? {
  /// Converts nullable to Result, using provided error if null.
  Result<T> toResult([Exception? errorIfNull]) {
    if (this != null) {
      return Result.ok(this as T);
    }
    return Result.error(errorIfNull ?? Exception('Value is null'));
  }
}

/// Extension for converting Future to Result.
extension ResultFutureExtension<T> on Future<T> {
  /// Wraps a Future in a Result, catching exceptions.
  Future<Result<T>> toResult() async {
    try {
      return Result.ok(await this);
    } on Exception catch (e) {
      return Result.error(e);
    }
  }
}

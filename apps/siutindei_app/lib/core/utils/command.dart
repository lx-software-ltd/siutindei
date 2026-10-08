import 'package:flutter/foundation.dart';

import 'result.dart';

/// Command pattern for async operations with loading/error states.
///
/// Based on Flutter architecture guide's Command pattern.
/// Encapsulates an async operation with its state.
///
/// ## Usage
///
/// ```dart
/// // In ViewModel
/// late final searchCommand = Command1<SearchFilters, SearchResults>(_search);
///
/// Future<Result<SearchResults>> _search(SearchFilters filters) async {
///   return _repository.search(filters);
/// }
///
/// // In UI
/// final isLoading = ref.watch(
///   viewModel.select((vm) => vm.searchCommand.isRunning),
/// );
/// final error = ref.watch(viewModel.select((vm) => vm.searchCommand.error));
///
/// ElevatedButton(
///   onPressed: isLoading
///       ? null
///       : () => viewModel.searchCommand.execute(filters),
///   child: Text(isLoading ? 'Loading...' : 'Search'),
/// )
/// ```
abstract class Command<T> extends ChangeNotifier {
  Command();

  bool _isRunning = false;
  Result<T>? _result;

  /// Whether the command is currently executing.
  bool get isRunning => _isRunning;

  /// The most recent result (success or error).
  Result<T>? get result => _result;

  /// The most recent error, if any.
  Exception? get error => _result?.errorOrNull;

  /// Whether the command completed successfully.
  bool get isCompleted => _result != null && _result!.isOk;

  /// Whether the command completed with an error.
  bool get isError => _result != null && _result!.isError;

  /// Clears the result and error state.
  void clearResult() {
    _result = null;
    notifyListeners();
  }

  /// Internal method to set running state.
  @protected
  void setRunning(bool value) {
    _isRunning = value;
    notifyListeners();
  }

  /// Internal method to set result.
  @protected
  void setResult(Result<T> result) {
    _result = result;
    _isRunning = false;
    notifyListeners();
  }
}

/// Command with no arguments.
class Command0<T> extends Command<T> {
  Command0(this._action);

  final Future<Result<T>> Function() _action;

  /// Executes the command.
  Future<void> execute() async {
    if (_isRunning) return;

    setRunning(true);
    final result = await _action();
    setResult(result);
  }
}

/// Command with one argument.
class Command1<A, T> extends Command<T> {
  Command1(this._action);

  final Future<Result<T>> Function(A) _action;

  /// Executes the command with the given argument.
  Future<void> execute(A arg) async {
    if (_isRunning) return;

    setRunning(true);
    final result = await _action(arg);
    setResult(result);
  }
}

/// Command with two arguments.
class Command2<A, B, T> extends Command<T> {
  Command2(this._action);

  final Future<Result<T>> Function(A, B) _action;

  /// Executes the command with the given arguments.
  Future<void> execute(A arg1, B arg2) async {
    if (_isRunning) return;

    setRunning(true);
    final result = await _action(arg1, arg2);
    setResult(result);
  }
}

/// Extension to create commands from functions.
extension CommandExtensions<T> on Future<Result<T>> Function() {
  /// Creates a Command0 from this function.
  Command0<T> toCommand() => Command0(this);
}

# Command Pattern

The Command pattern encapsulates asynchronous operations with their loading and error states, providing a clean API for UI components.

## Overview

Commands wrap async functions and track:
- `isRunning` - Whether the operation is in progress
- `result` - The most recent Result (success or error)
- `error` - Convenience access to the error, if any

## Location

```
lib/core/utils/command.dart
```

## Command Types

### Command0 - No Arguments

```dart
class Command0<T> extends Command<T> {
  Command0(Future<Result<T>> Function() action);
  
  Future<void> execute();
}
```

### Command1 - One Argument

```dart
class Command1<A, T> extends Command<T> {
  Command1(Future<Result<T>> Function(A) action);
  
  Future<void> execute(A arg);
}
```

### Command2 - Two Arguments

```dart
class Command2<A, B, T> extends Command<T> {
  Command2(Future<Result<T>> Function(A, B) action);
  
  Future<void> execute(A arg1, B arg2);
}
```

## Basic Usage

### Creating Commands

```dart
class MyViewModel extends ChangeNotifier {
  final SearchActivitiesUseCase _searchUseCase;
  
  late final searchCommand = Command1<SearchFilters, SearchResultsEntity>(
    _performSearch,
  );
  
  Future<Result<SearchResultsEntity>> _performSearch(
    SearchFilters filters,
  ) async {
    return _searchUseCase.execute(filters);
  }
}
```

### Executing Commands

```dart
// Execute with argument
await viewModel.searchCommand.execute(filters);

// Check state
if (viewModel.searchCommand.isRunning) {
  // Show loading indicator
}

if (viewModel.searchCommand.isCompleted) {
  final data = viewModel.searchCommand.result?.valueOrNull;
}

if (viewModel.searchCommand.isError) {
  final error = viewModel.searchCommand.error;
}
```

### In UI (with Riverpod)

```dart
class SearchButton extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final viewModel = ref.watch(searchViewModelProvider);
    final isLoading = viewModel.searchCommand.isRunning;
    
    return ElevatedButton(
      onPressed: isLoading 
        ? null 
        : () => viewModel.searchCommand.execute(filters),
      child: isLoading
        ? const CircularProgressIndicator()
        : const Text('Search'),
    );
  }
}
```

## Features

### Prevents Duplicate Execution

Commands automatically prevent concurrent execution:

```dart
await command.execute(arg1); // Starts
await command.execute(arg2); // Ignored while first is running
```

### Clears Previous Results

```dart
// Clear the previous result before new operation
command.clearResult();
await command.execute(newArgs);
```

### Extends ChangeNotifier

Commands notify listeners when state changes:

```dart
command.addListener(() {
  print('Command state changed');
  print('Running: ${command.isRunning}');
  print('Completed: ${command.isCompleted}');
});
```

## Integration with ViewModels

Commands complement the Result type in ViewModels:

```dart
class ActivitiesViewModel extends Notifier<ActivitiesState> {
  late final SearchActivitiesUseCase _searchUseCase;

  @override
  ActivitiesState build() {
    _searchUseCase = ref.watch(searchActivitiesUseCaseProvider);
    return ActivitiesState.initial;
  }
  
  Future<void> search(SearchFilters filters) async {
    state = state.copyWith(isLoading: true, clearError: true);
    
    final result = await _searchUseCase.execute(filters);
    
    switch (result) {
      case Ok(value: final data):
        state = state.copyWith(results: data, isLoading: false);
      case Error(error: final e):
        state = state.copyWith(
          isLoading: false,
          errorMessage: _formatError(e),
        );
    }
  }
}
```

## When to Use Commands vs Notifier

| Scenario | Recommendation |
|----------|---------------|
| Single async operation | Command |
| Multiple related operations | Notifier |
| Simple loading state | Command |
| Complex state with multiple fields | Notifier |
| Form submission | Command |
| Feature-wide state | Notifier |

## Extension Method

Convert a function to a Command:

```dart
final myFunction = () async => Result.ok(42);
final command = myFunction.toCommand();
```

## Best Practices

1. **Define commands as late final**: Initialize once in constructor
2. **Use appropriate Command type**: Match argument count
3. **Handle all states in UI**: Loading, success, error
4. **Disable UI during execution**: Prevent double-submit
5. **Clear results when appropriate**: Before new unrelated operations

## Testing

```dart
test('command tracks loading state', () async {
  final command = Command0(() async {
    await Future.delayed(Duration(milliseconds: 100));
    return Result.ok(42);
  });
  
  expect(command.isRunning, isFalse);
  
  final future = command.execute();
  expect(command.isRunning, isTrue);
  
  await future;
  expect(command.isRunning, isFalse);
  expect(command.isCompleted, isTrue);
  expect(command.result?.valueOrNull, equals(42));
});

test('command prevents duplicate execution', () async {
  var callCount = 0;
  final command = Command0(() async {
    callCount++;
    await Future.delayed(Duration(milliseconds: 100));
    return Result.ok(callCount);
  });
  
  // Start two executions
  command.execute();
  command.execute();
  
  await Future.delayed(Duration(milliseconds: 150));
  
  // Only one execution happened
  expect(callCount, equals(1));
});
```

## Related

- [Result Type](result.md) - Return type for Command operations
- [ViewModels](../viewmodels/README.md) - Using Commands with Notifier

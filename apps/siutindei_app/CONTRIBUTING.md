# Contributing to Siutindei App

Thank you for your interest in contributing! This document provides guidelines for contributing to the Siutindei Flutter app.

## Code of Conduct

Be respectful and constructive in all interactions. We're all here to build something great together.

## Getting Started

1. Read the [Getting Started Guide](docs/getting-started.md)
2. Familiarize yourself with the [Architecture](README.md#architecture-overview)
3. Set up your development environment

## Development Workflow

### Branch Naming

```
feature/short-description    # New features
fix/issue-number-description # Bug fixes
refactor/description         # Code refactoring
docs/description             # Documentation updates
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `docs`: Documentation
- `test`: Tests
- `chore`: Maintenance

Examples:
```
feat(search): add district filter chip

fix(activity-card): fix price formatting for free activities

refactor(viewmodel): use Result type for error handling

docs(readme): add architecture diagram
```

### Pull Requests

1. Create a feature branch from `main`
2. Make your changes
3. Write/update tests
4. Ensure all tests pass: `flutter test`
5. Ensure code passes analysis: `flutter analyze`
6. Format code: `dart format lib test`
7. Submit PR with clear description

## Code Style

### General Principles

- Follow [Effective Dart](https://dart.dev/guides/language/effective-dart)
- Keep lines under 80 characters
- Use meaningful names
- Write self-documenting code
- Add comments for complex logic

### File Organization

```dart
// 1. Library directive (if needed)
library my_feature;

// 2. Dart imports
import 'dart:async';

// 3. Package imports
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

// 4. Relative imports (project files)
import '../core/core.dart';
import '../domain/domain.dart';
```

### Class Organization

```dart
class MyClass {
  // 1. Constructors
  const MyClass({required this.field});

  // 2. Static fields/methods
  static const defaultValue = 10;

  // 3. Final fields
  final String field;

  // 4. Mutable fields (avoid when possible)
  // int _counter = 0;

  // 5. Getters/Setters
  String get displayField => field.toUpperCase();

  // 6. Public methods
  void doSomething() { ... }

  // 7. Private methods
  void _helperMethod() { ... }

  // 8. Override methods
  @override
  String toString() => 'MyClass($field)';
}
```

### Widget Organization

```dart
class MyWidget extends ConsumerWidget {
  const MyWidget({super.key, required this.data});

  final DataType data;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // 1. Watch providers with selectors
    final tokens = ref.watch(
      componentTokensProvider.select((t) => t.myWidget),
    );

    // 2. Cache computed values
    final borderRadius = BorderRadius.circular(tokens.radius);

    // 3. Return widget tree
    return Container(...);
  }
}
```

## Architecture Guidelines

### Domain Layer

- Entities should be immutable
- Use enums instead of strings for known values
- Repositories define interfaces only
- Use cases contain business logic

```dart
// Good
class ActivityEntity {
  const ActivityEntity({required this.id, required this.name});
  final String id;
  final String name;
}

// Bad - mutable, no const constructor
class ActivityEntity {
  String id;
  String name;
}
```

### Data Layer

- Repositories implement domain interfaces
- Use mappers for data transformation
- Always return `Result<T>`

```dart
// Good
@override
Future<Result<Entity>> getData() async {
  try {
    final response = await _api.fetch();
    return Result.ok(Mapper.toEntity(response));
  } on Exception catch (e) {
    return Result.error(e);
  }
}
```

### Presentation Layer

- Use `ConsumerWidget` or `ConsumerStatefulWidget`
- Use `select` for granular state watching
- Extract widgets for smaller rebuild scopes
- Use component tokens for styling

```dart
// Good - granular watching
final items = ref.watch(
  viewModelProvider.select((s) => s.items),
);

// Avoid - watches entire state
final state = ref.watch(viewModelProvider);
```

## Testing Guidelines

### Test Structure

```
test/
├── area_filter_chips_test.dart
├── area_filter_options_test.dart
├── geographic_area_tree_test.dart
└── home_wizard_choices_test.dart
```

Tests are flat today. Name each file after the source it covers
(`area_filter_options_test.dart` for `area_filter_options.dart`).

### Writing Tests

```dart
void main() {
  group('MyClass', () {
    late MyClass subject;
    late MockDependency mockDep;

    setUp(() {
      mockDep = MockDependency();
      subject = MyClass(mockDep);
    });

    test('does something', () {
      // Arrange
      when(mockDep.method()).thenReturn(value);

      // Act
      final result = subject.doSomething();

      // Assert
      expect(result, expectedValue);
      verify(mockDep.method()).called(1);
    });
  });
}
```

### Test Naming

```dart
test('returns error when input is invalid', () { ... });
test('emits loading state before fetching', () { ... });
test('maps API response to entity correctly', () { ... });
```

## Documentation

### Code Documentation

- Add doc comments to public APIs
- Use `///` for documentation comments
- Include examples for complex APIs

```dart
/// Searches for activities matching the given filters.
///
/// Returns [SearchResultsEntity] containing matching activities.
/// Returns error if filters are invalid.
///
/// Example:
/// ```dart
/// final result = await useCase.execute(SearchFilters(age: 8));
/// ```
Future<Result<SearchResultsEntity>> execute(SearchFilters filters);
```

### README Updates

Update documentation when:
- Adding new features
- Changing architecture
- Adding new dependencies
- Modifying configuration

## Performance Considerations

### Do

- Use `const` constructors
- Use `select` for Riverpod watching
- Cache computed values (BorderRadius, etc.)
- Use `ListView.builder` for lists
- Extract widgets for isolation

### Don't

- Create objects in build methods
- Watch entire state when only part needed
- Use `Container` when `DecoratedBox` suffices
- Rebuild expensive widgets unnecessarily

## Questions?

- Check documentation in `docs/`
- Ask in team chat
- Create a discussion issue

Thank you for contributing!

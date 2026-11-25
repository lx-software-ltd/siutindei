# Base Widgets

Token-aware base widgets provide consistent styling across the app while respecting the design token system.

## Overview

Base widgets are foundational UI components that:
- Automatically consume design tokens
- Follow Flutter performance best practices
- Provide consistent styling
- Are reusable across features

## Location

```
lib/core/widgets/
├── token_aware_widget.dart  # Base class for token consumption
├── base_card.dart           # Card components
├── base_avatar.dart         # Avatar components
└── base_badge.dart          # Badge components
```

## TokenAwareWidget

Abstract base class for widgets that consume design tokens.

### Usage

```dart
abstract class TokenAwareWidget extends ConsumerWidget {
  // Override to access tokens in build
}

// Or use the mixin for StatefulWidgets
class MyWidget extends ConsumerStatefulWidget {
  @override
  ConsumerState<MyWidget> createState() => _MyWidgetState();
}

class _MyWidgetState extends ConsumerState<MyWidget> 
    with TokenAwareStateMixin {
  @override
  Widget build(BuildContext context) {
    // Access tokens via mixin helpers
  }
}
```

### Performance Note

For optimal performance, use `ref.select` to watch only the specific tokens needed:

```dart
// Good - only rebuilds when spacing changes
final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));

// Avoid - rebuilds on any semantic token change
final tokens = ref.watch(semanticTokensProvider);
```

## BaseCard

A token-aware card component with optional tap handling.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `child` | `Widget` | Card content |
| `onTap` | `VoidCallback?` | Tap handler |
| `padding` | `EdgeInsets?` | Override default padding |

### Usage

```dart
BaseCard(
  onTap: () => navigateToDetail(),
  child: Row(
    children: [
      BaseAvatar(name: 'Organization'),
      Text('Content'),
    ],
  ),
)
```

## SectionCard

A specialized card for content sections with title and icon.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `title` | `String` | Section title |
| `icon` | `IconData` | Section icon |
| `child` | `Widget` | Section content |

### Usage

```dart
SectionCard(
  title: 'Schedule',
  icon: Icons.schedule,
  child: Column(
    children: [
      Text('Monday'),
      Text('9:00 AM - 10:00 AM'),
    ],
  ),
)
```

## BaseAvatar

A token-aware avatar with image support and initials fallback.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `String` | Name for initials fallback |
| `imageUrl` | `String?` | Optional image URL |
| `size` | `AvatarSize` | Size variant |

### Sizes

```dart
enum AvatarSize {
  sm,  // 32px
  md,  // 40px
  lg,  // 56px
  xl,  // 80px
}
```

### Usage

```dart
BaseAvatar(
  name: 'John Doe',
  imageUrl: 'https://example.com/avatar.jpg',
  size: AvatarSize.lg,
)
```

### Features

- Automatic initials generation from name
- Image loading with error fallback
- Cached image dimensions for performance

## BaseBadge

A token-aware badge/tag component.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `label` | `String` | Badge text |
| `icon` | `IconData?` | Optional leading icon |
| `variant` | `BadgeVariant` | Color variant |

### Variants

```dart
enum BadgeVariant {
  primary,   // Primary color
  secondary, // Secondary/muted
  success,   // Green
  warning,   // Orange/yellow
  error,     // Red
}
```

### Usage

```dart
// Simple badge
BaseBadge(label: 'EN')

// With icon and variant
BaseBadge(
  label: 'Verified',
  icon: Icons.verified,
  variant: BadgeVariant.success,
)

// Warning badge
BaseBadge(
  label: 'Limited spots',
  variant: BadgeVariant.warning,
)
```

## Performance Optimizations

All base widgets follow these performance patterns:

### 1. Granular Token Selection

```dart
// Select specific token subset
final cardTokens = ref.watch(
  componentTokensProvider.select((t) => t.card),
);
```

### 2. Cached Layout Objects

```dart
// Cache BorderRadius to avoid recreation
final borderRadius = BorderRadius.circular(tokens.borderRadius);
```

### 3. DecoratedBox Usage

```dart
// Use DecoratedBox instead of Container for static decorations
DecoratedBox(
  decoration: BoxDecoration(
    color: tokens.background,
    borderRadius: borderRadius,
  ),
  child: child,
)
```

### 4. Image Caching

```dart
Image.network(
  imageUrl,
  cacheWidth: 160,  // Resize before caching
  cacheHeight: 160,
)
```

## Creating Custom Base Widgets

Follow this pattern when creating new base widgets:

```dart
class BaseCustomWidget extends ConsumerWidget {
  const BaseCustomWidget({
    super.key,
    required this.child,
  });

  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // 1. Select specific tokens needed
    final tokens = ref.watch(
      componentTokensProvider.select((t) => t.custom),
    );
    final spacing = ref.watch(
      semanticTokensProvider.select((s) => s.spacing),
    );

    // 2. Cache computed values
    final borderRadius = BorderRadius.circular(tokens.borderRadius);

    // 3. Use efficient widgets
    return DecoratedBox(
      decoration: BoxDecoration(
        color: tokens.background,
        borderRadius: borderRadius,
      ),
      child: Padding(
        padding: EdgeInsets.all(spacing.md),
        child: child,
      ),
    );
  }
}
```

## Testing

```dart
testWidgets('BaseCard renders with tokens', (tester) async {
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        home: BaseCard(child: Text('Test')),
      ),
    ),
  );

  expect(find.text('Test'), findsOneWidget);
});

testWidgets('BaseAvatar shows initials when no image', (tester) async {
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        home: BaseAvatar(name: 'John Doe'),
      ),
    ),
  );

  expect(find.text('JD'), findsOneWidget);
});
```

## Related

- [Design Tokens](../design/tokens.md) - Token system overview
- [JSON Token Ingestion](../design/json-tokens.md) - How component tokens are loaded

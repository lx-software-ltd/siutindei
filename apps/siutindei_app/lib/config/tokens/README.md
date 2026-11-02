# Design Token System

This document explains the modular design token architecture used by siutindei_app.

## Overview

The app uses a **three-tier token hierarchy** that separates raw values from meaning from component styling:

```
┌─────────────────┐
│   Primitive     │  Raw values: colors, sizes, fonts
│   (Foundation)  │  e.g., indigo500, space4, fontSizeLg
└────────┬────────┘
         │
┌────────▼────────┐
│    Semantic     │  Meaning applied to primitives
│   (Purpose)     │  e.g., primary, error, spacing.md
└────────┬────────┘
         │
┌────────▼────────┐
│   Component     │  Leaf tokens for specific widgets
│    (Leaf)       │  e.g., button.primaryBackground, card.padding
└─────────────────┘
```

## Why This Architecture?

### 1. Separation of Concerns
- **Primitives**: Define the raw palette (doesn't change per context)
- **Semantic**: Define what primitives mean (can change for themes/modes)
- **Component**: Define widget-specific styling (maximum flexibility)

### 2. Easy Theme Switching
Change the entire app's appearance by swapping primitive values:
```dart
// New brand colors automatically cascade to all components
final brandPrimitives = PrimitiveTokens(
  colors: PrimitiveColors(
    indigo500: Color(0xFF...),  // Your brand color
    // ...
  ),
);
```

### 3. Consistent Design System
All buttons use `tokens.button.*`, all cards use `tokens.card.*` - ensuring consistency while allowing per-component customization.

### 4. JSON Ingestion
Load tokens from external sources (Figma, design tools, CMS):
```dart
final tokens = await TokenLoader.fromAsset('assets/tokens/brand.json');
```

## Token Files

| File | Purpose |
|------|---------|
| `primitive_tokens.dart` | Raw values (colors, spacing, typography) |
| `semantic_tokens.dart` | Meaning (primary, error, textPrimary) |
| `component_tokens.dart` | Leaf tokens (button.*, card.*, activityCard.*) |
| `token_registry.dart` | Token management and providers |
| `tokens.dart` | Barrel export |

## Usage in Widgets

### Using Leaf Tokens (Recommended)

```dart
class MyButton extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = ref.watch(componentTokensProvider);
    
    return Container(
      color: tokens.button.primaryBackground,
      padding: EdgeInsets.symmetric(
        horizontal: tokens.button.paddingHorizontal,
        vertical: tokens.button.paddingVertical,
      ),
      child: Text('Click me'),
    );
  }
}
```

### Using TokenAwareWidget Base Class

```dart
class MyCard extends TokenAwareWidget {
  @override
  Widget buildWithTokens(context, ref, ComponentTokens tokens) {
    return Container(
      color: tokens.card.background,
      borderRadius: BorderRadius.circular(tokens.card.borderRadius),
      child: // ...
    );
  }
}
```

### Using the Extension

```dart
// Shorthand access
final tokens = ref.tokens;
final designTokens = ref.designTokens;
```

## Ingesting Custom Tokens

### Method 1: JSON Asset

Create `assets/tokens/brand.json`:
```json
{
  "primitive": {
    "colors": {
      "indigo500": "#6366F1",
      "indigo600": "#4F46E5"
    },
    "spacing": {
      "space4": 16
    }
  }
}
```

Load at startup:
```dart
void main() async {
  final tokens = await TokenLoader.fromAsset('assets/tokens/brand.json');
  runApp(
    ProviderScope(
      overrides: [
        designTokensProvider.overrideWithValue(tokens),
      ],
      child: App(),
    ),
  );
}
```

### Method 2: Runtime Update

`designTokensProvider` watches `designTokensNotifierProvider`, so the
call below rebuilds every widget that reads `ref.tokens` and the
`ThemeData` from `tokenThemeDataProvider`. Overriding
`designTokensProvider` (Methods 1 and 3) pins the value and turns this
off.

```dart
// Load new tokens dynamically
ref.read(designTokensNotifierProvider.notifier).loadFromJson({
  'primitive': {
    'colors': {
      'indigo500': '#FF0000',  // Change primary to red
    },
  },
});
```

### Method 3: Provider Override

```dart
final myBrandTokens = DesignTokens.withPrimitives(
  PrimitiveTokens(
    colors: PrimitiveColors(/* brand colors */),
    // ...
  ),
);

ProviderScope(
  overrides: [
    designTokensProvider.overrideWithValue(myBrandTokens),
  ],
  child: App(),
)
```

## Component Token Reference

### ButtonTokens
```dart
tokens.button.primaryBackground      // Primary button background
tokens.button.primaryForeground      // Primary button text
tokens.button.secondaryBackground    // Outlined button background
tokens.button.secondaryBorder        // Outlined button border
tokens.button.paddingHorizontal      // Horizontal padding
tokens.button.paddingVertical        // Vertical padding
tokens.button.borderRadius           // Corner radius
```

### CardTokens
```dart
tokens.card.background     // Card background color
tokens.card.border         // Card border color
tokens.card.borderRadius   // Card corner radius
tokens.card.padding        // Card internal padding
tokens.card.shadow         // Card shadow (if any)
```

### ActivityCardTokens (App-Specific)
```dart
tokens.activityCard.titleColor         // Activity name color
tokens.activityCard.titleFontSize      // Activity name size
tokens.activityCard.organizationColor  // Org name color
tokens.activityCard.locationIconColor  // Location icon tint
tokens.activityCard.scheduleColor      // Schedule text color
tokens.activityCard.ageBackground      // Age badge background
tokens.activityCard.ageForeground      // Age badge text
tokens.activityCard.avatarSize         // Org avatar size
```

### FilterChipTokens (App-Specific)
```dart
tokens.filterChip.background           // Default background
tokens.filterChip.backgroundSelected   // Selected background
tokens.filterChip.border               // Default border
tokens.filterChip.borderSelected       // Selected border
tokens.filterChip.text                 // Default text color
tokens.filterChip.textSelected         // Selected text color
tokens.filterChip.badgeBackground      // Count badge background
tokens.filterChip.badgeForeground      // Count badge text
```

## Adding New Component Tokens

1. **Define the token class** in `component_tokens.dart`:
```dart
class MyWidgetTokens {
  const MyWidgetTokens({
    required this.background,
    required this.foreground,
    // ...
  });
  
  final Color background;
  final Color foreground;
  
  factory MyWidgetTokens.fromSemantic(SemanticTokens s) {
    return MyWidgetTokens(
      background: s.color.surface,
      foreground: s.color.textPrimary,
    );
  }
}
```

2. **Add to ComponentTokens**:
```dart
class ComponentTokens {
  // Add field
  final MyWidgetTokens myWidget;
  
  // Add to constructor and factory
}
```

3. **Use in widget**:
```dart
final tokens = ref.watch(componentTokensProvider).myWidget;
```

## Best Practices

1. **Never hardcode colors/sizes in widgets** - always use tokens
2. **Use leaf tokens for components** - they provide maximum flexibility
3. **Add app-specific tokens** for custom components (like ActivityCard)
4. **Document token purposes** in the token class
5. **Keep primitives minimal** - only add what's needed
6. **Test with different token values** to ensure flexibility

## Architecture Benefits

| Benefit | How It's Achieved |
|---------|-------------------|
| Easy theming | Swap primitive tokens |
| Consistent design | All components use same token source |
| Flexible components | Each widget has its own leaf tokens |
| External integration | JSON ingestion from design tools |
| Type safety | Dart classes with compile-time checks |
| Testability | Override providers in tests |

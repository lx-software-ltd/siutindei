import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'component_tokens.dart';
import 'primitive_tokens.dart';
import 'semantic_tokens.dart';

/// Design token registry - the central hub for token management.
///
/// This class manages the complete token hierarchy and provides:
/// - Token initialization from defaults
/// - JSON ingestion from files or network
/// - Token overrides at any level
/// - Type-safe token access
///
/// ## Usage
///
/// ```dart
/// // Access via provider
/// final tokens = ref.watch(designTokensProvider);
///
/// // Use leaf tokens in widgets
/// Container(
///   color: tokens.component.activityCard.background,
///   padding: EdgeInsets.all(tokens.component.activityCard.padding),
/// );
/// ```
///
/// ## Token Hierarchy
///
/// ```
/// ┌─────────────┐
/// │  Primitive  │  Raw values (colors, sizes)
/// └──────┬──────┘
///        │
/// ┌──────▼──────┐
/// │  Semantic   │  Meaning (primary, error, spacing.md)
/// └──────┬──────┘
///        │
/// ┌──────▼──────┐
/// │  Component  │  Leaf tokens (button.primaryBackground)
/// └─────────────┘
/// ```
class DesignTokens {
  const DesignTokens({
    required this.primitive,
    required this.semantic,
    required this.component,
  });

  /// Primitive (raw) tokens - the foundation.
  final PrimitiveTokens primitive;

  /// Semantic tokens - meaning applied to primitives.
  final SemanticTokens semantic;

  /// Component (leaf) tokens - what widgets consume.
  final ComponentTokens component;

  /// Create default token set.
  factory DesignTokens.defaults() {
    final primitive = PrimitiveTokens.defaults;
    final semantic = SemanticTokens.fromPrimitives(primitive);
    final component = ComponentTokens.fromSemantic(semantic);
    return DesignTokens(
      primitive: primitive,
      semantic: semantic,
      component: component,
    );
  }

  /// Create tokens from JSON configuration.
  ///
  /// JSON structure:
  /// ```json
  /// {
  ///   "primitive": { "colors": {...}, "spacing": {...} },
  ///   "semantic": { ... },
  ///   "component": { "button": {...}, "card": {...} }
  /// }
  /// ```
  factory DesignTokens.fromJson(Map<String, dynamic> json) {
    // Parse primitives (or use defaults)
    final primitive = json['primitive'] != null
        ? PrimitiveTokens.fromJson(json['primitive'] as Map<String, dynamic>)
        : PrimitiveTokens.defaults;

    // Build semantic from primitives, with optional overrides
    final semantic = json['semantic'] != null
        ? SemanticTokens.fromJson(
            json['semantic'] as Map<String, dynamic>,
            primitive,
          )
        : SemanticTokens.fromPrimitives(primitive);

    // Build component from semantic, with optional overrides
    final component = json['component'] != null
        ? ComponentTokens.fromJson(
            json['component'] as Map<String, dynamic>,
            semantic,
          )
        : ComponentTokens.fromSemantic(semantic);

    return DesignTokens(
      primitive: primitive,
      semantic: semantic,
      component: component,
    );
  }

  /// Create tokens with primitive overrides only.
  ///
  /// Useful when you just want to change the color palette
  /// and let semantic/component tokens derive automatically.
  factory DesignTokens.withPrimitives(PrimitiveTokens primitive) {
    final semantic = SemanticTokens.fromPrimitives(primitive);
    final component = ComponentTokens.fromSemantic(semantic);
    return DesignTokens(
      primitive: primitive,
      semantic: semantic,
      component: component,
    );
  }

  /// Export tokens to JSON.
  Map<String, dynamic> toJson() => {
    'primitive': primitive.toJson(),
    // semantic and component can be derived, so optional to export
  };

  /// Generate Flutter ThemeData from tokens.
  ThemeData toThemeData() {
    final s = semantic;
    final c = component;

    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme(
        brightness: Brightness.light,
        primary: s.color.primary,
        onPrimary: s.color.onPrimary,
        secondary: s.color.secondary,
        onSecondary: s.color.onSecondary,
        error: s.color.error,
        onError: s.color.onError,
        surface: s.color.surface,
        onSurface: s.color.textPrimary,
      ),
      scaffoldBackgroundColor: s.color.background,
      appBarTheme: AppBarTheme(
        backgroundColor: c.appBar.background,
        foregroundColor: c.appBar.foreground,
        elevation: c.appBar.elevation,
        titleTextStyle: TextStyle(
          fontSize: c.appBar.titleFontSize,
          fontWeight: c.appBar.titleFontWeight,
          color: c.appBar.foreground,
        ),
      ),
      cardTheme: CardThemeData(
        color: c.card.background,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(c.card.borderRadius),
          side: BorderSide(color: c.card.border),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: c.input.background,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(c.input.borderRadius),
          borderSide: BorderSide(color: c.input.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(c.input.borderRadius),
          borderSide: BorderSide(color: c.input.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(c.input.borderRadius),
          borderSide: BorderSide(
            color: c.input.borderFocused,
            width: c.input.borderWidthFocused,
          ),
        ),
        contentPadding: EdgeInsets.symmetric(
          horizontal: c.input.paddingHorizontal,
          vertical: c.input.paddingVertical,
        ),
        hintStyle: TextStyle(color: c.input.placeholder),
        labelStyle: TextStyle(color: c.input.label),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: c.button.primaryBackground,
          foregroundColor: c.button.primaryForeground,
          disabledBackgroundColor: c.button.primaryBackgroundDisabled,
          disabledForegroundColor: c.button.primaryForegroundDisabled,
          padding: EdgeInsets.symmetric(
            horizontal: c.button.paddingHorizontal,
            vertical: c.button.paddingVertical,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(c.button.borderRadius),
          ),
          elevation: 0,
          textStyle: TextStyle(
            fontSize: c.button.fontSize,
            fontWeight: c.button.fontWeight,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: c.button.secondaryForeground,
          padding: EdgeInsets.symmetric(
            horizontal: c.button.paddingHorizontal,
            vertical: c.button.paddingVertical,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(c.button.borderRadius),
          ),
          side: BorderSide(color: c.button.secondaryBorder),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: c.button.textForeground),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: c.chip.background,
        selectedColor: c.chip.backgroundSelected,
        labelStyle: TextStyle(fontSize: c.chip.fontSize),
        padding: EdgeInsets.symmetric(horizontal: c.chip.paddingHorizontal),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(c.chip.borderRadius),
          side: BorderSide(color: c.chip.border),
        ),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: c.bottomSheet.background,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(c.bottomSheet.borderRadius),
          ),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: s.color.border,
        thickness: 1,
        space: 1,
      ),
    );
  }
}

/// Token loader for ingesting tokens from various sources.
class TokenLoader {
  const TokenLoader._();

  /// Load tokens from a JSON asset file.
  ///
  /// ```dart
  /// final tokens = await TokenLoader.fromAsset('assets/tokens/brand.json');
  /// ```
  static Future<DesignTokens> fromAsset(String assetPath) async {
    try {
      final jsonString = await rootBundle.loadString(assetPath);
      final json = jsonDecode(jsonString) as Map<String, dynamic>;
      return DesignTokens.fromJson(json);
    } catch (e) {
      debugPrint('TokenLoader: Failed to load from asset $assetPath: $e');
      return DesignTokens.defaults();
    }
  }

  /// Load tokens from a JSON string.
  static DesignTokens fromJsonString(String jsonString) {
    try {
      final json = jsonDecode(jsonString) as Map<String, dynamic>;
      return DesignTokens.fromJson(json);
    } catch (e) {
      debugPrint('TokenLoader: Failed to parse JSON: $e');
      return DesignTokens.defaults();
    }
  }

  /// Load tokens from a network URL.
  ///
  /// Useful for dynamic theming from a CMS or design tool.
  // static Future<DesignTokens> fromUrl(String url) async {
  //   // Implement HTTP fetch and parse
  // }
}

// ============================================================
// RIVERPOD PROVIDERS
// ============================================================

/// Provider for the complete design tokens.
///
/// This is the main entry point for accessing tokens in widgets.
///
/// ```dart
/// class MyWidget extends ConsumerWidget {
///   Widget build(context, ref) {
///     final tokens = ref.watch(designTokensProvider);
///     return Container(
///       color: tokens.component.card.background,
///     );
///   }
/// }
/// ```
final designTokensProvider = Provider<DesignTokens>((ref) {
  // Default implementation - can be overridden
  return DesignTokens.defaults();
});

/// Provider for just the component (leaf) tokens.
///
/// Convenience provider for direct leaf token access.
final componentTokensProvider = Provider<ComponentTokens>((ref) {
  return ref.watch(designTokensProvider).component;
});

/// Provider for semantic tokens.
final semanticTokensProvider = Provider<SemanticTokens>((ref) {
  return ref.watch(designTokensProvider).semantic;
});

/// Provider for primitive tokens.
final primitiveTokensProvider = Provider<PrimitiveTokens>((ref) {
  return ref.watch(designTokensProvider).primitive;
});

/// Provider for ThemeData generated from tokens.
final tokenThemeDataProvider = Provider<ThemeData>((ref) {
  return ref.watch(designTokensProvider).toThemeData();
});

/// Notifier for dynamic token switching.
///
/// Use this if you need to change tokens at runtime:
/// ```dart
/// ref.read(designTokensNotifierProvider.notifier).loadFromJson(json);
/// ```
class DesignTokensNotifier extends Notifier<DesignTokens> {
  @override
  DesignTokens build() => DesignTokens.defaults();

  /// Load tokens from JSON map.
  void loadFromJson(Map<String, dynamic> json) {
    state = DesignTokens.fromJson(json);
  }

  /// Load tokens from JSON string.
  void loadFromJsonString(String jsonString) {
    state = TokenLoader.fromJsonString(jsonString);
  }

  /// Reset to default tokens.
  void reset() {
    state = DesignTokens.defaults();
  }

  /// Apply primitive overrides (semantic/component derive automatically).
  void applyPrimitives(PrimitiveTokens primitives) {
    state = DesignTokens.withPrimitives(primitives);
  }
}

/// Notifier provider for dynamic token management.
final designTokensNotifierProvider =
    NotifierProvider<DesignTokensNotifier, DesignTokens>(
      DesignTokensNotifier.new,
    );

// ============================================================
// CONVENIENCE EXTENSIONS
// ============================================================

/// Extension for easy token access from WidgetRef.
extension TokenRefExtension on WidgetRef {
  /// Get component (leaf) tokens.
  ComponentTokens get tokens => watch(componentTokensProvider);

  /// Get all design tokens.
  DesignTokens get designTokens => watch(designTokensProvider);
}

/// Extension for token access from BuildContext.
extension TokenContextExtension on BuildContext {
  // Note: This requires the tokens to be provided via InheritedWidget
  // For now, use ref.tokens in ConsumerWidgets
}

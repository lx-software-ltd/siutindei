import 'package:flutter/material.dart';

import 'primitive_tokens.dart';

/// Semantic design tokens - meaning applied to primitives.
///
/// These tokens define the PURPOSE of design decisions, not the raw values.
/// They reference primitive tokens and give them semantic meaning.
///
/// ## Token Hierarchy
/// ```
/// Primitive → Semantic (this file) → Component (leaf)
/// ```
///
/// ## Naming Convention
/// - `{category}{variant}{state}` e.g., `colorPrimaryDefault`, `textBodyMuted`
///
/// ## Usage
/// Semantic tokens CAN be used in widgets, but component tokens are preferred
/// for maximum flexibility. Semantic tokens are best for one-off styling.
class SemanticTokens {
  const SemanticTokens({
    required this.color,
    required this.spacing,
    required this.radius,
    required this.text,
    required this.shadow,
  });

  final SemanticColors color;
  final SemanticSpacing spacing;
  final SemanticRadius radius;
  final SemanticText text;
  final SemanticShadow shadow;

  /// Create semantic tokens from primitives.
  factory SemanticTokens.fromPrimitives(PrimitiveTokens primitives) {
    return SemanticTokens(
      color: SemanticColors.fromPrimitives(primitives.colors),
      spacing: SemanticSpacing.fromPrimitives(primitives.spacing),
      radius: SemanticRadius.fromPrimitives(primitives.radius),
      text: SemanticText.fromPrimitives(primitives),
      shadow: SemanticShadow.fromPrimitives(primitives.shadows),
    );
  }

  /// Create with JSON overrides applied on top of primitives.
  factory SemanticTokens.fromJson(
    Map<String, dynamic> json,
    PrimitiveTokens primitives,
  ) {
    final base = SemanticTokens.fromPrimitives(primitives);
    // JSON overrides can be applied here
    // For now, return base
    return base;
  }
}

/// Semantic color tokens.
class SemanticColors {
  const SemanticColors({
    // Primary
    required this.primary,
    required this.primaryHover,
    required this.primaryPressed,
    required this.primaryMuted,
    required this.onPrimary,
    // Secondary
    required this.secondary,
    required this.secondaryHover,
    required this.secondaryMuted,
    required this.onSecondary,
    // Background
    required this.background,
    required this.backgroundElevated,
    required this.backgroundMuted,
    // Surface
    required this.surface,
    required this.surfaceHover,
    required this.surfacePressed,
    // Border
    required this.border,
    required this.borderMuted,
    required this.borderFocused,
    // Text
    required this.textPrimary,
    required this.textSecondary,
    required this.textTertiary,
    required this.textInverse,
    required this.textLink,
    // Status
    required this.error,
    required this.errorMuted,
    required this.onError,
    required this.success,
    required this.successMuted,
    required this.onSuccess,
    required this.warning,
    required this.warningMuted,
    required this.onWarning,
    // Interactive
    required this.interactive,
    required this.interactiveHover,
    required this.interactivePressed,
    required this.interactiveDisabled,
  });

  // Primary
  final Color primary;
  final Color primaryHover;
  final Color primaryPressed;
  final Color primaryMuted;
  final Color onPrimary;

  // Secondary
  final Color secondary;
  final Color secondaryHover;
  final Color secondaryMuted;
  final Color onSecondary;

  // Background
  final Color background;
  final Color backgroundElevated;
  final Color backgroundMuted;

  // Surface
  final Color surface;
  final Color surfaceHover;
  final Color surfacePressed;

  // Border
  final Color border;
  final Color borderMuted;
  final Color borderFocused;

  // Text
  final Color textPrimary;
  final Color textSecondary;
  final Color textTertiary;
  final Color textInverse;
  final Color textLink;

  // Status
  final Color error;
  final Color errorMuted;
  final Color onError;
  final Color success;
  final Color successMuted;
  final Color onSuccess;
  final Color warning;
  final Color warningMuted;
  final Color onWarning;

  // Interactive
  final Color interactive;
  final Color interactiveHover;
  final Color interactivePressed;
  final Color interactiveDisabled;

  factory SemanticColors.fromPrimitives(PrimitiveColors p) {
    return SemanticColors(
      // Primary - maps to indigo
      primary: p.indigo500,
      primaryHover: p.indigo600,
      primaryPressed: p.indigo700,
      primaryMuted: p.indigo100,
      onPrimary: p.white,
      // Secondary - maps to emerald
      secondary: p.emerald500,
      secondaryHover: p.emerald600,
      secondaryMuted: p.emerald100,
      onSecondary: p.white,
      // Background
      background: p.slate50,
      backgroundElevated: p.white,
      backgroundMuted: p.slate100,
      // Surface
      surface: p.white,
      surfaceHover: p.slate50,
      surfacePressed: p.slate100,
      // Border
      border: p.slate200,
      borderMuted: p.slate100,
      borderFocused: p.indigo500,
      // Text
      textPrimary: p.slate800,
      textSecondary: p.slate500,
      textTertiary: p.slate400,
      textInverse: p.white,
      textLink: p.indigo500,
      // Status
      error: p.red500,
      errorMuted: Color.alphaBlend(p.red500.withValues(alpha: 0.1), p.white),
      onError: p.white,
      success: p.green500,
      successMuted: Color.alphaBlend(
        p.green500.withValues(alpha: 0.1),
        p.white,
      ),
      onSuccess: p.white,
      warning: p.amber500,
      warningMuted: Color.alphaBlend(
        p.amber500.withValues(alpha: 0.1),
        p.white,
      ),
      onWarning: p.slate800,
      // Interactive
      interactive: p.indigo500,
      interactiveHover: p.indigo600,
      interactivePressed: p.indigo700,
      interactiveDisabled: p.slate300,
    );
  }
}

/// Semantic spacing tokens.
class SemanticSpacing {
  const SemanticSpacing({
    required this.none,
    required this.xs,
    required this.sm,
    required this.md,
    required this.lg,
    required this.xl,
    required this.xxl,
    // Specific use cases
    required this.insetXs,
    required this.insetSm,
    required this.insetMd,
    required this.insetLg,
    required this.stackXs,
    required this.stackSm,
    required this.stackMd,
    required this.stackLg,
    required this.inlineXs,
    required this.inlineSm,
    required this.inlineMd,
    required this.inlineLg,
  });

  // Generic spacing
  final double none;
  final double xs;
  final double sm;
  final double md;
  final double lg;
  final double xl;
  final double xxl;

  // Inset (padding)
  final double insetXs;
  final double insetSm;
  final double insetMd;
  final double insetLg;

  // Stack (vertical spacing)
  final double stackXs;
  final double stackSm;
  final double stackMd;
  final double stackLg;

  // Inline (horizontal spacing)
  final double inlineXs;
  final double inlineSm;
  final double inlineMd;
  final double inlineLg;

  factory SemanticSpacing.fromPrimitives(PrimitiveSpacing p) {
    return SemanticSpacing(
      none: p.space0,
      xs: p.space1,
      sm: p.space2,
      md: p.space4,
      lg: p.space6,
      xl: p.space8,
      xxl: p.space12,
      // Insets map to standard spacing
      insetXs: p.space1,
      insetSm: p.space2,
      insetMd: p.space4,
      insetLg: p.space6,
      // Stack spacing
      stackXs: p.space1,
      stackSm: p.space2,
      stackMd: p.space4,
      stackLg: p.space6,
      // Inline spacing
      inlineXs: p.space1,
      inlineSm: p.space2,
      inlineMd: p.space3,
      inlineLg: p.space4,
    );
  }
}

/// Semantic radius tokens.
class SemanticRadius {
  const SemanticRadius({
    required this.none,
    required this.sm,
    required this.md,
    required this.lg,
    required this.xl,
    required this.full,
    // Component-specific
    required this.button,
    required this.input,
    required this.card,
    required this.chip,
    required this.modal,
    required this.sheet,
  });

  final double none;
  final double sm;
  final double md;
  final double lg;
  final double xl;
  final double full;

  // Component defaults
  final double button;
  final double input;
  final double card;
  final double chip;
  final double modal;
  final double sheet;

  factory SemanticRadius.fromPrimitives(PrimitiveRadius p) {
    return SemanticRadius(
      none: p.none,
      sm: p.sm,
      md: p.md,
      lg: p.lg,
      xl: p.xl,
      full: p.full,
      // Component mappings
      button: p.lg,
      input: p.lg,
      card: p.lg,
      chip: p.md,
      modal: p.xl,
      sheet: p.xl3,
    );
  }
}

/// Semantic text style tokens.
class SemanticText {
  const SemanticText({
    required this.displayLarge,
    required this.displayMedium,
    required this.headlineLarge,
    required this.headlineMedium,
    required this.headlineSmall,
    required this.titleLarge,
    required this.titleMedium,
    required this.titleSmall,
    required this.bodyLarge,
    required this.bodyMedium,
    required this.bodySmall,
    required this.labelLarge,
    required this.labelMedium,
    required this.labelSmall,
    required this.caption,
  });

  final TextStyle displayLarge;
  final TextStyle displayMedium;
  final TextStyle headlineLarge;
  final TextStyle headlineMedium;
  final TextStyle headlineSmall;
  final TextStyle titleLarge;
  final TextStyle titleMedium;
  final TextStyle titleSmall;
  final TextStyle bodyLarge;
  final TextStyle bodyMedium;
  final TextStyle bodySmall;
  final TextStyle labelLarge;
  final TextStyle labelMedium;
  final TextStyle labelSmall;
  final TextStyle caption;

  factory SemanticText.fromPrimitives(PrimitiveTokens p) {
    final t = p.typography;
    final c = p.colors;

    return SemanticText(
      displayLarge: TextStyle(
        fontSize: 32,
        fontWeight: t.fontWeightBold,
        color: c.slate800,
        height: t.lineHeightTight,
      ),
      displayMedium: TextStyle(
        fontSize: 28,
        fontWeight: t.fontWeightBold,
        color: c.slate800,
        height: t.lineHeightTight,
      ),
      headlineLarge: TextStyle(
        fontSize: t.fontSize3xl,
        fontWeight: t.fontWeightBold,
        color: c.slate800,
        height: t.lineHeightTight,
      ),
      headlineMedium: TextStyle(
        fontSize: t.fontSize2xl,
        fontWeight: t.fontWeightSemibold,
        color: c.slate800,
        height: t.lineHeightTight,
      ),
      headlineSmall: TextStyle(
        fontSize: t.fontSizeXl,
        fontWeight: t.fontWeightSemibold,
        color: c.slate800,
        height: t.lineHeightTight,
      ),
      titleLarge: TextStyle(
        fontSize: t.fontSizeLg,
        fontWeight: t.fontWeightSemibold,
        color: c.slate800,
        height: t.lineHeightNormal,
      ),
      titleMedium: TextStyle(
        fontSize: t.fontSizeMd,
        fontWeight: t.fontWeightSemibold,
        color: c.slate800,
        height: t.lineHeightNormal,
      ),
      titleSmall: TextStyle(
        fontSize: t.fontSizeSm,
        fontWeight: t.fontWeightSemibold,
        color: c.slate800,
        height: t.lineHeightNormal,
      ),
      bodyLarge: TextStyle(
        fontSize: t.fontSizeLg,
        fontWeight: t.fontWeightNormal,
        color: c.slate600,
        height: t.lineHeightRelaxed,
      ),
      bodyMedium: TextStyle(
        fontSize: t.fontSizeMd,
        fontWeight: t.fontWeightNormal,
        color: c.slate600,
        height: t.lineHeightRelaxed,
      ),
      bodySmall: TextStyle(
        fontSize: t.fontSizeSm,
        fontWeight: t.fontWeightNormal,
        color: c.slate600,
        height: t.lineHeightRelaxed,
      ),
      labelLarge: TextStyle(
        fontSize: t.fontSizeMd,
        fontWeight: t.fontWeightMedium,
        color: c.slate600,
        height: t.lineHeightNormal,
      ),
      labelMedium: TextStyle(
        fontSize: t.fontSizeSm,
        fontWeight: t.fontWeightMedium,
        color: c.slate600,
        height: t.lineHeightNormal,
      ),
      labelSmall: TextStyle(
        fontSize: t.fontSizeXs,
        fontWeight: t.fontWeightMedium,
        color: c.slate600,
        height: t.lineHeightNormal,
      ),
      caption: TextStyle(
        fontSize: t.fontSizeXs,
        fontWeight: t.fontWeightNormal,
        color: c.slate400,
        height: t.lineHeightNormal,
      ),
    );
  }
}

/// Semantic shadow tokens.
class SemanticShadow {
  const SemanticShadow({
    required this.none,
    required this.sm,
    required this.md,
    required this.lg,
    required this.xl,
    // Component-specific
    required this.card,
    required this.dropdown,
    required this.modal,
    required this.button,
  });

  final List<BoxShadow> none;
  final List<BoxShadow> sm;
  final List<BoxShadow> md;
  final List<BoxShadow> lg;
  final List<BoxShadow> xl;

  // Component defaults
  final List<BoxShadow> card;
  final List<BoxShadow> dropdown;
  final List<BoxShadow> modal;
  final List<BoxShadow> button;

  factory SemanticShadow.fromPrimitives(PrimitiveShadows p) {
    return SemanticShadow(
      none: p.none,
      sm: p.sm,
      md: p.md,
      lg: p.lg,
      xl: p.xl,
      // Component mappings
      card: p.none, // Flat design, no shadow
      dropdown: p.lg,
      modal: p.xl,
      button: p.none,
    );
  }
}

import 'package:flutter/material.dart';

/// Primitive design tokens - the raw building blocks.
///
/// These are the foundational values that never change based on context.
/// They represent the raw palette and measurements available to the
/// design system.
///
/// ## Token Hierarchy
/// ```
/// Primitive (this file) → Semantic → Component (leaf)
/// ```
///
/// ## Naming Convention
/// - Colors: `{color}{shade}` e.g., `blue500`, `gray100`
/// - Sizes: `{category}{size}` e.g., `space4`, `radius8`
/// - Typography: `{property}{variant}` e.g., `fontSizeLg`, `fontWeightBold`
///
/// ## Usage
/// Primitives should NOT be used directly in widgets.
/// They should only be referenced by semantic tokens.
class PrimitiveTokens {
  const PrimitiveTokens({
    required this.colors,
    required this.spacing,
    required this.radius,
    required this.typography,
    required this.shadows,
  });

  final PrimitiveColors colors;
  final PrimitiveSpacing spacing;
  final PrimitiveRadius radius;
  final PrimitiveTypography typography;
  final PrimitiveShadows shadows;

  /// Default primitive tokens - can be overridden via JSON ingestion.
  static const PrimitiveTokens defaults = PrimitiveTokens(
    colors: PrimitiveColors.defaults,
    spacing: PrimitiveSpacing.defaults,
    radius: PrimitiveRadius.defaults,
    typography: PrimitiveTypography.defaults,
    shadows: PrimitiveShadows.defaults,
  );

  /// Create primitives from JSON map.
  factory PrimitiveTokens.fromJson(Map<String, dynamic> json) {
    return PrimitiveTokens(
      colors: json['colors'] != null
          ? PrimitiveColors.fromJson(json['colors'] as Map<String, dynamic>)
          : PrimitiveColors.defaults,
      spacing: json['spacing'] != null
          ? PrimitiveSpacing.fromJson(json['spacing'] as Map<String, dynamic>)
          : PrimitiveSpacing.defaults,
      radius: json['radius'] != null
          ? PrimitiveRadius.fromJson(json['radius'] as Map<String, dynamic>)
          : PrimitiveRadius.defaults,
      typography: json['typography'] != null
          ? PrimitiveTypography.fromJson(
              json['typography'] as Map<String, dynamic>,
            )
          : PrimitiveTypography.defaults,
      shadows: json['shadows'] != null
          ? PrimitiveShadows.fromJson(json['shadows'] as Map<String, dynamic>)
          : PrimitiveShadows.defaults,
    );
  }

  Map<String, dynamic> toJson() => {
    'colors': colors.toJson(),
    'spacing': spacing.toJson(),
    'radius': radius.toJson(),
    'typography': typography.toJson(),
    'shadows': shadows.toJson(),
  };
}

/// Primitive color palette.
class PrimitiveColors {
  const PrimitiveColors({
    // Indigo scale
    required this.indigo50,
    required this.indigo100,
    required this.indigo200,
    required this.indigo300,
    required this.indigo400,
    required this.indigo500,
    required this.indigo600,
    required this.indigo700,
    required this.indigo800,
    required this.indigo900,
    // Emerald scale
    required this.emerald50,
    required this.emerald100,
    required this.emerald200,
    required this.emerald300,
    required this.emerald400,
    required this.emerald500,
    required this.emerald600,
    required this.emerald700,
    // Slate scale (neutrals)
    required this.slate50,
    required this.slate100,
    required this.slate200,
    required this.slate300,
    required this.slate400,
    required this.slate500,
    required this.slate600,
    required this.slate700,
    required this.slate800,
    required this.slate900,
    // Status colors
    required this.red500,
    required this.red600,
    required this.amber500,
    required this.green500,
    // Base
    required this.white,
    required this.black,
    required this.transparent,
  });

  // Indigo scale
  final Color indigo50;
  final Color indigo100;
  final Color indigo200;
  final Color indigo300;
  final Color indigo400;
  final Color indigo500;
  final Color indigo600;
  final Color indigo700;
  final Color indigo800;
  final Color indigo900;

  // Emerald scale
  final Color emerald50;
  final Color emerald100;
  final Color emerald200;
  final Color emerald300;
  final Color emerald400;
  final Color emerald500;
  final Color emerald600;
  final Color emerald700;

  // Slate scale (neutrals)
  final Color slate50;
  final Color slate100;
  final Color slate200;
  final Color slate300;
  final Color slate400;
  final Color slate500;
  final Color slate600;
  final Color slate700;
  final Color slate800;
  final Color slate900;

  // Status colors
  final Color red500;
  final Color red600;
  final Color amber500;
  final Color green500;

  // Base
  final Color white;
  final Color black;
  final Color transparent;

  static const PrimitiveColors defaults = PrimitiveColors(
    // Indigo scale
    indigo50: Color(0xFFEEF2FF),
    indigo100: Color(0xFFE0E7FF),
    indigo200: Color(0xFFC7D2FE),
    indigo300: Color(0xFFA5B4FC),
    indigo400: Color(0xFF818CF8),
    indigo500: Color(0xFF6366F1),
    indigo600: Color(0xFF4F46E5),
    indigo700: Color(0xFF4338CA),
    indigo800: Color(0xFF3730A3),
    indigo900: Color(0xFF312E81),
    // Emerald scale
    emerald50: Color(0xFFECFDF5),
    emerald100: Color(0xFFD1FAE5),
    emerald200: Color(0xFFA7F3D0),
    emerald300: Color(0xFF6EE7B7),
    emerald400: Color(0xFF34D399),
    emerald500: Color(0xFF10B981),
    emerald600: Color(0xFF059669),
    emerald700: Color(0xFF047857),
    // Slate scale
    slate50: Color(0xFFF8FAFC),
    slate100: Color(0xFFF1F5F9),
    slate200: Color(0xFFE2E8F0),
    slate300: Color(0xFFCBD5E1),
    slate400: Color(0xFF94A3B8),
    slate500: Color(0xFF64748B),
    slate600: Color(0xFF475569),
    slate700: Color(0xFF334155),
    slate800: Color(0xFF1E293B),
    slate900: Color(0xFF0F172A),
    // Status
    red500: Color(0xFFEF4444),
    red600: Color(0xFFDC2626),
    amber500: Color(0xFFF59E0B),
    green500: Color(0xFF22C55E),
    // Base
    white: Color(0xFFFFFFFF),
    black: Color(0xFF000000),
    transparent: Color(0x00000000),
  );

  factory PrimitiveColors.fromJson(Map<String, dynamic> json) {
    Color parseColor(String? hex, Color fallback) {
      if (hex == null) return fallback;
      final hexCode = hex.replaceFirst('#', '');
      return Color(int.parse('FF$hexCode', radix: 16));
    }

    return PrimitiveColors(
      indigo50: parseColor(json['indigo50'] as String?, defaults.indigo50),
      indigo100: parseColor(json['indigo100'] as String?, defaults.indigo100),
      indigo200: parseColor(json['indigo200'] as String?, defaults.indigo200),
      indigo300: parseColor(json['indigo300'] as String?, defaults.indigo300),
      indigo400: parseColor(json['indigo400'] as String?, defaults.indigo400),
      indigo500: parseColor(json['indigo500'] as String?, defaults.indigo500),
      indigo600: parseColor(json['indigo600'] as String?, defaults.indigo600),
      indigo700: parseColor(json['indigo700'] as String?, defaults.indigo700),
      indigo800: parseColor(json['indigo800'] as String?, defaults.indigo800),
      indigo900: parseColor(json['indigo900'] as String?, defaults.indigo900),
      emerald50: parseColor(json['emerald50'] as String?, defaults.emerald50),
      emerald100: parseColor(
        json['emerald100'] as String?,
        defaults.emerald100,
      ),
      emerald200: parseColor(
        json['emerald200'] as String?,
        defaults.emerald200,
      ),
      emerald300: parseColor(
        json['emerald300'] as String?,
        defaults.emerald300,
      ),
      emerald400: parseColor(
        json['emerald400'] as String?,
        defaults.emerald400,
      ),
      emerald500: parseColor(
        json['emerald500'] as String?,
        defaults.emerald500,
      ),
      emerald600: parseColor(
        json['emerald600'] as String?,
        defaults.emerald600,
      ),
      emerald700: parseColor(
        json['emerald700'] as String?,
        defaults.emerald700,
      ),
      slate50: parseColor(json['slate50'] as String?, defaults.slate50),
      slate100: parseColor(json['slate100'] as String?, defaults.slate100),
      slate200: parseColor(json['slate200'] as String?, defaults.slate200),
      slate300: parseColor(json['slate300'] as String?, defaults.slate300),
      slate400: parseColor(json['slate400'] as String?, defaults.slate400),
      slate500: parseColor(json['slate500'] as String?, defaults.slate500),
      slate600: parseColor(json['slate600'] as String?, defaults.slate600),
      slate700: parseColor(json['slate700'] as String?, defaults.slate700),
      slate800: parseColor(json['slate800'] as String?, defaults.slate800),
      slate900: parseColor(json['slate900'] as String?, defaults.slate900),
      red500: parseColor(json['red500'] as String?, defaults.red500),
      red600: parseColor(json['red600'] as String?, defaults.red600),
      amber500: parseColor(json['amber500'] as String?, defaults.amber500),
      green500: parseColor(json['green500'] as String?, defaults.green500),
      white: parseColor(json['white'] as String?, defaults.white),
      black: parseColor(json['black'] as String?, defaults.black),
      transparent: defaults.transparent,
    );
  }

  Map<String, String> toJson() {
    String colorToHex(Color c) {
      final argb = c.toARGB32();
      return '#${argb.toRadixString(16).padLeft(8, '0').substring(2)}';
    }

    return {
      'indigo50': colorToHex(indigo50),
      'indigo500': colorToHex(indigo500),
      // ... add all colors as needed
    };
  }
}

/// Primitive spacing scale (based on 4px grid).
class PrimitiveSpacing {
  const PrimitiveSpacing({
    required this.space0,
    required this.space1,
    required this.space2,
    required this.space3,
    required this.space4,
    required this.space5,
    required this.space6,
    required this.space8,
    required this.space10,
    required this.space12,
    required this.space16,
    required this.space20,
    required this.space24,
    required this.space32,
    required this.space40,
    required this.space48,
    required this.space64,
  });

  final double space0;
  final double space1;
  final double space2;
  final double space3;
  final double space4;
  final double space5;
  final double space6;
  final double space8;
  final double space10;
  final double space12;
  final double space16;
  final double space20;
  final double space24;
  final double space32;
  final double space40;
  final double space48;
  final double space64;

  static const PrimitiveSpacing defaults = PrimitiveSpacing(
    space0: 0,
    space1: 4,
    space2: 8,
    space3: 12,
    space4: 16,
    space5: 20,
    space6: 24,
    space8: 32,
    space10: 40,
    space12: 48,
    space16: 64,
    space20: 80,
    space24: 96,
    space32: 128,
    space40: 160,
    space48: 192,
    space64: 256,
  );

  factory PrimitiveSpacing.fromJson(Map<String, dynamic> json) {
    return PrimitiveSpacing(
      space0: (json['space0'] as num?)?.toDouble() ?? defaults.space0,
      space1: (json['space1'] as num?)?.toDouble() ?? defaults.space1,
      space2: (json['space2'] as num?)?.toDouble() ?? defaults.space2,
      space3: (json['space3'] as num?)?.toDouble() ?? defaults.space3,
      space4: (json['space4'] as num?)?.toDouble() ?? defaults.space4,
      space5: (json['space5'] as num?)?.toDouble() ?? defaults.space5,
      space6: (json['space6'] as num?)?.toDouble() ?? defaults.space6,
      space8: (json['space8'] as num?)?.toDouble() ?? defaults.space8,
      space10: (json['space10'] as num?)?.toDouble() ?? defaults.space10,
      space12: (json['space12'] as num?)?.toDouble() ?? defaults.space12,
      space16: (json['space16'] as num?)?.toDouble() ?? defaults.space16,
      space20: (json['space20'] as num?)?.toDouble() ?? defaults.space20,
      space24: (json['space24'] as num?)?.toDouble() ?? defaults.space24,
      space32: (json['space32'] as num?)?.toDouble() ?? defaults.space32,
      space40: (json['space40'] as num?)?.toDouble() ?? defaults.space40,
      space48: (json['space48'] as num?)?.toDouble() ?? defaults.space48,
      space64: (json['space64'] as num?)?.toDouble() ?? defaults.space64,
    );
  }

  Map<String, double> toJson() => {
    'space0': space0,
    'space1': space1,
    'space2': space2,
    'space3': space3,
    'space4': space4,
    'space5': space5,
    'space6': space6,
    'space8': space8,
    'space10': space10,
    'space12': space12,
    'space16': space16,
    'space20': space20,
    'space24': space24,
    'space32': space32,
    'space40': space40,
    'space48': space48,
    'space64': space64,
  };
}

/// Primitive border radius scale.
class PrimitiveRadius {
  const PrimitiveRadius({
    required this.none,
    required this.sm,
    required this.md,
    required this.lg,
    required this.xl,
    required this.xl2,
    required this.xl3,
    required this.full,
  });

  final double none;
  final double sm;
  final double md;
  final double lg;
  final double xl;
  final double xl2;
  final double xl3;
  final double full;

  static const PrimitiveRadius defaults = PrimitiveRadius(
    none: 0,
    sm: 4,
    md: 8,
    lg: 12,
    xl: 16,
    xl2: 20,
    xl3: 24,
    full: 9999,
  );

  factory PrimitiveRadius.fromJson(Map<String, dynamic> json) {
    return PrimitiveRadius(
      none: (json['none'] as num?)?.toDouble() ?? defaults.none,
      sm: (json['sm'] as num?)?.toDouble() ?? defaults.sm,
      md: (json['md'] as num?)?.toDouble() ?? defaults.md,
      lg: (json['lg'] as num?)?.toDouble() ?? defaults.lg,
      xl: (json['xl'] as num?)?.toDouble() ?? defaults.xl,
      xl2: (json['xl2'] as num?)?.toDouble() ?? defaults.xl2,
      xl3: (json['xl3'] as num?)?.toDouble() ?? defaults.xl3,
      full: (json['full'] as num?)?.toDouble() ?? defaults.full,
    );
  }

  Map<String, double> toJson() => {
    'none': none,
    'sm': sm,
    'md': md,
    'lg': lg,
    'xl': xl,
    'xl2': xl2,
    'xl3': xl3,
    'full': full,
  };
}

/// Primitive typography scale.
class PrimitiveTypography {
  const PrimitiveTypography({
    required this.fontFamily,
    required this.fontSizeXs,
    required this.fontSizeSm,
    required this.fontSizeMd,
    required this.fontSizeLg,
    required this.fontSizeXl,
    required this.fontSize2xl,
    required this.fontSize3xl,
    required this.fontWeightNormal,
    required this.fontWeightMedium,
    required this.fontWeightSemibold,
    required this.fontWeightBold,
    required this.lineHeightTight,
    required this.lineHeightNormal,
    required this.lineHeightRelaxed,
  });

  final String fontFamily;
  final double fontSizeXs;
  final double fontSizeSm;
  final double fontSizeMd;
  final double fontSizeLg;
  final double fontSizeXl;
  final double fontSize2xl;
  final double fontSize3xl;
  final FontWeight fontWeightNormal;
  final FontWeight fontWeightMedium;
  final FontWeight fontWeightSemibold;
  final FontWeight fontWeightBold;
  final double lineHeightTight;
  final double lineHeightNormal;
  final double lineHeightRelaxed;

  static const PrimitiveTypography defaults = PrimitiveTypography(
    fontFamily: 'System',
    fontSizeXs: 11,
    fontSizeSm: 12,
    fontSizeMd: 14,
    fontSizeLg: 16,
    fontSizeXl: 18,
    fontSize2xl: 20,
    fontSize3xl: 24,
    fontWeightNormal: FontWeight.w400,
    fontWeightMedium: FontWeight.w500,
    fontWeightSemibold: FontWeight.w600,
    fontWeightBold: FontWeight.w700,
    lineHeightTight: 1.25,
    lineHeightNormal: 1.5,
    lineHeightRelaxed: 1.75,
  );

  factory PrimitiveTypography.fromJson(Map<String, dynamic> json) {
    FontWeight parseWeight(int? value, FontWeight fallback) {
      if (value == null) return fallback;
      return FontWeight.values.firstWhere(
        (w) => w.value == value,
        orElse: () => fallback,
      );
    }

    return PrimitiveTypography(
      fontFamily: json['fontFamily'] as String? ?? defaults.fontFamily,
      fontSizeXs:
          (json['fontSizeXs'] as num?)?.toDouble() ?? defaults.fontSizeXs,
      fontSizeSm:
          (json['fontSizeSm'] as num?)?.toDouble() ?? defaults.fontSizeSm,
      fontSizeMd:
          (json['fontSizeMd'] as num?)?.toDouble() ?? defaults.fontSizeMd,
      fontSizeLg:
          (json['fontSizeLg'] as num?)?.toDouble() ?? defaults.fontSizeLg,
      fontSizeXl:
          (json['fontSizeXl'] as num?)?.toDouble() ?? defaults.fontSizeXl,
      fontSize2xl:
          (json['fontSize2xl'] as num?)?.toDouble() ?? defaults.fontSize2xl,
      fontSize3xl:
          (json['fontSize3xl'] as num?)?.toDouble() ?? defaults.fontSize3xl,
      fontWeightNormal: parseWeight(
        json['fontWeightNormal'] as int?,
        defaults.fontWeightNormal,
      ),
      fontWeightMedium: parseWeight(
        json['fontWeightMedium'] as int?,
        defaults.fontWeightMedium,
      ),
      fontWeightSemibold: parseWeight(
        json['fontWeightSemibold'] as int?,
        defaults.fontWeightSemibold,
      ),
      fontWeightBold: parseWeight(
        json['fontWeightBold'] as int?,
        defaults.fontWeightBold,
      ),
      lineHeightTight:
          (json['lineHeightTight'] as num?)?.toDouble() ??
          defaults.lineHeightTight,
      lineHeightNormal:
          (json['lineHeightNormal'] as num?)?.toDouble() ??
          defaults.lineHeightNormal,
      lineHeightRelaxed:
          (json['lineHeightRelaxed'] as num?)?.toDouble() ??
          defaults.lineHeightRelaxed,
    );
  }

  Map<String, dynamic> toJson() => {
    'fontFamily': fontFamily,
    'fontSizeXs': fontSizeXs,
    'fontSizeSm': fontSizeSm,
    'fontSizeMd': fontSizeMd,
    'fontSizeLg': fontSizeLg,
    'fontSizeXl': fontSizeXl,
    'fontSize2xl': fontSize2xl,
    'fontSize3xl': fontSize3xl,
  };
}

/// Primitive shadow definitions.
class PrimitiveShadows {
  const PrimitiveShadows({
    required this.none,
    required this.sm,
    required this.md,
    required this.lg,
    required this.xl,
  });

  final List<BoxShadow> none;
  final List<BoxShadow> sm;
  final List<BoxShadow> md;
  final List<BoxShadow> lg;
  final List<BoxShadow> xl;

  static const PrimitiveShadows defaults = PrimitiveShadows(
    none: [],
    sm: [
      BoxShadow(color: Color(0x0D000000), blurRadius: 2, offset: Offset(0, 1)),
    ],
    md: [
      BoxShadow(color: Color(0x1A000000), blurRadius: 6, offset: Offset(0, 2)),
    ],
    lg: [
      BoxShadow(color: Color(0x1A000000), blurRadius: 15, offset: Offset(0, 4)),
    ],
    xl: [
      BoxShadow(
        color: Color(0x26000000),
        blurRadius: 25,
        offset: Offset(0, 10),
      ),
    ],
  );

  factory PrimitiveShadows.fromJson(Map<String, dynamic> json) {
    // Shadow parsing from JSON can be added later
    return defaults;
  }

  Map<String, dynamic> toJson() => {};
}
